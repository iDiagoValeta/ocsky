"""The command line: what ocsky accepts and what the help says. It builds nothing; main.py does."""
from __future__ import annotations

import argparse
from typing import Callable, List, Tuple

from ocsky.adapters.driving.tui.app import RANGES
from ocsky.adapters.driving.tui.i18n import LANGS, Tr

VIEWS = ["sky", "clock", "trace"]
COLOR_MODES = ["truecolor", "256"]


def _size(tr: Tr) -> Callable[[str], Tuple[int, int]]:
    """An argparse type for COLSxROWS, with the error in the interface language."""

    def parse_size(text: str) -> Tuple[int, int]:
        cols, sep, rows = text.lower().partition("x")
        if not sep or not cols.isdigit() or not rows.isdigit():
            raise argparse.ArgumentTypeError(tr("cli.bad_size", value=text))
        return int(cols), int(rows)

    return parse_size


def parse(argv: List[str], tr: Tr) -> argparse.Namespace:
    """The parsed command line. Help and errors come out in tr's language."""
    p = argparse.ArgumentParser(prog="ocsky", description=tr("cli.description"))
    p.add_argument("--range", choices=[key for key, _ in RANGES], default="24h", help=tr("cli.range"))
    p.add_argument("--all", action="store_true", help=tr("cli.all"))
    p.add_argument("--view", choices=VIEWS, default="sky", help=tr("cli.view"))
    p.add_argument("--light", action="store_true", help=tr("cli.light"))
    p.add_argument("--db", metavar="PATH", default=None, help=tr("cli.db"))
    p.add_argument("--colors", choices=COLOR_MODES, default=None, help=tr("cli.colors"))
    p.add_argument("--once", metavar="COLSxROWS", type=_size(tr), default=None, help=tr("cli.once"))
    p.add_argument("--lang", choices=list(LANGS), default=None, help=tr("cli.lang"))
    p.add_argument("--demo", action="store_true", help=tr("cli.demo"))
    p.add_argument("--version", action="store_true", help=tr("cli.version"))
    return p.parse_args(argv)
