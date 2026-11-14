"""A palette as RGB colours, the model accents and the default colour mode."""
from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Dict, List

from ocsky.adapters.driving.tui.canvas import RGB, mix

# The neutrals from the background to the text. A palette without one gets a blend of its neighbours.
NEUTRALS = ["base", "surface0", "surface1", "surface2", "overlay0", "overlay1", "subtext0", "text"]
# The accent colours a model can take, in slot order. A model's slot comes from its hash.
ACCENTS = ["mauve", "sky", "peach", "green", "pink", "yellow", "teal", "lavender", "maroon",
           "sapphire", "flamingo", "blue"]


class Theme:
    """A palette as RGB tuples, one attribute per colour name, plus the accents in order."""

    def __init__(self, palette: Dict[str, str]):
        for name, hexv in palette.items():
            setattr(self, name, (int(hexv[0:2], 16), int(hexv[2:4], 16), int(hexv[4:6], 16)))
        have = [i for i, name in enumerate(NEUTRALS) if name in palette]
        for i, name in enumerate(NEUTRALS):
            if name not in palette:
                lo = max(j for j in have if j < i)
                hi = min(j for j in have if j > i)
                setattr(self, name, mix(getattr(self, NEUTRALS[lo]), getattr(self, NEUTRALS[hi]),
                                        (i - lo) / (hi - lo)))
        self.accents: List[RGB] = [getattr(self, a) for a in ACCENTS]
        # A light background: the backdrops draw ink on paper rather than light in the dark.
        self.light = sum(self.base) > 3 * 128

    def model_color(self, model: str, taken: set) -> RGB:
        """The accent of a model: its hash picks a slot, then the first accent not already taken.

        The same model gets the same colour in every run, unless its slot is taken.
        """
        slot = int(hashlib.md5(model.encode()).hexdigest(), 16) % len(self.accents)
        # When every accent is taken this keeps the last one tried, as the original did.
        for i in range(len(self.accents)):
            c = self.accents[(slot + i) % len(self.accents)]
            if c not in taken:
                break
        return c


def default_colors(environ: Mapping[str, str]) -> str:
    """24-bit colour, except in Apple's Terminal when it does not announce it."""
    if environ.get("COLORTERM", "").lower() in ("truecolor", "24bit"):
        return "truecolor"
    return "256" if environ.get("TERM_PROGRAM") == "Apple_Terminal" else "truecolor"
