"""The process readers: parsing of ps, lsof and elapsed times, argv matching and reader selection."""
from __future__ import annotations

import sys
import unittest

from tests import helpers  # noqa: F401
from ocsky.adapters.driven.processes import (
    NoProcesses,
    ProcfsProcesses,
    PsProcesses,
    is_opencode,
    mode_of,
    parse_etime,
    parse_lsof_cwd,
    parse_ps,
    system_processes,
)


class ProcessParsingTest(unittest.TestCase):
    def test_ps_output_is_parsed_and_wrappers_are_skipped(self):
        out = ("  4121  51200     01:02:03 /Users/me/.opencode/bin/opencode run -m p/m hello there\n"
               "   311   9000  2-00:00:05 node /usr/local/bin/opencode\n"
               "   312  20480  2-00:00:04 /usr/local/lib/node_modules/opencode-ai/bin/opencode\n"
               "   999   1000        00:07 /bin/zsh -c opencode run\n")
        rows = {pid: (started, rss, argv) for pid, started, rss, argv in parse_ps(out, 1_000_000.0)}
        self.assertEqual(sorted(rows), [312, 4121])  # npm's node wrapper and a shell are skipped
        self.assertEqual(rows[4121][0], 1_000_000.0 - 3723)
        self.assertEqual(rows[4121][1], 50.0)
        self.assertEqual(mode_of(rows[4121][2]), "run")
        self.assertEqual(mode_of(rows[312][2]), "tui")
        self.assertEqual(rows[312][0], 1_000_000.0 - (2 * 86400 + 4))

    def test_lsof_output_gives_the_working_directories(self):
        out = "p4121\nfcwd\nn/Users/me/hunt\np312\nfcwd\nn/\n"
        self.assertEqual(parse_lsof_cwd(out), {4121: "/Users/me/hunt", 312: "/"})

    def test_elapsed_time_with_and_without_days_and_hours(self):
        self.assertEqual(parse_etime("01:02:03"), 3723)
        self.assertEqual(parse_etime("2-00:00:05"), 2 * 86400 + 5)
        self.assertEqual(parse_etime("00:07"), 7)

    def test_is_opencode_matches_the_binary_only(self):
        self.assertTrue(is_opencode(["/usr/bin/opencode"]))
        self.assertTrue(is_opencode(["opencode", "run"]))
        self.assertFalse(is_opencode(["node", "/usr/local/bin/opencode"]))
        self.assertFalse(is_opencode(["opencode-ai"]))
        self.assertFalse(is_opencode([]))

    def test_is_opencode_accepts_the_windows_executable_in_any_case(self):
        self.assertTrue(is_opencode(["opencode.exe"]))
        self.assertTrue(is_opencode(["C:\\Program Files\\opencode\\OPENCODE.EXE", "run"]))
        self.assertFalse(is_opencode(["C:\\tools\\notopencode.exe"]))

    def test_mode_is_the_first_word_that_is_not_a_flag(self):
        self.assertEqual(mode_of(["opencode", "run", "x"]), "run")
        self.assertEqual(mode_of(["opencode", "--print-logs"]), "tui")
        self.assertEqual(mode_of(["opencode"]), "tui")


class ReaderSelectionTest(unittest.TestCase):
    def test_linux_with_procfs_reads_proc(self):
        self.assertIsInstance(system_processes("linux", True), ProcfsProcesses)

    def test_linux_without_procfs_and_macos_use_ps(self):
        self.assertIsInstance(system_processes("linux", False), PsProcesses)
        self.assertIsInstance(system_processes("darwin", False), PsProcesses)

    def test_windows_reads_nothing(self):
        self.assertIsInstance(system_processes("win32", False), NoProcesses)
        self.assertIsInstance(system_processes("win32", True), NoProcesses)
        self.assertEqual(NoProcesses().processes(), [])

    @unittest.skipUnless(sys.platform.startswith("linux"), "reads /proc, so Linux only")
    def test_the_real_procfs_reader_returns_a_list(self):
        self.assertIsInstance(ProcfsProcesses().processes(), list)


if __name__ == "__main__":
    unittest.main()
