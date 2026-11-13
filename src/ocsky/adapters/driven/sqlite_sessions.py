"""opencode's database as a ForReadingSessions adapter. Read only.

The connection is opened with mode=ro, so SQLite itself refuses every write. Only the tables
session_v2 and session_message are ever named here.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import urllib.parse
from typing import Callable, List, Mapping, Optional, Tuple

from ocsky.core.activity import clean
from ocsky.core.model import Message, Session
from ocsky.core.ports.for_reading_sessions import StoreUnavailable

DAY_MS = 86_400_000
# A session still marked busy is kept for a week, however old its last update is.
BUSY_LOOKBACK_MS = 7 * DAY_MS
SESSION_LIMIT = 400

SESSION_COLUMNS = (
    "id,parent_id,slug,title,agent,model,directory,cost,tokens_input,tokens_output,"
    "tokens_reasoning,tokens_cache_read,time_created,time_updated,time_busy,time_idle,"
    "idle_outcome,time_compacting,time_suspended"
)


def default_db(environ: Mapping[str, str], home: str, platform: str = "linux",
               exists: Callable[[str], bool] = os.path.exists) -> str:
    """opencode keeps its data under XDG_DATA_HOME, ~/.local/share by default, macOS included.

    Where opencode keeps it on Windows is not known, so there the first candidate that exists wins:
    XDG_DATA_HOME, %LOCALAPPDATA%, %APPDATA%, then the XDG default. None existing gives the last one.
    """
    xdg = environ.get("XDG_DATA_HOME")
    fallback = os.path.join(home, ".local", "share", "opencode", "opencode.db")
    if not platform.startswith("win"):
        return os.path.join(xdg, "opencode", "opencode.db") if xdg else fallback
    candidates = [os.path.join(base, "opencode", "opencode.db")
                  for base in (xdg, environ.get("LOCALAPPDATA"), environ.get("APPDATA")) if base]
    candidates.append(fallback)
    return next((c for c in candidates if exists(c)), candidates[-1])


def parse_model(raw: Optional[str]) -> str:
    """"provider/id" from opencode's JSON model column. "" when empty, the raw text when not JSON."""
    if not raw:
        return ""
    try:
        model = json.loads(raw)
    except (ValueError, TypeError):
        return str(raw)
    if not isinstance(model, dict):
        return str(raw)
    return "%s/%s" % (model.get("providerID", "?"), model.get("id", "?"))


def _uri(path: str) -> str:
    """A read-only SQLite URI for a file path. Spaces, '?' and '#' are quoted; Windows drives work."""
    p = path.replace("\\", "/")
    if re.match(r"^[A-Za-z]:", p):
        p = "/" + p  # file:/C:/... is the form SQLite expects for a drive letter
    return "file:%s?mode=ro" % urllib.parse.quote(p, safe="/:")


def _session(row: Tuple) -> Session:
    (sid, parent, slug, title, agent, model, directory, cost, tokens_in, tokens_out,
     tokens_reasoning, tokens_cache, created, updated, busy, idle, outcome, compacting,
     suspended) = row
    return Session(
        id=sid, parent=parent, slug=slug or sid[-6:], title=clean(title or ""),
        agent=agent or "build", model=parse_model(model), directory=directory or "",
        cost=cost or 0.0, tokens_in=tokens_in or 0, tokens_out=tokens_out or 0,
        tokens_reasoning=tokens_reasoning or 0, tokens_cache=tokens_cache or 0,
        created=created, updated=updated, busy=busy, idle=idle, outcome=outcome,
        compacting=compacting, suspended=suspended,
    )


class SqliteSessions:
    """ForReadingSessions over opencode's SQLite database. Opens lazily and reconnects after a failure."""

    def __init__(self, path: str):
        self._path = path
        self._db: Optional[sqlite3.Connection] = None

    def conn(self) -> sqlite3.Connection:
        if self._db is None:
            self._db = sqlite3.connect(_uri(self._path), uri=True, timeout=2)
        return self._db

    def _query(self, sql: str, params: Tuple = ()) -> List[Tuple]:
        try:
            return self.conn().execute(sql, params).fetchall()
        except sqlite3.Error as e:
            self._drop()
            raise StoreUnavailable(str(e)) from e

    def close(self) -> None:
        """Release the file. Safe to call twice; a later query reopens it."""
        self._drop()

    def _drop(self) -> None:
        db, self._db = self._db, None
        if db is not None:
            try:
                db.close()
            except sqlite3.Error:
                pass

    def sessions(self, since_ms: int, now_ms: int) -> List[Session]:
        rows = self._query(
            "select %s from session_v2 where time_archived is null and (time_updated > ? or "
            "(time_busy is not null and (time_idle is null or time_busy > time_idle) "
            "and time_updated > ?)) order by time_updated desc limit %d"
            % (SESSION_COLUMNS, SESSION_LIMIT),
            (since_ms, now_ms - BUSY_LOOKBACK_MS))
        return [_session(r) for r in rows]

    def messages(self, session_id: str, limit: int) -> List[Message]:
        rows = self._query(
            "select time_created,type,data from session_message where session_id=? "
            "and type in ('assistant','user','compaction','idle') order by seq desc limit ?",
            (session_id, limit))
        out: List[Message] = []
        for t, kind, raw in reversed(rows):
            try:
                data = json.loads(raw)
            except (ValueError, TypeError):
                continue
            if isinstance(data, dict):
                out.append(Message(t, kind, data))
        return out

    def pulse(self, session_ids: List[str], since_ms: int) -> List[Tuple[str, int, int]]:
        if not session_ids:
            return []
        marks = ",".join("?" * len(session_ids))
        rows = self._query(
            # json_extract, not ->>: the ->> operator needs SQLite 3.38, newer than some 3.9 builds.
            "select session_id,time_created,coalesce(json_extract(data,'$.tokens.output'),0)+"
            "coalesce(json_extract(data,'$.tokens.reasoning'),0) from session_message "
            "where type='assistant' and json_valid(data) and time_created > ? "
            "and session_id in (%s)" % marks,
            (since_ms, *session_ids))
        return [(sid, t, tokens) for sid, t, tokens in rows]
