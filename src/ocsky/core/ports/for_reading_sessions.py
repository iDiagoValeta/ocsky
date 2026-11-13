"""Port: reading opencode's sessions, their messages and their token pulse. Read only."""
from __future__ import annotations

from typing import Protocol

from ocsky.core.model import Message, Session


class StoreUnavailable(Exception):
    """The session store cannot be read right now."""


class ForReadingSessions(Protocol):
    def sessions(self, since_ms: int, now_ms: int) -> list[Session]:
        """Sessions updated after since_ms, newest first. Raises StoreUnavailable."""

    def messages(self, session_id: str, limit: int) -> list[Message]:
        """The newest `limit` messages of a session, oldest first. Raises StoreUnavailable."""

    def pulse(self, session_ids: list[str], since_ms: int) -> list[tuple[str, int, int]]:
        """(session id, time, output plus reasoning tokens) of assistant messages after since_ms."""
