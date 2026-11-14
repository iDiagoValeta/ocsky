"""The backdrops of the sky: what is drawn behind the list, on the cells nothing else uses.

Every backdrop is quiet on purpose. The list is the subject; the sky behind it only sets the mood.
A backdrop has two layers: dots on the free cells, and a glow that tints the background of the
whole pane, text included, so light reads as light and not as grain. On a light palette the same
shapes are drawn as ink on paper: stronger dots, a watercolour glow.
"""
from __future__ import annotations

import math
import zlib
from typing import TYPE_CHECKING, Callable, Collection, Dict, List, Tuple

from ocsky.adapters.driving.tui.canvas import BRAILLE_BITS, RGB, Braille, Canvas, mix
from ocsky.adapters.driving.tui.views.common import starfield

if TYPE_CHECKING:
    from ocsky.adapters.driving.tui.app import App

# How much of a backdrop's own colour reaches a dot, on a dark and on a light palette.
INK = {False: 0.5, True: 0.72}
# The most a glow tints a background. Text sits on it, so it stays low.
GLOW = {False: 0.16, True: 0.13}
AURORA_INK = 0.76  # a curtain covers far more cells than a galaxy, so its dots are fainter
ARMS_MIN, ARMS_MAX = 2, 6
DUST = 220  # grains per arm of the galaxy
WINDING = 2.4 * math.pi  # how far an arm turns from the core to the rim
TILT, FLATTEN = -0.3, 0.5  # the disc is seen at an angle
TURN = 0.04  # radians per second
CURTAINS = 4
RAMP = 24  # colour steps from the foot of a curtain to its top
SPARSE = {False: 0.45, True: 0.7}  # on paper fewer dots, or the curtain turns to grit; the glow carries it
METEOR_EVERY, METEOR_LIFE, METEOR_FIRST = 11.0, 0.9, 2.4  # seconds


class Pane:
    """The cells a backdrop may paint: a rectangle, minus header rows and a left gap, minus what is used."""

    def __init__(self, cv: Canvas, app: App, x: int, y: int, w: int, h: int,
                 skip_rows: Collection[int], left_gap: int):
        self.cv, self.app = cv, app
        self.x, self.y, self.w, self.h = x, y, w, h
        self.skip_rows, self.left_gap = skip_rows, left_gap
        self.light = app.theme.light
        self.ink = INK[self.light]

    def blit(self, br: Braille, ink: float = 1.0) -> None:
        """Paint the lit cells of a dot canvas that are free, washed towards the background."""
        cv, base, ink = self.cv, self.app.theme.base, ink * self.ink
        for (cx, cy), bits in br.bits.items():
            x, y = self.x + cx, self.y + cy
            if cx < self.left_gap or y in self.skip_rows or cv.used[y][x] or cv.bg[y][x] != base:
                continue
            cv.put(x, y, chr(0x2800 + bits), mix(base, br.col[(cx, cy)], ink))

    def stars(self, t: float) -> None:
        starfield(self.cv, self.app.theme, self.x, self.y, self.w, self.h, t, self.skip_rows, self.left_gap)

    def glow(self, light: Callable[[int, int], Tuple[RGB, float]]) -> None:
        """Tint the background of every plain cell by light(cx, cy) = (colour, 0..1).

        Only cells still on the base colour change, so the selected row keeps its own. In 256
        colours a faint tint would round to blotches, so the glow is left out there.
        """
        if self.app.options.colors == "256":
            return
        cv, base, most = self.cv, self.app.theme.base, GLOW[self.light]
        for cy in range(self.h):
            y = self.y + cy
            row = cv.bg[y]
            for cx in range(self.w):
                if row[self.x + cx] != base:
                    continue
                col, k = light(cx, cy)
                if k > 0.02:
                    row[self.x + cx] = mix(base, col, k * most)


def stars(pane: Pane, t: float) -> None:
    """Twinkling stars and, now and then, a shooting star."""
    pane.stars(t)
    _meteor(pane, t)


def _meteor(pane: Pane, t: float) -> None:
    """A short streak that crosses the lower sky, where the list rarely reaches, every few seconds."""
    since = t - METEOR_FIRST
    if since < 0 or since % METEOR_EVERY > METEOR_LIFE:
        return
    n = int(since // METEOR_EVERY)
    life = (since % METEOR_EVERY) / METEOR_LIFE
    seed = zlib.crc32(b"meteor %d" % n)
    w, h = pane.w * 2, pane.h * 4
    x0 = w * (0.35 + 0.6 * (seed % 1000) / 1000)
    y0 = h * (0.45 + 0.3 * ((seed >> 10) % 1000) / 1000)
    angle = math.pi * (0.78 + 0.1 * ((seed >> 20) % 100) / 100)  # down and to the left
    dx, dy = math.cos(angle), math.sin(angle) * 0.6
    travel = min(w, h * 2) * 0.45
    head = travel * life
    tail = 22 * math.sin(math.pi * life)  # it grows, then burns out
    th = pane.app.theme
    br = Braille(pane.w, pane.h)
    for i in range(int(tail)):
        d = head - i
        if d < 0:
            break
        br.dot(x0 + dx * d, y0 + dy * d, mix(th.text, th.base, i / max(1.0, tail)))
    pane.blit(br, 1 / pane.ink)  # its own fade already; at full strength


def _grains() -> List[Tuple[float, float, float]]:
    """(along the arm, across it, around it) of every grain, from a fixed seed: the same galaxy every run.

    Across is the mean of three draws, so grains crowd the middle of an arm and thin out at its edges.
    """
    seed, out = 11, []
    for _ in range(DUST):
        vals = []
        for _ in range(5):
            seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
            vals.append((seed % 10000) / 10000)
        out.append((vals[0], (vals[1] + vals[2] + vals[3]) / 3 - 0.5, vals[4] - 0.5))
    return out


GRAINS = _grains()


def _project(cx: float, cy: float, r: float, angle: float) -> Tuple[float, float]:
    x, y = r * math.cos(angle), r * math.sin(angle) * FLATTEN
    return cx + x * math.cos(TILT) - y * math.sin(TILT), cy + x * math.sin(TILT) + y * math.cos(TILT)


def galaxy(pane: Pane, t: float) -> None:
    """A spiral galaxy turning slowly, one arm in the colour of each model in use, glowing from within."""
    app, th = pane.app, pane.app.theme
    br = Braille(pane.w, pane.h)
    cx, cy = pane.w, pane.h * 2
    rim = min(pane.w * 0.95, pane.h * 3.4)
    models = [u.model for u in app.snapshot.models[:ARMS_MAX]] or [""]
    arms = max(ARMS_MIN, len(models))
    colors = [app.model_colors.get(models[j % len(models)], th.lavender) for j in range(arms)]
    core = mix(th.yellow, th.peach, 0.5) if pane.light else mix(th.yellow, th.rosewater, 0.4)
    turn = t * TURN
    for j, col in enumerate(colors):
        for along, across, around in GRAINS:
            r = rim * (0.1 + 0.9 * along) + across * rim * 0.12 * (0.4 + along)
            angle = j * 2 * math.pi / arms + along * WINDING + around * 0.1 + turn
            br.dot(*_project(cx, cy, r, angle), mix(col, th.base, 0.1 + 0.6 * along))
    for along, across, around in GRAINS[::3]:  # the bulge: a few sparks, the glow does the rest
        r = rim * 0.1 * along ** 1.5
        br.dot(*_project(cx, cy, r, (across + around) * 40 + turn * 3), core)
    pane.blit(br)
    pane.stars(t)
    cos_t, sin_t = math.cos(-TILT), math.sin(-TILT)

    def light(x: int, y: int) -> Tuple[RGB, float]:
        u, v = x * 2 + 1 - cx, y * 4 + 2 - cy  # the cell centre, in dots, from the core
        dx, dy = u * cos_t - v * sin_t, (u * sin_t + v * cos_t) / FLATTEN  # back onto the disc
        r = math.hypot(dx, dy) / rim
        bulge = math.exp(-(r / 0.16) ** 2)
        along = (r - 0.1) / 0.9
        theta = math.atan2(dy, dx)
        best, col = 0.0, colors[0]
        for j, c in enumerate(colors):
            phase = theta - (j * 2 * math.pi / arms + along * WINDING + turn)
            k = (0.5 + 0.5 * math.cos(phase)) ** 8
            if k > best:
                best, col = k, c
        arm = best * max(0.0, 1 - r) ** 1.2 * 0.75
        if bulge > arm:
            return core, bulge
        return col, arm

    pane.glow(light)


def aurora(pane: Pane, t: float) -> None:
    """Curtains of light along the bottom, one per model, taller while its agents work."""
    app, th = pane.app, pane.app.theme
    br = Braille(pane.w, pane.h)
    h = pane.h * 4
    models = app.snapshot.models[:CURTAINS]
    curtains = []
    for i, u in enumerate(models):
        col = app.model_colors.get(u.model, th.teal)
        foot = h * (0.86 + 0.14 * (i + 0.5) / len(models))
        tall = h * (0.3 if u.active else 0.1)
        curtains.append((col, _curtain(br, th.base, col, t, i, foot, tall, SPARSE[pane.light])))
    pane.blit(br, AURORA_INK)
    pane.stars(t)

    def light(x: int, y: int) -> Tuple[RGB, float]:
        """Where bands overlap their colours blend, weighted by how bright each one is there."""
        total, r, g, b, dark = 0.0, 0.0, 0.0, 0.0, 1.0
        py = y * 4 + 2
        for c, columns in curtains:
            foot, height, power = columns[min(x, len(columns) - 1)]
            f = (foot - py) / max(1.0, height)  # 0 at the hem, 1 at the top
            if f > 1:
                continue
            # Brightest at the hem, fading up to the top and a little below the hem.
            k = power * ((1 - f) ** 2 if f >= 0 else math.exp(-(f * height / 6) ** 2))
            total, dark = total + k, dark * (1 - k)
            r, g, b = r + k * c[0], g + k * c[1], b + k * c[2]
        if total <= 0:
            return th.base, 0.0
        return (round(r / total), round(g / total), round(b / total)), 1 - dark

    pane.glow(light)


def _curtain(br: Braille, base: RGB, col: RGB, t: float, i: int, foot: float, tall: float,
             sparse: float) -> List[Tuple[float, float, float]]:
    """Rays rising from a wavy foot line, thinning out to nothing at the top.

    sparse (0..1) is the share of dots left out even at the foot. Returns (foot, height,
    brightness) per terminal column for the glow, which follows the slow folds and not the single
    rays. It writes the dots itself instead of calling Braille.dot: a wide screen has tens of thousands.
    """
    ramp = [mix(col, base, 0.05 + 0.85 * n / RAMP) for n in range(RAMP + 1)]
    fade = [255 * (sparse + (1 - sparse) * (n / RAMP) ** 0.7) for n in range(RAMP + 1)]
    bits, colors, rows = br.bits, br.col, br.ch * 4
    columns = []
    for x in range(br.cw * 2):
        wave = math.sin(x * 0.028 + t * 0.4 + i * 2.1) + 0.45 * math.sin(x * 0.071 - t * 0.6 + i)
        fold = 0.62 + 0.38 * math.sin(x * 0.033 - t * 0.35 + i * 1.3) * math.sin(x * 0.012 + t * 0.2 + i)
        strand = 0.8 + 0.2 * (((x + i * 7) * 2654435761) >> 7 & 15) / 15  # each ray its own length
        height = int(tall * fold * strand)
        y0 = int(foot + 6 * wave)
        if x % 2 == 0:
            columns.append((y0, tall * fold, fold))
        seed = x * 73856093
        for dy in range(min(height, y0 + 1)):
            n = dy * RAMP // height
            y = y0 - dy
            # The hash is multiplied through, or the dots line up in diagonal streaks.
            if ((seed ^ (dy * 19349663)) * 2654435761 >> 16) & 255 < fade[n] or y >= rows:
                continue
            cell = (x >> 1, y >> 2)
            bits[cell] = bits.get(cell, 0) | BRAILLE_BITS[y & 3][x & 1]
            colors[cell] = ramp[n]
    return columns


# In the order the `n` key walks them. The name shown is tr("backdrop.<name>").
BACKDROPS: Dict[str, Callable[[Pane, float], None]] = {
    "stars": stars, "galaxy": galaxy, "aurora": aurora}
BACKDROP_NAMES = list(BACKDROPS)
