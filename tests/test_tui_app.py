"""The interface end to end: what a person sees in the frame and what each key does."""
from __future__ import annotations

import os
import re
import tempfile
import unittest
from typing import List

from tests import helpers  # noqa: F401
# isort: split
from ocsky.adapters.driven.demo_database import DEMO_HERE, DEMO_HOME, build_demo_db
from ocsky.adapters.driven.sqlite_sessions import SqliteSessions
from ocsky.adapters.driving.tui.app import App, Options
from ocsky.adapters.driving.tui.canvas import Canvas
from ocsky.adapters.driving.tui.i18n import STRINGS, Tr
from ocsky.adapters.driving.tui.theme import MOCHA, Theme
from ocsky.adapters.driving.tui.views.common import clock_text, pulse_top, sparkline, starfield
from ocsky.core.model import Proc
from ocsky.core.observatory import PULSE_BUCKETS, Observatory
from tests.doubles import (
    assistant_message,
    FixedClock,
    FixedProcesses,
    InMemorySessions,
    MemoryPreferences,
    RecordingClipboard,
    RecordingOpener,
    make_session,
)

NOW = 1_800_000_000_000
LIST_W = 83  # width of the list at 140 columns; the focus pane starts after it
UP, DOWN, PGDN, ENTER, ESC, TAB = "\x1b[A", "\x1b[B", "\x1b[6~", "\r", "\x1b", "\t"


def frame_text(app: App, cols: int = 140, rows: int = 40) -> str:
    """The frame as the plain text a person reads, one screen line per line."""
    raw = app.frame(cols, rows)
    raw = re.sub(r"\x1b\[(\d+);1H", "\n", raw)
    return re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]", "", raw)[1:]  # the first cursor move leaves a leading newline


def left(text: str) -> List[str]:
    """The list column of the frame, without the focus pane."""
    return [line[:LIST_W] for line in text.splitlines()]


class FailingOpener:
    def open(self, session) -> None:
        raise FileNotFoundError("opencode")


class DemoFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        path = os.path.join(self.tmp.name, "opencode.db")
        build_demo_db(path, NOW)
        self.clock = FixedClock(NOW)
        self.opener, self.clipboard, self.prefs = RecordingOpener(), RecordingClipboard(), MemoryPreferences()
        procs = FixedProcesses([Proc(1, "tui", DEMO_HERE, 0.0, 1.0)])
        store = SqliteSessions(path)
        self.addCleanup(store.close)  # runs before the directory goes: Windows cannot delete an open file
        self.observatory = Observatory(store, procs, self.clock, DEMO_HOME, DEMO_HERE)
        self.app = self.make_app()

    def make_app(self, opener=None, **options) -> App:
        app = App(self.observatory, self.clock, opener or self.opener, self.clipboard, self.prefs,
                  Options(instant=True, **options), DEMO_HOME)
        app.refresh(force=True)
        return app

    def press(self, *keys: str) -> None:
        for k in keys:
            self.assertTrue(self.app.key(k))


class DemoAppTest(DemoFixture):
    def test_the_default_view_shows_only_what_is_alive_and_how_much_is_working(self):
        text = frame_text(self.app)
        lines = text.splitlines()
        self.assertIn("working", lines[0])
        self.assertNotIn("processes", lines[0])
        self.assertNotIn("sessions", lines[0])
        column = "\n".join(left(text))
        here = column.index("here ~/bug-hunts/acme-parser/repo")
        self.assertLess(here, column.index("~/dev/shop-api"))
        self.assertLess(column.index("Hunt acme/parser: logic, security"), column.index("Hunter H-003"))
        hunters = [line for line in left(text) if "bh-hunter" in line]
        self.assertEqual(len(hunters), 2)
        self.assertTrue(all("↳" in line for line in hunters))
        self.assertIn("+2 finished", column)
        for gone in ("Reproduce H-001-02", "Probe the billing typecheck", "Fix flaky checkout test"):
            self.assertNotIn(gone, text)

    def test_a_row_does_not_name_its_model_and_the_focus_pane_does(self):
        text = frame_text(self.app)
        self.assertNotIn("deepseek", "\n".join(left(text)))
        self.assertIn("deepseek/deepseek-flash", text)
        self.assertIn("Two hunters are working", text)
        self.assertIn("thinking", text)
        self.assertIn("steps", text)

    def test_space_unfolds_the_finished_subagents_and_folds_them_again(self):
        self.press(" ")
        column = "\n".join(left(frame_text(self.app)))
        self.assertIn("Hunter H-001: src/lexer", column)
        self.assertNotIn("+2 finished", column)
        self.press(" ")
        column = "\n".join(left(frame_text(self.app)))
        self.assertNotIn("Hunter H-001: src/lexer", column)
        self.assertIn("+2 finished", column)

    def test_the_history_key_brings_back_finished_and_stalled_sessions(self):
        self.assertNotIn("Probe the billing typecheck", frame_text(self.app))
        self.press("a")
        self.assertIn("Probe the billing typecheck", frame_text(self.app))

    def test_a_stalled_session_says_how_long_it_has_been_quiet_once_selected(self):
        self.press("a")
        while self.app.selected.title != "Probe the billing typecheck":
            self.press("j")
        self.assertIn("no activity for", frame_text(self.app))

    def test_narrow_and_tiny_terminals(self):
        wide = frame_text(self.app, 140, 40)
        narrow = frame_text(self.app, 80, 24)
        self.assertIn("│", wide)
        self.assertNotIn("│", narrow)
        self.assertIn("Hunt acme/parser", narrow)
        tiny = [line for line in frame_text(self.app, 50, 10).splitlines() if line.strip()]
        self.assertEqual(len(tiny), 1)
        self.assertIn("bigger", tiny[0])

    def test_the_language_key_switches_to_spanish_and_saves_it(self):
        self.press("j", "L")
        text = frame_text(self.app)
        self.assertIn("trabajando", text)
        self.assertEqual(self.prefs.prefs["lang"], "es")
        self.assertNotIn("working", text)
        self.assertIn(Tr("es")("toast.lang"), text)

    def test_copy_keys_put_the_id_and_the_directory_on_the_clipboard_and_the_toast_expires(self):
        self.press("y")
        self.assertEqual(self.clipboard.copied, ["ses_orc"])
        self.assertIn("session id copied", frame_text(self.app))
        self.press("Y")
        self.assertEqual(self.clipboard.copied[-1], DEMO_HERE)
        self.assertIn("directory copied", frame_text(self.app))
        self.clock.now += 3000
        text = frame_text(self.app)
        self.assertNotIn("directory copied", text)
        self.assertNotIn("session id copied", text)

    def test_the_open_key_hands_the_selected_session_to_the_opener(self):
        self.press("o")
        self.assertEqual(self.app.pending_open.id, "ses_orc")
        self.app.open_pending()
        self.assertEqual([s.id for s in self.opener.opened], ["ses_orc"])
        self.assertIsNone(self.app.pending_open)

    def test_an_opener_that_cannot_start_opencode_gives_a_toast_not_a_crash(self):
        self.app = self.make_app(opener=FailingOpener())
        self.press("o")
        self.app.open_pending()
        self.assertIn("could not start opencode", frame_text(self.app))

    def test_tab_shows_the_clock_enter_the_trace_and_escape_goes_back(self):
        self.press(TAB)
        self.assertIn("24 H CLOCK", frame_text(self.app))
        self.press(TAB)
        self.assertEqual(self.app.view, "sky")
        self.press(ENTER)
        text = frame_text(self.app)
        self.assertIn("you: Run the hunt", text)
        self.assertNotIn("here ~/bug-hunts", text)
        self.press(ESC)
        self.assertEqual(self.app.view, "sky")
        self.assertIn("here ~/bug-hunts", frame_text(self.app))

    def test_the_help_box_lists_every_key_and_any_key_closes_it_without_quitting(self):
        self.press("?")
        text = frame_text(self.app)
        for key, value in STRINGS["en"].items():
            if key.startswith("help."):
                self.assertIn(value, text, key)
        self.assertTrue(self.app.key("q"))
        self.assertNotIn(STRINGS["en"]["help.close"], frame_text(self.app))
        self.assertFalse(self.app.key("q"))

    def test_the_selection_only_ever_lands_on_sessions_in_row_order(self):
        for history in (False, True):
            if history:
                self.press("a")
            self.app.sel = 0
            ids = [s.id for s in self.app.snapshot.rows]
            visited = [self.app.selected.id]
            for _ in range(len(ids) - 1):
                self.press("j")
                visited.append(self.app.selected.id)
            self.assertEqual(visited, ids)
            self.press("j")
            self.assertEqual(self.app.selected.id, ids[-1])

    def test_256_colours_never_emit_24_bit_sequences(self):
        raw = self.make_app(colors="256").frame(140, 40)
        self.assertIn("38;5;", raw)
        self.assertNotIn("38;2;", raw)

    def test_the_selection_follows_its_session_when_the_rows_change(self):
        self.press("j", "j")
        chosen = self.app.selected.id
        self.press("a")
        self.assertEqual(self.app.selected.id, chosen)
        self.press("a")
        self.assertEqual(self.app.selected.id, chosen)

    def test_the_selected_row_stays_on_screen_when_the_list_is_longer_than_the_window(self):
        self.press("a", PGDN, PGDN, PGDN)
        last = self.app.snapshot.rows[-1]
        self.assertEqual(self.app.selected.id, last.id)
        text = frame_text(self.app, 140, 16)
        self.assertIn(last.title, "\n".join(left(text)))

    def test_the_range_and_theme_keys_confirm_and_the_theme_is_saved(self):
        self.press("r")
        self.assertIn("range: 7d", frame_text(self.app))
        self.press("t")
        self.assertEqual(self.prefs.prefs["theme"], "light")
        self.assertIn("48;2;239;241;245", self.app.frame(140, 40))  # Latte base
        self.press("t")
        self.assertEqual(self.prefs.prefs["theme"], "dark")


def tool_part(command: str) -> dict:
    return {"type": "tool", "name": "bash", "state": {"status": "completed", "input": {"command": command}}}


def make_in_memory_app(sessions, messages=None, here: str = DEMO_HERE) -> App:
    clock = FixedClock(NOW)
    store = InMemorySessions(sessions, messages)
    observatory = Observatory(store, FixedProcesses([]), clock, DEMO_HOME, here)
    app = App(observatory, clock, RecordingOpener(), RecordingClipboard(), MemoryPreferences(),
              Options(instant=True), DEMO_HOME)
    app.refresh(force=True)
    return app


class PolishTest(DemoFixture):
    """The small decisions about what the frame shows once and what it leaves out."""

    def test_footer_hints_have_a_plain_gap_between_the_key_chip_and_its_label(self):
        footer = frame_text(self.app).splitlines()[-1]
        self.assertIn(" ?  help   ⏎  trace", footer)  # chip, one plain space, label, two spaces, next chip
        cv = self.app.canvas(140, 40)
        y, x = cv.h - 1, cv.ch[cv.h - 1].index("?")
        th = self.app.theme
        self.assertEqual([cv.bg[y][x + i] for i in (-1, 0, 1)], [th.lavender] * 3)  # the chip is ` ? `
        self.assertEqual(cv.bg[y][x + 2], th.mantle)  # the gap is normal background
        self.assertEqual((cv.ch[y][x + 3], cv.bg[y][x + 3]), ("h", th.mantle))

    def test_the_starfield_leaves_the_two_leftmost_columns_and_header_rows_alone(self):
        th = Theme(MOCHA)
        for tick in range(0, 80):
            cv = Canvas(80, 6, th.base, th.text)
            starfield(cv, th, 0, 0, 80, 6, tick * 0.37, skip_rows=(1, 4), left_gap=2)
            for y in range(6):
                self.assertEqual(cv.ch[y][:2], [" ", " "])
            self.assertEqual((cv.ch[1], cv.ch[4]), ([" "] * 80, [" "] * 80))
        stars = 0
        for tick in range(0, 80):  # the rule is not vacuous: stars do appear elsewhere
            cv = Canvas(80, 6, th.base, th.text)
            starfield(cv, th, 0, 0, 80, 6, tick * 0.37, skip_rows=(1, 4), left_gap=2)
            stars += sum(ch != " " for row in cv.ch for ch in row)
        self.assertGreater(stars, 0)

    def test_the_sky_has_no_star_before_a_group_header_in_any_frame(self):
        for tick in range(0, 40_000, 1_900):
            self.clock.now = NOW + tick
            self.app.refresh(force=True)
            lines = frame_text(self.app, 140, 40).splitlines()
            for line in lines[:-1]:
                head = line[:LIST_W]
                if head.lstrip().startswith(("here ", "~/", "…/")):
                    self.assertEqual(head[:2], "  ", head)
                    self.assertNotRegex(head, r"[·.✦✧*⋆]\s*(here|~/|…/)")

    def test_nothing_in_the_list_touches_the_focus_separator(self):
        for tick in range(0, 40_000, 3_700):
            self.clock.now = NOW + tick
            self.app.refresh(force=True)
            lines = frame_text(self.app).splitlines()
            for line in lines[1:-1]:
                self.assertEqual(line[LIST_W], "│", line)

    def test_the_starfield_never_draws_on_the_selected_row(self):
        th = Theme(MOCHA)
        for tick in range(0, 60):
            cv = Canvas(80, 5, th.base, th.text)
            cv.fill(0, 2, 80, 1, th.surface0)
            starfield(cv, th, 0, 0, 80, 5, tick * 0.37)
            self.assertEqual(cv.ch[2], [" "] * 80)
        row = next(i for i, line in enumerate(left(frame_text(self.app))) if line.startswith("▌ ● "))
        cv = self.app.canvas(140, 40)
        self.assertTrue(all(cv.bg[row][x] == th.surface0 for x in range(LIST_W)))

    def test_a_selected_finished_session_without_activity_has_no_second_line(self):
        from ocsky.adapters.driving.tui.views.sky import build_lines

        app = make_in_memory_app([
            make_session("a", title="Finished alone", directory=DEMO_HERE, busy=NOW - 9000, idle=NOW - 5000,
                         outcome="succeeded", updated=NOW - 5000)])
        app.only_active = False  # history, so the finished session is listed
        app.refresh(force=True)
        selected = app.snapshot.rows[app.sel]
        self.assertFalse(selected.working)
        self.assertIsNone(selected.activity)
        self.assertEqual([line.kind for line in build_lines(app)], ["group", "session"])
        shown = [line for line in left(frame_text(app)) if "Finished alone" in line]
        self.assertEqual(len(shown), 1)

    def test_only_the_exact_start_directory_is_labelled_here(self):
        below = DEMO_HERE + "/pkg"
        app = make_in_memory_app([
            make_session("a", title="At home", directory=DEMO_HERE, busy=NOW - 1000, updated=NOW - 1000),
            make_session("b", title="Below it", directory=below, busy=NOW - 2000, updated=NOW - 2000),
        ])
        lines = left(frame_text(app))
        labelled = [line for line in lines if "here" in line]
        self.assertEqual(len(labelled), 1)
        self.assertIn("here ~/bug-hunts/acme-parser/repo", labelled[0])
        self.assertNotIn("pkg", labelled[0])
        headers = [line for line in lines if line.startswith("  ~/") or line.startswith("  here")]
        self.assertEqual(len(headers), 2)
        self.assertIn("~/…/acme-parser/repo/pkg", headers[1])

    def test_starting_in_the_home_directory_labels_only_the_home_group(self):
        app = make_in_memory_app([
            make_session("a", title="In home", directory=DEMO_HOME, busy=NOW - 1000, updated=NOW - 1000),
            make_session("b", title="In a project", directory=DEMO_HOME + "/dev/x", busy=NOW - 2000,
                         updated=NOW - 2000),
        ], here=DEMO_HOME + "/")
        text = "\n".join(left(frame_text(app)))
        self.assertEqual(text.count("here "), 1)
        self.assertIn("here ~", text)

    def test_a_long_group_path_shows_its_last_three_components(self):
        deep = "/tmp/x/0a1b2c3d-0000-4000-8000-123456789abc/scratchpad/ocsky-demo"
        app = make_in_memory_app([make_session("a", title="Deep", directory=deep, busy=NOW - 1000,
                                               updated=NOW - 1000)])
        text = frame_text(app)
        self.assertIn("…/0a1b2c3d-0000-4000-8000-123456789abc/scratchpad/ocsky-demo", text)
        self.assertNotIn("/tmp/x", text)

    def test_identical_consecutive_steps_are_one_line_with_the_last_time_and_a_count(self):
        msgs = {"a": [assistant_message(NOW - 60_000 + i * 1000, [tool_part("make test")]) for i in range(5)]
                + [assistant_message(NOW - 10_000, [tool_part("make lint")]),
                   assistant_message(NOW - 5_000, [tool_part("make lint")])]}
        app = make_in_memory_app([make_session("a", title="Looper", directory=DEMO_HERE, busy=NOW - 90_000,
                                               updated=NOW - 1000)], msgs)
        lines = [ln[LIST_W:] for ln in frame_text(app).splitlines()]
        steps = [ln for ln in lines if "make " in ln]
        self.assertEqual(len(steps), 2)
        self.assertIn("make test ×5", steps[0])
        self.assertIn("make lint ×2", steps[1])
        self.assertNotIn("×", "".join(ln for ln in lines if "×" in ln and "make" not in ln))
        self.assertIn(clock_text(NOW - 56_000, "%H:%M:%S"), steps[0])  # the time of the last one
        app.key(ENTER)
        trace = [ln for ln in frame_text(app).splitlines() if "make " in ln]
        self.assertEqual(len(trace), 2)
        self.assertIn("make test ×5", trace[0])

    def test_a_single_step_has_no_count(self):
        text = frame_text(self.app)
        self.assertNotRegex(text, r"escape ×")
        self.assertIn("hunt.py loop --run demo ×12", text)

    def test_the_help_box_fits_in_two_columns_on_a_short_terminal(self):
        self.press("?")
        for rows in (14, 16, 18):
            text = frame_text(self.app, 130, rows)
            for key, value in STRINGS["en"].items():
                if key.startswith("help."):
                    self.assertIn(value, text, (rows, key))
            self.assertEqual(len(text.splitlines()), rows)
        tall = frame_text(self.app, 130, 19)
        for key, value in STRINGS["en"].items():
            if key.startswith("help."):
                self.assertIn(value, tall, key)


    def _help_cut(self, lang: str, cols: int, rows: int) -> List[str]:
        """Descriptions that do not appear whole in the help box of a cols x rows screen."""
        self.app.tr = Tr(lang)
        text = frame_text(self.app, cols, rows)
        self.assertEqual(len(text.splitlines()), rows)
        self.assertTrue(all(len(line) <= cols for line in text.splitlines()))
        return [k for k, v in STRINGS[lang].items() if k.startswith("help.") and k != "help.title"
                and v not in text]

    def test_the_help_box_never_cuts_a_description_when_some_layout_can_avoid_it(self):
        self.press("?")
        for lang in ("en", "es"):
            self.assertEqual(self._help_cut(lang, 80, 24), [], lang)  # one column
            self.assertEqual(self._help_cut(lang, 130, 16), [], lang)  # two columns
        text = frame_text(self.app, 80, 24)
        self.assertEqual(sum(1 for line in text.splitlines() if "PgUp PgDn" in line), 1)  # one column

    def test_the_help_box_on_a_small_screen_stays_inside_it(self):
        self.press("?")
        for lang in ("en", "es"):
            self._help_cut(lang, 80, 16)  # checks the line count and that no line is wider than the screen
        self.assertIn("PgUp PgDn", frame_text(self.app, 80, 16))


class DelegationTest(DemoFixture):
    def test_a_parent_waiting_on_its_subagents_says_how_many_instead_of_naming_one(self):
        column = "\n".join(left(frame_text(self.app)))
        self.assertIn("waiting on 2 subagents", column)
        # The subagent it launched last is listed right below, so the call is not repeated.
        self.assertNotIn("task Hunter H-004", column)

    def test_the_count_is_translated(self):
        self.app.key("L")
        self.assertIn("esperando a 2 subagentes", "\n".join(left(frame_text(self.app))))


class PulseTrackTest(DemoFixture):
    def tracks(self):
        """(row text, column where its pulse track starts) of every working row."""
        cv = self.app.canvas(140, 40)
        blocks = set("▁▂▃▄▅▆▇█")
        found = []
        for y in range(cv.h):
            row = "".join(cv.ch[y][:83])
            start = next((x for x in range(len(row) - PULSE_BUCKETS + 1)
                          if set(row[x:x + PULSE_BUCKETS]) <= blocks), None)
            if start is not None:
                found.append((row, start))
        return found

    def test_every_working_row_has_a_full_track_starting_at_the_same_column(self):
        tracks = self.tracks()
        self.assertEqual(len(tracks), 5)  # the two roots and their three subagents
        self.assertEqual(len({start for _, start in tracks}), 1)

    def test_quiet_buckets_draw_a_baseline_and_busy_ones_a_taller_block(self):
        row, start = self.tracks()[0]
        track = row[start:start + PULSE_BUCKETS]
        self.assertIn("▁", track)
        self.assertTrue(set(track) - {"▁"})

    def test_bars_share_one_scale_so_a_quieter_session_is_lower(self):
        quiet = make_session("q", pulse=[0] * (PULSE_BUCKETS - 1) + [100])
        busy = make_session("b", pulse=[0] * (PULSE_BUCKETS - 1) + [1600])
        quiet.state = busy.state = "working"
        top = pulse_top([quiet, busy])
        self.assertEqual(sparkline(busy, top)[-1], 8)
        self.assertEqual(sparkline(quiet, top)[-1], 2)
        self.assertEqual(sparkline(quiet, top)[0], 0)


class StoreFailureTest(unittest.TestCase):
    def test_the_last_rows_stay_on_screen_with_the_error_when_the_store_goes_away(self):
        store = InMemorySessions([make_session("a", title="Alpha session", directory=DEMO_HERE,
                                               busy=NOW - 1000, updated=NOW - 1000)])
        clock = FixedClock(NOW)
        observatory = Observatory(store, FixedProcesses([]), clock, DEMO_HOME, DEMO_HERE)
        app = App(observatory, clock, RecordingOpener(), RecordingClipboard(), MemoryPreferences(),
                  Options(instant=True), DEMO_HOME)
        app.refresh(force=True)
        self.assertIn("Alpha session", frame_text(app))
        store.fail = True
        app.refresh(force=True)
        text = frame_text(app)
        self.assertIn("Alpha session", text)
        self.assertIn("cannot read the opencode database", text)

    def test_an_empty_range_says_so_and_points_at_the_history(self):
        store = InMemorySessions([])
        clock = FixedClock(NOW)
        observatory = Observatory(store, FixedProcesses([]), clock, DEMO_HOME, DEMO_HERE)
        app = App(observatory, clock, RecordingOpener(), RecordingClipboard(), MemoryPreferences(),
                  Options(instant=True), DEMO_HOME)
        app.refresh(force=True)
        text = frame_text(app)
        self.assertIn("All quiet. No agent is working.", text)
        self.assertIn("a shows the history", text)
        self.assertIn("all quiet", text.splitlines()[0])


if __name__ == "__main__":
    unittest.main()
