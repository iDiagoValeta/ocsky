"""Colour palettes (Catppuccin Mocha and Latte), the model accents and the default colour mode."""
from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Dict, List

from ocsky.adapters.driving.tui.canvas import RGB

# Catppuccin, a predefined palette: Mocha for dark terminals, Latte for light ones.
MOCHA = {"base": "1e1e2e", "mantle": "181825", "crust": "11111b", "surface0": "313244",
         "surface1": "45475a", "surface2": "585b70", "overlay0": "6c7086", "overlay1": "7f849c",
         "subtext0": "a6adc8", "text": "cdd6f4", "rosewater": "f5e0dc", "flamingo": "f2cdcd",
         "pink": "f5c2e7", "mauve": "cba6f7", "red": "f38ba8", "maroon": "eba0ac",
         "peach": "fab387", "yellow": "f9e2af", "green": "a6e3a1", "teal": "94e2d5",
         "sky": "89dceb", "sapphire": "74c7ec", "blue": "89b4fa", "lavender": "b4befe"}
LATTE = {"base": "eff1f5", "mantle": "e6e9ef", "crust": "dce0e8", "surface0": "ccd0da",
         "surface1": "bcc0cc", "surface2": "acb0be", "overlay0": "9ca0b0", "overlay1": "8c8fa1",
         "subtext0": "6c6f85", "text": "4c4f69", "rosewater": "dc8a78", "flamingo": "dd7878",
         "pink": "ea76cb", "mauve": "8839ef", "red": "d20f39", "maroon": "e64553",
         "peach": "fe640b", "yellow": "df8e1d", "green": "40a02b", "teal": "179299",
         "sky": "04a5e5", "sapphire": "209fb5", "blue": "1e66f5", "lavender": "7287fd"}
# The accent colours a model can take, in slot order. A model's slot comes from its hash.
ACCENTS = ["mauve", "sky", "peach", "green", "pink", "yellow", "teal", "lavender", "maroon",
           "sapphire", "flamingo", "blue"]


class Theme:
    """A palette as RGB tuples, one attribute per colour name, plus the accents in order."""

    def __init__(self, palette: Dict[str, str]):
        for name, hexv in palette.items():
            setattr(self, name, (int(hexv[0:2], 16), int(hexv[2:4], 16), int(hexv[4:6], 16)))
        self.accents: List[RGB] = [getattr(self, a) for a in ACCENTS]

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
