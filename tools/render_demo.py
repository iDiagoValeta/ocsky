"""Render the README demo: docs/sky.png, docs/clock.png and docs/demo.gif.

A development tool, not part of the package. Run it from the repository root:

    python3 tools/render_demo.py

It builds the demo app exactly as `ocsky --demo` does, but with a fixed clock that the script
advances itself, so the output is the same on every run (the demo database is built relative to
that clock). The cells of the Canvas are drawn straight to an image, one background rectangle and
one glyph per cell. Glyphs come from DejaVu Sans Mono; a character it lacks is taken from the
first fallback font that has it, and the script exits with an error if some character of the
frames can be drawn by no font. Needs Pillow (a development dependency only).
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from ocsky.adapters.driven.demo_database import DEMO_HERE, DEMO_HOME, build_demo_db  # noqa: E402
from ocsky.adapters.driven.sqlite_sessions import SqliteSessions  # noqa: E402
from ocsky.adapters.driving.tui.app import App, Options  # noqa: E402
from ocsky.adapters.driving.tui.canvas import Canvas  # noqa: E402
from ocsky.core.model import Proc  # noqa: E402
from ocsky.core.observatory import Observatory  # noqa: E402

DOCS = os.path.join(ROOT, "docs")
COLS, ROWS = 120, 32
CELL_W, CELL_H = 9, 19
FONT_SIZE, BASELINE = 15, 15
FRAME_MS = 100
DEMO_SHOP = "/home/demo/dev/shop-api"
# Local time reads mid-afternoon whatever the time zone of the machine that renders.
NOW = int(time.mktime(datetime(2026, 11, 12, 15, 20, 0).timetuple()) * 1000)

DEJAVU = "/usr/share/fonts/truetype/dejavu/"
NOTO = "/usr/share/fonts/truetype/noto/"
JETBRAINS = os.path.expanduser("~/.local/share/fonts/JetBrainsMonoNerd/")
FONTS = {  # bold -> candidates, main font first
    False: [DEJAVU + "DejaVuSansMono.ttf", JETBRAINS + "JetBrainsMonoNerdFontMono-Regular.ttf",
            NOTO + "NotoSansMono-Regular.ttf", DEJAVU + "DejaVuSans.ttf",
            NOTO + "NotoSansSymbols2-Regular.ttf", NOTO + "NotoSansSymbols-Regular.ttf"],
    True: [DEJAVU + "DejaVuSansMono-Bold.ttf", JETBRAINS + "JetBrainsMonoNerdFontMono-Bold.ttf",
           NOTO + "NotoSansMono-Bold.ttf", DEJAVU + "DejaVuSans-Bold.ttf",
           NOTO + "NotoSansSymbols2-Regular.ttf", NOTO + "NotoSansSymbols-Bold.ttf"],
}
KEY = {"down": "\x1b[B", "space": " ", "a": "a", "tab": "\t", "enter": "\r", "esc": "\x1b"}
# (seconds from the start, key). The script of the GIF, in the order the README tells it.
SCRIPT = [(2.5, "down"), (3.1, "down"), (3.7, "space"), (4.8, "space"), (5.5, "a"), (7.0, "a"),
          (7.5, "tab"), (10.0, "tab"), (10.5, "enter"), (12.5, "esc")]
GIF_SECONDS = 12.9
GIF_LIMIT = 2_500_000


class Clock:
    """A clock that only moves when the script moves it."""

    def __init__(self, now_ms: int):
        self.now = now_ms

    def now_ms(self) -> int:
        return self.now


class NoOpener:
    def open(self, session) -> None:
        del session  # parameter names are part of the port


class NoClipboard:
    def copy(self, text: str) -> None:
        del text


class NoPreferences:
    def load(self) -> Dict[str, str]:
        return {}

    def save(self, prefs: Dict[str, str]) -> None:
        del prefs


def build_app(db_path: str, clock: Clock, instant: bool) -> Tuple[App, SqliteSessions]:
    """The demo app and the store it reads, which the caller closes before deleting the database."""
    build_demo_db(db_path, clock.now)
    started = clock.now / 1000 - 45 * 60
    procs = _Procs([Proc(4101, "tui", DEMO_HERE, started, 412.0),
                    Proc(4188, "tui", DEMO_SHOP, started + 25 * 60, 268.0)])
    store = SqliteSessions(db_path)
    observatory = Observatory(store, procs, clock, DEMO_HOME, DEMO_HERE)
    app = App(observatory, clock, NoOpener(), NoClipboard(), NoPreferences(), Options(instant=instant),
              DEMO_HOME)
    app.refresh(force=True)
    return app, store


class _Procs:
    def __init__(self, procs: List[Proc]):
        self._procs = procs

    def processes(self) -> List[Proc]:
        return list(self._procs)


class Glyphs:
    """Draws characters into cell-sized masks, choosing per character a font that really has it."""

    def __init__(self) -> None:
        self.paths = {bold: [p for p in paths if os.path.exists(p)] for bold, paths in FONTS.items()}
        self.fonts: Dict[Tuple[str, int], ImageFont.FreeTypeFont] = {}
        self.notdef: Dict[Tuple[str, int], bytes] = {}
        self.masks: Dict[Tuple[str, bool, int], Optional[Image.Image]] = {}

    def font(self, path: str, size: int) -> ImageFont.FreeTypeFont:
        key = (path, size)
        if key not in self.fonts:
            self.fonts[key] = ImageFont.truetype(path, size)
            # Pillow's stubs type the mask as ImagingCore, which bytes() does accept at runtime.
            self.notdef[key] = bytes(self.fonts[key].getmask("\U0010fffe"))  # pyright: ignore[reportArgumentType]
        return self.fonts[key]

    def has(self, path: str, ch: str) -> bool:
        """True when the font draws something for ch other than its missing-glyph box."""
        font = self.font(path, FONT_SIZE)
        mask = font.getmask(ch)
        return mask.getbbox() is not None and bytes(mask) != self.notdef[(path, FONT_SIZE)]  # pyright: ignore[reportArgumentType]

    def pick(self, ch: str, bold: bool) -> Optional[str]:
        for path in self.paths[bold]:
            if self.has(path, ch):
                return path
        return None

    def mask(self, ch: str, bold: bool, cells: int) -> Optional[Image.Image]:
        """An L-mode image of cells x one cell with ch drawn in it, or None when no font has it."""
        key = (ch, bold, cells)
        if key in self.masks:
            return self.masks[key]
        path = self.pick(ch, bold)
        mask = None
        if path is not None:
            width = CELL_W * cells
            mask = Image.new("L", (width, CELL_H), 0)
            size = FONT_SIZE
            font = self.font(path, size)
            main = path == self.paths[bold][0]
            while not main and size > 8:
                left, top, right, bottom = font.getbbox(ch, anchor="ls")
                if right - left <= width and bottom - top <= CELL_H - 1:
                    break
                size -= 1
                font = self.font(path, size)
            if main:
                x = (width - font.getlength(ch)) / 2
            else:
                left, _, right, _ = font.getbbox(ch, anchor="ls")
                x = (width - (right - left)) / 2 - left
            ImageDraw.Draw(mask).text((x, BASELINE), ch, fill=255, font=font, anchor="ls")
        self.masks[key] = mask
        return mask


def draw_canvas(cv: Canvas, glyphs: Glyphs, missing: Set[str]) -> Image.Image:
    """The cells of a canvas as an image: each cell its background, then its character."""
    img = Image.new("RGB", (cv.w * CELL_W, cv.h * CELL_H))
    draw = ImageDraw.Draw(img)
    for y in range(cv.h):
        x = 0
        while x < cv.w:  # one rectangle per run of equal background
            start = x
            while x < cv.w and cv.bg[y][x] == cv.bg[y][start]:
                x += 1
            draw.rectangle((start * CELL_W, y * CELL_H, x * CELL_W - 1, (y + 1) * CELL_H - 1),
                           fill=cv.bg[y][start])
    for y in range(cv.h):
        for x in range(cv.w):
            ch = cv.ch[y][x]
            if ch in ("", " "):
                continue
            cells = 2 if x + 1 < cv.w and cv.ch[y][x + 1] == "" else 1
            mask = glyphs.mask(ch, cv.bold[y][x], cells)
            if mask is None:
                missing.add(ch)
                continue
            img.paste(cv.fg[y][x], (x * CELL_W, y * CELL_H), mask)
    return img


class DemoRun:
    """The demo app, its clock and its temporary database, for as long as the script needs them."""

    def __init__(self, instant: bool):
        self.tmp = tempfile.TemporaryDirectory()
        self.clock = Clock(NOW)
        self.app, self.store = build_app(os.path.join(self.tmp.name, "opencode.db"), self.clock, instant)

    def advance(self, ms: int) -> None:
        self.clock.now += ms
        self.app.refresh()

    def close(self) -> None:
        self.store.close()  # Windows cannot delete a database that is still open
        self.tmp.cleanup()


def still(path: str, view_keys: List[str], seconds: float, glyphs: Glyphs, missing: Set[str]) -> None:
    s = DemoRun(instant=True)
    try:
        for _ in range(int(seconds * 1000 / FRAME_MS)):
            s.advance(FRAME_MS)
        for k in view_keys:
            s.app.key(KEY[k])
        draw_canvas(s.app.canvas(COLS, ROWS), glyphs, missing).save(path, optimize=True)
    finally:
        s.close()


def shared_palette(frames: List[Image.Image]) -> Image.Image:
    """One 256-colour palette for every frame, so colours do not flicker between frames."""
    sample = frames[:: max(1, len(frames) // 12)]
    sheet = Image.new("RGB", (frames[0].width, frames[0].height * len(sample)))
    for i, frame in enumerate(sample):
        sheet.paste(frame, (0, i * frame.height))
    return sheet.quantize(256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)


def gif(path: str, glyphs: Glyphs, missing: Set[str], step: int = 1) -> int:
    """Play SCRIPT on the app and write the frames; step=2 keeps every second frame (5 fps)."""
    s = DemoRun(instant=False)
    frames: List[Image.Image] = []
    pending = list(SCRIPT)
    try:
        for n in range(int(GIF_SECONDS * 1000 / FRAME_MS)):
            s.advance(FRAME_MS)
            while pending and pending[0][0] <= (n + 1) * FRAME_MS / 1000:
                s.app.key(KEY[pending.pop(0)[1]])
            canvas = s.app.canvas(COLS, ROWS)  # drawn every frame so the thoughts type in at full pace
            if n % step == 0:
                frames.append(draw_canvas(canvas, glyphs, missing))
    finally:
        s.close()
    if missing:
        return 0
    palette = shared_palette(frames)
    quantized = [f.quantize(palette=palette, dither=Image.Dither.NONE) for f in frames]
    quantized[0].save(path, save_all=True, append_images=quantized[1:], duration=FRAME_MS * step,
                      loop=0, optimize=True)
    return os.path.getsize(path)


def main() -> int:
    os.makedirs(DOCS, exist_ok=True)
    glyphs = Glyphs()
    missing: Set[str] = set()
    still(os.path.join(DOCS, "sky.png"), [], 3.0, glyphs, missing)
    still(os.path.join(DOCS, "clock.png"), ["tab"], 3.0, glyphs, missing)
    gif_path = os.path.join(DOCS, "demo.gif")
    size = gif(gif_path, glyphs, missing)
    if missing:
        print("no font can draw: " + " ".join("%s (U+%04X)" % (c, ord(c)) for c in sorted(missing)),
              file=sys.stderr)
        return 1
    if size > GIF_LIMIT:
        print("demo.gif is %d bytes, over the %d limit" % (size, GIF_LIMIT), file=sys.stderr)
        return 1
    for name in ("sky.png", "clock.png", "demo.gif"):
        print("%-10s %8d bytes" % (name, os.path.getsize(os.path.join(DOCS, name))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
