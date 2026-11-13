"""The sky, the default view: sessions grouped by directory, one line each, and a focus pane."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Optional, Tuple

from ocsky.adapters.driving.tui import icons
from ocsky.adapters.driving.tui.canvas import Canvas, mix
from ocsky.adapters.driving.tui.fmt import fmt_age, fmt_cost, fmt_tokens
from ocsky.adapters.driving.tui.text import fit, short_dir, text_width, wrap
from ocsky.adapters.driving.tui.views.common import (
    clock_text,
    collapse_steps,
    glyph,
    repeat_suffix,
    draw_sparkline,
    pulse_top,
    starfield,
)
from ocsky.core.model import STALLED, Session
from ocsky.core.observatory import PULSE_BUCKETS

if TYPE_CHECKING:
    from ocsky.adapters.driving.tui.app import App

# The focus pane needs room beside the list; narrower terminals get the list alone.
FOCUS_MIN_COLS = 100
LIST_TOP = 2
LEFT_MARGIN = 2
AGENT_NAME_MAX = 14
DIR_PARTS = 3  # a long directory shows its last three components
FOCUS_MESSAGES = 40  # read this many messages for the steps pane, so folded runs leave it full


@dataclass
class Line:
    """One visual line of the list. Only "session" lines can be selected."""

    kind: str  # "group" | "blank" | "session" | "activity" | "folded"
    session: Optional[Session]
    row_index: int  # index in snapshot.rows of the row this line belongs to


def hints(app: App) -> List[Tuple[str, str]]:
    tr = app.tr
    return [("?", tr("key.help")), (icons.KEY_ENTER, tr("key.trace")), ("o", tr("key.open")),
            (icons.KEY_TAB, tr("key.clock")),
            ("a", tr("key.active") if not app.only_active else tr("key.history")), ("q", tr("key.quit"))]


def _shows_activity(app: App, s: Session, index: int) -> bool:
    """Working roots always say what they are doing; any other row only while it is selected."""
    if index == app.sel:
        return s.working or s.activity is not None
    return s.working and s.depth == 0


def _fold_line(lines: List[Line], opened: Tuple[Session, int]) -> None:
    s, index = opened
    if s.hidden_children:
        lines.append(Line("folded", s, index))


def build_lines(app: App) -> List[Line]:
    """Every visual line of the list, in order: group headers, rows, activity and folded counts."""
    lines: List[Line] = []
    open_rows: List[Tuple[Session, int]] = []  # rows whose subagents are still being listed
    previous_dir: Optional[str] = None
    for index, s in enumerate(app.snapshot.rows):
        while len(open_rows) > s.depth:
            _fold_line(lines, open_rows.pop())
        if s.depth == 0 and s.directory != previous_dir:
            if previous_dir is not None:
                lines.append(Line("blank", None, index))
            lines.append(Line("group", s, index))
            previous_dir = s.directory
        lines.append(Line("session", s, index))
        if _shows_activity(app, s, index):
            lines.append(Line("activity", s, index))
        open_rows.append((s, index))
    while open_rows:
        _fold_line(lines, open_rows.pop())
    return lines


def scroll_into_view(app: App, lines: List[Line], height: int) -> None:
    """Move app.scroll the least that keeps the selected row, its activity and its group header in view."""
    mine = [i for i, line in enumerate(lines)
            if line.row_index == app.sel and line.kind in ("session", "activity")]
    if mine:
        first, last = mine[0], mine[-1]
        while first > 0 and lines[first - 1].kind in ("group", "blank"):
            first -= 1  # the header of a group goes with its first row
        if first < app.scroll:
            app.scroll = first
        if last >= app.scroll + height:
            app.scroll = last - height + 1
    app.scroll = max(0, min(app.scroll, max(0, len(lines) - height)))


def _arrow_x(depth: int) -> int:
    return LEFT_MARGIN + 2 * depth


def _glyph_x(depth: int) -> int:
    return _arrow_x(depth) + (2 if depth else 0)


def _select_bar(cv: Canvas, app: App, s: Session, y: int, w: int) -> None:
    th = app.theme
    cv.fill(0, y, w, 1, th.surface0)
    cv.put(0, y, icons.SELECTION_BAR, app.model_color(s), th.surface0)


def draw_group(cv: Canvas, app: App, s: Session, y: int, w: int) -> None:
    th = app.theme
    x = LEFT_MARGIN
    if s.directory.rstrip("/") == app.observatory.here.rstrip("/"):  # only the exact directory
        x = cv.put(x, y, app.tr("group.here") + " ", th.mauve, bold=True)
    cv.put(x, y, short_dir(s.directory, w - x - 1, app.home, DIR_PARTS), th.overlay1)


# Room for the ages a working row shows ("3h 05m", "59 min"); a longer one just eats the gap.
AGE_WIDTH = 6


def draw_session(cv: Canvas, app: App, s: Session, y: int, w: int, selected: bool, agent_w: int,
                 t: float) -> None:
    th = app.theme
    bg = th.surface0 if selected else None
    col = app.model_color(s)
    if selected:
        _select_bar(cv, app, s, y, w)
    x = _arrow_x(s.depth)
    if s.is_subagent:
        x = cv.put(x, y, icons.SUBAGENT + " ", th.surface2, bg)
    char, char_col = glyph(app, s, t)
    x = cv.put(x, y, char + " ", char_col, bg, bold=True)
    if s.is_subagent:
        x = cv.put(x, y, fit(s.agent, AGENT_NAME_MAX).ljust(agent_w) + "  ", th.lavender, bg)
    now = app.now_ms
    age = fmt_age(now - (s.busy if s.working and s.busy else s.updated), app.tr.lang)
    cv.put(w - 1 - text_width(age), y, age, th.overlay1, bg)
    # The age column has a fixed width, so the pulse tracks of every row start at the same column.
    right = w - 1 - AGE_WIDTH
    spark_x = right - 2 - PULSE_BUCKETS
    show_spark = s.working and spark_x - x >= 16
    if show_spark:
        draw_sparkline(cv, app, s, spark_x, y, pulse_top(app.snapshot.rows), bg)
    title_col = col if s.live else (th.subtext0 if selected else th.overlay1)
    limit = (spark_x if show_spark else right) - 2 - x
    cv.put(x, y, fit(s.title or s.slug, limit), title_col, bg, bold=s.working)


def draw_activity(cv: Canvas, app: App, s: Session, y: int, w: int, selected: bool) -> None:
    th, tr = app.theme, app.tr
    bg = th.surface0 if selected else None
    if selected:
        _select_bar(cv, app, s, y, w)
    icon, text = icons.doing_line(s, tr)
    if s.state == STALLED:
        text = "%s · %s" % (tr("row.stalled", age=fmt_age(app.now_ms - s.updated, tr.lang)), text)
    thinking = icon == icons.ACTIVITY_ICONS["reasoning"]
    x = cv.put(_glyph_x(s.depth) + 2, y, icon + " ", th.mauve if thinking else th.peach, bg)
    cv.put(x, y, fit(text, w - x - 1), th.overlay1 if thinking else th.subtext0, bg)


def draw_folded(cv: Canvas, app: App, s: Session, y: int) -> None:
    th = app.theme
    text = icons.SUBAGENT + " " + app.tr("row.folded", n=s.hidden_children)
    cv.put(_arrow_x(s.depth + 1), y, text, th.overlay0)


def draw_empty(cv: Canvas, app: App, w: int, height: int) -> None:
    th, tr = app.theme, app.tr
    message = tr("empty.active") if app.only_active else tr("empty.range")
    y = LIST_TOP + height // 2 - 1
    cv.put(max(1, (w - text_width(message)) // 2), y, message, th.subtext0)
    if app.only_active:
        hint = tr("empty.hint")
        cv.put(max(1, (w - text_width(hint)) // 2), y + 1, hint, th.overlay0)


def draw_list(cv: Canvas, app: App, w: int, height: int, t: float) -> List[int]:
    """Draw the list. Returns the screen rows that hold a group header."""
    lines = build_lines(app)
    if not lines:
        draw_empty(cv, app, w, height)
        return []
    scroll_into_view(app, lines, height)
    subagents = [text_width(s.agent) for s in app.snapshot.rows if s.is_subagent]
    agent_w = min(AGENT_NAME_MAX, max(subagents, default=0))
    headers: List[int] = []
    for i, line in enumerate(lines[app.scroll:app.scroll + height]):
        y = LIST_TOP + i
        s = line.session
        selected = line.row_index == app.sel
        if line.kind == "group" and s:
            headers.append(y)
            draw_group(cv, app, s, y, w)
        elif line.kind == "session" and s:
            draw_session(cv, app, s, y, w, selected, agent_w, t)
        elif line.kind == "activity" and s:
            draw_activity(cv, app, s, y, w, selected)
        elif line.kind == "folded" and s:
            draw_folded(cv, app, s, y)
    return headers


# -- the focus pane

def _rule(cv: Canvas, app: App, x: int, y: int, w: int, label: str, extra: str = "") -> None:
    th = app.theme
    x2 = cv.put(x, y, label + " ", th.overlay1)
    x2 = cv.put(x2, y, extra + (" " if extra else ""), th.mauve)
    cv.put(x2, y, icons.RULE * max(0, x + w - x2), th.surface1)


def _focus_head(cv: Canvas, app: App, s: Session, x0: int, y0: int, w: int, t: float) -> None:
    th, tr = app.theme, app.tr
    col = app.model_color(s)
    char, char_col = glyph(app, s, t)
    x = cv.put(x0, y0, char + " ", char_col, bold=True)
    cv.put(x, y0, fit(s.title or s.slug, x0 + w - x), col, bold=True)
    state = "%s · %s · %s" % (tr("state." + s.state), s.agent, s.slug) if s.state else s.agent
    cv.put(x0, y0 + 1, fit(state, w), th.subtext0)
    cv.put(x0, y0 + 2, fit(s.model, w), col)
    cv.put(x0, y0 + 3, short_dir(s.directory, w, app.home, DIR_PARTS), th.overlay1)
    end = s.idle if s.idle and not s.working else app.now_ms
    stats = tr("focus.stats", tin=fmt_tokens(s.tokens_in, tr.lang),
               tout=fmt_tokens(s.tokens_out + s.tokens_reasoning, tr.lang),
               cost=fmt_cost(s.cost, tr.lang), age=fmt_age(end - s.created, tr.lang))
    cv.put(x0, y0 + 4, fit(stats, w), th.subtext0)


def _focus_thought(cv: Canvas, app: App, s: Session, thought: str, x0: int, y: int, w: int,
                   height: int) -> None:
    th = app.theme
    if not thought:
        cv.put(x0, y, app.tr("focus.no_thought"), th.overlay0)
        return
    shown = app.typed(s, thought)
    lines = wrap(thought[:shown], w)[-height:]
    for i, line in enumerate(lines):
        cv.put(x0, y + i, line, mix(th.overlay1, th.text, (i + 1) / len(lines)))
    if shown < len(thought) and lines:
        cv.put(x0 + min(w - 1, text_width(lines[-1])), y + len(lines) - 1, icons.CARET, th.mauve)


def _focus_steps(cv: Canvas, app: App, s: Session, steps: list, x0: int, y: int, w: int,
                 room: int) -> None:
    th = app.theme
    runs = collapse_steps([st for st in steps if st.activity.kind != "reasoning"], app.tr)
    tail = runs[-room:] if room > 0 else []
    for i, run in enumerate(tail):
        fresh = i == len(tail) - 1 and s.working
        x = cv.put(x0, y + i, clock_text(run.step.time, "%H:%M:%S") + " ", th.overlay0)
        near_user = run.step.activity.kind in ("user", "text")
        x = cv.put(x, y + i, run.icon + " ", th.sky if near_user else th.peach)
        suffix = repeat_suffix(run.count)
        x = cv.put(x, y + i, fit(run.text, x0 + w - x - len(suffix)),
                   th.text if fresh else th.subtext0, bold=fresh)
        cv.put(x, y + i, suffix, th.overlay0)


def draw_focus(cv: Canvas, app: App, s: Session, x0: int, y0: int, w: int, h: int, t: float) -> None:
    """Everything about the selected session: who it is, what it thinks, what it did last."""
    tr = app.tr
    _focus_head(cv, app, s, x0, y0, w, t)
    steps = app.steps(s, FOCUS_MESSAGES)
    thought = s.thought or next((st.activity.detail for st in reversed(steps)
                                 if st.activity.kind == "reasoning"), "")
    think_h = max(3, min(8, (h - 6) // 3))
    y = y0 + 6
    spinner = icons.SPINNER[int(t * 8) % len(icons.SPINNER)] if s.working else ""
    _rule(cv, app, x0, y, w, tr("focus.thinking"), spinner)
    _focus_thought(cv, app, s, thought, x0, y + 1, w, think_h)
    y += think_h + 2
    _rule(cv, app, x0, y, w, tr("focus.steps"))
    _focus_steps(cv, app, s, steps, x0, y + 1, w, y0 + h - y - 1)


def draw(cv: Canvas, app: App, t: float) -> None:
    th = app.theme
    # With nothing to select there is no detail to show: the list takes the whole width.
    focus = cv.w >= FOCUS_MIN_COLS and bool(app.snapshot.rows)
    right_w = max(38, min(64, cv.w * 2 // 5)) if focus else 0
    left_w = cv.w - right_w - (1 if focus else 0)
    height = cv.h - 1 - LIST_TOP
    headers = draw_list(cv, app, left_w, height, t)
    starfield(cv, th, 0, LIST_TOP, left_w, height, t, headers, LEFT_MARGIN)
    if focus:
        for y in range(1, cv.h - 1):
            cv.put(left_w, y, icons.DIVIDER, th.surface0)
        if app.selected:
            draw_focus(cv, app, app.selected, left_w + 2, LIST_TOP, right_w - 3, height, t)
