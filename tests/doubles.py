"""In-memory doubles of the driven ports, plus small builders for sessions and messages."""
from __future__ import annotations

import dataclasses

from tests import helpers  # noqa: F401  (puts src/ on sys.path before ocsky is imported)
from ocsky.core.model import Message, Proc, Session
from ocsky.core.ports.for_reading_sessions import StoreUnavailable


class InMemorySessions:
    """ForReadingSessions over a fixed list of sessions and messages. Set `fail` to break it."""

    def __init__(self, sessions: list[Session], messages: dict[str, list[Message]] | None = None):
        self._sessions = list(sessions)
        self._messages = dict(messages or {})
        self.fail = False

    def _check(self) -> None:
        if self.fail:
            raise StoreUnavailable("the in-memory store is switched off")

    def sessions(self, since_ms: int, now_ms: int) -> list[Session]:
        self._check()
        picked = [s for s in self._sessions if s.updated > since_ms]
        picked.sort(key=lambda s: s.updated, reverse=True)
        # Fresh copies, so that classify and build_rows never leak state between calls.
        return [dataclasses.replace(s, children=[], pulse=[]) for s in picked]

    def messages(self, session_id: str, limit: int) -> list[Message]:
        self._check()
        msgs = self._messages.get(session_id, [])
        return list(msgs[max(0, len(msgs) - limit):])

    def pulse(self, session_ids: list[str], since_ms: int) -> list[tuple[str, int, int]]:
        self._check()
        out = []
        for sid in session_ids:
            for m in self._messages.get(sid, []):
                if m.type != "assistant" or m.time <= since_ms:
                    continue
                tokens = m.data.get("tokens") or {}
                out.append((sid, m.time, int(tokens.get("output", 0)) + int(tokens.get("reasoning", 0))))
        return out


class FixedProcesses:
    """ForListingProcesses that always reports the same processes."""

    def __init__(self, procs: list[Proc]):
        self._procs = list(procs)

    def processes(self) -> list[Proc]:
        return list(self._procs)


class FixedClock:
    """ForTellingTime with a settable `now`."""

    def __init__(self, now_ms: int):
        self.now = now_ms

    def now_ms(self) -> int:
        return self.now


class RecordingOpener:
    """ForOpeningSessions that remembers what it was asked to open."""

    def __init__(self):
        self.opened: list[Session] = []

    def open(self, session: Session) -> None:
        self.opened.append(session)


class RecordingClipboard:
    """ForCopyingText that remembers what was copied."""

    def __init__(self):
        self.copied: list[str] = []

    def copy(self, text: str) -> None:
        self.copied.append(text)


class MemoryPreferences:
    """ForKeepingPreferences backed by a dict."""

    def __init__(self, prefs: dict[str, str] | None = None):
        self.prefs = dict(prefs or {})

    def load(self) -> dict[str, str]:
        return dict(self.prefs)

    def save(self, prefs: dict[str, str]) -> None:
        self.prefs = dict(prefs)


def make_session(id: str, **overrides) -> Session:
    """A session with sensible defaults. Any field can be overridden by keyword."""
    values = dict(parent=None, title="", agent="build", model="deepseek/deepseek-flash",
                  directory="/work/app", cost=0.0, tokens_in=0, tokens_out=0, tokens_reasoning=0,
                  tokens_cache=0, created=1_000, updated=1_000, busy=None, idle=None, outcome=None,
                  compacting=None, suspended=None)
    values.update(overrides)
    return Session(id=id, **values)


def assistant_message(time: int, parts: list[dict], output: int = 0, reasoning: int = 0) -> Message:
    return Message(time, "assistant", {"content": list(parts),
                                       "tokens": {"output": output, "reasoning": reasoning}})


def user_message(time: int, text: str) -> Message:
    return Message(time, "user", {"text": text})


def idle_message(time: int, outcome: str) -> Message:
    return Message(time, "idle", {"outcome": outcome})
