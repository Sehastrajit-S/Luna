"""
Structured tracing and metrics for Luna.

Records every LLM call, memory retrieval, and tool execution as a span.
Aggregates into dashboard-ready metrics without touching hot paths on failure.

Usage:
    async with tracer.span("llm_call", conversation_id=cid, model=model) as span:
        response = await llm.complete(messages)
        span.record(tokens_in=n_in, tokens_out=n_out)
"""
from __future__ import annotations

import json
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field, asdict
from typing import Any, AsyncGenerator, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

# Cost per 1 M tokens (input USD, output USD). Local models = 0.
_COSTS: dict[str, tuple[float, float]] = {
    "gpt-4o":              (5.00, 15.00),
    "gpt-4o-mini":         (0.15,  0.60),
    "o1":                  (15.0,  60.0),
    "claude-opus":         (15.0,  75.0),
    "claude-sonnet":       (3.00,  15.0),
    "claude-haiku":        (0.25,   1.25),
    "gemini-1.5-pro":      (3.50,  10.5),
    "gemini-1.5-flash":    (0.075,  0.30),
    "gemini-2.0-flash":    (0.10,   0.40),
    "llama":               (0.0,    0.0),
    "mistral":             (0.0,    0.0),
    "ollama":              (0.0,    0.0),
}


def _cost_usd(model: str, tokens_in: int, tokens_out: int) -> float:
    model_lc = model.lower()
    for key, (cin, cout) in _COSTS.items():
        if key in model_lc:
            return (tokens_in * cin + tokens_out * cout) / 1_000_000
    return 0.0


# ── Span ──────────────────────────────────────────────────────────────────────

@dataclass
class Span:
    span_id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    parent_id: Optional[str] = None
    name: str = ""
    conversation_id: Optional[int] = None
    start_time: float = field(default_factory=time.monotonic)
    end_time: Optional[float] = None
    status: str = "ok"       # ok | error
    _attrs: dict = field(default_factory=dict)

    def record(self, **kwargs: Any) -> None:
        self._attrs.update(kwargs)

    @property
    def latency_ms(self) -> float:
        if self.end_time is not None:
            return max(0.0, (self.end_time - self.start_time) * 1000)
        return 0.0

    def cost_usd(self) -> float:
        return _cost_usd(
            self._attrs.get("model", ""),
            self._attrs.get("tokens_in", 0),
            self._attrs.get("tokens_out", 0),
        )


# ── Tracer ────────────────────────────────────────────────────────────────────

class Tracer:
    """
    Lightweight span-based tracer backed by the Luna SQLite DB.

    Spans are buffered in memory and flushed in batches so hot paths
    are never blocked on DB I/O.  All exceptions inside the tracer are
    silently swallowed — telemetry must never crash the app.
    """

    _FLUSH_EVERY = 25  # spans

    def __init__(self) -> None:
        self._session_factory = None   # set by init()
        self._buffer: list[Span] = []

    def init(self, session_factory) -> None:
        self._session_factory = session_factory

    @asynccontextmanager
    async def span(
        self,
        name: str,
        *,
        conversation_id: Optional[int] = None,
        parent_id: Optional[str] = None,
        **attrs: Any,
    ) -> AsyncGenerator[Span, None]:
        s = Span(name=name, conversation_id=conversation_id, parent_id=parent_id, _attrs=dict(attrs))
        try:
            yield s
        except Exception as exc:
            s.status = "error"
            s._attrs["error"] = str(exc)[:200]
            raise
        finally:
            s.end_time = time.monotonic()
            self._buffer.append(s)
            if len(self._buffer) >= self._FLUSH_EVERY:
                await self.flush()

    async def flush(self) -> None:
        if not self._buffer or self._session_factory is None:
            return
        batch, self._buffer = self._buffer[:], []
        try:
            with self._session_factory() as db:
                for s in batch:
                    db.execute(
                        text(
                            "INSERT INTO traces "
                            "(span_id, parent_id, name, conversation_id, start_time, end_time, "
                            "latency_ms, status, attributes, cost_usd) "
                            "VALUES (:sid, :pid, :name, :cid, :st, :et, :lat, :status, :attrs, :cost)"
                        ),
                        {
                            "sid":    s.span_id,
                            "pid":    s.parent_id,
                            "name":   s.name,
                            "cid":    s.conversation_id,
                            "st":     s.start_time,
                            "et":     s.end_time,
                            "lat":    round(s.latency_ms, 2),
                            "status": s.status,
                            "attrs":  json.dumps(s._attrs),
                            "cost":   round(s.cost_usd(), 6),
                        },
                    )
                db.commit()
        except Exception:
            pass  # telemetry must never break the app


tracer = Tracer()


# ── Metrics aggregation ───────────────────────────────────────────────────────

def _pct(values: list[float], p: int) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    return s[min(int(len(s) * p / 100), len(s) - 1)]


def get_metrics(db: Session, since_hours: int = 24) -> dict:
    """
    Aggregate recent spans into a dashboard-ready dict.

    Keys: llm, memory, tools — each with call counts, latency percentiles,
    error rates, token totals, and cost estimates.
    """
    cutoff = time.monotonic() - since_hours * 3600

    rows = db.execute(
        text(
            "SELECT name, latency_ms, status, attributes, cost_usd "
            "FROM traces WHERE start_time > :c ORDER BY start_time DESC LIMIT 5000"
        ),
        {"c": cutoff},
    ).fetchall()

    def _attrs(row) -> dict:
        try:
            return json.loads(row[3] or "{}")
        except Exception:
            return {}

    llm    = [r for r in rows if r[0] == "llm_call"]
    mem    = [r for r in rows if r[0] == "memory_retrieve"]
    tools  = [r for r in rows if r[0] == "tool_call"]

    llm_lat  = [r[1] for r in llm  if r[1]]
    mem_lat  = [r[1] for r in mem  if r[1]]
    tool_lat = [r[1] for r in tools if r[1]]

    return {
        "window_hours": since_hours,
        "llm": {
            "calls":          len(llm),
            "errors":         sum(1 for r in llm if r[2] == "error"),
            "p50_ms":         round(_pct(llm_lat, 50)),
            "p95_ms":         round(_pct(llm_lat, 95)),
            "tokens_in":      sum(_attrs(r).get("tokens_in", 0)  for r in llm),
            "tokens_out":     sum(_attrs(r).get("tokens_out", 0) for r in llm),
            "cost_usd":       round(sum(r[4] or 0.0 for r in llm), 4),
            "providers":      list({_attrs(r).get("provider", "unknown") for r in llm}),
        },
        "memory": {
            "retrievals":     len(mem),
            "p50_ms":         round(_pct(mem_lat, 50)),
            "p95_ms":         round(_pct(mem_lat, 95)),
            "avg_hits":       round(sum(_attrs(r).get("hits", 0) for r in mem) / max(len(mem), 1), 1),
            "cache_hit_rate": round(sum(1 for r in mem if _attrs(r).get("cache_hit")) / max(len(mem), 1), 2),
        },
        "tools": {
            "calls":          len(tools),
            "success_rate":   round(sum(1 for r in tools if r[2] == "ok") / max(len(tools), 1), 3),
            "p50_ms":         round(_pct(tool_lat, 50)),
            "p95_ms":         round(_pct(tool_lat, 95)),
            "top_tools":      _top_tools(tools),
        },
    }


def _top_tools(rows) -> list[dict]:
    counts: dict[str, int] = {}
    for r in rows:
        try:
            name = json.loads(r[3] or "{}").get("tool", "unknown")
        except Exception:
            name = "unknown"
        counts[name] = counts.get(name, 0) + 1
    return sorted([{"tool": k, "calls": v} for k, v in counts.items()], key=lambda x: -x["calls"])[:10]


def get_traces(db: Session, conversation_id: Optional[int] = None, limit: int = 100) -> list[dict]:
    """Return recent spans, optionally filtered by conversation."""
    if conversation_id is not None:
        rows = db.execute(
            text(
                "SELECT span_id, parent_id, name, conversation_id, latency_ms, status, attributes, cost_usd "
                "FROM traces WHERE conversation_id = :cid ORDER BY start_time DESC LIMIT :l"
            ),
            {"cid": conversation_id, "l": limit},
        ).fetchall()
    else:
        rows = db.execute(
            text(
                "SELECT span_id, parent_id, name, conversation_id, latency_ms, status, attributes, cost_usd "
                "FROM traces ORDER BY start_time DESC LIMIT :l"
            ),
            {"l": limit},
        ).fetchall()

    return [
        {
            "span_id":         r[0],
            "parent_id":       r[1],
            "name":            r[2],
            "conversation_id": r[3],
            "latency_ms":      r[4],
            "status":          r[5],
            "attrs":           json.loads(r[6] or "{}"),
            "cost_usd":        r[7],
        }
        for r in rows
    ]
