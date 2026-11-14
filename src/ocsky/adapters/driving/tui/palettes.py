"""The palettes the interface can wear, each from its project's own published colours.

Every palette is written in Catppuccin's names, since the views ask for colours by those names.
A palette that has no colour for a name either reuses its nearest official colour or leaves the
name out; Theme then blends the missing neutrals from the ones it has. Sources:

  Catppuccin       github.com/catppuccin/palette (palette.json)
  Dracula, Alucard draculatheme.com/spec
  Gruvbox          github.com/morhetz/gruvbox (colors/gruvbox.vim)
  Nord             github.com/nordtheme/nord (src/nord.css)
  Rosé Pine        github.com/rose-pine/palette and rose-pine/neovim (the highlight colours)
  Solarized        github.com/altercation/solarized (README)
  Tokyo Night      github.com/folke/tokyonight.nvim (colors/night.lua over storm.lua)
"""
from __future__ import annotations

from typing import Dict, NamedTuple


class Palette(NamedTuple):
    label: str
    pair: str  # the palette the `t` key switches to: the same family on the other side of the day
    colors: Dict[str, str]


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
DRACULA = {"base": "282a36", "mantle": "21222c", "crust": "191a21", "surface0": "44475a",
           "surface1": "424450", "surface2": "6272a4", "overlay0": "6272a4", "text": "f8f8f2",
           "rosewater": "ffb86c", "flamingo": "ff92df", "pink": "ff79c6", "mauve": "bd93f9",
           "red": "ff5555", "maroon": "ff6e6e", "peach": "ffb86c", "yellow": "f1fa8c",
           "green": "50fa7b", "teal": "69ff94", "sky": "8be9fd", "sapphire": "a4ffff",
           "blue": "d6acff", "lavender": "bd93f9"}
ALUCARD = {"base": "fffbeb", "mantle": "efeddc", "crust": "dedccf", "surface0": "cfcfde",
           "surface1": "cecccf", "surface2": "bcbab3", "overlay0": "6c664b", "text": "1f1f1f",
           "rosewater": "a34d14", "flamingo": "bf185a", "pink": "a3144d", "mauve": "644ac9",
           "red": "cb3a2a", "maroon": "d74c3d", "peach": "a34d14", "yellow": "846e15",
           "green": "14710a", "teal": "198d0c", "sky": "036a96", "sapphire": "047fb4",
           "blue": "7862d0", "lavender": "7862d0"}
GRUVBOX_DARK = {"base": "282828", "mantle": "1d2021", "crust": "1d2021", "surface0": "3c3836",
                "surface1": "504945", "surface2": "665c54", "overlay0": "7c6f64", "overlay1": "928374",
                "subtext0": "a89984", "text": "ebdbb2", "rosewater": "fabd2f", "flamingo": "d65d0e",
                "pink": "b16286", "mauve": "d3869b", "red": "fb4934", "maroon": "cc241d",
                "peach": "fe8019", "yellow": "fabd2f", "green": "b8bb26", "teal": "689d6a",
                "sky": "8ec07c", "sapphire": "458588", "blue": "83a598", "lavender": "83a598"}
GRUVBOX_LIGHT = {"base": "fbf1c7", "mantle": "ebdbb2", "crust": "d5c4a1", "surface0": "d5c4a1",
                 "surface1": "bdae93", "surface2": "a89984", "overlay0": "928374", "overlay1": "7c6f64",
                 "subtext0": "665c54", "text": "3c3836", "rosewater": "b57614", "flamingo": "d65d0e",
                 "pink": "b16286", "mauve": "8f3f71", "red": "9d0006", "maroon": "cc241d",
                 "peach": "af3a03", "yellow": "b57614", "green": "79740e", "teal": "427b58",
                 "sky": "076678", "sapphire": "689d6a", "blue": "458588", "lavender": "458588"}
NORD = {"base": "2e3440", "mantle": "3b4252", "crust": "3b4252", "surface0": "434c5e",
        "surface1": "4c566a", "surface2": "4c566a", "text": "d8dee9", "rosewater": "ebcb8b",
        "flamingo": "d08770", "pink": "b48ead", "mauve": "b48ead", "red": "bf616a",
        "maroon": "bf616a", "peach": "d08770", "yellow": "ebcb8b", "green": "a3be8c",
        "teal": "8fbcbb", "sky": "88c0d0", "sapphire": "81a1c1", "blue": "5e81ac",
        "lavender": "81a1c1"}
ROSE_PINE = {"base": "191724", "mantle": "1f1d2e", "crust": "26233a", "surface0": "26233a",
             "surface1": "403d52", "surface2": "524f67", "overlay0": "6e6a86", "subtext0": "908caa",
             "text": "e0def4", "rosewater": "ebbcba", "flamingo": "ebbcba", "pink": "eb6f92",
             "mauve": "c4a7e7", "red": "eb6f92", "maroon": "eb6f92", "peach": "ebbcba",
             "yellow": "f6c177", "green": "9ccfd8", "teal": "31748f", "sky": "9ccfd8",
             "sapphire": "31748f", "blue": "31748f", "lavender": "c4a7e7"}
ROSE_PINE_DAWN = {"base": "faf4ed", "mantle": "f2e9e1", "crust": "fffaf3", "surface0": "dfdad9",
                  "surface1": "dfdad9", "surface2": "cecacd", "overlay0": "9893a5", "subtext0": "797593",
                  "text": "464261", "rosewater": "d7827e", "flamingo": "d7827e", "pink": "b4637a",
                  "mauve": "907aa9", "red": "b4637a", "maroon": "b4637a", "peach": "d7827e",
                  "yellow": "ea9d34", "green": "56949f", "teal": "286983", "sky": "56949f",
                  "sapphire": "286983", "blue": "286983", "lavender": "907aa9"}
_SOLARIZED_ACCENTS = {"rosewater": "b58900", "flamingo": "d33682", "pink": "d33682", "mauve": "6c71c4",
                      "red": "dc322f", "maroon": "dc322f", "peach": "cb4b16", "yellow": "b58900",
                      "green": "859900", "teal": "2aa198", "sky": "2aa198", "sapphire": "268bd2",
                      "blue": "268bd2", "lavender": "6c71c4"}
SOLARIZED_DARK = dict({"base": "002b36", "mantle": "073642", "crust": "073642", "surface0": "073642",
                       "surface2": "586e75", "overlay0": "586e75", "overlay1": "657b83",
                       "subtext0": "839496", "text": "93a1a1"}, **_SOLARIZED_ACCENTS)
SOLARIZED_LIGHT = dict({"base": "fdf6e3", "mantle": "eee8d5", "crust": "eee8d5", "surface0": "eee8d5",
                        "surface2": "93a1a1", "overlay0": "93a1a1", "overlay1": "839496",
                        "subtext0": "657b83", "text": "586e75"}, **_SOLARIZED_ACCENTS)
TOKYO_NIGHT = {"base": "1a1b26", "mantle": "16161e", "crust": "0c0e14", "surface0": "292e42",
               "surface1": "3b4261", "surface2": "414868", "overlay0": "565f89", "overlay1": "737aa2",
               "subtext0": "a9b1d6", "text": "c0caf5", "rosewater": "e0af68", "flamingo": "f7768e",
               "pink": "ff007c", "mauve": "bb9af7", "red": "f7768e", "maroon": "db4b4b",
               "peach": "ff9e64", "yellow": "e0af68", "green": "9ece6a", "teal": "73daca",
               "sky": "7dcfff", "sapphire": "2ac3de", "blue": "7aa2f7", "lavender": "9d7cd8"}

# In the order the palette menu lists them within each side (dark, then light).
PALETTES: Dict[str, Palette] = {
    "catppuccin-mocha": Palette("Catppuccin Mocha", "catppuccin-latte", MOCHA),
    "dracula": Palette("Dracula", "alucard", DRACULA),
    "gruvbox-dark": Palette("Gruvbox Dark", "gruvbox-light", GRUVBOX_DARK),
    "nord": Palette("Nord", "catppuccin-latte", NORD),
    "rose-pine": Palette("Rosé Pine", "rose-pine-dawn", ROSE_PINE),
    "solarized-dark": Palette("Solarized Dark", "solarized-light", SOLARIZED_DARK),
    "tokyo-night": Palette("Tokyo Night", "catppuccin-latte", TOKYO_NIGHT),
    "catppuccin-latte": Palette("Catppuccin Latte", "catppuccin-mocha", LATTE),
    "alucard": Palette("Alucard", "dracula", ALUCARD),
    "gruvbox-light": Palette("Gruvbox Light", "gruvbox-dark", GRUVBOX_LIGHT),
    "rose-pine-dawn": Palette("Rosé Pine Dawn", "rose-pine", ROSE_PINE_DAWN),
    "solarized-light": Palette("Solarized Light", "solarized-dark", SOLARIZED_LIGHT),
}
DARK, LIGHT = "catppuccin-mocha", "catppuccin-latte"
