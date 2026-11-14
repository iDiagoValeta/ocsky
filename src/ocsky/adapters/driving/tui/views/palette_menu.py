"""The palette menu: a quick pick at the top of the screen, as an editor lists its colour themes.

Typing filters the list, the arrows move through it and the screen behind already wears the
palette under the cursor. Every row carries a chip drawn in that palette's own colours.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional, Tuple

from ocsky.adapters.driving.tui import icons
from ocsky.adapters.driving.tui.palettes import PALETTES
from ocsky.adapters.driving.tui.text import fit, text_width
from ocsky.adapters.driving.tui.theme import Theme

if TYPE_CHECKING:
    from ocsky.adapters.driving.tui.app import App
    from ocsky.adapters.driving.tui.canvas import Canvas

WIDTH = 50
CHIP = ["mauve", "sky", "peach", "green", "pink", "yellow"]  # the first accents a model takes
CHIP_W = 2 * len(CHIP) + 1
CURRENT = "✓"


def _lines(app: App) -> List[Tuple[str, Optional[str]]]:
    """(kind, palette) per line of the list: a "side" heading before each side, then its palettes."""
    out: List[Tuple[str, Optional[str]]] = []
    side = None
    for name in app.palette_choices():
        light = Theme(PALETTES[name].colors).light
        if light != side:
            out.append(("light" if light else "dark", None))
            side = light
        out.append(("palette", name))
    return out


def draw(cv: Canvas, app: App) -> None:
    th, tr, menu = app.theme, app.tr, app.menu
    if menu is None:
        return
    w = min(cv.w - 2, WIDTH)
    x0 = (cv.w - w) // 2
    lines = _lines(app)
    room = max(1, cv.h - 7)  # header row, borders, query, hint, footer
    shown = min(len(lines), room) or 1
    choices = app.palette_choices()
    cursor = next((i for i, (_, name) in enumerate(lines) if choices and name == choices[menu.index]), 0)
    top = max(0, cursor - shown + 1)  # the least scroll that shows the cursor
    h = shown + 4
    y0 = 1
    tl, tr_, bl, br = icons.BOX
    for y in range(y0, y0 + h):
        cv.put(x0, y, " " * w, th.text, th.mantle)
        cv.put(x0, y, icons.DIVIDER, th.surface2, th.mantle)
        cv.put(x0 + w - 1, y, icons.DIVIDER, th.surface2, th.mantle)
    cv.put(x0, y0, tl + icons.RULE * (w - 2) + tr_, th.surface2, th.mantle)
    cv.put(x0 + 2, y0, " %s " % tr("palette.title"), th.mauve, th.mantle, bold=True)
    cv.put(x0, y0 + h - 1, bl + icons.RULE * (w - 2) + br, th.surface2, th.mantle)
    # The query, in a field of its own.
    qy = y0 + 1
    cv.put(x0 + 2, qy, " " * (w - 4), th.text, th.surface0)
    x = cv.put(x0 + 3, qy, "› ", th.lavender, th.surface0, bold=True)
    if menu.query:
        x = cv.put(x, qy, fit(menu.query, w - 8), th.text, th.surface0)
    else:
        cv.put(x + 1, qy, fit(tr("palette.placeholder"), w - 9), th.overlay0, th.surface0)
    cv.put(x, qy, icons.CARET, th.mauve, th.surface0)
    if not choices:
        cv.put(x0 + 3, qy + 1, fit(tr("palette.none"), w - 6), th.overlay1, th.mantle)
    for i, (kind, name) in enumerate(lines[top:top + shown]):
        y = qy + 1 + i
        if kind != "palette":
            label = " " + tr("palette." + kind)
            rule = icons.RULE * max(0, w - 5 - text_width(label))
            cv.put(x0 + 2, y, rule, th.surface1, th.mantle)
            cv.put(x0 + 2 + len(rule), y, label, th.overlay1, th.mantle)
            continue
        _row(cv, app, name, x0, y, w, top + i == cursor)
    hint = tr("palette.hint")
    cv.put(x0 + w - 2 - text_width(hint), y0 + h - 1, hint, th.overlay1, th.mantle)


def _row(cv: Canvas, app: App, name: Optional[str], x0: int, y: int, w: int, selected: bool) -> None:
    th = app.theme
    if name is None:
        return
    p = PALETTES[name]
    bg = th.surface0 if selected else th.mantle
    cv.put(x0 + 1, y, " " * (w - 2), th.text, bg)
    if selected:
        cv.put(x0 + 1, y, icons.SELECTION_BAR, th.lavender, bg)
    mark = CURRENT if app.menu and name == app.menu.before else " "
    cv.put(x0 + 3, y, mark, th.green, bg, bold=True)
    label_w = w - 8 - CHIP_W
    cv.put(x0 + 5, y, fit(p.label, label_w), th.text if selected else th.subtext0, bg, bold=selected)
    own = Theme(p.colors)
    cx = x0 + w - 2 - CHIP_W
    cv.put(cx, y, " " * CHIP_W, own.text, own.base)
    for j, colour in enumerate(CHIP):
        cv.put(cx + 1 + 2 * j, y, "●", getattr(own, colour), own.base)
