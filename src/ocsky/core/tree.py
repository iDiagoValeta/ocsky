"""Groups sessions by directory, folds subagents under their parent and orders the rows. Pure."""
from __future__ import annotations

from ocsky.core.model import COMPACTING, STALLED, WAITING, WORKING, ModelUsage, Session

# Lower ranks come first inside a group of root sessions.
STATE_RANK = {WORKING: 0, COMPACTING: 0, WAITING: 1, STALLED: 2}
UNRANKED = 3


def is_here(directory: str, here: str) -> bool:
    """True when the directory is `here` itself or one of its subdirectories."""
    if not directory or not here:
        return False
    base = here.replace("\\", "/").rstrip("/")  # opencode may store Windows paths with backslashes
    d = directory.replace("\\", "/").rstrip("/")
    return d == base or d.startswith(base + "/")


def alive(s: Session) -> bool:
    """A session is alive when it is live itself or any of its subagents is."""
    return s.live or any(alive(c) for c in s.children)


def build_rows(sessions: list[Session], here: str, only_active: bool,
               expanded: set[str]) -> list[Session]:
    """The rows the list shows, in display order.

    Links every subagent to its parent (the parent must be in `sessions`) and sets their depth,
    `here` and `hidden_children`. Roots are grouped by directory: the groups of `here` first, then
    the groups with a live root, then the most recently updated. Live subagents are always listed
    under their parent; finished ones only when the parent id is in `expanded`, otherwise they are
    counted in `hidden_children`. With `only_active`, roots that are not alive are dropped.
    """
    by_id = {s.id: s for s in sessions}
    for s in sessions:
        s.children = []
        s.depth = 0
        s.hidden_children = 0
        s.here = is_here(s.directory, here)
    roots: list[Session] = []
    for s in sessions:
        if s.parent is not None and s.parent in by_id and s.parent != s.id:
            by_id[s.parent].children.append(s)
        else:
            roots.append(s)

    # Plain dicts keep insertion order, so the groups stay in the order they were first seen.
    groups: dict[str, list[Session]] = {}
    for r in roots:
        groups.setdefault(r.directory, []).append(r)

    def group_order(item: tuple[str, list[Session]]) -> tuple[int, int, int]:
        directory, members = item
        return (0 if is_here(directory, here) else 1,
                0 if any(alive(r) for r in members) else 1,
                -max(r.updated for r in members))

    def root_order(s: Session) -> tuple[int, int, int]:
        return (0 if alive(s) else 1, STATE_RANK.get(s.state, UNRANKED), -s.updated)

    rows: list[Session] = []

    def add(s: Session, depth: int) -> None:
        s.depth = depth
        rows.append(s)
        for c in sorted(s.children, key=lambda c: (0 if alive(c) else 1, c.created)):
            if alive(c) or s.id in expanded:
                add(c, depth + 1)
            else:
                s.hidden_children += 1

    for _, members in sorted(groups.items(), key=group_order):
        for r in sorted(members, key=root_order):
            if only_active and not alive(r):
                continue
            add(r, 0)
    return rows


def usage(sessions: list[Session]) -> list[ModelUsage]:
    """Per model: tokens (input plus output), cost, session count and working count. Most tokens first."""
    totals: dict[str, list] = {}
    for s in sessions:
        t = totals.setdefault(s.model, [0, 0.0, 0, 0])
        t[0] += s.tokens_in + s.tokens_out
        t[1] += s.cost
        t[2] += 1
        t[3] += 1 if s.working else 0
    out = [ModelUsage(model=m, tokens=t[0], cost=t[1], sessions=t[2], active=t[3])
           for m, t in totals.items()]
    out.sort(key=lambda u: (-u.tokens, u.model))
    return out
