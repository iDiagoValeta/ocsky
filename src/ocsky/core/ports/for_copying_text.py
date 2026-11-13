"""Port: copying text to the clipboard of the person at the terminal."""
from __future__ import annotations

from typing import Protocol


class ForCopyingText(Protocol):
    def copy(self, text: str) -> None:
        """Puts the text on the clipboard."""
