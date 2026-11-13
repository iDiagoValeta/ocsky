"""The small driven adapters: the launcher, the OSC 52 clipboard, the preferences, the clock."""
from __future__ import annotations

import base64
import os
import shutil
import tempfile
import time
import unittest

from tests import helpers  # noqa: F401
from ocsky.adapters.driven.json_preferences import JsonPreferences, default_config
from ocsky.adapters.driven.opencode_launcher import OpencodeLauncher
from ocsky.adapters.driven.osc52_clipboard import Osc52Clipboard
from ocsky.adapters.driven.system_clock import SystemClock
from tests.doubles import make_session


class Recorder:
    """Stands in for subprocess.call: remembers the argv and the keyword arguments."""

    def __init__(self):
        self.calls = []

    def __call__(self, argv, **kwargs):
        self.calls.append((argv, kwargs))
        return 0


class TextRecorder:
    """A terminal stream that remembers what was written and whether it was flushed."""

    def __init__(self):
        self.parts = []
        self.flushed = False

    def write(self, text):
        self.parts.append(text)

    def flush(self):
        self.flushed = True


class LauncherTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_a_binary_found_on_the_path_is_run_by_its_full_path(self):
        recorder = Recorder()
        session = make_session("ses_abc", directory=self.dir)
        found = {"opencode": r"C:\npm\opencode.cmd"}
        OpencodeLauncher(run=recorder, which=found.get).open(session)
        self.assertEqual(recorder.calls[0][0], [r"C:\npm\opencode.cmd", "--session", "ses_abc"])

    def test_the_session_opens_in_its_directory(self):
        recorder = Recorder()
        session = make_session("ses_abc", directory=self.dir)
        self.assertIsNone(OpencodeLauncher("opencode-x", run=recorder, which=lambda _b: None).open(session))
        self.assertEqual(recorder.calls, [(["opencode-x", "--session", "ses_abc"], {"cwd": self.dir})])

    def test_a_missing_directory_means_no_cwd(self):
        recorder = Recorder()
        session = make_session("ses_abc", directory=os.path.join(self.dir, "gone"))
        OpencodeLauncher(run=recorder, which=lambda _b: None).open(session)
        self.assertEqual(recorder.calls, [(["opencode", "--session", "ses_abc"], {})])

    def test_a_binary_that_does_not_exist_raises_an_os_error(self):
        session = make_session("ses_abc", directory=self.dir)
        with self.assertRaises(OSError):
            OpencodeLauncher(binary=os.path.join(self.dir, "no-such-opencode")).open(session)


class ClipboardTest(unittest.TestCase):
    def test_the_text_goes_out_as_base64_inside_osc_52_and_is_flushed(self):
        stream = TextRecorder()
        Osc52Clipboard(stream).copy("ses_abc héllo")
        payload = base64.b64encode("ses_abc héllo".encode("utf-8")).decode("ascii")
        self.assertEqual("".join(stream.parts), "\x1b]52;c;" + payload + "\x07")
        self.assertTrue(stream.flushed)


class PreferencesTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "sub", "config.json")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_a_saved_preference_comes_back_after_a_new_instance(self):
        JsonPreferences(self.path).save({"lang": "es", "theme": "light"})
        self.assertEqual(JsonPreferences(self.path).load(), {"lang": "es", "theme": "light"})
        self.assertFalse(os.path.exists(self.path + ".tmp"))

    def test_a_missing_file_loads_as_empty(self):
        self.assertEqual(JsonPreferences(self.path).load(), {})

    def test_a_corrupt_file_or_a_non_object_loads_as_empty(self):
        os.makedirs(os.path.dirname(self.path))
        for text in ("{not json", "[1, 2]", '"just a string"'):
            with open(self.path, "w", encoding="utf-8") as f:
                f.write(text)
            self.assertEqual(JsonPreferences(self.path).load(), {}, text)

    def test_values_that_are_not_strings_are_dropped(self):
        os.makedirs(os.path.dirname(self.path))
        with open(self.path, "w", encoding="utf-8") as f:
            f.write('{"lang": "es", "count": 3, "nested": {"a": 1}}')
        self.assertEqual(JsonPreferences(self.path).load(), {"lang": "es"})

    def test_an_unwritable_location_does_not_raise(self):
        blocker = os.path.join(self.dir, "a-file")
        with open(blocker, "w", encoding="utf-8") as f:
            f.write("")
        JsonPreferences(os.path.join(blocker, "config.json")).save({"lang": "en"})  # directory is a file
        self.assertEqual(JsonPreferences(os.path.join(blocker, "config.json")).load(), {})


class DefaultConfigTest(unittest.TestCase):
    def test_linux_uses_xdg_config_home_then_dot_config(self):
        self.assertEqual(default_config({"XDG_CONFIG_HOME": "/cfg"}, "/home/u", "linux"),
                         os.path.join("/cfg", "ocsky", "config.json"))
        self.assertEqual(default_config({}, "/home/u", "linux"),
                         os.path.join("/home/u", ".config", "ocsky", "config.json"))

    def test_windows_uses_appdata_when_xdg_is_not_set(self):
        appdata = "C:\\Users\\u\\AppData\\Roaming"
        self.assertEqual(default_config({"APPDATA": appdata}, "C:\\Users\\u", "win32"),
                         os.path.join(appdata, "ocsky", "config.json"))

    def test_windows_xdg_config_home_still_wins(self):
        self.assertEqual(default_config({"APPDATA": "C:\\x", "XDG_CONFIG_HOME": "/cfg"}, "C:\\u", "win32"),
                         os.path.join("/cfg", "ocsky", "config.json"))

    def test_appdata_is_ignored_outside_windows(self):
        self.assertEqual(default_config({"APPDATA": "/appdata"}, "/home/u", "linux"),
                         os.path.join("/home/u", ".config", "ocsky", "config.json"))


class SystemClockTest(unittest.TestCase):
    def test_now_is_the_epoch_time_in_milliseconds(self):
        before = time.time() * 1000
        now = SystemClock().now_ms()
        after = time.time() * 1000
        self.assertIsInstance(now, int)
        self.assertLessEqual(before - 1, now)
        self.assertLessEqual(now, after + 1)


if __name__ == "__main__":
    unittest.main()
