"""Opens a session in opencode by running `opencode --session <id>` in the session's directory."""
from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any, Callable, Dict, List, Optional

from ocsky.core.model import Session


class OpencodeLauncher:
    """ForOpeningSessions. The child inherits the terminal, so opencode takes it over until it exits.

    Raises OSError (FileNotFoundError when the binary is not on the PATH) if it cannot be started.
    `run` is subprocess.call by default; tests pass a recorder. `which` resolves the binary to a full
    path, which is how an npm `.cmd` shim is found on Windows; an unresolved name is kept as it is.
    """

    def __init__(self, binary: str = "opencode", run: Callable[..., Any] = subprocess.call,
                 which: Callable[[str], Optional[str]] = shutil.which):
        self._binary = binary
        self._run = run
        self._which = which

    def open(self, session: Session) -> None:
        argv: List[str] = [self._which(self._binary) or self._binary, "--session", session.id]
        options: Dict[str, str] = {}
        if session.directory and os.path.isdir(session.directory):
            options["cwd"] = session.directory
        self._run(argv, **options)
