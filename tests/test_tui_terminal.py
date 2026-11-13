"""The terminal layer: key parsing, the Windows key mapping, terminal selection and the run loop."""
from __future__ import annotations

import os
import re
import select
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from typing import List, Tuple

from tests import helpers  # noqa: F401
# isort: split
from ocsky.adapters.driven.demo_database import DEMO_HERE, DEMO_HOME, build_demo_db
from ocsky.adapters.driven.sqlite_sessions import SqliteSessions
from ocsky.adapters.driving.tui.app import App, Options
from ocsky.adapters.driving.tui.terminal import (
    PosixTerminal,
    WindowsTerminal,
    parse_keys,
    run,
    system_terminal,
    translate_windows_keys,
)
from ocsky.core.model import Proc
from ocsky.core.observatory import Observatory
from tests.doubles import (
    FixedClock,
    FixedProcesses,
    MemoryPreferences,
    RecordingClipboard,
    RecordingOpener,
)

NOW = 1_800_000_000_000
UP, DOWN, RIGHT, LEFT = "\x1b[A", "\x1b[B", "\x1b[C", "\x1b[D"
PGUP, PGDN = "\x1b[5~", "\x1b[6~"


class ParseKeysTest(unittest.TestCase):
    def test_arrow_sequences_are_one_key_each(self):
        self.assertEqual(parse_keys(UP + DOWN + RIGHT + LEFT), [UP, DOWN, RIGHT, LEFT])

    def test_page_keys_keep_their_tilde(self):
        self.assertEqual(parse_keys(PGUP + PGDN), [PGUP, PGDN])

    def test_plain_letters_are_one_key_each(self):
        self.assertEqual(parse_keys("jkq"), ["j", "k", "q"])

    def test_a_lone_escape_is_an_escape_key(self):
        self.assertEqual(parse_keys("\x1b"), ["\x1b"])

    def test_an_escape_before_a_letter_is_not_a_sequence(self):
        self.assertEqual(parse_keys("\x1bq"), ["\x1b", "q"])

    def test_mixed_input_is_split_in_order(self):
        data = "j" + DOWN + "\x1b" + PGDN + "\r\t"
        self.assertEqual(parse_keys(data), ["j", DOWN, "\x1b", PGDN, "\r", "\t"])

    def test_empty_input_has_no_keys(self):
        self.assertEqual(parse_keys(""), [])


class WindowsKeysTest(unittest.TestCase):
    def test_both_prefixes_map_every_special_key(self):
        expected = {"H": UP, "P": DOWN, "K": LEFT, "M": RIGHT, "I": PGUP, "Q": PGDN}
        for prefix in ("\x00", "\xe0"):
            for code, key in expected.items():
                self.assertEqual(translate_windows_keys([prefix, code]), [key], repr(prefix + code))

    def test_backspace_becomes_delete(self):
        self.assertEqual(translate_windows_keys(["\x08"]), ["\x7f"])

    def test_everything_else_passes_through(self):
        chars = ["\r", "\t", "\x1b", "\x03", "q", "j", "Y", "?", "é"]
        self.assertEqual(translate_windows_keys(chars), chars)

    def test_a_code_letter_without_a_prefix_is_a_plain_letter(self):
        self.assertEqual(translate_windows_keys(["H", "P"]), ["H", "P"])

    def test_special_keys_mix_with_plain_ones_in_order(self):
        self.assertEqual(translate_windows_keys(["j", "\xe0", "P", "\x08", "\x00", "I", "q"]),
                         ["j", DOWN, "\x7f", PGUP, "q"])

    def test_an_unknown_special_key_vanishes_instead_of_leaking_a_letter(self):
        self.assertEqual(translate_windows_keys(["\x00", ";", "q"]), ["q"])  # F1 is "\x00;"
        self.assertEqual(translate_windows_keys(["\xe0"]), [])  # cut off after the prefix

    def test_no_keys_is_no_keys(self):
        self.assertEqual(translate_windows_keys([]), [])


class SystemTerminalTest(unittest.TestCase):
    def test_windows_gets_the_windows_terminal_without_touching_the_console(self):
        self.assertIsInstance(system_terminal("win32"), WindowsTerminal)
        self.assertNotIn("msvcrt", sys.modules)

    def test_every_other_platform_gets_the_posix_terminal(self):
        for platform in ("linux", "darwin", "freebsd14"):
            self.assertIsInstance(system_terminal(platform), PosixTerminal, platform)


class ScriptedTerminal:
    """A Terminal double: plays back scripted key batches and records everything the loop does."""

    def __init__(self, script: List[List[str]], events: List[str]):
        self._script = list(script)
        self.events = events
        self.frames: List[str] = []

    def size(self) -> Tuple[int, int]:
        return 140, 40

    def read_keys(self, timeout: float) -> List[str]:
        if not self._script:
            raise AssertionError("the loop kept running after the scripted keys were used up")
        return self._script.pop(0)

    def write(self, frame: str) -> None:
        self.frames.append(frame)

    def suspend(self) -> None:
        self.events.append("suspend")

    def resume(self) -> None:
        self.events.append("resume")


class OrderedOpener(RecordingOpener):
    def __init__(self, events: List[str]):
        super().__init__()
        self._events = events

    def open(self, session) -> None:
        self._events.append("open")
        super().open(session)


class RunLoopTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        path = os.path.join(self.tmp.name, "opencode.db")
        build_demo_db(path, NOW)
        store = SqliteSessions(path)
        self.addCleanup(store.close)  # runs first: Windows cannot delete an open file
        self.clock = FixedClock(NOW)
        procs = FixedProcesses([Proc(1, "tui", DEMO_HERE, 0.0, 1.0)])
        self.observatory = Observatory(store, procs, self.clock, DEMO_HOME, DEMO_HERE)
        previous = signal.getsignal(signal.SIGTERM)
        self.addCleanup(signal.signal, signal.SIGTERM, previous)  # run() installs a handler

    def make_app(self, opener) -> App:
        return App(self.observatory, self.clock, opener, RecordingClipboard(), MemoryPreferences(),
                   Options(instant=True), DEMO_HOME)

    def test_j_then_o_then_q_opens_the_selected_session_with_the_terminal_released(self):
        twin = self.make_app(RecordingOpener())  # the same keys pressed by hand say which session is selected
        twin.refresh(force=True)
        twin.key("j")
        twin.key("o")
        expected = twin.pending_open.id

        events: List[str] = []
        opener = OrderedOpener(events)
        term = ScriptedTerminal([["j"], ["o"], ["q"]], events)
        run(self.make_app(opener), term)

        self.assertEqual(events, ["suspend", "open", "resume"])
        self.assertEqual([s.id for s in opener.opened], [expected])
        self.assertEqual(len(term.frames), 3)  # one frame per pass, and none after q
        self.assertTrue(all("\x1b[" in f and len(f) > 500 for f in term.frames))


def plain(data: bytes) -> bytes:
    """The output without its colour and cursor sequences, so the text can be searched."""
    return re.sub(rb"\x1b\[[0-9;?]*[a-zA-Z]", b"", data)


@unittest.skipUnless(os.name == "posix", "needs a pseudo terminal")
class PosixPseudoTerminalTest(unittest.TestCase):
    def test_the_real_terminal_enters_the_alternate_screen_and_leaves_it_on_q(self):
        import fcntl
        import pty
        import struct
        import termios

        master, slave = pty.openpty()
        proc = None
        try:
            fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 140, 0, 0))
            with tempfile.TemporaryDirectory() as config:
                env = dict(os.environ, PYTHONPATH=helpers.SRC, XDG_CONFIG_HOME=config, TERM="xterm-256color")
                proc = subprocess.Popen([sys.executable, "-m", "ocsky", "--demo"], stdin=slave, stdout=slave,
                                        stderr=slave, env=env, close_fds=True)
                os.close(slave)
                slave = -1
                out = b""

                def drain(seconds: float) -> None:
                    nonlocal out
                    end = time.monotonic() + seconds
                    while time.monotonic() < end:
                        if not select.select([master], [], [], 0.1)[0]:
                            continue
                        try:
                            chunk = os.read(master, 65536)
                        except OSError:  # Linux reports the closed slave as EIO
                            return
                        if not chunk:
                            return
                        out += chunk

                deadline = time.monotonic() + 10
                while time.monotonic() < deadline and not (b"\x1b[?1049h" in out and b"ocsky" in plain(out)):
                    drain(0.2)
                self.assertIn(b"\x1b[?1049h", out)
                self.assertIn(b"ocsky", plain(out))  # drawn letter by letter, each coloured

                os.write(master, b"q")
                end = time.monotonic() + 5
                while proc.poll() is None and time.monotonic() < end:
                    drain(0.1)  # keep reading so the child never blocks on a full pty buffer
                self.assertEqual(proc.poll(), 0)
                drain(0.3)
                self.assertIn(b"\x1b[?1049l", out)
        finally:
            if proc is not None and proc.poll() is None:
                proc.kill()
                proc.wait()
            if slave != -1:
                os.close(slave)
            os.close(master)


if __name__ == "__main__":
    unittest.main()
