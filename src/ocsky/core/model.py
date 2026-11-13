"""The data the core works with: sessions, processes, messages and the snapshot of a moment.

Plain data only. Nothing here knows about storage, the clock or the terminal.
"""
from __future__ import annotations

from dataclasses import dataclass, field

WORKING, COMPACTING, WAITING, STALLED = "working", "compacting", "waiting", "stalled"
SUSPENDED, FAILED, INTERRUPTED, DONE = "suspended", "failed", "interrupted", "done"


@dataclass
class Activity:
    """What a session is doing now, in a language-free form. The interface translates it."""

    kind: str  # "reasoning" | "text" | "tool" | "user" | "idle" | "compaction" | "other"
    tool: str = ""  # tool name when kind is "tool", e.g. "bash" or "read"
    detail: str = ""  # command, relative path, pattern, user text...
    status: str = ""  # "" | "running" | "error" (tool only)
    outcome: str = ""  # idle only: opencode's outcome, may be ""


@dataclass
class Step:
    """One line of a trace."""

    time: int  # milliseconds
    activity: Activity


@dataclass
class Message:
    """One row of opencode's session_message table, decoded."""

    time: int
    type: str  # "assistant" | "user" | "compaction" | "idle"
    data: dict


@dataclass
class Session:
    id: str
    parent: str | None = None
    slug: str = ""  # defaults to the last 6 characters of the id
    title: str = ""
    agent: str = "build"
    model: str = ""  # "provider/id", or "" when unknown
    directory: str = ""
    cost: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    tokens_reasoning: int = 0
    tokens_cache: int = 0
    created: int = 0
    updated: int = 0
    busy: int | None = None
    idle: int | None = None
    outcome: str | None = None
    compacting: int | None = None
    suspended: int | None = None
    state: str = ""
    activity: Activity | None = None
    thought: str = ""
    pulse: list[int] = field(default_factory=list)
    children: list[Session] = field(default_factory=list)
    depth: int = 0
    hidden_children: int = 0  # finished subagents folded under this row
    here: bool = False  # its directory is the one ocsky runs in, or below it

    def __post_init__(self) -> None:
        if not self.slug:
            self.slug = self.id[-6:]

    @property
    def working(self) -> bool:
        return self.state in (WORKING, COMPACTING)

    @property
    def live(self) -> bool:
        return self.working or self.state == WAITING

    @property
    def is_subagent(self) -> bool:
        return self.parent is not None


@dataclass(frozen=True)
class Proc:
    """A running opencode process."""

    pid: int
    mode: str  # "tui", "run", "serve", "web", "acp"...
    cwd: str
    started: float  # epoch seconds
    rss_mb: float


@dataclass
class ModelUsage:
    model: str
    tokens: int
    cost: float
    sessions: int
    active: int  # sessions working right now


@dataclass
class Snapshot:
    sessions: list[Session]  # everything in range, newest first
    rows: list[Session]  # what the list shows, in display order
    procs: list[Proc]
    models: list[ModelUsage]  # most tokens first
    error: str = ""  # "" or "store_unavailable"
    error_detail: str = ""
