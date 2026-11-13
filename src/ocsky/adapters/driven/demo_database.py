"""The demo database: two projects, a hunt in progress and some history. Used by --demo and the tests.

Every title and message is in English. The database is built on a new file only, so an existing
opencode database can never be overwritten by mistake.
"""
from __future__ import annotations

import itertools
import json
import os
import sqlite3
from typing import Any, Dict, Optional

DEMO_HERE = "/home/demo/bug-hunts/acme-parser/repo"
DEMO_HOME = "/home/demo"

MIN = 60_000
SHOP = "/home/demo/dev/shop-api"

SCHEMA = """
create table session_v2 (id text primary key, parent_id text, slug text not null, title text,
  agent text, model text, directory text not null, cost real default 0 not null,
  tokens_input integer default 0 not null, tokens_output integer default 0 not null,
  tokens_reasoning integer default 0 not null, tokens_cache_read integer default 0 not null,
  time_created integer not null, time_updated integer not null, time_busy integer,
  time_idle integer, idle_outcome text, time_compacting integer, time_suspended integer,
  time_archived integer);
create table session_message (id text primary key, session_id text not null, type text not null,
  seq integer not null, time_created integer not null, data text not null);
"""


def _model(provider: str, model_id: str) -> str:
    return json.dumps({"id": model_id, "providerID": provider})


def build_demo_db(path: str, now_ms: int) -> None:
    """Writes a new demo database at `path`. Refuses to touch a file that already exists."""
    if os.path.exists(path):
        raise FileExistsError(path)
    now = now_ms
    flash = _model("deepseek", "deepseek-flash")
    free = _model("opencode", "deepseek-v4.1-flash-free")
    qwen = _model("openrouter", "qwen3-coder")
    sonnet = _model("anthropic", "claude-sonnet-5-5")
    repo = DEMO_HERE

    db = sqlite3.connect(path)
    db.executescript(SCHEMA)
    seq = itertools.count(1)

    def session(sid: str, slug: str, title: str, agent: str, model: str, directory: str, *,
                created: int, updated: int, busy: Optional[int] = None, idle: Optional[int] = None,
                outcome: Optional[str] = None, parent: Optional[str] = None, cost: float = 0.0,
                tokens_in: int = 0, tokens_out: int = 0) -> None:
        db.execute("insert into session_v2 (id,parent_id,slug,title,agent,model,directory,cost,"
                   "tokens_input,tokens_output,time_created,time_updated,time_busy,time_idle,"
                   "idle_outcome) values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   (sid, parent, slug, title, agent, model, directory, cost, tokens_in, tokens_out,
                    created, updated, busy, idle, outcome))

    def msg(sid: str, kind: str, t: int, data: Dict[str, Any]) -> None:
        n = next(seq)
        db.execute("insert into session_message values (?,?,?,?,?,?)",
                   ("msg_%06d" % n, sid, kind, n, t, json.dumps(data)))

    def step(sid: str, t: int, out: int, *parts: Dict[str, Any]) -> None:
        msg(sid, "assistant", t, {"tokens": {"output": out, "reasoning": out // 2},
                                  "content": list(parts)})

    def tool(name: str, status: str = "completed", **args: object) -> Dict[str, Any]:
        return {"type": "tool", "name": name, "state": {"status": status, "input": args}}

    def think(text: str) -> Dict[str, Any]:
        return {"type": "reasoning", "text": text}

    # The hunt in the repo directory: an orchestrator, two hunters working, two finished hunters.
    session("ses_orc", "brave-orbit", "Hunt acme/parser: logic, security", "bh-orchestrator", flash,
            repo, created=now - 42 * MIN, updated=now - 5_000, busy=now - 42 * MIN,
            cost=0.31, tokens_in=412_000, tokens_out=38_000)
    session("ses_h1", "quiet-lynx", "Hunter H-003: src/tokenizer", "bh-hunter", free, repo,
            created=now - 9 * MIN, updated=now - 3_000, busy=now - 9 * MIN, parent="ses_orc",
            cost=0.0, tokens_in=96_000, tokens_out=11_000)
    session("ses_h2", "amber-heron", "Hunter H-004: src/escape", "bh-hunter", qwen, repo,
            created=now - 6 * MIN, updated=now - 20_000, busy=now - 6 * MIN, parent="ses_orc",
            cost=0.04, tokens_in=71_000, tokens_out=8_000)
    session("ses_h3", "calm-harbor", "Hunter H-001: src/lexer", "bh-hunter", flash, repo,
            created=now - 40 * MIN, updated=now - 31 * MIN, busy=now - 40 * MIN,
            idle=now - 31 * MIN, outcome="succeeded", parent="ses_orc",
            cost=0.05, tokens_in=120_000, tokens_out=14_000)
    session("ses_h4", "steady-falcon", "Hunter H-002: src/ast", "bh-hunter", flash, repo,
            created=now - 30 * MIN, updated=now - 22 * MIN, busy=now - 30 * MIN,
            idle=now - 22 * MIN, outcome="succeeded", parent="ses_orc",
            cost=0.04, tokens_in=98_000, tokens_out=9_000)
    session("ses_fail", "lucky-cactus", "Reproduce H-001-02", "bh-reproducer", free, repo,
            created=now - 3 * 60 * MIN, updated=now - 170 * MIN, busy=now - 3 * 60 * MIN,
            idle=now - 170 * MIN, outcome="failed", tokens_in=22_000, tokens_out=900)

    # Older history in other directories.
    session("ses_old", "sunny-nebula", "Probe the billing typecheck", "build", flash,
            "/home/demo/dev/billing", created=now - 26 * 60 * MIN, updated=now - 25 * MIN,
            busy=now - 26 * 60 * MIN, cost=0.02, tokens_in=135_000, tokens_out=6_000)
    session("ses_done", "happy-meadow", "Security audit of atlas", "revisor", flash,
            "/home/demo/bug-hunts/atlas/repo", created=now - 13 * 60 * MIN,
            updated=now - 12 * 60 * MIN, busy=now - 13 * 60 * MIN, idle=now - 12 * 60 * MIN,
            outcome="succeeded", cost=0.06, tokens_in=166_000, tokens_out=16_000)

    # The shop API: one working root with a working subagent, and one interrupted root.
    session("ses_shop", "keen-willow", "Add pagination to the orders endpoint", "build", sonnet, SHOP,
            created=now - 18 * MIN, updated=now - 8_000, busy=now - 18 * MIN, cost=0.12,
            tokens_in=210_000, tokens_out=15_000)
    session("ses_explore", "bright-otter", "Find where orders are queried", "explore", flash, SHOP,
            created=now - 5 * MIN, updated=now - 6_000, busy=now - 5 * MIN, parent="ses_shop",
            cost=0.01, tokens_in=54_000, tokens_out=4_000)
    session("ses_shop_old", "quiet-ember", "Fix flaky checkout test", "build", sonnet, SHOP,
            created=now - 3 * 60 * MIN, updated=now - 150 * MIN, busy=now - 3 * 60 * MIN,
            idle=now - 150 * MIN, outcome="interrupted", cost=0.07,
            tokens_in=143_000, tokens_out=11_000)

    # Messages. Times are kept in the same order as the steps happen.
    msg("ses_orc", "user", now - 42 * MIN,
        {"text": "Run the hunt on acme/parser with the logic and security scopes."})
    for i in range(12):
        step("ses_orc", now - (250 - 20 * i) * 1000, 300 + 170 * (i % 5),
             tool("bash", command="hunt.py loop --run demo"))
    step("ses_orc", now - 5_000, 900,
         think("Two hunters are working. H-003 has ticked 41 of 58 files; H-004 started six minutes "
               "ago. Next: wait for the loop to report a finished slot, then launch the debaters."),
         tool("task", description="Hunter H-004: src/escape", subagent_type="bh-hunter"))
    for i in range(8):
        step("ses_h1", now - (270 - 33 * i) * 1000, 500 + 260 * (i % 4),
             tool("read", filePath=repo + "/src/tokenizer.py", offset=1 + 150 * i))
    step("ses_h1", now - 3_000, 1400,
         think("The loop at line 212 stops at len(buf) - 1, so a closing quote in the last byte is "
               "never seen and the token runs to the end of input. Check the caller before writing it."),
         tool("grep", pattern="def read_string"))
    for i in range(5):
        step("ses_h2", now - (200 - 35 * i) * 1000, 400 + 300 * (i % 3),
             tool("read", filePath=repo + "/src/escape.py"))
    step("ses_h2", now - 20_000, 700,
         tool("edit", filePath="/home/demo/bug-hunts/acme-parser/notes/H-004.md"))
    msg("ses_h3", "idle", now - 31 * MIN, {"outcome": "succeeded"})
    msg("ses_h4", "idle", now - 22 * MIN, {"outcome": "succeeded"})
    msg("ses_fail", "idle", now - 170 * MIN, {"outcome": "failed"})

    step("ses_old", now - 25 * MIN, 80, tool("bash", command="pnpm -v"))
    msg("ses_done", "user", now - 13 * 60 * MIN, {"text": "Read-only security audit of atlas."})
    step("ses_done", now - 12 * 60 * MIN, 2000, {"type": "text", "text": "Two findings, both traced."})
    msg("ses_done", "idle", now - 12 * 60 * MIN, {"outcome": "succeeded"})

    msg("ses_shop", "user", now - 18 * MIN,
        {"text": "Add cursor pagination to GET /orders and keep the existing filters."})
    step("ses_shop", now - 4 * MIN, 600,
         tool("read", filePath=SHOP + "/src/orders/routes.ts"))
    step("ses_shop", now - 2 * MIN, 900,
         tool("read", filePath=SHOP + "/src/orders/repository.ts", offset=1))
    step("ses_shop", now - 8_000, 1200,
         think("The handler builds its query in findOrders. The cursor has to come from the last "
               "row's created_at and id, so the tests need a fixture with two pages."),
         tool("bash", status="running", command="pnpm test orders"))
    msg("ses_explore", "user", now - 5 * MIN,
        {"text": "Find where orders are queried. Report the files and the functions."})
    for i in range(4):
        step("ses_explore", now - (150 - 40 * i) * 1000, 250 + 120 * i,
             tool("read", filePath=SHOP + "/src/orders/repository.ts", offset=1 + 120 * i))
    step("ses_explore", now - 6_000, 450,
         tool("grep", pattern="findOrders"))

    msg("ses_shop_old", "user", now - 3 * 60 * MIN, {"text": "Fix the flaky checkout test."})
    msg("ses_shop_old", "idle", now - 150 * MIN, {"outcome": "interrupted"})

    db.commit()
    db.close()
