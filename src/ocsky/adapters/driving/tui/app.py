"""The state of the interface: what is selected, which view is open, and what every key does."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from ocsky.adapters.driving.tui.canvas import RGB, Canvas
from ocsky.adapters.driving.tui.i18n import Tr
from ocsky.adapters.driving.tui.theme import LATTE, MOCHA, Theme
from ocsky.adapters.driving.tui.views import clock as clock_view
from ocsky.adapters.driving.tui.views import common
from ocsky.adapters.driving.tui.views import help as help_view
from ocsky.adapters.driving.tui.views import sky, trace
from ocsky.core.model import Session, Snapshot, Step
from ocsky.core.observatory import Observatory
from ocsky.core.ports.for_copying_text import ForCopyingText
from ocsky.core.ports.for_keeping_preferences import ForKeepingPreferences
from ocsky.core.ports.for_opening_sessions import ForOpeningSessions
from ocsky.core.ports.for_telling_time import ForTellingTime

# (key, milliseconds). The label is tr("range." + key).
RANGES = [("1h", 3600_000), ("6h", 6 * 3600_000), ("24h", 86400_000), ("7d", 7 * 86400_000)]

MIN_COLS, MIN_ROWS = 60, 14
REFRESH_MS = 1000  # the database is read at most once a second
TOAST_MS = 2000
STEPS_TTL_MS = 1000
TYPING_CHARS_PER_FRAME = 14
PAGE = 10

KEYS_UP = ("\x1b[A", "k")
KEYS_DOWN = ("\x1b[B", "j")
KEYS_OPEN = ("\r", "\n", "l", "\x1b[C")
KEYS_BACK = ("\x1b", "\x7f", "h", "\x1b[D")
KEYS_CLOCK = ("\t", "c")
KEYS_QUIT = ("q", "\x03")
KEY_PAGE_UP, KEY_PAGE_DOWN = "\x1b[5~", "\x1b[6~"


@dataclass
class Options:
    """What the person asked for on the command line. main.py fills it in; nothing here reads the system."""

    range: str = "24h"
    all: bool = False
    view: str = "sky"
    light: bool = False
    colors: str = "truecolor"
    lang: str = "en"
    instant: bool = False  # draw thoughts whole instead of typing them in (a single frame)


class App:
    def __init__(self, observatory: Observatory, clock: ForTellingTime, opener: ForOpeningSessions,
                 clipboard: ForCopyingText, prefs: ForKeepingPreferences, options: Options, home: str):
        self.observatory = observatory
        self.clock = clock
        self.opener = opener
        self.clipboard = clipboard
        self.prefs = prefs
        self.options = options
        self.home = home
        self.tr = Tr(options.lang)
        self.light = options.light
        self.theme = Theme(LATTE if self.light else MOCHA)
        self.range_index = [key for key, _ in RANGES].index(options.range)
        self.view = options.view
        self.only_active = not options.all  # live agents first; the history is one key away
        self.snapshot = Snapshot(sessions=[], rows=[], procs=[], models=[])
        self.model_colors: Dict[str, RGB] = {}
        self.expanded: Set[str] = set()
        self.sel = 0
        self.scroll = 0
        self.trace_scroll = 0
        self.help_open = False
        self.pending_open: Optional[Session] = None
        self.start_ms = clock.now_ms()
        self._last_refresh: Optional[int] = None
        self._toast: Tuple[str, int] = ("", 0)
        self._steps: Dict[Tuple[str, int], Tuple[int, List[Step]]] = {}
        self._typed: Dict[str, int] = {}
        self._keep: Optional[str] = None  # a row to select after the next refresh

    # -- state the views read

    @property
    def now_ms(self) -> int:
        return self.clock.now_ms()

    @property
    def selected(self) -> Optional[Session]:
        rows = self.snapshot.rows
        return rows[min(self.sel, len(rows) - 1)] if rows else None

    def model_color(self, s: Session) -> RGB:
        return self.model_colors.get(s.model, self.theme.overlay1)

    def toast_text(self) -> str:
        text, until = self._toast
        return text if self.now_ms < until else ""

    def steps(self, s: Session, limit: int = 14) -> List[Step]:
        """The newest steps of a session. Read at most once a second, since frames come much faster."""
        now = self.now_ms
        hit = self._steps.get((s.id, limit))
        if hit is None or now - hit[0] >= STEPS_TTL_MS:
            hit = (now, self.observatory.trace(s, limit))
            self._steps[(s.id, limit)] = hit
        return hit[1]

    def typed(self, s: Session, thought: str) -> int:
        """How many characters of a thought to show: a working session's thought types itself in."""
        key = s.id + str(len(thought))
        shown = self._typed.get(key, 0 if s.working and not self.options.instant else len(thought))
        self._typed[key] = min(len(thought), shown + TYPING_CHARS_PER_FRAME)
        return shown

    # -- data

    def _assign_colors(self) -> None:
        taken: Set[RGB] = set()
        self.model_colors = {}
        for model in sorted(u.model for u in self.snapshot.models):
            self.model_colors[model] = self.theme.model_color(model, taken)
            taken.add(self.model_colors[model])

    def refresh(self, force: bool = False) -> None:
        now = self.now_ms
        if not force and self._last_refresh is not None and now - self._last_refresh < REFRESH_MS:
            return
        keep = self._keep or (self.selected.id if self.selected else None)
        self._keep = None
        self.snapshot = self.observatory.observe(RANGES[self.range_index][1], self.only_active,
                                                 self.expanded)
        self._assign_colors()
        ids = [s.id for s in self.snapshot.rows]
        self.sel = ids.index(keep) if keep in ids else min(self.sel, max(0, len(ids) - 1))
        self._last_refresh = now

    # -- drawing

    def frame(self, cols: int, rows: int) -> str:
        return self.canvas(cols, rows).render(self.options.colors)

    def canvas(self, cols: int, rows: int) -> Canvas:
        """The screen as cells, before any escape sequence is written."""
        th = self.theme
        cv = Canvas(cols, rows, th.base, th.text)
        if cols < MIN_COLS or rows < MIN_ROWS:
            cv.put(1, 1, self.tr("error.small"), th.yellow)
            return cv
        t = (self.now_ms - self.start_ms) / 1000
        screen = {"clock": clock_view, "trace": trace}.get(self.view, sky)
        common.draw_header(cv, self, t)
        screen.draw(cv, self, t)
        common.draw_footer(cv, self, screen.hints(self))
        if self.help_open:
            help_view.draw(cv, self)
        return cv

    # -- keys

    def key(self, k: str) -> bool:
        """Handle one key. False means quit."""
        if self.help_open:
            self.help_open = False
            return True
        if k in KEYS_QUIT:
            return False
        if self.view == "trace" and self._key_trace(k):
            return True
        if self.view == "sky" and self._key_sky(k):
            return True
        self._key_common(k)
        return True

    def _key_sky(self, k: str) -> bool:
        n = len(self.snapshot.rows)
        last = max(0, n - 1)
        if k in KEYS_UP:
            self.sel = max(0, self.sel - 1)
        elif k in KEYS_DOWN:
            self.sel = min(last, self.sel + 1)
        elif k == KEY_PAGE_UP:
            self.sel = max(0, self.sel - PAGE)
        elif k == KEY_PAGE_DOWN:
            self.sel = min(last, self.sel + PAGE)
        elif k in KEYS_OPEN and n:
            self.view, self.trace_scroll = "trace", 0
        elif k == " ":
            self._toggle_fold()
        else:
            return False
        return True

    def _key_trace(self, k: str) -> bool:
        if k in KEYS_UP:
            self.trace_scroll += 1
        elif k in KEYS_DOWN:
            self.trace_scroll = max(0, self.trace_scroll - 1)
        elif k == KEY_PAGE_UP:
            self.trace_scroll += PAGE
        elif k == KEY_PAGE_DOWN:
            self.trace_scroll = max(0, self.trace_scroll - PAGE)
        else:
            return False
        return True

    def _key_common(self, k: str) -> None:
        s = self.selected
        if k in KEYS_BACK and self.view != "sky":
            self.view = "sky"
        elif k in KEYS_CLOCK:
            self.view = "clock" if self.view == "sky" else "sky"
        elif k == "a":
            self.only_active = not self.only_active
            self.refresh(force=True)
        elif k == "r":
            self.range_index = (self.range_index + 1) % len(RANGES)
            self.refresh(force=True)
            self._set_toast(self.tr("toast.range", range=self.tr("range." + RANGES[self.range_index][0])))
        elif k == "?":
            self.help_open = True
        elif k == "L":
            self._switch_language()
        elif k == "t":
            self._switch_theme()
        elif k == "o" and s:
            self.pending_open = s
        elif k == "y" and s:
            self.clipboard.copy(s.id)
            self._set_toast(self.tr("toast.copied_id"))
        elif k == "Y" and s:
            self.clipboard.copy(s.directory)
            self._set_toast(self.tr("toast.copied_dir"))

    def _toggle_fold(self) -> None:
        """Unfold or fold the finished subagents of the selected row (or of its parent, for a leaf)."""
        s = self.selected
        if s is None:
            return
        target = s.id
        if s.is_subagent and not s.children and s.parent:
            target = s.parent
        if target in self.expanded:
            self.expanded.discard(target)
            self._keep = target  # the subagent may vanish with the fold; stay on its parent
        else:
            self.expanded.add(target)
        self.refresh(force=True)

    def _switch_language(self) -> None:
        self.tr = self.tr.next()
        self._save({"lang": self.tr.lang})
        self._set_toast(self.tr("toast.lang"))

    def _switch_theme(self) -> None:
        self.light = not self.light
        self.theme = Theme(LATTE if self.light else MOCHA)
        self._assign_colors()
        self._save({"theme": "light" if self.light else "dark"})
        self._set_toast(self.tr("toast.theme_light" if self.light else "toast.theme_dark"))

    def _save(self, change: Dict[str, str]) -> None:
        prefs = self.prefs.load()
        prefs.update(change)
        self.prefs.save(prefs)

    def _set_toast(self, text: str) -> None:
        self._toast = (text, self.now_ms + TOAST_MS)

    # -- actions the run loop performs

    def open_pending(self) -> None:
        """Open the session the `o` key chose, in opencode. The loop calls this with the terminal released."""
        s, self.pending_open = self.pending_open, None
        if s is None:
            return
        try:
            self.opener.open(s)
        except OSError:
            self._set_toast(self.tr("toast.open_failed"))
