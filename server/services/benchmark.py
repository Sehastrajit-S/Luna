"""
Luna benchmark suite — publishable performance metrics.

Suites:
  memory  — retrieval hit-rate, category precision, p50/p95 latency
  llm     — time-to-first-token (TTFT), total latency, success rate
  tools   — per-tool success rate and latency
  planner — plan creation latency, step execution success rate

Results are stored in benchmark_results and exposed via /api/observe/benchmark.
Compare runs over time to track regressions and improvements.

Usage:
    runner = BenchmarkRunner(db, llm_client, memory_manager, tool_executor)
    results = await runner.run("all")   # or "memory", "llm", "tools", "planner"
"""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Coroutine, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session


# ── Result type ───────────────────────────────────────────────────────────────

@dataclass
class BenchResult:
    suite:      str
    timestamp:  float           = field(default_factory=time.time)
    metrics:    dict[str, Any]  = field(default_factory=dict)
    errors:     list[str]       = field(default_factory=list)
    duration_s: float           = 0.0

    def passed(self) -> bool:
        return not self.errors


# ── Helpers ───────────────────────────────────────────────────────────────────

def _pct(values: list[float], p: int) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    return s[min(int(len(s) * p / 100), len(s) - 1)]


# ── Memory suite ──────────────────────────────────────────────────────────────

_MEMORY_PROBES: list[tuple[str, list[str]]] = [
    ("What is my name?",            ["personal", "identity", "name"]),
    ("Where do I work or study?",   ["work", "job", "career", "study", "education"]),
    ("What are my hobbies?",        ["hobby", "interest", "activity"]),
    ("Where do I live?",            ["location", "home", "city", "country"]),
    ("What do I prefer to eat?",    ["food", "diet", "nutrition", "preference"]),
    ("What is my schedule like?",   ["schedule", "routine", "calendar", "time"]),
    ("Who are my close contacts?",  ["relationship", "friend", "family", "contact"]),
]


async def bench_memory(memory_manager) -> BenchResult:
    start  = time.monotonic()
    result = BenchResult(suite="memory")
    hits, cat_hits, latencies = 0, 0, []

    for query, expected_cats in _MEMORY_PROBES:
        t0 = time.monotonic()
        try:
            facts = await memory_manager.retrieve_relevant(query)
            latencies.append((time.monotonic() - t0) * 1000)
            if facts:
                hits += 1
                all_cats = " ".join(
                    str(f.get("category", "")).lower() for f in facts
                )
                if any(kw in all_cats for kw in expected_cats):
                    cat_hits += 1
        except Exception as exc:
            result.errors.append(f"memory['{query[:30]}']: {exc}")
            latencies.append((time.monotonic() - t0) * 1000)

    n = len(_MEMORY_PROBES)
    result.metrics = {
        "probes":             n,
        "hit_rate":           round(hits / n, 3) if n else 0,
        "category_precision": round(cat_hits / max(hits, 1), 3),
        "p50_ms":             round(_pct(latencies, 50)),
        "p95_ms":             round(_pct(latencies, 95)),
        "avg_ms":             round(sum(latencies) / len(latencies)) if latencies else 0,
    }
    result.duration_s = round(time.monotonic() - start, 2)
    return result


# ── LLM suite ─────────────────────────────────────────────────────────────────

_LLM_PROMPTS = [
    "Reply with exactly: pong",
    "What is 7 × 8? Answer with just the number.",
    "Name three primary colours. One word each, comma-separated.",
]


async def bench_llm(llm_client) -> BenchResult:
    start  = time.monotonic()
    result = BenchResult(suite="llm")
    ttfts, totals, successes = [], [], 0

    for prompt in _LLM_PROMPTS:
        t0 = time.monotonic()
        first_seen = False
        ttft: Optional[float] = None
        try:
            async for chunk in llm_client.stream_chat([{"role": "user", "content": prompt}]):
                if not first_seen and chunk.strip():
                    ttft = (time.monotonic() - t0) * 1000
                    first_seen = True
            total_ms = (time.monotonic() - t0) * 1000
            totals.append(total_ms)
            if ttft is not None:
                ttfts.append(ttft)
            successes += 1
        except Exception as exc:
            result.errors.append(f"llm['{prompt[:30]}']: {exc}")

    n = len(_LLM_PROMPTS)
    result.metrics = {
        "prompts":      n,
        "success_rate": round(successes / n, 3) if n else 0,
        "ttft_p50_ms":  round(_pct(ttfts,  50)),
        "ttft_p95_ms":  round(_pct(ttfts,  95)),
        "total_p50_ms": round(_pct(totals, 50)),
        "total_p95_ms": round(_pct(totals, 95)),
    }
    result.duration_s = round(time.monotonic() - start, 2)
    return result


# ── Tool suite ────────────────────────────────────────────────────────────────

_TOOL_PROBES: list[tuple[str, dict]] = [
    ("workspace_list",   {"path": ""}),
    ("web_search",       {"query": "Luna AI engine benchmark test"}),
]


async def bench_tools(tool_executor: Callable) -> BenchResult:
    start  = time.monotonic()
    result = BenchResult(suite="tools")
    successes, latencies, per_tool = 0, [], []

    for tool_name, args in _TOOL_PROBES:
        t0 = time.monotonic()
        try:
            res = await tool_executor(tool_name, args)
            lat = (time.monotonic() - t0) * 1000
            latencies.append(lat)
            ok = bool(res)
            if ok:
                successes += 1
            per_tool.append({"tool": tool_name, "ok": ok, "ms": round(lat)})
        except Exception as exc:
            lat = (time.monotonic() - t0) * 1000
            latencies.append(lat)
            result.errors.append(f"tool[{tool_name}]: {exc}")
            per_tool.append({"tool": tool_name, "ok": False, "ms": round(lat)})

    n = len(_TOOL_PROBES)
    result.metrics = {
        "probes":       n,
        "success_rate": round(successes / n, 3) if n else 0,
        "p50_ms":       round(_pct(latencies, 50)),
        "p95_ms":       round(_pct(latencies, 95)),
        "per_tool":     per_tool,
    }
    result.duration_s = round(time.monotonic() - start, 2)
    return result


# ── Planner suite ─────────────────────────────────────────────────────────────

_PLANNER_GOALS = [
    "Search for today's AI news and summarise the top 3 stories.",
    "List my workspace files and tell me which are largest.",
]


async def bench_planner(planner_service) -> BenchResult:
    start  = time.monotonic()
    result = BenchResult(suite="planner")
    plan_latencies, exec_successes = [], []

    for goal in _PLANNER_GOALS:
        t0 = time.monotonic()
        try:
            plan = await planner_service.create_plan(goal)
            plan_latencies.append((time.monotonic() - t0) * 1000)
            step_statuses: list[bool] = []
            async for event in planner_service.execute(plan):
                if event.get("type") == "step_done":
                    step_statuses.append(True)
                elif event.get("type") == "step_failed":
                    step_statuses.append(False)
            exec_successes.append(
                round(sum(step_statuses) / max(len(step_statuses), 1), 2)
            )
        except Exception as exc:
            result.errors.append(f"planner['{goal[:30]}']: {exc}")
            plan_latencies.append((time.monotonic() - t0) * 1000)

    n = len(_PLANNER_GOALS)
    result.metrics = {
        "goals":              n,
        "plan_p50_ms":        round(_pct(plan_latencies, 50)),
        "step_success_rate":  round(sum(exec_successes) / max(len(exec_successes), 1), 3),
    }
    result.duration_s = round(time.monotonic() - start, 2)
    return result


# ── Runner ────────────────────────────────────────────────────────────────────

class BenchmarkRunner:
    """
    Orchestrates all suites and persists results to benchmark_results.

    Inject the same service instances already running in the app —
    the runner does not create its own sessions or clients.
    """

    SUITES = ["memory", "llm", "tools", "planner"]

    def __init__(
        self,
        db: Session,
        llm_client,
        memory_manager,
        tool_executor: Callable,
        planner_service=None,
    ) -> None:
        self.db       = db
        self.llm      = llm_client
        self.memory   = memory_manager
        self.tools    = tool_executor
        self.planner  = planner_service

    async def run(self, suite: str = "all") -> list[BenchResult]:
        targets = self.SUITES if suite == "all" else [suite]
        results: list[BenchResult] = []

        for name in targets:
            try:
                if name == "memory":
                    r = await bench_memory(self.memory)
                elif name == "llm":
                    r = await bench_llm(self.llm)
                elif name == "tools":
                    r = await bench_tools(self.tools)
                elif name == "planner" and self.planner is not None:
                    r = await bench_planner(self.planner)
                else:
                    continue
            except Exception as exc:
                r = BenchResult(suite=name, errors=[str(exc)])

            results.append(r)
            self._save(r)

        return results

    def _save(self, r: BenchResult) -> None:
        try:
            self.db.execute(
                text(
                    "INSERT INTO benchmark_results (suite, timestamp, metrics, errors, duration_s) "
                    "VALUES (:s, :t, :m, :e, :d)"
                ),
                {
                    "s": r.suite,
                    "t": r.timestamp,
                    "m": json.dumps(r.metrics),
                    "e": json.dumps(r.errors),
                    "d": r.duration_s,
                },
            )
            self.db.commit()
        except Exception:
            pass

    def history(self, suite: Optional[str] = None, limit: int = 50) -> list[dict]:
        q      = "SELECT suite, timestamp, metrics, errors, duration_s FROM benchmark_results"
        params: dict = {}
        if suite:
            q += " WHERE suite = :s"
            params["s"] = suite
        q += " ORDER BY timestamp DESC LIMIT :l"
        params["l"] = limit
        rows = self.db.execute(text(q), params).fetchall()
        return [
            {
                "suite":      r[0],
                "timestamp":  r[1],
                "metrics":    json.loads(r[2] or "{}"),
                "errors":     json.loads(r[3] or "[]"),
                "duration_s": r[4],
            }
            for r in rows
        ]

    def latest_per_suite(self) -> dict[str, dict]:
        """Return the most recent result for each suite — useful for a status badge."""
        out: dict[str, dict] = {}
        for name in self.SUITES:
            rows = self.history(suite=name, limit=1)
            if rows:
                out[name] = rows[0]
        return out
