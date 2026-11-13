"""Copies text to the clipboard of the person at the terminal, with the OSC 52 escape sequence.

The terminal itself does the copy, so it works over SSH too, as long as the terminal allows OSC 52.
"""
from __future__ import annotations

import base64
from typing import TextIO


class Osc52Clipboard:
    """ForCopyingText that writes to the terminal stream it is given."""

    def __init__(self, stream: TextIO):
        self._stream = stream

    def copy(self, text: str) -> None:
        payload = base64.b64encode(text.encode("utf-8", errors="replace")).decode("ascii")
        self._stream.write("\x1b]52;c;%s\x07" % payload)
        self._stream.flush()
