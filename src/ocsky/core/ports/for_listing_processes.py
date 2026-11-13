"""Port: listing the running opencode processes."""
from __future__ import annotations

from typing import Protocol

from ocsky.core.model import Proc


class ForListingProcesses(Protocol):
    def processes(self) -> list[Proc]:
        """The running opencode processes, oldest first."""
