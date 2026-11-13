"""Every state that classify can give a session, and the rules that choose between them."""
from __future__ import annotations

import unittest

from tests import helpers  # noqa: F401
from ocsky.core.model import (
    COMPACTING,
    DONE,
    FAILED,
    INTERRUPTED,
    STALLED,
    SUSPENDED,
    WAITING,
    WORKING,
    Proc,
)
from ocsky.core.states import STALL_MS, classify
from tests.doubles import make_session

NOW = 10_000_000
RECENT = NOW - 1_000
PROJECT = "/work/app"


def proc(mode: str = "tui", cwd: str = PROJECT) -> Proc:
    return Proc(pid=1, mode=mode, cwd=cwd, started=0.0, rss_mb=1.0)


def state_of(session, procs=(), newer=()) -> str:
    """Classifies the session, after the sessions in `newer` (which are newer, so listed first)."""
    classify([*newer, session], list(procs), NOW)
    return session.state


class StateTest(unittest.TestCase):
    def test_a_busy_session_with_recent_progress_is_working(self):
        s = make_session("a", busy=RECENT - 500, updated=RECENT)
        self.assertEqual(state_of(s), WORKING)

    def test_a_busy_session_that_is_compacting_is_compacting(self):
        s = make_session("a", busy=NOW - 5_000, compacting=NOW - 4_000, updated=RECENT)
        self.assertEqual(state_of(s), COMPACTING)

    def test_a_busy_session_without_progress_for_longer_than_the_stall_limit_is_stalled(self):
        s = make_session("a", busy=NOW - 5_000, updated=NOW - STALL_MS - 1)
        self.assertEqual(state_of(s), STALLED)

    def test_a_busy_session_exactly_at_the_stall_limit_is_still_working(self):
        s = make_session("a", busy=NOW - 5_000, updated=NOW - STALL_MS)
        self.assertEqual(state_of(s), WORKING)

    def test_a_session_idle_after_it_became_busy_is_not_busy_any_more(self):
        s = make_session("a", busy=1_000, idle=2_000, outcome="stop", updated=RECENT)
        self.assertEqual(state_of(s), DONE)

    def test_a_suspended_session_that_is_not_busy_is_suspended(self):
        s = make_session("a", busy=1_000, idle=2_000, suspended=NOW - 100, updated=RECENT)
        self.assertEqual(state_of(s), SUSPENDED)

    def test_busy_wins_over_a_fresh_suspension(self):
        s = make_session("a", busy=NOW - 5_000, suspended=NOW - 100, updated=RECENT)
        self.assertEqual(state_of(s), WORKING)

    def test_a_root_session_in_a_directory_with_a_live_process_is_waiting(self):
        s = make_session("a", busy=1_000, idle=2_000, outcome="stop", updated=RECENT)
        self.assertEqual(state_of(s, procs=[proc()]), WAITING)

    def test_only_the_newest_root_session_of_a_directory_is_waiting(self):
        newest = make_session("new", busy=1_000, idle=2_000, outcome="stop", updated=5_000)
        older = make_session("old", busy=1_000, idle=2_000, outcome="stop", updated=4_000)
        classify([newest, older], [proc()], NOW)
        self.assertEqual((newest.state, older.state), (WAITING, DONE))

    def test_a_subagent_is_never_waiting_even_in_a_directory_with_a_live_process(self):
        sub = make_session("sub", parent="root", busy=1_000, idle=2_000, outcome="stop", updated=RECENT)
        self.assertEqual(state_of(sub, procs=[proc()]), DONE)

    def test_serve_web_and_acp_processes_do_not_make_a_session_wait(self):
        for mode in ("serve", "web", "acp"):
            s = make_session("a", busy=1_000, idle=2_000, outcome="stop", updated=RECENT)
            self.assertEqual(state_of(s, procs=[proc(mode=mode)]), DONE, mode)

    def test_a_process_in_another_directory_does_not_make_a_session_wait(self):
        s = make_session("a", busy=1_000, idle=2_000, outcome="stop", updated=RECENT)
        self.assertEqual(state_of(s, procs=[proc(cwd="/elsewhere")]), DONE)

    def test_a_session_that_ended_in_failure_is_failed(self):
        s = make_session("a", busy=1_000, idle=2_000, outcome="failed", updated=RECENT)
        self.assertEqual(state_of(s), FAILED)

    def test_a_session_that_was_interrupted_is_interrupted(self):
        s = make_session("a", busy=1_000, idle=2_000, outcome="interrupted", updated=RECENT)
        self.assertEqual(state_of(s), INTERRUPTED)

    def test_a_session_that_ended_normally_is_done(self):
        s = make_session("a", busy=1_000, idle=2_000, outcome="stop", updated=RECENT)
        self.assertEqual(state_of(s), DONE)

    def test_a_session_with_no_timestamps_at_all_is_done(self):
        self.assertEqual(state_of(make_session("a")), DONE)


if __name__ == "__main__":
    unittest.main()
