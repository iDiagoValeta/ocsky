"""The pure translation of message parts into Activity objects."""
from __future__ import annotations

import unittest

from tests import helpers  # noqa: F401
from ocsky.core.activity import clean, describe_message, describe_part, relative
from ocsky.core.model import Activity, Message
from tests.doubles import assistant_message, idle_message, user_message

HOME = "/home/ana"
PROJECT = "/home/ana/dev/project"


def tool(name: str, status: str | None = None, input: dict | None = None) -> dict:
    state: dict = {}
    if status is not None:
        state["status"] = status
    if input is not None:
        state["input"] = input
    return {"type": "tool", "name": name, "state": state}


class CleanTest(unittest.TestCase):
    def test_a_text_with_newlines_tabs_and_control_characters_is_flattened_to_one_line(self):
        self.assertEqual(clean("  first line\n\tsecond\x07 line\x7f  "), "first line second line")

    def test_a_missing_text_becomes_an_empty_string(self):
        self.assertEqual(clean(""), "")
        self.assertEqual(clean(None), "")


class RelativeTest(unittest.TestCase):
    def test_a_windows_path_is_relative_to_a_windows_directory_with_its_own_separators(self):
        self.assertEqual(relative("C:\\Users\\x\\proj\\src\\tok.py", "C:\\Users\\x\\proj", HOME),
                         "src\\tok.py")
        self.assertEqual(relative("C:/Users/x/proj/src/tok.py", "C:\\Users\\x\\proj", HOME), "src/tok.py")
        self.assertEqual(relative("C:\\Users\\x\\proj2\\a.py", "C:\\Users\\x\\proj", HOME),
                         "C:\\Users\\x\\proj2\\a.py")

    def test_a_path_inside_the_session_directory_is_shown_relative_to_it(self):
        self.assertEqual(relative(PROJECT + "/src/tok.py", PROJECT, HOME), "src/tok.py")

    def test_a_path_under_home_outside_the_session_directory_starts_with_a_tilde(self):
        self.assertEqual(relative(HOME + "/notes/todo.md", PROJECT, HOME), "~/notes/todo.md")

    def test_any_other_path_is_returned_unchanged(self):
        self.assertEqual(relative("/etc/hosts", PROJECT, HOME), "/etc/hosts")

    def test_an_empty_home_never_turns_every_path_into_a_tilde_path(self):
        self.assertEqual(relative("/etc/hosts", PROJECT, ""), "/etc/hosts")


class DescribePartTest(unittest.TestCase):
    def test_a_reasoning_part_keeps_its_cleaned_text(self):
        a = describe_part({"type": "reasoning", "text": "Two  hunters\nare working"}, PROJECT, HOME)
        self.assertEqual((a.kind, a.detail), ("reasoning", "Two hunters are working"))

    def test_a_text_part_keeps_its_cleaned_text(self):
        a = describe_part({"type": "text", "text": "Done.\n"}, PROJECT, HOME)
        self.assertEqual((a.kind, a.detail), ("text", "Done."))

    def test_a_bash_command_is_kept_whole_even_when_it_contains_paths(self):
        cmd = "ls " + PROJECT + "/src"
        a = describe_part(tool("bash", "completed", {"command": cmd}), PROJECT, HOME)
        self.assertEqual(a, Activity("tool", tool="bash", detail=cmd, status=""))

    def test_a_file_path_argument_is_made_relative_to_the_session_directory(self):
        a = describe_part(tool("read", "completed", {"filePath": PROJECT + "/src/tok.py"}), PROJECT, HOME)
        self.assertEqual(a.detail, "src/tok.py")

    def test_an_offset_is_appended_to_the_detail_of_a_read(self):
        part = tool("read", "completed", {"filePath": PROJECT + "/src/tok.py", "offset": 120})
        self.assertEqual(describe_part(part, PROJECT, HOME).detail, "src/tok.py :120")

    def test_an_error_status_is_reported_as_error(self):
        a = describe_part(tool("bash", "error", {"command": "make"}), PROJECT, HOME)
        self.assertEqual((a.tool, a.status), ("bash", "error"))

    def test_a_running_or_pending_tool_is_reported_as_running(self):
        for status in ("running", "pending"):
            a = describe_part(tool("grep", status, {"pattern": "TODO"}), PROJECT, HOME)
            self.assertEqual(a.status, "running", status)

    def test_a_completed_tool_has_no_status(self):
        a = describe_part(tool("grep", "completed", {"pattern": "TODO"}), PROJECT, HOME)
        self.assertEqual((a.detail, a.status), ("TODO", ""))

    def test_when_no_known_argument_exists_the_first_string_argument_is_the_detail(self):
        a = describe_part(tool("custom", "completed", {"flag": 3, "target": "alpha"}), PROJECT, HOME)
        self.assertEqual(a.detail, "alpha")

    def test_a_tool_without_a_name_is_called_tool(self):
        a = describe_part({"type": "tool", "state": {"status": "completed"}}, PROJECT, HOME)
        self.assertEqual(a.tool, "tool")

    def test_a_part_of_an_unknown_type_is_other_with_its_type_as_detail(self):
        a = describe_part({"type": "step-start"}, PROJECT, HOME)
        self.assertEqual(a, Activity("other", detail="step-start"))


class DescribeMessageTest(unittest.TestCase):
    def test_a_user_message_is_a_user_activity_with_its_cleaned_text(self):
        acts = describe_message(user_message(1, "fix\nthe  parser "), PROJECT, HOME)
        self.assertEqual(acts, [Activity("user", detail="fix the parser")])

    def test_an_idle_message_carries_its_outcome_or_an_empty_one(self):
        self.assertEqual(describe_message(idle_message(1, "stop"), PROJECT, HOME),
                         [Activity("idle", outcome="stop")])
        self.assertEqual(describe_message(Message(1, "idle", {}), PROJECT, HOME),
                         [Activity("idle", outcome="")])

    def test_a_compaction_message_is_a_compaction_activity(self):
        self.assertEqual(describe_message(Message(1, "compaction", {}), PROJECT, HOME),
                         [Activity("compaction")])

    def test_an_assistant_message_gives_one_activity_per_content_part_in_order(self):
        msg = assistant_message(1, [{"type": "reasoning", "text": "plan"},
                                    tool("bash", "running", {"command": "make"})])
        acts = describe_message(msg, PROJECT, HOME)
        self.assertEqual([a.kind for a in acts], ["reasoning", "tool"])
        self.assertEqual(acts[1].status, "running")

    def test_an_assistant_message_without_content_gives_no_activity(self):
        self.assertEqual(describe_message(Message(1, "assistant", {}), PROJECT, HOME), [])


if __name__ == "__main__":
    unittest.main()
