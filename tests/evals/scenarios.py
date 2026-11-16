"""Short-scenario eval: ~20 quick checks, each in a fresh conversation.

Built from bugs found while building the agent loop, so each one guards a real
regression: reminders at the right local time, noun-first save requests,
"remind me: what…" recall questions, recipes answered instead of refused, code
answers kept intact, pastes that must not create tasks, framework names that
aren't files, recall across a crew-looking question, live device state via a
tool, multi-step requests, and more.

Checks: reply text (must / must not match), tools called (must / must not),
the path that answered (no crew / coding agent unless asked), and the eval
database (tasks/events created, at the expected local time). Run it through
`python -m tests.evals.run --suite scenarios` (isolated backend), never
against the live one.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

API = os.environ.get("LUNA_API", "http://127.0.0.1:8898") + "/api/chat"
DB = Path(os.environ.get("LUNA_EVAL_DB", Path(__file__).resolve().parents[2] / ".tmp" / "luna-eval-data" / "luna.db"))
OUT = sys.argv[1] if len(sys.argv) > 1 else "scenarios_results.json"

TODAY = datetime.now()
TOMORROW = TODAY + timedelta(days=1)


@dataclass
class Scenario:
    name: str
    turns: list[str]
    must: list[str] = field(default_factory=list)          # regexes the last reply must match
    must_not: list[str] = field(default_factory=list)      # regexes no reply may match
    tools: list[str] = field(default_factory=list)         # each must be called (any turn)
    no_tools: list[str] = field(default_factory=list)      # none may be called ("*" = no tools at all)
    any_tools: list[str] = field(default_factory=list)     # at least one of these must be called
    tasks: list[tuple[str, datetime | None]] = field(default_factory=list)   # (title regex, local due)
    events: list[tuple[str, datetime | None]] = field(default_factory=list)  # (title regex, local start)
    no_new_rows: bool = False                              # no task/event may be created
    min_chars: int = 1


def at(day: datetime, hour: int, minute: int = 0) -> datetime:
    return day.replace(hour=hour, minute=minute, second=0, microsecond=0)


REFUSAL = r"(?i)i (?:don't|do not) have a tool|i can't (?:write|generate|create) (?:code|recipes?|that)"
SCENARIOS = [
    Scenario("reminder at a local time", ["remind me to call mom at 6 pm"],
             must=[r"(?i)\b6(?::00)?\s*(?:pm|p\.m\.)"], tasks=[(r"(?i)mom", at(TODAY, 18))]),
    Scenario("noun-first appointment", ["I have a dentist appointment tomorrow at 2 pm. Make sure to add that."],
             events=[(r"(?i)dentist", at(TOMORROW, 14))]),
    Scenario("'tonight' is today", ["add a task to read the quarterly report tonight at 9 pm"],
             tasks=[(r"(?i)report", at(TODAY, 21))]),
    Scenario("update instead of duplicate", ["remind me to stretch at 4 pm", "make it 5 pm instead"],
             tasks=[(r"(?i)stretch", at(TODAY, 17))]),
    Scenario("'remind me: what' is a question", ["Our new project is called Orca.", "remind me: what's our project called?"],
             must=[r"(?i)\borca\b"], no_new_rows=True),
    Scenario("recall through a crew-looking question", ["The code word for the test is walrus.",
                                                         "Quick check: what's the code word for the test?"],
             must=[r"(?i)walrus"], no_new_rows=True),
    Scenario("recipe answered, not refused", ["give me a recipe for butter chicken"],
             must_not=[REFUSAL], no_tools=["*"], min_chars=300),
    Scenario("knowledge without tools", ["explain what a B-tree is in three sentences"],
             must=[r"(?i)b-?tree"], no_tools=["*"]),
    Scenario("code answer kept intact", ["Write a Python function that validates an email address with a regex."],
             must=[r"```|def \w+\("], no_tools=["workspace_write", "create_task", "create_event"], no_new_rows=True,
             min_chars=150),
    Scenario("framework name is not a file", ["Explain how event loops work in Node.js in two short paragraphs."],
             must=[r"(?i)event loop"], min_chars=200),
    Scenario("endpoint request is not a calendar event", ["Add a DELETE /items/{id} endpoint to a FastAPI app."],
             no_tools=["create_event", "create_task", "workspace_write"], no_new_rows=True, min_chars=100),
    Scenario("code stays in the reply", ["write a hello world flask app"],
             must=[r"(?i)flask"], no_tools=["workspace_write"], min_chars=80),
    Scenario("long paste creates nothing",
             ["Here is a log:\n" + ("Schedule packet queue record commit batch schedule. " * 60) +
              "\nQuestion: what word appears most in this log?"], no_new_rows=True),
    Scenario("device state comes from a tool", ["what's my system volume right now?"], tools=["get_volume"]),
    Scenario("today's date without the web", ["what's today's date?"],
             must=[rf"(?i){TODAY:%B} {TODAY.day}\b|{TODAY:%Y-%m-%d}|{TODAY.month}/{TODAY.day}"],
             no_tools=["web_search", "use_skill"]),
    Scenario("small talk stays small", ["hey"], no_tools=["*"], must_not=[r"(?i)let me know|anything else"]),
    Scenario("multi-step: look up, then save", ["Look up the latest Python release, then add a task to read its "
                                                "changelog tomorrow at 10 am."],
             # Outcome, not mechanism: the lookup ran and the task exists at the right time
             # (the model sometimes claims the save and the claim guard makes it).
             any_tools=["web_search", "use_skill", "web_fetch", "browser_read"],
             tasks=[(r"(?i)changelog|python", at(TOMORROW, 10))]),
    Scenario("current price uses a lookup", ["What's the current price of an RTX 5090?"],
             any_tools=["web_search", "use_skill", "web_fetch", "browser_read"],
             must_not=[r"(?i)let me check\.?$"], min_chars=40),
    Scenario("no endearments or sign-offs", ["I'm so tired today"],
             must_not=[r"(?i)\b(?:darling|honey|babe|sweetheart|dear)\b", r"(?i)let me know|is there anything else"]),
    Scenario("no ellipses in prose", ["tell me a short joke"], must_not=[r"(?<!\.)\.\.\.(?!\.)"]),
]


def _max_ids(db: sqlite3.Connection) -> tuple[int, int]:
    return (db.execute("select coalesce(max(id),0) from tasks").fetchone()[0],
            db.execute("select coalesce(max(id),0) from calendar_events").fetchone()[0])


def _utc_naive(local: datetime) -> datetime:
    """Stored times are naive UTC; scenario times are local."""
    return datetime.fromtimestamp(local.timestamp(), tz=timezone.utc).replace(tzinfo=None)


def send(client: httpx.Client, message: str, conv_id: int | None) -> tuple[int | None, str, list[str], set[str]]:
    text, tools, kinds = "", [], set()
    with client.stream("POST", f"{API}/stream", json={"message": message, "conversation_id": conv_id}, timeout=600) as r:
        for line in r.iter_lines():
            if not line.startswith("data:"):
                continue
            ev = json.loads(line[5:])
            kinds.add(ev.get("type"))
            if ev.get("type") == "meta":
                conv_id = ev.get("conversation_id") or conv_id
            elif ev.get("type") == "message_part":
                text += ("\n\n" if text else "") + ev.get("content", "")
            elif ev.get("type") == "tool_call":
                tools.append(ev.get("tool"))
            elif ev.get("type") == "done" and str(ev.get("route", "")).startswith("shortcut:skill:"):
                tools.append(ev["route"])                 # a skill shortcut is a lookup too
    return conv_id, text.strip(), tools, kinds


def check(s: Scenario, replies: list[str], tools: list[str], kinds: set[str], new_tasks, new_events) -> list[str]:
    problems = []
    last = replies[-1] if replies else ""
    if len(last) < s.min_chars:
        problems.append(f"reply too short ({len(last)} chars)")
    problems += [f"reply lacks /{p}/" for p in s.must if not re.search(p, last)]
    problems += [f"reply has /{p}/" for p in s.must_not for r in replies if re.search(p, r)]
    problems += [f"tool {t} not called" for t in s.tools if t not in tools]
    if "*" in s.no_tools and tools:
        problems.append(f"called tools {tools}")
    problems += [f"called {t}" for t in s.no_tools if t != "*" and t in tools]
    if s.any_tools and not (set(s.any_tools) & set(tools) or any(t.startswith("shortcut:skill:") for t in tools)):
        problems.append(f"none of {s.any_tools} called")
    if {"crew_done", "agent_token", "coding_tool_call"} & kinds:
        problems.append("routed to crew/coding agent")
    if s.no_new_rows and (new_tasks or new_events):
        problems.append(f"created rows: {[t[1] for t in new_tasks] + [e[1] for e in new_events]}")
    for rows, wanted, what in ((new_tasks, s.tasks, "task"), (new_events, s.events, "event")):
        for pattern, local in wanted:
            match = [r for r in rows if re.search(pattern, r[1] or "")]
            if not match:
                problems.append(f"no {what} matching /{pattern}/")
            elif local is not None and not any(r[2] and abs(datetime.fromisoformat(str(r[2])) - _utc_naive(local))
                                               <= timedelta(minutes=1) for r in match):
                problems.append(f"{what} time {[str(r[2]) for r in match]} != {local:%a %H:%M} local")
        if wanted and len([r for r in rows if any(re.search(p, r[1] or "") for p, _ in wanted)]) > len(wanted):
            problems.append(f"duplicate {what}s: {[r[1] for r in rows]}")
    return problems


def main() -> None:
    db = sqlite3.connect(DB)
    results = {"scenarios": []}
    with httpx.Client() as client:
        for n, s in enumerate(SCENARIOS, start=1):
            client.post(f"{API}/context", json={"active_conversation_id": None})
            before = _max_ids(db)
            started, conv, replies, tools, kinds = time.time(), None, [], [], set()
            for message in s.turns:
                conv, reply, called, seen = send(client, message, conv)
                replies.append(reply)
                tools += called
                kinds |= seen
            time.sleep(1.0)                                  # finalize commits after the stream ends
            new_tasks = db.execute("select id, title, due_date from tasks where id > ?", (before[0],)).fetchall()
            new_events = db.execute("select id, title, start_datetime from calendar_events where id > ?",
                                    (before[1],)).fetchall()
            problems = check(s, replies, tools, kinds, new_tasks, new_events)
            row = {"n": n, "name": s.name, "ok": not problems, "problems": problems, "secs": round(time.time() - started, 1),
                   "tools": tools, "reply": (replies[-1] if replies else "")[:500]}
            results["scenarios"].append(row)
            mark = "PASS" if row["ok"] else "FAIL"
            print(f"[{n:>2}] {mark} {s.name:<42} {row['secs']:>5.1f}s {'; '.join(problems)}", flush=True)
            json.dump(results, open(OUT, "w", encoding="utf-8"), indent=2)
    passed = sum(r["ok"] for r in results["scenarios"])
    print(f"{passed}/{len(SCENARIOS)} scenarios passed")


if __name__ == "__main__":
    main()
