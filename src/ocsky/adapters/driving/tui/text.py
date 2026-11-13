"""Terminal text measurement and cutting: cell widths, cleaning, fitting and wrapping."""
from __future__ import annotations

import unicodedata
from typing import List, Optional


def char_width(ch: str) -> int:
    """Terminal cells one character takes: 0 for combining marks, 2 for wide East Asian ones."""
    if unicodedata.combining(ch):
        return 0
    return 2 if unicodedata.east_asian_width(ch) in "WF" else 1


def clean(text: str) -> str:
    """Single-line text: control and format characters dropped, whitespace collapsed."""
    out = []
    for ch in text or "":
        if ch in "\n\r\t":
            out.append(" ")
        elif ord(ch) >= 32 and ord(ch) != 127 and unicodedata.category(ch) not in ("Cc", "Cf"):
            out.append(ch)
    return " ".join("".join(out).split())


def text_width(text: str) -> int:
    """Terminal cells the whole text takes."""
    return sum(char_width(c) for c in text)


def fit(text: str, width: int) -> str:
    """Cut text to width cells, ending with an ellipsis when it was longer."""
    if width <= 0:
        return ""
    if text_width(text) <= width:
        return text
    out, used = [], 0
    for ch in text:
        w = char_width(ch)
        if used + w > width - 1:
            break
        out.append(ch)
        used += w
    return "".join(out) + "…"


def wrap(text: str, width: int) -> List[str]:
    """Break cleaned text into lines of at most width cells, splitting words that are too long."""
    lines, line = [], ""
    for word in clean(text).split(" "):
        while text_width(word) > width:
            if line:
                lines.append(line)
                line = ""
            lines.append(fit(word, width))
            word = word[width - 1:]
        cand = (line + " " + word) if line else word
        if text_width(cand) <= width:
            line = cand
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def short_dir(d: str, width: int, home: str, max_parts: Optional[int] = None) -> str:
    """A directory shortened to width cells: home becomes ~, middle parts become an ellipsis.

    With max_parts, a path of more than max_parts + 1 components keeps only its last max_parts
    (`…/b/c/d`, or `~/…/b/c/d` under home), however much room there is. The width rule applies after.
    """
    d = d.replace(home, "~", 1) if home and d.startswith(home) else d
    if max_parts is not None:
        comps = [p for p in d.split("/") if p]
        if len(comps) > max_parts + 1:
            prefix = "~/…/" if d.startswith("~") else "…/"
            kept = comps[-max_parts:]
            while len(kept) > 1 and text_width(prefix + "/".join(kept)) > width:
                kept.pop(0)
            return fit(prefix + "/".join(kept), width)
    if text_width(d) <= width:
        return d
    parts = d.split("/")
    if len(parts) < 2:  # nothing to elide, e.g. a Windows path with backslashes
        return fit(d, width)
    tail = parts[-1]
    for p in reversed(parts[1:-1]):
        cand = p + "/" + tail
        if text_width(parts[0] + "/…/" + cand) > width:
            break
        tail = cand
    return fit(parts[0] + "/…/" + tail, width)
