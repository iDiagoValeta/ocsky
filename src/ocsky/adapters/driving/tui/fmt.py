"""Numbers, money and durations as text, in the conventions of each interface language."""
from __future__ import annotations


def _decimal(text: str, lang: str) -> str:
    """Spanish writes the decimal point as a comma."""
    return text.replace(".", ",") if lang == "es" else text


def fmt_tokens(n: int, lang: str) -> str:
    """A token count: 999, 412k, 1.2M (es: 412 k, 1,2 M)."""
    es = lang == "es"
    if n >= 1_000_000:
        return _decimal(f"{n / 1e6:.1f}", lang) + (" M" if es else "M")
    if n >= 1000:
        k = round(n / 1000)
        return f"{k} k" if es else f"{k}k"
    return str(n)


def fmt_cost(c: float, lang: str) -> str:
    """A cost in dollars: $0.31, free, <$0.01 (es: 0,31 $, gratis, <0,01 $)."""
    if c == 0:
        return "gratis" if lang == "es" else "free"
    if c < 0.005:
        return "<0,01 $" if lang == "es" else "<$0.01"
    if lang == "es":
        return _decimal(f"{c:.2f}", lang) + " $"
    return f"${c:.2f}"


def fmt_age(ms: int, lang: str) -> str:
    """An age or duration in milliseconds: 5s, 12m, 3h 05m, 2d (es: 5 s, 12 min, 3 h 05, 2 d)."""
    s = max(0, ms // 1000)
    if lang == "es":
        if s < 60:
            return f"{s} s"
        if s < 3600:
            return f"{s // 60} min"
        if s < 86400:
            return f"{s // 3600} h {s % 3600 // 60:02d}"
        return f"{s // 86400} d"
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m"
    if s < 86400:
        return f"{s // 3600}h {s % 3600 // 60:02d}m"
    return f"{s // 86400}d"
