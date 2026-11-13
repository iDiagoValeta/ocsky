"""Works out the state of every session from its timestamps and the running processes. Pure."""
from __future__ import annotations

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
    Session,
)

# A session still marked busy with no progress for this long is history, not a live agent.
STALL_MS = 20 * 60_000

# Processes in these modes serve other clients; they do not mean a session is waiting for you.
NON_INTERACTIVE_MODES = ("serve", "web", "acp")


def classify(sessions: list[Session], procs: list[Proc], now_ms: int) -> None:
    """Sets the state of every session. `sessions` must be ordered newest first."""
    proc_dirs = {p.cwd for p in procs if p.mode not in NON_INTERACTIVE_MODES}
    newest_in_dir: dict[str, Session] = {}
    for s in sessions:
        newest_in_dir.setdefault(s.directory, s)
    for s in sessions:
        busy = s.busy is not None and (s.idle is None or s.busy > s.idle)
        # A running session can carry a fresh time_suspended for a moment, so busy wins.
        if busy and s.compacting and s.compacting >= s.busy:
            s.state = COMPACTING
        elif busy:
            s.state = STALLED if now_ms - s.updated > STALL_MS else WORKING
        elif s.suspended and s.suspended >= max(s.busy or 0, s.idle or 0):
            s.state = SUSPENDED
        elif s.directory in proc_dirs and newest_in_dir.get(s.directory) is s and not s.parent:
            s.state = WAITING
        elif s.outcome == "failed":
            s.state = FAILED
        elif s.outcome == "interrupted":
            s.state = INTERRUPTED
        else:
            s.state = DONE
