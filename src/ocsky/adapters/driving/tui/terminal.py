"""The terminal: raw mode, size, keys and drawing, plus the loop that runs the app."""
from __future__ import annotations

import os
import select
import shutil
import signal
import sys
import time
from typing import Any, Dict, List, Optional, Protocol, Tuple

from ocsky.adapters.driving.tui.app import App

FRAME_SECONDS = 1 / 12  # about twelve frames a second
ENTER_SCREEN = "\x1b[?1049h\x1b[?25l\x1b[?7l"  # alternate screen, hide the cursor, no line wrap
LEAVE_SCREEN = "\x1b[0m\x1b[?7h\x1b[?25h\x1b[?1049l"
SYNC_BEGIN, SYNC_END = "\x1b[?2026h", "\x1b[?2026l"  # the terminal shows the frame whole or not at all


def parse_keys(data: str) -> List[str]:
    """Split what the terminal sent into keys. An escape sequence like "\\x1b[A" is one key."""
    keys, i = [], 0
    while i < len(data):
        if data[i] == "\x1b" and i + 1 < len(data) and data[i + 1] == "[":
            j = i + 2
            while j < len(data) and not ("@" <= data[j] <= "~"):
                j += 1
            keys.append(data[i:j + 1])
            i = j + 1
        else:
            keys.append(data[i])
            i += 1
    return keys


class Terminal(Protocol):
    """What the loop needs from a terminal, so the POSIX and the Windows ones are interchangeable."""

    def size(self) -> Tuple[int, int]: ...

    def read_keys(self, timeout: float) -> List[str]: ...

    def write(self, frame: str) -> None: ...

    def suspend(self) -> None: ...

    def resume(self) -> None: ...


class PosixTerminal:
    """Linux and macOS. A context manager that leaves the terminal as it found it, even on an error."""

    def __init__(self) -> None:
        self._fd = -1
        self._saved: Optional[List[Any]] = None
        self._out = sys.stdout

    def __enter__(self) -> PosixTerminal:
        import termios

        self._fd = sys.stdin.fileno()
        self._saved = termios.tcgetattr(self._fd)
        self.resume()
        return self

    def __exit__(self, *exc: object) -> None:
        self.suspend()

    def resume(self) -> None:
        """Take the terminal over: keys one at a time, alternate screen, no cursor."""
        import tty

        tty.setcbreak(self._fd)
        self._out.write(ENTER_SCREEN)
        self._out.flush()

    def suspend(self) -> None:
        """Hand the terminal back, for a program that needs it (opencode) or for good."""
        import termios

        self._out.write(LEAVE_SCREEN)
        self._out.flush()
        if self._saved is not None:
            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._saved)

    def size(self) -> Tuple[int, int]:
        """(columns, rows)."""
        size = shutil.get_terminal_size()
        return size.columns, size.lines

    def read_keys(self, timeout: float) -> List[str]:
        """The keys pressed within timeout seconds, or none."""
        ready, _, _ = select.select([self._fd], [], [], timeout)
        if not ready:
            return []
        return parse_keys(os.read(self._fd, 64).decode(errors="ignore"))

    def write(self, frame: str) -> None:
        self._out.write(SYNC_BEGIN + frame + SYNC_END)
        self._out.flush()


# msvcrt.getwch returns "\x00" or "\xe0" and then a scan code for the keys that are not characters.
WINDOWS_SCAN_CODES: Dict[str, str] = {
    "H": "\x1b[A", "P": "\x1b[B", "K": "\x1b[D", "M": "\x1b[C", "I": "\x1b[5~", "Q": "\x1b[6~",
}
WINDOWS_PREFIXES = ("\x00", "\xe0")
VT_OUTPUT = 0x0004  # ENABLE_VIRTUAL_TERMINAL_PROCESSING


def translate_windows_keys(chars: List[str]) -> List[str]:
    """What msvcrt.getwch returned, as the strings a POSIX terminal sends. Unknown special keys vanish."""
    keys, i = [], 0
    while i < len(chars):
        ch = chars[i]
        if ch in WINDOWS_PREFIXES:
            code = WINDOWS_SCAN_CODES.get(chars[i + 1]) if i + 1 < len(chars) else None
            if code:
                keys.append(code)
            i += 2  # a scan code that is not mapped must not leak out as a letter
        else:
            keys.append("\x7f" if ch == "\x08" else ch)
            i += 1
    return keys


class WindowsTerminal:
    """The Windows console. The same escape sequences as POSIX, once virtual terminal processing is on.

    msvcrt and ctypes.windll are imported inside the methods, so this module imports everywhere.
    """

    def __init__(self) -> None:
        self._out = sys.stdout
        self._handle: Any = None
        self._saved_mode: Optional[int] = None

    def __enter__(self) -> WindowsTerminal:
        reconfigure = getattr(sys.stdout, "reconfigure", None)
        if reconfigure is not None:  # the legacy console code page cannot encode box drawing
            reconfigure(encoding="utf-8", errors="replace")
        self._enable_virtual_terminal()
        try:
            self.resume()
        except BaseException:
            self._restore_mode()
            raise
        return self

    def __exit__(self, *exc: object) -> None:
        try:
            self.suspend()
        finally:
            self._restore_mode()

    def _enable_virtual_terminal(self) -> None:
        import ctypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            self._handle, self._saved_mode = handle, mode.value
            kernel32.SetConsoleMode(handle, mode.value | VT_OUTPUT)

    def _restore_mode(self) -> None:
        if self._saved_mode is not None:
            import ctypes

            ctypes.windll.kernel32.SetConsoleMode(self._handle, self._saved_mode)  # type: ignore[attr-defined]
            self._saved_mode = None

    def resume(self) -> None:
        self._out.write(ENTER_SCREEN)
        self._out.flush()

    def suspend(self) -> None:
        self._out.write(LEAVE_SCREEN)
        self._out.flush()

    def size(self) -> Tuple[int, int]:
        """(columns, rows)."""
        size = shutil.get_terminal_size()
        return size.columns, size.lines

    def read_keys(self, timeout: float) -> List[str]:
        """The keys pressed within timeout seconds, or none."""
        import msvcrt

        deadline = time.monotonic() + timeout
        while not msvcrt.kbhit():  # type: ignore[attr-defined]
            if time.monotonic() >= deadline:
                return []
            time.sleep(0.01)
        chars: List[str] = []
        while msvcrt.kbhit():  # type: ignore[attr-defined]
            ch = msvcrt.getwch()  # type: ignore[attr-defined]
            chars.append(ch)
            if ch in WINDOWS_PREFIXES:
                chars.append(msvcrt.getwch())  # type: ignore[attr-defined]
        return translate_windows_keys(chars)

    def write(self, frame: str) -> None:
        self._out.write(SYNC_BEGIN + frame + SYNC_END)
        self._out.flush()


def system_terminal(platform: str) -> Terminal:
    """The terminal for this system. `platform` is sys.platform."""
    return WindowsTerminal() if platform.startswith("win") else PosixTerminal()


def run(app: App, term: Terminal) -> None:
    """Draw and read keys until the person quits. SIGTERM and ctrl-c leave the terminal clean."""
    try:
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    except (ValueError, OSError):  # not the main thread, or a platform without it: ctrl-c still works
        pass
    try:
        app.refresh(force=True)
        while True:
            app.refresh()
            cols, rows = term.size()
            term.write(app.frame(cols, rows))
            for key in term.read_keys(FRAME_SECONDS):
                if not app.key(key):
                    return
            if app.pending_open is not None:
                term.suspend()
                app.open_pending()
                term.resume()
                app.refresh(force=True)
    except KeyboardInterrupt:
        pass
