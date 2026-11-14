"""The command line and the composition root, run for real against the demo database."""
from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
import unittest
from typing import List, Tuple
from unittest import mock

from tests import helpers  # noqa: F401
# isort: split
from ocsky import __version__
from ocsky.adapters.driving.tui.palettes import PALETTES
from ocsky.adapters.driving.cli import parse
from ocsky.adapters.driving.tui.i18n import Tr
from ocsky.main import main


def run_main(argv: List[str]) -> Tuple[int, str, str]:
    """(exit code, stdout, stderr), with the user's real config kept out of reach."""
    out, err = io.StringIO(), io.StringIO()
    with tempfile.TemporaryDirectory() as config:
        with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": config}):
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = main(argv)
    return code, out.getvalue(), err.getvalue()


class MainTest(unittest.TestCase):
    def test_version_prints_the_version_and_succeeds(self):
        code, out, _ = run_main(["--version"])
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "ocsky " + __version__)

    def test_the_demo_renders_one_frame_with_both_projects(self):
        code, out, _ = run_main(["--demo", "--once", "140x40"])
        self.assertEqual(code, 0)
        self.assertIn("Hunt acme/parser", out)
        self.assertIn("shop-api", out)

    def test_once_writes_the_frame_as_utf8_when_the_stream_can_be_reconfigured(self):
        class Reconfigurable(io.StringIO):
            def reconfigure(self, **kwargs):
                self.kwargs = kwargs

        out = Reconfigurable()
        with tempfile.TemporaryDirectory() as config:
            with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": config}), contextlib.redirect_stdout(out):
                self.assertEqual(main(["--demo", "--once", "100x30"]), 0)
        self.assertEqual(out.kwargs, {"encoding": "utf-8", "errors": "replace"})
        self.assertIn("shop-api", out.getvalue())

    def test_the_language_option_translates_the_frame(self):
        code, out, _ = run_main(["--demo", "--once", "140x40", "--lang", "es"])
        self.assertEqual(code, 0)
        self.assertIn("trabajando", out)

    def test_a_saved_language_is_used_when_no_option_is_given(self):
        out = io.StringIO()
        with tempfile.TemporaryDirectory() as config:
            os.makedirs(os.path.join(config, "ocsky"))
            with open(os.path.join(config, "ocsky", "config.json"), "w", encoding="utf-8") as f:
                f.write('{"lang": "es"}')
            with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": config}), contextlib.redirect_stdout(out):
                self.assertEqual(main(["--demo", "--once", "140x40"]), 0)
        self.assertIn("trabajando", out.getvalue())

    def test_every_view_renders_in_one_frame(self):
        for backdrop in ("stars", "galaxy", "aurora"):
            code, out, _ = run_main(["--demo", "--once", "100x30", "--backdrop", backdrop])
            self.assertEqual(code, 0, backdrop)
            self.assertTrue(out.strip(), backdrop)
        for view in ("sky", "clock", "trace"):
            code, out, _ = run_main(["--demo", "--once", "100x30", "--view", view])
            self.assertEqual(code, 0, view)
            self.assertTrue(out.strip(), view)

    def test_every_palette_renders_one_frame(self):
        for palette in PALETTES:
            code, out, _ = run_main(["--demo", "--once", "100x30", "--palette", palette])
            self.assertEqual(code, 0, palette)
            self.assertTrue(out.strip(), palette)

    def test_a_missing_database_is_reported_on_stderr(self):
        code, out, err = run_main(["--db", "/nonexistent/x.db", "--once", "100x30"])
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("No opencode database at /nonexistent/x.db", err)

    def test_without_a_terminal_it_refuses_to_start_the_live_view(self):
        with mock.patch.object(sys, "stdin", io.StringIO()):
            code, _, err = run_main(["--demo"])
        self.assertEqual(code, 1)
        self.assertIn("interactive terminal", err)


class ParseTest(unittest.TestCase):
    def test_defaults(self):
        args = parse([], Tr("en"))
        self.assertEqual((args.range, args.all, args.view, args.light), ("24h", False, "sky", False))
        self.assertEqual((args.db, args.colors, args.lang, args.once), (None, None, None, None))
        self.assertFalse(args.demo)
        self.assertFalse(args.version)

    def test_once_becomes_a_size(self):
        self.assertEqual(parse(["--once", "140x40"], Tr("en")).once, (140, 40))

    def test_a_malformed_size_is_an_error_in_the_interface_language(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit):
            parse(["--once", "wide"], Tr("es"))
        self.assertIn("COLSxFILAS", err.getvalue())

    def test_help_speaks_the_requested_language(self):
        out = io.StringIO()
        with tempfile.TemporaryDirectory() as config:
            with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": config}):
                with contextlib.redirect_stdout(out), self.assertRaises(SystemExit) as raised:
                    main(["--lang", "es", "--help"])
        self.assertEqual(raised.exception.code, 0)
        self.assertIn("Una vista en directo", out.getvalue())
        self.assertIn("paleta clara", out.getvalue())


if __name__ == "__main__":
    unittest.main()
