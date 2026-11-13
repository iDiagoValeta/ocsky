"""The use case of the observatory: what the sessions look like right now. Pure orchestration.

It talks only to the ports. Every time and every directory it needs arrives as an argument or
through a port, so the same code runs against the real store and against the test doubles.
"""
from __future__ import annotations

from dataclasses import replace

from ocsky.core.activity import clean, describe_message
from ocsky.core.model import STALLED, Session, Snapshot, Step
from ocsky.core.ports.for_listing_processes import ForListingProcesses
from ocsky.core.ports.for_reading_sessions import ForReadingSessions, StoreUnavailable
from ocsky.core.ports.for_telling_time import ForTellingTime
from ocsky.core.states import classify
from ocsky.core.tree import build_rows, usage

# Twelve buckets of twenty five seconds: short enough that the bar of a session moves while you watch it.
PULSE_BUCKETS = 12
PULSE_WINDOW_MS = 5 * 60_000
# Sessions beyond the live and stalled ones that still get a pulse, so the list can show it.
OTHER_PULSE_LIMIT = 60
STORE_UNAVAILABLE = "store_unavailable"


class Observatory:
    def __init__(self, store: ForReadingSessions, processes: ForListingProcesses,
                 clock: ForTellingTime, home: str, here: str):
        self.store = store
        self.processes = processes
        self.clock = clock
        self.home = home
        self.here = here
        self._last: Snapshot | None = None
        self._traces: dict[str, list[Step]] = {}

    def observe(self, range_ms: int, only_active: bool, expanded: set[str]) -> Snapshot:
        now = self.clock.now_ms()
        try:
            sessions = self.store.sessions(now - range_ms, now)
            procs = self.processes.processes()
            classify(sessions, procs, now)
            visible = self._visible(sessions)
            window_start = now - PULSE_WINDOW_MS
            buckets = {s.id: [0] * PULSE_BUCKETS for s in visible}
            for sid, t, tokens in self.store.pulse([s.id for s in visible], window_start):
                if sid not in buckets:
                    continue
                i = int((t - window_start) * PULSE_BUCKETS / PULSE_WINDOW_MS)
                buckets[sid][min(PULSE_BUCKETS - 1, max(0, i))] += int(tokens or 0)
            for s in visible:
                s.pulse = buckets[s.id]
                if s.live or s.state == STALLED:
                    self._activity(s)
        except StoreUnavailable as e:
            if self._last is None:
                return Snapshot(sessions=[], rows=[], procs=[], models=[],
                                error=STORE_UNAVAILABLE, error_detail=str(e))
            return replace(self._last, error=STORE_UNAVAILABLE, error_detail=str(e))
        snap = Snapshot(sessions=sessions,
                        rows=build_rows(sessions, self.here, only_active, expanded),
                        procs=procs, models=usage(sessions))
        self._last = snap
        return snap

    def trace(self, session: Session, limit: int = 14) -> list[Step]:
        """The newest steps of one session, oldest first. Falls back to the last trace read."""
        try:
            msgs = self.store.messages(session.id, limit)
        except StoreUnavailable:
            return self._traces.get(session.id, [])
        steps = [Step(m.time, a) for m in msgs for a in describe_message(m, session.directory, self.home)]
        self._traces[session.id] = steps
        return steps

    @staticmethod
    def _is_primary(s: Session) -> bool:
        return s.live or s.state == STALLED

    def _visible(self, sessions: list[Session]) -> list[Session]:
        primary = [s for s in sessions if self._is_primary(s)]
        others = [s for s in sessions if not self._is_primary(s)][:OTHER_PULSE_LIMIT]
        return primary + others

    def _activity(self, s: Session) -> None:
        msgs = self.store.messages(s.id, 2)
        if not msgs:
            return
        last = msgs[-1]
        acts = describe_message(last, s.directory, self.home)
        if acts:
            s.activity = acts[-1]
        if last.type == "assistant":
            parts = last.data.get("content") or []
            if isinstance(parts, list):
                for p in reversed(parts):
                    if p.get("type") == "reasoning":
                        s.thought = clean(p.get("text", ""))
                        break
