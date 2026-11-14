"""A cell canvas that renders to ANSI escape sequences, and a braille dot canvas drawn on top of it."""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from ocsky.adapters.driving.tui.text import char_width

RGB = Tuple[int, int, int]

BRAILLE_BITS = ((0x01, 0x08), (0x02, 0x10), (0x04, 0x20), (0x40, 0x80))


def xterm256(c: RGB) -> int:
    """The nearest colour of the xterm 256-colour palette: its 6x6x6 cube or its grey ramp."""
    steps = (0, 95, 135, 175, 215, 255)
    idx = [min(range(6), key=lambda i: abs(steps[i] - v)) for v in c]
    cube = tuple(steps[i] for i in idx)
    grey = max(0, min(23, round((sum(c) / 3 - 8) / 10)))
    grey_rgb = (8 + grey * 10,) * 3

    def dist(a: RGB) -> int:
        return sum((x - y) ** 2 for x, y in zip(a, c))

    if dist(grey_rgb) < dist(cube):
        return 232 + grey
    return 16 + 36 * idx[0] + 6 * idx[1] + idx[2]


def mix(a: RGB, b: RGB, t: float) -> RGB:
    """Blend from a towards b by t, clamped to 0..1."""
    t = max(0.0, min(1.0, t))
    return (round(a[0] + (b[0] - a[0]) * t), round(a[1] + (b[1] - a[1]) * t),
            round(a[2] + (b[2] - a[2]) * t))


class Canvas:
    """A grid of cells, each with a character, colours and weight, rendered in one string."""

    def __init__(self, w: int, h: int, bg: RGB, fg: RGB):
        self.w, self.h = w, h
        self.ch: List[List[str]] = [[" "] * w for _ in range(h)]
        self.fg: List[List[RGB]] = [[fg] * w for _ in range(h)]
        self.bg: List[List[RGB]] = [[bg] * w for _ in range(h)]
        self.bold: List[List[bool]] = [[False] * w for _ in range(h)]
        self.used: List[List[bool]] = [[False] * w for _ in range(h)]  # cells some text was written to

    def put(self, x: int, y: int, text: str, fg: RGB, bg: Optional[RGB] = None,
            bold: bool = False, maxw: Optional[int] = None) -> int:
        """Write text at (x, y), clipped to the canvas and to maxw cells. Returns the next free x."""
        if not 0 <= y < self.h:
            return x
        limit = self.w if maxw is None else min(self.w, x + maxw)
        for ch in text:
            w = char_width(ch)
            if w == 0:
                continue
            if x + w > limit:
                break
            if x >= 0:
                for i in range(w):
                    self.ch[y][x + i] = ch if i == 0 else ""
                    self.fg[y][x + i] = fg
                    self.bold[y][x + i] = bold
                    self.used[y][x + i] = True
                    if bg is not None:
                        self.bg[y][x + i] = bg
            x += w
        return x

    def fill(self, x: int, y: int, w: int, h: int, bg: RGB) -> None:
        """Set the background of a rectangle, clipped to the canvas."""
        for yy in range(max(0, y), min(self.h, y + h)):
            for xx in range(max(0, x), min(self.w, x + w)):
                self.bg[yy][xx] = bg

    def render(self, colors: str = "truecolor") -> str:
        """The whole canvas as one ANSI string. colors is "256" or anything else for 24-bit."""
        out: List[str] = []
        cur = None
        for y in range(self.h):
            out.append(f"\x1b[{y + 1};1H")
            for x in range(self.w):
                ch = self.ch[y][x]
                if ch == "":
                    continue
                style = (self.fg[y][x], self.bg[y][x], self.bold[y][x])
                if ch == " " and cur is not None and style[1] == cur[1]:
                    style = cur  # a blank shows only its background, so its ink needs no new code
                if style != cur:
                    fg, bg, bold = style
                    # Only what changed: a colour code is most of the bytes on a busy frame.
                    fresh = cur is None or bold != cur[2]
                    codes = ["0;1" if bold else "0"] if fresh else []
                    if fresh or fg != cur[0]:
                        codes.append(f"38;5;{xterm256(fg)}" if colors == "256" else "38;2;%d;%d;%d" % fg)
                    if fresh or bg != cur[1]:
                        codes.append(f"48;5;{xterm256(bg)}" if colors == "256" else "48;2;%d;%d;%d" % bg)
                    out.append("\x1b[" + ";".join(codes) + "m")
                    cur = style
                out.append(ch)
        out.append("\x1b[0m")
        return "".join(out)


class Braille:
    """A dot canvas: every terminal cell holds 2x4 dots, which come out square."""

    def __init__(self, cw: int, ch: int):
        self.cw, self.ch = cw, ch
        self.bits: Dict[Tuple[int, int], int] = {}
        self.col: Dict[Tuple[int, int], RGB] = {}

    def dot(self, px: float, py: float, color: RGB) -> None:
        """Light the dot at dot coordinates (px, py); dots outside the canvas are dropped."""
        ix, iy = round(px), round(py)
        if ix < 0 or iy < 0:
            return
        cx, cy = ix // 2, iy // 4
        if cx >= self.cw or cy >= self.ch:
            return
        self.bits[(cx, cy)] = self.bits.get((cx, cy), 0) | BRAILLE_BITS[iy % 4][ix % 2]
        self.col[(cx, cy)] = color

    def blit(self, cv: Canvas, ox: int, oy: int) -> None:
        """Paint every lit cell onto the canvas at offset (ox, oy)."""
        for (cx, cy), bits in self.bits.items():
            cv.put(ox + cx, oy + cy, chr(0x2800 + bits), self.col[(cx, cy)])
