"""Port: telling the current time, so the core never reads the clock itself."""
from __future__ import annotations

from typing import Protocol


class ForTellingTime(Protocol):
    def now_ms(self) -> int:
        """The current time in milliseconds since the epoch."""
