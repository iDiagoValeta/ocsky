"""Every symbol the interface draws, and the helpers that turn what a session does into an icon and a line."""
from __future__ import annotations

from typing import Tuple

from ocsky.adapters.driving.tui.i18n import Tr
from ocsky.core.model import Activity, Session

TOOL_ICONS = {
    "read": "◫", "write": "✎", "edit": "✎", "patch": "✎", "multiedit": "✎", "apply_patch": "✎",
    "bash": "❯", "shell": "❯", "grep": "⌕", "glob": "⌕", "list": "⌕", "ls": "⌕",
    "webfetch": "⇄", "websearch": "⇄", "fetch": "⇄", "task": "⇢", "subagent": "⇢", "todowrite": "☰",
    "todoread": "☰", "skill": "✧", "question": "?",
}
ACTIVITY_ICONS = {"reasoning": "∴", "text": "✦", "user": "»", "idle": "◦", "compaction": "◌", "other": "·"}
DEFAULT_TOOL_ICON = "⚙"

SPARK = " ▁▂▃▄▅▆▇█"
SPINNER = "◜◠◝◞◡◟"
SUBAGENT = "↳"
REPEAT = "×"  # before the count of identical steps folded into one line

# Frame and layout pieces.
SELECTION_BAR = "▌"
DIVIDER = "│"
RULE = "─"
CARET = "▍"
BAR_FULL, BAR_EMPTY = "━", "─"
BOX = ("╭", "╮", "╰", "╯")

# Session states, as drawn in the list. A compacting session cycles through its frames.
GLYPH_WORKING, GLYPH_WAITING, GLYPH_STALLED = "●", "◉", "◍"
GLYPH_COMPACTING = "◌◍●◍"
GLYPH_FAILED, GLYPH_INTERRUPTED, GLYPH_SUSPENDED, GLYPH_DONE = "✕", "◑", "‖", "○"

# Header, clock and starfield.
LOGO = "✦"
PROC_ICON = "⚡"
STAR_FAINT, STAR_DIM, STAR_BRIGHT = "·", "⋅", "✧"
HEAD_ON, HEAD_OFF = "✦", "✧"
LEGEND_ACTIVE, LEGEND_IDLE = "◍", "○"


def tool_icon(name: str) -> str:
    """The icon of a tool. Plugins name tools like "server.read", so only the last part counts."""
    return TOOL_ICONS.get(name.split(".")[-1].lower(), DEFAULT_TOOL_ICON)


def activity_line(act: Activity, tr: Tr) -> Tuple[str, str]:
    """(icon, text) of one thing a session did."""
    if act.kind == "tool":
        text = (act.tool + " " + act.detail).strip()
        if act.status == "running":
            text += " …"
        elif act.status == "error":
            text += " ✕"
        return tool_icon(act.tool), text
    if act.kind == "user":
        return ACTIVITY_ICONS["user"], tr("act.you", text=act.detail)
    if act.kind == "idle":
        return ACTIVITY_ICONS["idle"], tr("act.finished", outcome=act.outcome or tr("act.no_outcome"))
    if act.kind == "compaction":
        return ACTIVITY_ICONS["compaction"], tr("act.compaction")
    return ACTIVITY_ICONS.get(act.kind, ACTIVITY_ICONS["other"]), act.detail


# Tools that hand work to a subagent (opencode 1 calls it task, opencode 2 subagent).
DELEGATING_TOOLS = ("task", "subagent")


def doing_line(session: Session, tr: Tr) -> Tuple[str, str]:
    """(icon, text) of what the session is doing now, as the list shows it."""
    act = session.activity
    if act is None:
        return ACTIVITY_ICONS["reasoning"], tr("act.thinking")
    if act.kind == "user":
        return ACTIVITY_ICONS["reasoning"], tr("act.reading_request", text=act.detail)
    if act.kind == "idle":
        return ACTIVITY_ICONS["idle"], tr("act.idle")
    running = sum(1 for c in session.children if c.working)
    if act.kind == "tool" and act.tool.split(".")[-1].lower() in DELEGATING_TOOLS and running:
        # The subagents are listed right below: naming the one just launched would say it twice.
        return tool_icon(act.tool), tr("act.delegating_one" if running == 1 else "act.delegating", n=running)
    return activity_line(act, tr)

# Key names shown in the footer and in the help box.
KEY_UPDOWN, KEY_ENTER, KEY_TAB, KEY_ESC = "↑↓", "⏎", "tab", "esc"
