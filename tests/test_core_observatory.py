"""The observatory use case, end to end through the in-memory doubles."""
from __future__ import annotations

import unittest

from tests import helpers  # noqa: F401
from ocsky.core.model import DONE, STALLED, Activity, Proc
from ocsky.core.observatory import PULSE_BUCKETS, PULSE_WINDOW_MS, STORE_UNAVAILABLE, Observatory
from ocsky.core.states import STALL_MS
from tests.doubles import (
    FixedClock,
    FixedProcesses,
    InMemorySessions,
    assistant_message,
    idle_message,
    make_session,
    user_message,
)

NOW = 1_000_000_000
HOME = "/home/ana"
HERE = "/work/app"
DAY_MS = 86_400_000
WINDOW_START = NOW - PULSE_WINDOW_MS


def working(sid: str, **overrides):
    values = dict(busy=NOW - 5_000, updated=NOW - 1_000, directory=HERE)
    values.update(overrides)
    return make_session(sid, **values)


def finished(sid: str, **overrides):
    values = dict(busy=1_000, idle=2_000, outcome="stop", updated=NOW - 1_000, directory=HERE)
    values.update(overrides)
    return make_session(sid, **values)


def build(sessions, messages=None, procs=()):
    store = InMemorySessions(sessions, messages or {})
    obs = Observatory(store, FixedProcesses(list(procs)), FixedClock(NOW), HOME, HERE)
    return obs, store


def ids(rows) -> list[str]:
    return [r.id for r in rows]


def bash(command: str, status: str = "completed") -> dict:
    return {"type": "tool", "name": "bash", "state": {"status": status, "input": {"command": command}}}


class PulseTest(unittest.TestCase):
    def test_the_output_and_reasoning_tokens_fall_into_the_buckets_of_the_window(self):
        messages = {"a": [
            assistant_message(WINDOW_START - 5, [], output=99),  # outside the window
            assistant_message(WINDOW_START + 1, [], output=3, reasoning=2),  # bucket 0
            assistant_message(NOW - PULSE_WINDOW_MS // 2 + 1, [], output=10),  # the middle bucket
            assistant_message(NOW - 1_000, [{"type": "text", "text": "ok"}], output=1),  # the last bucket
        ]}
        obs, _ = build([working("a")], messages)
        snap = obs.observe(DAY_MS, False, set())
        pulse = snap.sessions[0].pulse
        self.assertEqual(len(pulse), PULSE_BUCKETS)
        expected = [0] * PULSE_BUCKETS
        expected[0], expected[PULSE_BUCKETS // 2], expected[-1] = 5, 10, 1
        self.assertEqual(pulse, expected)


class ActivityTest(unittest.TestCase):
    def test_a_working_session_shows_its_last_tool_call_and_its_last_thought(self):
        messages = {"w": [assistant_message(NOW - 3_000, [
            {"type": "reasoning", "text": "Checking the tokenizer"},
            bash("pytest -q", status="running"),
        ])]}
        obs, _ = build([working("w")], messages)
        s = obs.observe(DAY_MS, False, set()).sessions[0]
        self.assertEqual(s.activity, Activity("tool", tool="bash", detail="pytest -q", status="running"))
        self.assertEqual(s.thought, "Checking the tokenizer")

    def test_the_thought_is_the_last_reasoning_part_of_the_last_message(self):
        messages = {"w": [assistant_message(NOW - 3_000, [
            {"type": "reasoning", "text": "first thought"},
            {"type": "reasoning", "text": "second  thought\n"},
        ])]}
        obs, _ = build([working("w")], messages)
        s = obs.observe(DAY_MS, False, set()).sessions[0]
        self.assertEqual(s.thought, "second thought")
        self.assertEqual(s.activity, Activity("reasoning", detail="second thought"))

    def test_a_user_message_is_the_activity_of_a_working_session(self):
        messages = {"w": [user_message(NOW - 3_000, "fix\nthe  parser")]}
        obs, _ = build([working("w")], messages)
        s = obs.observe(DAY_MS, False, set()).sessions[0]
        self.assertEqual(s.activity, Activity("user", detail="fix the parser"))

    def test_a_stalled_session_shows_its_idle_outcome_as_activity(self):
        messages = {"s": [idle_message(NOW - 3_000, "error")]}
        stalled = working("s", updated=NOW - STALL_MS - 5_000)
        obs, _ = build([stalled], messages)
        s = obs.observe(DAY_MS, False, set()).sessions[0]
        self.assertEqual(s.state, STALLED)
        self.assertEqual(s.activity, Activity("idle", outcome="error"))

    def test_a_finished_session_gets_no_activity_even_when_it_has_messages(self):
        messages = {"d": [assistant_message(NOW - 3_000, [{"type": "text", "text": "bye"}])]}
        obs, _ = build([finished("d")], messages)
        s = obs.observe(DAY_MS, False, set()).sessions[0]
        self.assertEqual(s.state, DONE)
        self.assertIsNone(s.activity)


class SnapshotTest(unittest.TestCase):
    def test_the_models_of_the_snapshot_are_ordered_by_tokens(self):
        sessions = [
            finished("a", model="x/a", tokens_in=100, tokens_out=100),
            finished("b", model="y/b", tokens_in=50, tokens_out=10),
            finished("c", model="z/c", tokens_in=150),
        ]
        obs, _ = build(sessions)
        snap = obs.observe(DAY_MS, False, set())
        self.assertEqual([m.model for m in snap.models], ["x/a", "z/c", "y/b"])

    def test_a_session_in_the_directory_ocsky_runs_in_is_marked_here(self):
        obs, _ = build([working("w", directory=HERE + "/sub"), working("x", directory="/elsewhere")])
        snap = obs.observe(DAY_MS, False, set())
        flags = {s.id: s.here for s in snap.sessions}
        self.assertEqual(flags, {"w": True, "x": False})

    def test_only_active_hides_the_finished_sessions_from_the_rows(self):
        obs, _ = build([working("w"), finished("d")])
        snap = obs.observe(DAY_MS, True, set())
        self.assertEqual(ids(snap.rows), ["w"])
        self.assertEqual(ids(snap.sessions), ["w", "d"])

    def test_the_expanded_set_decides_whether_finished_subagents_are_listed(self):
        parent = working("p")
        child = finished("c", parent="p")
        obs, _ = build([parent, child])
        self.assertEqual(ids(obs.observe(DAY_MS, False, set()).rows), ["p"])
        self.assertEqual(ids(obs.observe(DAY_MS, False, {"p"}).rows), ["p", "c"])

    def test_the_processes_come_back_in_the_snapshot(self):
        proc = Proc(pid=7, mode="tui", cwd=HERE, started=1.0, rss_mb=50.0)
        obs, _ = build([working("w")], procs=[proc])
        self.assertEqual(obs.observe(DAY_MS, False, set()).procs, [proc])


class StoreFailureTest(unittest.TestCase):
    def test_when_the_store_fails_before_any_snapshot_the_result_is_empty_with_the_error(self):
        obs, store = build([working("w")])
        store.fail = True
        snap = obs.observe(DAY_MS, False, set())
        self.assertEqual(snap.error, STORE_UNAVAILABLE)
        self.assertNotEqual(snap.error_detail, "")
        self.assertEqual((snap.sessions, snap.rows, snap.models), ([], [], []))

    def test_when_the_store_fails_after_a_snapshot_the_previous_rows_come_back_with_the_error(self):
        obs, store = build([working("w"), finished("d")])
        before = obs.observe(DAY_MS, False, set())
        store.fail = True
        after = obs.observe(DAY_MS, False, set())
        self.assertEqual(after.error, STORE_UNAVAILABLE)
        self.assertEqual(ids(after.rows), ids(before.rows))
        self.assertEqual(ids(after.sessions), ids(before.sessions))

    def test_the_error_clears_when_the_store_comes_back(self):
        obs, store = build([working("w")])
        obs.observe(DAY_MS, False, set())
        store.fail = True
        obs.observe(DAY_MS, False, set())
        store.fail = False
        self.assertEqual(obs.observe(DAY_MS, False, set()).error, "")


class TraceTest(unittest.TestCase):
    def setUp(self):
        self.session = working("w")
        self.messages = {"w": [
            user_message(1, "run the tests"),
            assistant_message(2, [bash("pytest -q")]),
            idle_message(3, "stop"),
        ]}

    def test_a_trace_lists_the_steps_of_a_session_oldest_first(self):
        obs, _ = build([self.session], self.messages)
        steps = obs.trace(self.session)
        self.assertEqual([s.time for s in steps], [1, 2, 3])
        self.assertEqual([s.activity.kind for s in steps], ["user", "tool", "idle"])
        self.assertEqual(steps[0].activity.detail, "run the tests")
        self.assertEqual(steps[1].activity.detail, "pytest -q")

    def test_a_trace_keeps_only_the_newest_steps_up_to_the_limit(self):
        obs, _ = build([self.session], self.messages)
        steps = obs.trace(self.session, limit=2)
        self.assertEqual([s.activity.kind for s in steps], ["tool", "idle"])

    def test_when_the_store_fails_the_trace_read_last_time_comes_back(self):
        obs, store = build([self.session], self.messages)
        first = obs.trace(self.session)
        store.fail = True
        again = obs.trace(self.session)
        self.assertEqual([s.time for s in again], [s.time for s in first])

    def test_when_the_store_fails_and_nothing_was_read_the_trace_is_empty(self):
        obs, store = build([self.session], self.messages)
        store.fail = True
        self.assertEqual(obs.trace(self.session), [])


if __name__ == "__main__":
    unittest.main()
