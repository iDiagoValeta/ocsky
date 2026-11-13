"""The trace of one session: every step it took, newest at the bottom."""
from __future__ import annotations

from typing import TYPE_CHECKING, List, Tuple

from ocsky.adapters.driving.tui import icons
from ocsky.adapters.driving.tui.canvas import RGB, Canvas
from ocsky.adapters.driving.tui.text import fit, short_dir, wrap
from ocsky.adapters.driving.tui.views.common import clock_text, collapse_steps, glyph, repeat_suffix

if TYPE_CHECKING:
    from ocsky.adapters.driving.tui.app import App

# Enough history to scroll through without reading the whole conversation.
TRACE_LIMIT = 200
TEXT_X = 13
TIME_W = 10


def hints(app: App) -> List[Tuple[str, str]]:
    tr = app.tr
    return [("?", tr("key.help")), (icons.KEY_ESC, tr("key.back")), (icons.KEY_UPDOWN, tr("key.scroll")),
            ("o", tr("key.open")), ("q", tr("key.quit"))]


def _kind_colors(app: App) -> dict:
    th = app.theme
    return {"reasoning": th.mauve, "user": th.sky, "text": th.green, "idle": th.overlay1,
            "compaction": th.yellow}


def _wrapped_lines(app: App, width: int) -> List[Tuple[str, str, RGB, RGB, bool, str, str]]:
    """(time, icon, icon colour, text colour, bold, text, dim suffix) for every screen line of the trace."""
    th = app.theme
    kinds = _kind_colors(app)
    lines = []
    for run in collapse_steps(app.steps(app.selected, TRACE_LIMIT), app.tr):
        act = run.step.activity
        stamp = clock_text(run.step.time, "%H:%M:%S")
        suffix = repeat_suffix(run.count)
        parts = wrap(run.text, width - len(suffix)) or [""]
        for i, part in enumerate(parts):
            lines.append((stamp if i == 0 else "", run.icon if i == 0 else " ", kinds.get(act.kind, th.peach),
                          th.overlay1 if act.kind == "reasoning" else th.text, act.kind == "user", part,
                          suffix if i == len(parts) - 1 else ""))
    return lines


def draw(cv: Canvas, app: App, t: float) -> None:
    th, tr = app.theme, app.tr
    s = app.selected
    if s is None:
        app.view = "sky"
        return
    char, char_col = glyph(app, s, t)
    x = cv.put(1, 1, char + " ", char_col, bold=True)
    x = cv.put(x, 1, s.title or s.slug, app.model_color(s), bold=True, maxw=cv.w - x - 1)
    detail = "  %s · %s · %s" % (s.agent, s.model, tr("state." + s.state) if s.state else "")
    cv.put(x, 1, fit(detail, cv.w - x - 1), th.subtext0)
    cv.put(3, 2, short_dir(s.directory, cv.w - 6, app.home), th.overlay1)
    lines = _wrapped_lines(app, cv.w - TEXT_X - 2)
    room = cv.h - 5
    app.trace_scroll = max(0, min(app.trace_scroll, max(0, len(lines) - room)))
    start = max(0, len(lines) - room - app.trace_scroll)
    for i, (stamp, icon, icon_col, text_col, bold, part, suffix) in enumerate(lines[start:start + room]):
        y = 4 + i
        cv.put(1, y, stamp, th.overlay0)
        cv.put(TIME_W + 1, y, icon, icon_col, bold=True)
        end = cv.put(TEXT_X, y, part, text_col, bold=bold)
        cv.put(end, y, suffix, th.overlay0)
    if not lines:
        cv.put(3, 5, tr("trace.empty"), th.overlay0)
    if app.trace_scroll:
        cv.put(cv.w - 24, 3, tr("trace.newer", n=app.trace_scroll), th.yellow)
