"""The preferences the person chose (language, theme), kept as a JSON object in the config directory.

Preferences are a convenience: a missing, corrupt or unwritable file never stops the program.
"""
from __future__ import annotations

import json
import os
from typing import Dict, Mapping


def default_config(environ: Mapping[str, str], home: str, platform: str) -> str:
    """$XDG_CONFIG_HOME/ocsky/config.json, else on Windows %APPDATA%/ocsky/config.json, else
    ~/.config/ocsky/config.json."""
    base = environ.get("XDG_CONFIG_HOME")
    if not base and platform.startswith("win") and environ.get("APPDATA"):
        base = environ["APPDATA"]
    if not base:
        base = os.path.join(home, ".config")
    return os.path.join(base, "ocsky", "config.json")


class JsonPreferences:
    """ForKeepingPreferences backed by one JSON file."""

    def __init__(self, path: str):
        self._path = path

    def load(self) -> Dict[str, str]:
        try:
            with open(self._path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return {}
        if not isinstance(data, dict):
            return {}
        return {key: value for key, value in data.items() if isinstance(value, str)}

    def save(self, prefs: Dict[str, str]) -> None:
        tmp = self._path + ".tmp"
        try:
            directory = os.path.dirname(self._path)
            if directory:
                os.makedirs(directory, exist_ok=True)
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(prefs, f, indent=2, sort_keys=True)
            os.replace(tmp, self._path)  # atomic: a reader sees the old file or the new one
        except OSError:
            return  # not writable: the preferences just are not kept this time
