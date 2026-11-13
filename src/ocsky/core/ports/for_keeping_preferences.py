"""Port: keeping the preferences the person chose (language, theme...) between runs."""
from __future__ import annotations

from typing import Protocol


class ForKeepingPreferences(Protocol):
    def load(self) -> dict[str, str]:
        """The saved preferences, or an empty dict when there are none."""

    def save(self, prefs: dict[str, str]) -> None:
        """Replaces the saved preferences."""
