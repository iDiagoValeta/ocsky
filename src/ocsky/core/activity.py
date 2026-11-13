"""Turns the parts and messages of a session into Activity objects. Pure functions.

The text of an activity is kept as it is in the store (cleaned of control characters), so the
interface can translate the kind and the tool name into its own language and icons.
"""
from __future__ import annotations

import unicodedata

from ocsky.core.model import Activity, Message

# Argument names that carry the most useful one-line summary of a tool call, in priority order.
TOOL_KEYS = ("command", "filePath", "file_path", "path", "pattern", "query", "url",
             "description", "prompt", "subagent_type")


def clean(text: str) -> str:
    """One line of text: control characters dropped, every run of white space made a single space."""
    out = []
    for ch in text or "":
        if ch in "\n\r\t":
            out.append(" ")
        elif ord(ch) >= 32 and ord(ch) != 127 and unicodedata.category(ch) not in ("Cc", "Cf"):
            out.append(ch)
    return " ".join("".join(out).split())


def relative(path: str, directory: str, home: str) -> str:
    """A path relative to the session directory, or with the home directory written as ~."""
    # Compare with backslashes read as slashes, but return the rest of the path as it was written.
    flat, base = path.replace("\\", "/"), directory.replace("\\", "/").rstrip("/")
    if directory and flat.startswith(base + "/"):
        return path[len(base) + 1:]
    if home and path.startswith(home):
        return path.replace(home, "~", 1)
    return path


def describe_part(part: dict, directory: str, home: str) -> Activity:
    """What one content part of an assistant message says the session is doing."""
    kind = part.get("type")
    if kind == "reasoning":
        return Activity("reasoning", detail=clean(part.get("text", "")))
    if kind == "text":
        return Activity("text", detail=clean(part.get("text", "")))
    if kind == "tool":
        name = part.get("name") or part.get("tool") or "tool"
        state = part.get("state") or {}
        args = state.get("input") or part.get("input") or {}
        detail = ""
        if isinstance(args, dict):
            for key in TOOL_KEYS:
                val = args.get(key)
                if isinstance(val, str) and val:
                    pathlike = ("/" in val or "\\" in val) and key != "command"
                    detail = relative(val, directory, home) if pathlike else val
                    break
            else:
                for val in args.values():
                    if isinstance(val, str):
                        detail = val
                        break
        if isinstance(args, dict) and isinstance(args.get("offset"), int):
            detail += f" :{args['offset']}"  # which chunk of the file it is reading
        status = state.get("status")
        if status == "error":
            mark = "error"
        elif status in ("running", "pending"):
            mark = "running"
        else:
            mark = ""
        return Activity("tool", tool=name, detail=clean(detail), status=mark)
    return Activity("other", detail=kind or "")


def describe_message(msg: Message, directory: str, home: str) -> list[Activity]:
    """The activities of one message: one per content part of an assistant message."""
    if msg.type == "user":
        return [Activity("user", detail=clean(msg.data.get("text", "")))]
    if msg.type == "compaction":
        return [Activity("compaction")]
    if msg.type == "idle":
        return [Activity("idle", outcome=msg.data.get("outcome") or "")]
    if msg.type == "assistant":
        parts = msg.data.get("content") or []
        if not isinstance(parts, list):
            return []
        return [describe_part(p, directory, home) for p in parts]
    return []
