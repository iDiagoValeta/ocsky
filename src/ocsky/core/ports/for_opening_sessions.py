"""Port: opening a session in opencode."""
from __future__ import annotations

from typing import Protocol

from ocsky.core.model import Session


class ForOpeningSessions(Protocol):
    def open(self, session: Session) -> None:
        """Opens the session in opencode, from its own directory."""
