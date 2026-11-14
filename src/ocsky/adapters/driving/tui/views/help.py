"""The help overlay: a centred box that lists every key, drawn over whatever view is open."""
from __future__ import annotations

from typing import TYPE_CHECKING, List, Tuple

from ocsky.adapters.driving.tui import icons
from ocsky.adapters.driving.tui.canvas import Canvas
from ocsky.adapters.driving.tui.text import fit, text_width

if TYPE_CHECKING:
    from ocsky.adapters.driving.tui.app import App

# (keys as typed, key of the description). The order is the order of the box.
KEYS: List[Tuple[str, str]] = [
    ("↑ ↓  j k", "help.select"), ("PgUp PgDn", "help.page"), (icons.KEY_ENTER + "  l  →", "help.trace"),
    ("esc  h  ←", "help.back"), ("tab  c", "help.clock"), ("n", "help.backdrop"), ("space", "help.fold"),
    ("a", "help.history"), ("r", "help.range"), ("o", "help.open"), ("y", "help.copy_id"),
    ("Y", "help.copy_dir"), ("L", "help.lang"), ("t", "help.theme"), ("p", "help.palette"),
    ("?", "help.help"), ("q", "help.quit"),
]
KEY_COL_W = 11


def _layout(cv: Canvas, descs: List[str]) -> Tuple[int, int]:
    """(columns, rows per column): the one that shows the most descriptions uncut for this screen.

    Two columns only win when they show strictly more, so a tie keeps the plainer single column.
    """
    best, best_shown = (1, len(KEYS)), -1
    for columns in (1, 2):
        per_col = (len(KEYS) + columns - 1) // columns
        room = max(0, min(per_col, cv.h - 4)) * columns  # rows beyond the screen are not drawn
        column_w = (cv.w - 4) // columns - KEY_COL_W  # as in draw()
        shown = sum(1 for i, d in enumerate(descs) if i < room and text_width(d) <= column_w)
        if shown > best_shown:
            best, best_shown = (columns, per_col), shown
    return best


def draw(cv: Canvas, app: App) -> None:
    th, tr = app.theme, app.tr
    descs = [tr(key) for _, key in KEYS]
    columns, per_col = _layout(cv, descs)
    two = columns == 2
    col_w = max(text_width(d) for d in descs) + KEY_COL_W
    inner = max(col_w * columns + (columns - 1) + 2, text_width(tr("help.close")) + 2)
    w = min(cv.w, inner + 2)
    h = min(cv.h, per_col + 4)
    x0, y0 = (cv.w - w) // 2, max(0, (cv.h - h) // 2)
    top_left, top_right, bottom_left, bottom_right = icons.BOX
    cv.put(x0, y0, " " * w, th.text, th.mantle)
    cv.put(x0, y0, top_left + icons.RULE * (w - 2) + top_right, th.surface2, th.mantle)
    title = " %s " % tr("help.title")
    cv.put(x0 + 2, y0, title, th.mauve, th.mantle, bold=True)
    for i in range(1, h - 1):
        cv.put(x0, y0 + i, " " * w, th.text, th.mantle)
        cv.put(x0, y0 + i, icons.DIVIDER, th.surface2, th.mantle)
        cv.put(x0 + w - 1, y0 + i, icons.DIVIDER, th.surface2, th.mantle)
    column_w = (w - 4) // 2 if two else w - 4
    for i, ((keys, _), desc) in enumerate(zip(KEYS, descs)):
        column, row = divmod(i, per_col)
        y = y0 + 1 + row
        if y >= y0 + h - 2:
            break
        x = x0 + 2 + column * (column_w + 1)
        cv.put(x, y, keys, th.lavender, th.mantle, bold=True)
        cv.put(x + KEY_COL_W, y, fit(desc, column_w - KEY_COL_W), th.subtext0, th.mantle)
    cv.put(x0, y0 + h - 1, bottom_left + icons.RULE * (w - 2) + bottom_right, th.surface2, th.mantle)
    close = fit(tr("help.close"), w - 4)
    cv.put(x0 + 2, y0 + h - 2, close, th.overlay1, th.mantle)
