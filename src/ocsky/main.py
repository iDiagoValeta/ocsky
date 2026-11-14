"""The composition root: the only place that knows every adapter and wires them to the interface."""
from __future__ import annotations

import contextlib
import os
import sys
import tempfile
from typing import List, Optional

from ocsky import __version__
from ocsky.adapters.driven.demo_database import DEMO_HERE, DEMO_HOME, build_demo_db
from ocsky.adapters.driven.json_preferences import JsonPreferences, default_config
from ocsky.adapters.driven.opencode_launcher import OpencodeLauncher
from ocsky.adapters.driven.osc52_clipboard import Osc52Clipboard
from ocsky.adapters.driven.processes import system_processes
from ocsky.adapters.driven.sqlite_sessions import SqliteSessions, default_db
from ocsky.adapters.driven.system_clock import SystemClock
from ocsky.adapters.driving.cli import parse
from ocsky.adapters.driving.tui.app import App, Options
from ocsky.adapters.driving.tui.i18n import Tr
from ocsky.adapters.driving.tui.terminal import run, system_terminal
from ocsky.adapters.driving.tui.theme import default_colors
from ocsky.core.model import Proc
from ocsky.core.observatory import Observatory

DEMO_SHOP = "/home/demo/dev/shop-api"


class _DemoProcesses:
    """Two opencode windows that exist only in --demo, so the demo reads the same on every machine."""

    def __init__(self, now_ms: int):
        self._started = now_ms / 1000 - 45 * 60

    def processes(self) -> List[Proc]:
        return [Proc(4101, "tui", DEMO_HERE, self._started, 412.0),
                Proc(4188, "tui", DEMO_SHOP, self._started + 25 * 60, 268.0)]


def _prescan_lang(argv: List[str]) -> Optional[str]:
    """The value of --lang, found before parsing so that --help already speaks that language."""
    for i, arg in enumerate(argv):
        if arg == "--lang" and i + 1 < len(argv):
            return argv[i + 1]
        if arg.startswith("--lang="):
            return arg[len("--lang="):]
    return None


def main(argv: Optional[List[str]] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    home, here = os.path.expanduser("~"), os.getcwd()
    prefs = JsonPreferences(default_config(os.environ, home, sys.platform))
    saved = prefs.load()
    tr = Tr(_prescan_lang(argv) or saved.get("lang") or "en")
    args = parse(argv, tr)
    if args.version:
        print("ocsky %s" % __version__)
        return 0
    lang = args.lang or tr.lang
    clock = SystemClock()
    with contextlib.ExitStack() as stack:
        if args.demo:
            tmp = stack.enter_context(tempfile.TemporaryDirectory())
            db_path = os.path.join(tmp, "opencode.db")
            build_demo_db(db_path, clock.now_ms())
            home, here = DEMO_HOME, DEMO_HERE
            processes = _DemoProcesses(clock.now_ms())
        else:
            db_path = args.db or default_db(os.environ, home, sys.platform)
            if not os.path.exists(db_path):
                print(Tr(lang)("error.no_db", path=db_path), file=sys.stderr)
                return 1
            processes = system_processes(sys.platform, os.path.isdir("/proc/self"))
        sessions = SqliteSessions(db_path)
        # Windows cannot delete the demo database while a connection holds it open.
        stack.callback(sessions.close)
        observatory = Observatory(sessions, processes, clock, home, here)
        options = Options(range=args.range, all=args.all, view=args.view,
                          backdrop=args.backdrop or saved.get("backdrop") or "stars",
                          light=args.light or (not saved.get("palette") and saved.get("theme") == "light"),
                          palette=args.palette or saved.get("palette", ""),
                          colors=args.colors or default_colors(os.environ), lang=lang,
                          instant=bool(args.once))
        app = App(observatory, clock, OpencodeLauncher(), Osc52Clipboard(sys.stdout), prefs, options, home)
        return _show(app, args.once, Tr(lang))


def _show(app: App, once: Optional[tuple], tr: Tr) -> int:
    """One frame to stdout with --once, otherwise the interactive screen."""
    if once:
        app.refresh(force=True)
        if hasattr(sys.stdout, "reconfigure"):
            # A redirected stdout on Windows uses a legacy code page that cannot encode the frame.
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stdout.write(app.frame(*once) + "\n")
        return 0
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        print(tr("error.no_tty"), file=sys.stderr)
        return 1
    with system_terminal(sys.platform) as term:
        run(app, term)
    return 0
