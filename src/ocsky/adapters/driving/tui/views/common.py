"""Pieces more than one view draws: header, footer, state glyph, sparkline and starfield."""
from __future__ import annotations

import math
import time
import zlib
from typing import TYPE_CHECKING, Collection, List, NamedTuple, Optional, Tuple

from ocsky.adapters.driving.tui import icons
from ocsky.adapters.driving.tui.canvas import RGB, Canvas, mix
from ocsky.adapters.driving.tui.fmt import fmt_cost
from ocsky.adapters.driving.tui.text import fit, text_width
from ocsky.adapters.driving.tui.theme import Theme
from ocsky.core.model import (
    COMPACTING,
    FAILED,
    INTERRUPTED,
    STALLED,
    SUSPENDED,
    WAITING,
    WORKING,
    Session,
    Step,
)
from ocsky.core.observatory import PULSE_BUCKETS

if TYPE_CHECKING:
    from ocsky.adapters.driving.tui.app import App

# How much of the star colour reaches the cell: the sky is a backdrop, never the subject. A light
# palette needs more, or its stars fade into the paper.
STAR_MIX = {False: 0.5, True: 0.8}
STAR_COUNT = 260


def make_stars() -> List[Tuple[float, float, float, float]]:
    """(x, y, phase, speed) of every star, from a fixed seed so the sky is the same in every run."""
    seed = 7
    stars = []
    for _ in range(STAR_COUNT):
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        x = (seed % 10000) / 10000
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        y = (seed % 10000) / 10000
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        stars.append((x, y, (seed % 628) / 100, 0.4 + (seed % 7) / 7))
    return stars


STARS = make_stars()


class Run(NamedTuple):
    """Consecutive identical steps as one line: the last step, its icon and text, and how many there were."""

    step: Step
    icon: str
    text: str
    count: int


def collapse_steps(steps: List[Step], tr) -> List[Run]:
    """Fold each run of consecutive steps with the same icon and text into one Run (time of the last)."""
    runs: List[Run] = []
    for st in steps:
        icon, text = icons.activity_line(st.activity, tr)
        if runs and runs[-1].icon == icon and runs[-1].text == text:
            runs[-1] = Run(st, icon, text, runs[-1].count + 1)
        else:
            runs.append(Run(st, icon, text, 1))
    return runs


def repeat_suffix(count: int) -> str:
    """` ×N` for a run of N >= 2 identical steps, nothing for a single one."""
    return " %s%d" % (icons.REPEAT, count) if count > 1 else ""


def phase_of(key: str) -> float:
    """A stable offset per id, so sessions pulse out of step. Python's hash() changes on every run."""
    return (zlib.crc32(key.encode()) % 100) / 16


def clock_text(ms: int, fmt: str = "%H:%M") -> str:
    """Local wall-clock time of an epoch in milliseconds."""
    return time.strftime(fmt, time.localtime(ms / 1000))


def starfield(cv: Canvas, theme: Theme, x0: int, y0: int, w: int, h: int, t: float,
              skip_rows: Collection[int] = (), left_gap: int = 0) -> None:
    """Twinkling stars, only on cells that hold no text and no highlight.

    Rows in `skip_rows` get none, and neither do the `left_gap` leftmost columns: a star right
    before a path or a title would read as a prefix of it.
    """
    for sx, sy, phase, speed in STARS:
        x, y = x0 + int(sx * w), y0 + int(sy * h)
        if not (x0 <= x < x0 + w and y0 <= y < y0 + h) or cv.used[y][x] or cv.bg[y][x] != theme.base:
            continue
        if y in skip_rows or x < x0 + left_gap:
            continue
        glow = 0.5 + 0.5 * math.sin(t * speed + phase)
        if glow < 0.55:
            continue
        ch = icons.STAR_FAINT if glow < 0.9 else icons.STAR_BRIGHT if glow > 0.985 else icons.STAR_DIM
        cv.put(x, y, ch, mix(cv.bg[y][x], theme.overlay0, glow * STAR_MIX[theme.light]))


def glyph(app: App, s: Session, t: float) -> Tuple[str, RGB]:
    """The character and colour that carry the state of a session."""
    th = app.theme
    col = app.model_color(s)
    phase = phase_of(s.id)
    if s.state == WORKING:
        k = 0.5 + 0.5 * math.sin(t * 4 + phase)
        return icons.GLYPH_WORKING, mix(mix(col, th.base, 0.55), col, k)
    if s.state == COMPACTING:
        frames = icons.GLYPH_COMPACTING
        return frames[int(t * 4) % len(frames)], th.yellow
    if s.state == WAITING:
        k = 0.5 + 0.5 * math.sin(t * 1.5 + phase)
        return icons.GLYPH_WAITING, mix(th.yellow, col, k)
    if s.state == STALLED:
        return icons.GLYPH_STALLED, th.overlay0
    if s.state == FAILED:
        return icons.GLYPH_FAILED, th.red
    if s.state == INTERRUPTED:
        return icons.GLYPH_INTERRUPTED, th.maroon
    if s.state == SUSPENDED:
        return icons.GLYPH_SUSPENDED, th.overlay1
    return icons.GLYPH_DONE, mix(col, th.base, 0.45)


def pulse_top(sessions: List[Session]) -> int:
    """The busiest pulse bucket of the working sessions: one scale, so their bars can be compared."""
    return max((v for s in sessions if s.working for v in s.pulse), default=0)


def sparkline(s: Session, top: int) -> List[int]:
    """One level per pulse bucket, 0 to 8: how tall its block is against the busiest bucket on screen.

    A bucket with any output is at least two levels tall, so it never reads as the idle baseline.
    """
    levels = [0] * PULSE_BUCKETS
    for i, v in enumerate(s.pulse[:PULSE_BUCKETS]):
        if v > 0 and top > 0:
            levels[i] = max(2, min(8, round(8 * math.sqrt(v / top))))
    return levels


def draw_sparkline(cv: Canvas, app: App, s: Session, x: int, y: int, top: int, bg: Optional[RGB]) -> None:
    """The pulse as a fixed track: a dim baseline for quiet buckets, a block in the model colour for
    busy ones, brighter towards now. The track keeps its width, so bars line up across rows."""
    th, col = app.theme, app.model_color(s)
    for i, level in enumerate(sparkline(s, top)):
        if level:
            k = 0.45 + 0.55 * i / max(1, PULSE_BUCKETS - 1)
            cv.put(x + i, y, icons.SPARK[level], mix(th.base, col, k), bg)
        else:
            cv.put(x + i, y, icons.SPARK[1], th.surface1, bg)


def draw_header(cv: Canvas, app: App, t: float) -> None:
    """Name, only the counts that are not zero, then the cost of the range and the time."""
    th, tr, snap = app.theme, app.tr, app.snapshot
    cv.fill(0, 0, cv.w, 1, th.mantle)
    x = 0
    for i, ch in enumerate(" %s %s " % (icons.LOGO, tr("app.name"))):
        k = 0.5 + 0.5 * math.sin(t * 1.4 - i * 0.55)
        x = cv.put(x, 0, ch, mix(th.mauve, th.sky, k), th.mantle, bold=True)
    working = sum(1 for s in snap.sessions if s.working)
    waiting = sum(1 for s in snap.sessions if s.state == WAITING)
    counts = [(tr("count.working", n=working), th.green)] if working else []
    counts += [(tr("count.waiting", n=waiting), th.yellow)] if waiting else []
    x += 1
    if not counts:
        x = cv.put(x, 0, tr("header.quiet"), th.overlay1, th.mantle)
    for i, (text, col) in enumerate(counts):
        x = cv.put(x, 0, " · " if i else "", th.overlay0, th.mantle)
        x = cv.put(x, 0, text, col, th.mantle)
    cost = sum(s.cost for s in snap.sessions)
    clock = clock_text(app.now_ms)
    right = (fmt_cost(cost, tr.lang) + "   " if cost > 0 else "") + clock + " "
    rx = max(x + 2, cv.w - text_width(right))
    if cost > 0:
        rx = cv.put(rx, 0, fmt_cost(cost, tr.lang) + "   ", th.peach, th.mantle)
    cv.put(rx, 0, clock, th.text, th.mantle)


def draw_footer(cv: Canvas, app: App, hints: List[Tuple[str, str]]) -> None:
    """The key hints, then the confirmation of the last action or the store error."""
    th = app.theme
    y = cv.h - 1
    cv.fill(0, y, cv.w, 1, th.mantle)
    x = 1
    for key, label in hints:
        x = cv.put(x, y, " %s " % key, th.base, th.lavender, bold=True)
        x = cv.put(x, y, " %s  " % label, th.subtext0, th.mantle)  # a gap after the chip, two between hints
    toast = app.toast_text()
    if toast:
        cv.put(x + 1, y, fit(toast, cv.w - x - 2), th.green, th.mantle, bold=True)
    elif app.snapshot.error:
        message = app.tr("error.store", detail=app.snapshot.error_detail)
        cv.put(x + 1, y, fit(message, cv.w - x - 2), th.red, th.mantle)
