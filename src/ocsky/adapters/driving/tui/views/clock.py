"""The 24 hour clock: every session of the last day as an arc on the orbit of its model."""
from __future__ import annotations

import math
import time
from typing import TYPE_CHECKING, Dict, List, Tuple

from ocsky.adapters.driving.tui import icons
from ocsky.adapters.driving.tui.canvas import RGB, Braille, Canvas, mix
from ocsky.adapters.driving.tui.fmt import fmt_age
from ocsky.adapters.driving.tui.text import fit, short_dir, text_width
from ocsky.adapters.driving.tui.views.common import clock_text, phase_of
from ocsky.core.model import Session

if TYPE_CHECKING:
    from ocsky.adapters.driving.tui.app import App

LEGEND_MIN_COLS = 110
LEGEND_W = 44
DAY_MS = 86_400_000
RING_MODELS = 8
HOUR_LABELS = (0, 6, 12, 18)


def hints(app: App) -> List[Tuple[str, str]]:
    tr = app.tr
    return [("?", tr("key.help")), (icons.KEY_TAB, tr("key.sky")), ("r", tr("key.range")),
            ("q", tr("key.quit"))]


def _angle(ms: float) -> float:
    """Where a moment sits on the dial: 0 h at the top, clockwise, local time."""
    lt = time.localtime(ms / 1000)
    secs = lt.tm_hour * 3600 + lt.tm_min * 60 + lt.tm_sec + (ms % 1000) / 1000
    return secs / 86400 * 2 * math.pi - math.pi / 2


def _draw_dial(br: Braille, app: App, cx: float, cy: float, radius: float) -> None:
    th = app.theme
    for i in range(720):
        a = i / 720 * 2 * math.pi
        br.dot(cx + radius * math.cos(a), cy + radius * math.sin(a), th.surface1)
    for hr in range(24):
        a = hr / 24 * 2 * math.pi - math.pi / 2
        for r in (radius + 1, radius + 2) if hr % 6 else (radius + 1, radius + 2, radius + 3):
            br.dot(cx + r * math.cos(a), cy + r * math.sin(a), th.overlay1 if hr % 6 else th.text)


def _draw_rings(br: Braille, app: App, rings: Dict[str, float], cx: float, cy: float) -> None:
    th = app.theme
    for model, r in rings.items():
        col = mix(app.model_colors.get(model, th.overlay0), th.base, 0.75)
        for i in range(int(r * 4)):
            if i % 6 == 0:
                a = i / (r * 4) * 2 * math.pi
                br.dot(cx + r * math.cos(a), cy + r * math.sin(a), col)


def _draw_arcs(br: Braille, app: App, rings: Dict[str, float], cx: float, cy: float
               ) -> List[Tuple[float, float, RGB, Session]]:
    """Dots of every session arc. Returns the head of each working one, for the twinkle."""
    th, now = app.theme, app.now_ms
    heads = []
    for s in sorted(app.snapshot.sessions, key=lambda s: s.created):
        if s.model not in rings or s.updated < now - DAY_MS:
            continue
        r = rings[s.model] + (int(phase_of(s.id) * 16) % 3 - 1) * 1.5  # a little spread inside the orbit
        start = max(s.busy or s.created, now - DAY_MS)
        end = now if s.working else max(s.idle or s.updated, start + 60_000)
        a0 = _angle(start)
        span = max((end - start) / DAY_MS * 2 * math.pi, 0.06)  # a two-minute session still reads as an arc
        col = app.model_color(s)
        if not s.working:
            col = mix(col, th.base, 0.35)
        steps = max(2, int(span * r * 1.2))
        for i in range(steps + 1):
            a = a0 + span * i / steps
            for dr in (-0.8, 0.8):  # two dots thick
                br.dot(cx + (r + dr) * math.cos(a), cy + (r + dr) * math.sin(a), col)
        if s.working:
            heads.append((a0 + span, r, app.model_color(s), s))
    return heads


def _draw_hand(br: Braille, app: App, cx: float, cy: float, radius: float) -> None:
    th = app.theme
    an = _angle(app.now_ms)
    for i in range(0, int(radius), 2):
        br.dot(cx + i * math.cos(an), cy + i * math.sin(an), mix(th.surface2, th.base, i / radius * 0.5))


def _draw_labels(cv: Canvas, app: App, cx: float, cy: float, radius: float, area_w: int) -> None:
    th, tr = app.theme, app.tr
    for hr in HOUR_LABELS:
        a = hr / 24 * 2 * math.pi - math.pi / 2
        label = str(hr)
        px, py = cx + (radius + 9) * math.cos(a), cy + (radius + 9) * math.sin(a)
        lx = 1 + int(px / 2) - len(label) // 2
        cv.put(max(1, min(area_w - len(label), lx)), 2 + int(py / 4), label, th.subtext0)
    ccx, ccy = 1 + int(cx / 2), 2 + int(cy / 4)
    hhmm = clock_text(app.now_ms)
    cv.put(ccx - len(hhmm) // 2, ccy - 1, hhmm, th.text, bold=True)
    active = sum(1 for s in app.snapshot.sessions if s.working)
    sub = tr("clock.active", n=active)
    cv.put(ccx - len(sub) // 2, ccy, sub, th.green if active else th.overlay1)
    x = cv.put(1, 1, tr("clock.title"), th.overlay1, bold=True)
    cv.put(x + 2, 1, tr("clock.subtitle"), th.overlay0)


def draw(cv: Canvas, app: App, t: float) -> None:
    th = app.theme
    legend_w = LEGEND_W if cv.w >= LEGEND_MIN_COLS else 0
    area_w, area_h = cv.w - legend_w - 2, cv.h - 3
    radius = min(area_w * 2, area_h * 4) / 2 - 10  # room outside the dial for the hour labels
    cx, cy = area_w, area_h * 2
    br = Braille(area_w, area_h)
    names = [u.model for u in app.snapshot.models][:RING_MODELS] or [""]
    rings = {m: radius * (0.3 + 0.62 * (i + 1) / len(names)) for i, m in enumerate(names)}
    _draw_dial(br, app, cx, cy, radius)
    _draw_rings(br, app, rings, cx, cy)
    heads = _draw_arcs(br, app, rings, cx, cy)
    _draw_hand(br, app, cx, cy, radius)
    br.blit(cv, 1, 2)
    for a, r, col, s in heads:  # twinkling heads of agents working now
        k = 0.5 + 0.5 * math.sin(t * 5 + phase_of(s.id))
        px, py = cx + r * math.cos(a), cy + r * math.sin(a)
        cv.put(1 + int(px / 2), 2 + int(py / 4), icons.HEAD_ON if k > 0.5 else icons.HEAD_OFF,
               mix(col, th.text, k * 0.6), bold=True)
    _draw_labels(cv, app, cx, cy, radius, area_w)
    if legend_w:
        draw_legend(cv, app, cv.w - legend_w, 2, legend_w - 1, cv.h - 3, t)


def _legend_models(cv: Canvas, app: App, x0: int, y: int, w: int) -> int:
    th, tr = app.theme, app.tr
    cv.put(x0, y, tr("clock.models"), th.overlay1, bold=True)
    y += 1
    for u in app.snapshot.models[:RING_MODELS]:
        col = app.model_colors.get(u.model, th.text)
        x = cv.put(x0, y, (icons.LEGEND_ACTIVE if u.active else icons.LEGEND_IDLE) + " ", col,
                   bold=bool(u.active))
        cv.put(x, y, fit(u.model, w - 12), col)
        cv.put(x0 + w - 9, y, tr("clock.sessions", n=u.sessions).rjust(8), th.subtext0)
        y += 1
    return y


def _legend_procs(cv: Canvas, app: App, x0: int, y: int, w: int, h: int, t: float) -> int:
    th, tr = app.theme, app.tr
    cv.put(x0, y, tr("clock.procs"), th.overlay1, bold=True)
    y += 1
    procs = app.snapshot.procs
    if not procs:
        cv.put(x0, y, tr("clock.no_procs"), th.overlay0)
        y += 1
    for p in procs[: max(0, h // 2 - 3)]:
        k = 0.5 + 0.5 * math.sin(t * 3 + p.pid)
        x = cv.put(x0, y, icons.PROC_ICON + " ", mix(th.yellow, th.peach, k))
        x = cv.put(x, y, "%-6s" % p.mode, th.text)
        age = fmt_age(app.now_ms - int(p.started * 1000), tr.lang)
        cv.put(x, y, fit(" " + tr("clock.proc", pid=p.pid, mb=int(p.rss_mb), age=age), x0 + w - x),
               th.subtext0)
        cv.put(x0 + 3, y + 1, short_dir(p.cwd, w - 3, app.home), th.overlay0)
        y += 2
    return y


def draw_legend(cv: Canvas, app: App, x0: int, y0: int, w: int, h: int, t: float) -> None:
    """Models in ring order, running processes and what is working now."""
    th, tr = app.theme, app.tr
    y = _legend_models(cv, app, x0, y0, w) + 1
    y = _legend_procs(cv, app, x0, y, w, h, t) + 1
    cv.put(x0, y, tr("clock.now"), th.overlay1, bold=True)
    y += 1
    busy = [s for s in app.snapshot.sessions if s.working]
    if not busy:
        cv.put(x0, y, tr("clock.nobody"), th.overlay0)
    shown = busy[: max(0, y0 + h - y)]
    # The sky names sessions by title, so this list does too; titles take at most half the legend.
    title_w = min(w // 2 - 2, max((text_width(s.title or s.slug) for s in shown), default=0))
    for s in shown:
        col = app.model_color(s)
        x = cv.put(x0, y, icons.LOGO + " ", col)
        cv.put(x, y, fit(s.title or s.slug, title_w), col, bold=True)
        x += title_w + 1
        icon, text = icons.doing_line(s, tr)
        cv.put(x, y, fit(icon + " " + text, x0 + w - x), th.subtext0)
        y += 1
