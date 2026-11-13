"""The SQLite adapter against a real database file: queries, the read-only guarantee, recovery, paths."""
from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
import unittest

from tests import helpers  # noqa: F401
from ocsky.adapters.driven.demo_database import DEMO_HERE, DEMO_HOME, build_demo_db
from ocsky.adapters.driven.sqlite_sessions import SqliteSessions, default_db, parse_model
from ocsky.core.model import STALLED
from ocsky.core.observatory import Observatory
from ocsky.core.ports.for_reading_sessions import StoreUnavailable
from tests.doubles import FixedClock, FixedProcesses

NOW = 1_800_000_000_000
MIN = 60_000
DAY = 86_400_000
DEMO_SESSIONS = 11


class SqliteSessionsTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)  # LIFO: runs after the stores close
        self.db = os.path.join(self.dir, "opencode.db")
        build_demo_db(self.db, NOW)

    def store(self, path=None) -> SqliteSessions:
        """A store that is closed before the directory goes: Windows cannot delete an open file."""
        store = SqliteSessions(path or self.db)
        self.addCleanup(store.close)
        return store

    def test_sessions_come_back_with_their_fields_and_parsed_models(self):
        got = {s.id: s for s in self.store().sessions(NOW - DAY, NOW)}
        self.assertEqual(len(got), DEMO_SESSIONS)
        orc = got["ses_orc"]
        self.assertEqual((orc.slug, orc.title, orc.agent),
                         ("brave-orbit", "Hunt acme/parser: logic, security", "bh-orchestrator"))
        self.assertEqual((orc.model, orc.directory), ("deepseek/deepseek-flash", DEMO_HERE))
        self.assertEqual((orc.tokens_in, orc.tokens_out, orc.cost), (412_000, 38_000, 0.31))
        self.assertIsNone(orc.parent)
        self.assertEqual(orc.busy, NOW - 42 * MIN)
        self.assertEqual(got["ses_h1"].parent, "ses_orc")
        self.assertEqual(got["ses_h1"].model, "opencode/deepseek-v4.1-flash-free")
        self.assertEqual(got["ses_h3"].outcome, "succeeded")
        self.assertEqual(got["ses_shop"].model, "anthropic/claude-sonnet-5-5")

    def test_a_busy_session_older_than_the_range_is_kept_for_a_week(self):
        ids = {s.id for s in self.store().sessions(NOW - 10 * MIN, NOW)}
        self.assertIn("ses_old", ids)  # busy, last updated 25 minutes ago
        self.assertNotIn("ses_done", ids)  # finished, and its busy window closed before the range
        self.assertNotIn("ses_fail", ids)

    def test_messages_are_the_newest_decoded_ones_oldest_first(self):
        msgs = self.store().messages("ses_orc", 3)
        self.assertEqual([m.time for m in msgs], [NOW - 50_000, NOW - 30_000, NOW - 5_000])
        self.assertEqual({m.type for m in msgs}, {"assistant"})
        self.assertEqual(msgs[-1].data["content"][0]["type"], "reasoning")

    def test_messages_whose_json_does_not_decode_or_is_not_an_object_are_skipped(self):
        with sqlite3.connect(self.db) as rw:
            rw.execute("insert into session_message values ('bad1','ses_orc','assistant',900,?,'not json')",
                       (NOW - 1_000,))
            rw.execute("insert into session_message values ('bad2','ses_orc','assistant',901,?,'[1, 2]')",
                       (NOW - 900,))
        msgs = self.store().messages("ses_orc", 3)
        # The limit counts rows before decoding, so the two bad rows use up the window.
        self.assertEqual([m.time for m in msgs], [NOW - 5_000])

    def test_pulse_sums_output_and_reasoning_tokens_of_assistant_messages(self):
        rows = self.store().pulse(["ses_orc", "ses_h1"], NOW - 14 * MIN)
        self.assertIn(("ses_orc", NOW - 5_000, 1350), rows)  # 900 output + 450 reasoning
        self.assertIn(("ses_h1", NOW - 3_000, 2100), rows)  # 1400 output + 700 reasoning
        self.assertEqual(self.store().pulse([], 0), [])

    def test_pulse_skips_rows_whose_json_is_broken_instead_of_failing(self):
        with sqlite3.connect(self.db) as rw:
            rw.execute("insert into session_message values ('bad1','ses_orc','assistant',900,?,'{broken')",
                       (NOW - 1_000,))
        rows = self.store().pulse(["ses_orc"], NOW - 14 * MIN)
        self.assertEqual(len([r for r in rows if r[0] == "ses_orc"]), 13)

    def test_the_connection_refuses_writes(self):
        with self.assertRaises(sqlite3.OperationalError):
            self.store().conn().execute("delete from session_v2")

    def test_reading_never_changes_the_file_bytes(self):
        with open(self.db, "rb") as f:
            before = f.read()
        store = self.store()
        store.sessions(0, NOW)
        store.messages("ses_orc", 50)
        store.pulse(["ses_orc"], 0)
        with open(self.db, "rb") as f:
            self.assertEqual(f.read(), before)

    def test_a_missing_file_is_unavailable_until_it_appears(self):
        absent = os.path.join(self.dir, "later.db")
        store = self.store(absent)
        with self.assertRaises(StoreUnavailable):
            store.sessions(0, NOW)
        with self.assertRaises(StoreUnavailable):
            store.messages("ses_orc", 1)
        build_demo_db(absent, NOW)
        self.assertEqual(len(store.sessions(0, NOW)), DEMO_SESSIONS)

    def test_a_path_with_spaces_and_a_hash_opens(self):
        folder = os.path.join(self.dir, "my data")
        os.makedirs(folder)
        path = os.path.join(folder, "opencode #1.db")
        build_demo_db(path, NOW)
        self.assertEqual(len(self.store(path).sessions(0, NOW)), DEMO_SESSIONS)

    @unittest.skipIf(os.name == "nt", "? is not a legal file name character on Windows")
    def test_a_path_with_a_question_mark_opens(self):
        path = os.path.join(self.dir, "what?.db")
        build_demo_db(path, NOW)
        self.assertEqual(len(self.store(path).sessions(0, NOW)), DEMO_SESSIONS)

    def test_close_releases_the_file_is_idempotent_and_a_later_query_reopens(self):
        store = self.store()
        store.sessions(0, NOW)
        store.close()
        store.close()
        self.assertEqual(len(store.sessions(0, NOW)), DEMO_SESSIONS)

    def test_default_db_on_windows_takes_the_first_candidate_that_exists(self):
        env = {"XDG_DATA_HOME": r"C:\xdg", "LOCALAPPDATA": r"C:\local", "APPDATA": r"C:\roaming"}
        db = os.path.join("opencode", "opencode.db")
        xdg, local, roaming = (os.path.join(env[k], db) for k in ("XDG_DATA_HOME", "LOCALAPPDATA", "APPDATA"))
        fallback = os.path.join("C:\\u", ".local", "share", db)
        for present, expected in (({xdg, local}, xdg), ({local, roaming}, local), ({roaming}, roaming),
                                  ({fallback}, fallback), (set(), fallback)):
            self.assertEqual(default_db(env, "C:\\u", "win32", present.__contains__), expected)
        only_local = {"LOCALAPPDATA": r"C:\local"}
        self.assertEqual(default_db(only_local, "C:\\u", "win32", lambda p: p == local), local)

    def test_default_db_off_windows_ignores_the_windows_directories_and_never_checks_the_disk(self):
        env = {"LOCALAPPDATA": r"C:\local", "APPDATA": r"C:\roaming"}
        got = default_db(env, "/home/u", "darwin", lambda p: self.fail("must not look at the disk"))
        self.assertEqual(got, os.path.join("/home/u", ".local", "share", "opencode", "opencode.db"))

    def test_default_db_follows_xdg_data_home(self):
        self.assertEqual(default_db({"XDG_DATA_HOME": "/data"}, "/home/u"),
                         os.path.join("/data", "opencode", "opencode.db"))
        self.assertEqual(default_db({}, "/home/u"),
                         os.path.join("/home/u", ".local", "share", "opencode", "opencode.db"))

    def test_parse_model_handles_empty_json_and_plain_text(self):
        self.assertEqual(parse_model(None), "")
        self.assertEqual(parse_model(""), "")
        self.assertEqual(parse_model('{"id": "m", "providerID": "p"}'), "p/m")
        self.assertEqual(parse_model("plain-text"), "plain-text")
        self.assertEqual(parse_model("5"), "5")

    def test_the_observatory_orders_the_hunt_and_folds_the_finished_hunters(self):
        obs = Observatory(self.store(), FixedProcesses([]), FixedClock(NOW), DEMO_HOME, DEMO_HERE)
        snap = obs.observe(DAY, True, set())
        ids = [s.id for s in snap.rows]
        self.assertEqual(ids[:3], ["ses_orc", "ses_h1", "ses_h2"])
        orc = snap.rows[0]
        self.assertEqual(orc.hidden_children, 2)
        self.assertTrue(orc.here)
        self.assertLess(ids.index("ses_h2"), ids.index("ses_shop"))  # the here group comes first
        self.assertEqual(ids[ids.index("ses_shop") + 1], "ses_explore")
        for gone in ("ses_old", "ses_done", "ses_fail", "ses_shop_old", "ses_h3", "ses_h4"):
            self.assertNotIn(gone, ids)
        states = {s.id: s.state for s in snap.sessions}
        self.assertEqual(states["ses_old"], STALLED)
        self.assertEqual(states["ses_fail"], "failed")
        self.assertEqual(states["ses_shop_old"], "interrupted")
        self.assertEqual(states["ses_h3"], "done")

    def test_without_only_active_the_history_appears(self):
        obs = Observatory(self.store(), FixedProcesses([]), FixedClock(NOW), DEMO_HOME, DEMO_HERE)
        ids = [s.id for s in obs.observe(DAY, False, set()).rows]
        for shown in ("ses_old", "ses_done", "ses_fail", "ses_shop_old"):
            self.assertIn(shown, ids)
        self.assertNotIn("ses_h3", ids)  # finished subagents stay folded until expanded


if __name__ == "__main__":
    unittest.main()
