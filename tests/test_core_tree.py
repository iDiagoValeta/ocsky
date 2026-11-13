"""Grouping by directory, folding subagents under their parent, row order and the model usage."""
from __future__ import annotations

import unittest

from tests import helpers  # noqa: F401
from ocsky.core.model import DONE, STALLED, WAITING, WORKING
from ocsky.core.tree import alive, build_rows, is_here, usage
from tests.doubles import make_session

HERE = "/work/app"


def ids(rows) -> list[str]:
    return [r.id for r in rows]


class IsHereTest(unittest.TestCase):
    def test_the_directory_itself_is_here(self):
        self.assertTrue(is_here("/work/app", HERE))

    def test_a_subdirectory_is_here(self):
        self.assertTrue(is_here("/work/app/src/deep", HERE))

    def test_a_sibling_that_only_shares_the_prefix_is_not_here(self):
        self.assertFalse(is_here("/work/app2", HERE))

    def test_a_parent_directory_is_not_here(self):
        self.assertFalse(is_here("/work", HERE))

    def test_windows_paths_with_backslashes_compare_by_component(self):
        here = "C:\\Users\\x\\proj"
        self.assertTrue(is_here("C:\\Users\\x\\proj", here))
        self.assertTrue(is_here("C:\\Users\\x\\proj\\src", here))
        self.assertTrue(is_here("C:/Users/x/proj/src", here))  # the two spellings meet
        self.assertFalse(is_here("C:\\Users\\x\\proj2", here))
        self.assertFalse(is_here("C:\\Users\\x", here))


class AliveTest(unittest.TestCase):
    def test_a_session_with_a_live_subagent_is_alive_even_when_it_is_done(self):
        parent = make_session("p", state=DONE)
        parent.children = [make_session("c", state=WORKING, parent="p")]
        self.assertTrue(alive(parent))

    def test_a_done_session_with_only_finished_children_is_not_alive(self):
        parent = make_session("p", state=DONE)
        parent.children = [make_session("c", state=DONE, parent="p")]
        self.assertFalse(alive(parent))


class GroupingTest(unittest.TestCase):
    def test_the_directory_ocsky_runs_in_comes_first_even_when_another_directory_is_busier(self):
        here_done = make_session("here", directory=HERE, state=DONE, updated=500)
        busy = make_session("busy", directory="/work/other", state=WORKING, updated=9_000)
        rows = build_rows([busy, here_done], HERE, False, set())
        self.assertEqual(ids(rows), ["here", "busy"])
        self.assertTrue(rows[0].here)
        self.assertFalse(rows[1].here)

    def test_groups_with_a_live_root_come_before_finished_ones_and_then_by_recency(self):
        a = make_session("a", directory="/a", state=DONE, updated=9_000)
        b = make_session("b", directory="/b", state=DONE, updated=5_000)
        c = make_session("c", directory="/c", state=WORKING, updated=100)
        rows = build_rows([a, b, c], "/nowhere", False, set())
        self.assertEqual(ids(rows), ["c", "a", "b"])

    def test_inside_a_group_live_roots_come_first_then_by_state_then_by_recency(self):
        working = make_session("working", directory="/g", state=WORKING, updated=100)
        waiting = make_session("waiting", directory="/g", state=WAITING, updated=900)
        stalled = make_session("stalled", directory="/g", state=STALLED, updated=1_000)
        done = make_session("done", directory="/g", state=DONE, updated=2_000)
        rows = build_rows([done, stalled, waiting, working], "/nowhere", False, set())
        self.assertEqual(ids(rows), ["working", "waiting", "stalled", "done"])

    def test_a_subagent_in_another_directory_stays_under_its_parent_and_starts_no_group(self):
        parent = make_session("p", directory=HERE, state=WORKING, updated=100)
        child = make_session("c", parent="p", directory="/elsewhere", state=WORKING, updated=100)
        other = make_session("q", directory="/work/zz", state=DONE, updated=50)
        rows = build_rows([other, child, parent], HERE, False, set())
        self.assertEqual(ids(rows), ["p", "c", "q"])
        self.assertEqual(rows[1].depth, 1)
        self.assertFalse(child.here)


class SubagentFoldingTest(unittest.TestCase):
    def test_a_finished_subagent_is_folded_under_its_parent(self):
        parent = make_session("p", state=WORKING, updated=100)
        child = make_session("c", parent="p", state=DONE, updated=50)
        rows = build_rows([parent, child], HERE, False, set())
        self.assertEqual(ids(rows), ["p"])
        self.assertEqual(rows[0].hidden_children, 1)

    def test_an_expanded_parent_lists_its_finished_subagents_one_level_down(self):
        parent = make_session("p", state=WORKING, updated=100)
        child = make_session("c", parent="p", state=DONE, updated=50)
        rows = build_rows([parent, child], HERE, False, {"p"})
        self.assertEqual(ids(rows), ["p", "c"])
        self.assertEqual(rows[1].depth, 1)
        self.assertEqual(rows[0].hidden_children, 0)

    def test_a_live_subagent_is_listed_under_its_parent_without_expanding(self):
        parent = make_session("p", state=WORKING, updated=100)
        child = make_session("c", parent="p", state=WORKING, updated=100)
        rows = build_rows([parent, child], HERE, False, set())
        self.assertEqual(ids(rows), ["p", "c"])
        self.assertEqual(rows[1].depth, 1)
        self.assertEqual(rows[0].hidden_children, 0)

    def test_when_expanded_live_subagents_come_first_and_each_group_is_oldest_first(self):
        parent = make_session("p", state=WORKING, updated=100)
        done = make_session("a", parent="p", state=DONE, created=100, updated=50)
        late = make_session("b", parent="p", state=WORKING, created=300, updated=100)
        early = make_session("c", parent="p", state=WORKING, created=200, updated=100)
        rows = build_rows([parent, done, late, early], HERE, False, {"p"})
        self.assertEqual(ids(rows), ["p", "c", "b", "a"])

    def test_a_subagent_of_a_subagent_is_indented_one_more_level(self):
        root = make_session("r", state=WORKING, updated=100)
        mid = make_session("m", parent="r", state=WORKING, updated=100)
        leaf = make_session("l", parent="m", state=WORKING, updated=100)
        rows = build_rows([root, mid, leaf], HERE, False, set())
        self.assertEqual([(r.id, r.depth) for r in rows], [("r", 0), ("m", 1), ("l", 2)])


class OnlyActiveTest(unittest.TestCase):
    def build(self):
        working = make_session("w", directory="/g", state=WORKING, updated=100)
        done = make_session("d", directory="/g", state=DONE, updated=50)
        parent = make_session("e", directory="/g", state=DONE, updated=40)
        child = make_session("k", parent="e", state=WORKING, updated=40)
        return [working, done, parent, child]

    def test_only_active_drops_finished_roots_and_keeps_the_live_ones_with_their_children(self):
        rows = build_rows(self.build(), HERE, True, set())
        self.assertEqual(ids(rows), ["w", "e", "k"])

    def test_without_only_active_every_root_is_listed(self):
        rows = build_rows(self.build(), HERE, False, set())
        self.assertEqual(ids(rows), ["w", "e", "k", "d"])


class UsageTest(unittest.TestCase):
    def test_usage_adds_input_and_output_tokens_per_model_and_sorts_most_tokens_first(self):
        sessions = [
            make_session("a", model="x/a", tokens_in=100, tokens_out=100, cost=0.5, state=WORKING),
            make_session("b", model="y/b", tokens_in=50, tokens_out=10, cost=0.25, state=DONE),
            make_session("c", model="x/a", tokens_in=1, tokens_out=2, cost=0.1, state=DONE),
        ]
        models = usage(sessions)
        self.assertEqual([m.model for m in models], ["x/a", "y/b"])
        first = models[0]
        self.assertEqual((first.tokens, first.sessions, first.active), (203, 2, 1))
        self.assertAlmostEqual(first.cost, 0.6)


if __name__ == "__main__":
    unittest.main()
