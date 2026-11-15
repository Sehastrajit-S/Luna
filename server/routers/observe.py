"""
Observability and benchmark API.

GET  /api/observe/metrics             — aggregated latency, token, cost metrics
GET  /api/observe/traces              — recent spans (optional ?conversation_id=N)
GET  /api/observe/traces/{conv_id}    — all spans for one conversation
GET  /api/observe/memory/graph        — knowledge graph for a query
GET  /api/observe/memory/episodes     — recent episodic memories
POST /api/observe/benchmark           — trigger benchmark run
GET  /api/observe/benchmark           — benchmark history (optional ?suite=memory)
GET  /api/observe/benchmark/latest    — most recent result per suite
GET  /api/observe/plans               — recent persisted plans
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.models.database import SessionLocal, get_db
from backend.services.telemetry import get_metrics, get_traces, tracer
from backend.services.memory_graph import MemoryGraph
from backend.services.benchmark import BenchmarkRunner
from backend.services.llm import LLMClient
from backend.services.tool_registry import TOOL_REGISTRY

router = APIRouter(prefix="/api/observe", tags=["observe"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_llm() -> LLMClient:
    return LLMClient()


async def _tool_executor(tool_name: str, args: dict) -> str:
    """
    Minimal tool executor for the benchmark suite.
    Only exercises safe, read-only tools to avoid side effects.
    """
    SAFE_TOOLS = {"workspace_list", "workspace_read", "web_search", "web_fetch"}
    if tool_name not in SAFE_TOOLS:
        return f"[skipped — tool {tool_name!r} not in safe set]"

    from backend.services import workspace, web_tools
    if tool_name == "workspace_list":
        items = workspace.list_workspace(args.get("path", ""))
        return str(items)
    if tool_name == "workspace_read":
        return workspace.read_workspace_file(args.get("path", ""))
    if tool_name == "web_search":
        return await web_tools.web_search(args.get("query", "test"))
    if tool_name == "web_fetch":
        return await web_tools.web_fetch(args.get("url", ""))
    return ""


# ── Telemetry ─────────────────────────────────────────────────────────────────

@router.get("/metrics")
async def metrics(
    hours: int = Query(default=24, ge=1, le=168),
    db: Session = Depends(get_db),
):
    """Aggregated metrics for the last N hours (default 24)."""
    await tracer.flush()
    return get_metrics(db, since_hours=hours)


@router.get("/traces")
async def traces(
    conversation_id: Optional[int] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Recent spans, optionally filtered to a specific conversation."""
    await tracer.flush()
    return get_traces(db, conversation_id=conversation_id, limit=limit)


@router.get("/traces/{conversation_id}")
async def traces_for_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
):
    """All spans recorded for a conversation, ordered newest-first."""
    await tracer.flush()
    spans = get_traces(db, conversation_id=conversation_id, limit=500)
    if not spans:
        raise HTTPException(status_code=404, detail="No traces found for this conversation.")
    return spans


# ── Memory graph ──────────────────────────────────────────────────────────────

@router.get("/memory/graph")
async def memory_graph(
    fact_ids: str = Query(description="Comma-separated fact IDs to use as seeds"),
    depth: int    = Query(default=2, ge=1, le=4),
    db: Session   = Depends(get_db),
):
    """
    Return the knowledge subgraph reachable from the given fact IDs.
    Useful for graph visualisation in the front-end.
    """
    try:
        ids = [int(x.strip()) for x in fact_ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status_code=422, detail="fact_ids must be comma-separated integers.")

    mg = MemoryGraph(db)
    return mg.get_subgraph(seed_fact_ids=ids, max_depth=depth)


@router.get("/memory/clusters")
async def memory_clusters(db: Session = Depends(get_db)):
    """Connected components in the knowledge graph (fact ID groups)."""
    mg = MemoryGraph(db)
    return {"clusters": mg.find_clusters()}


@router.get("/memory/episodes")
async def memory_episodes(
    query: str   = Query(default=""),
    limit: int   = Query(default=10, ge=1, le=50),
    db: Session  = Depends(get_db),
):
    """
    Recent episodic memories.  If a query is provided, results are ranked
    by semantic similarity (requires an embedding model to be configured).
    """
    mg = MemoryGraph(db)
    if query:
        llm = _get_llm()
        embed_fn = None
        try:
            embed_fn = lambda text: llm.embed(text)  # noqa: E731
        except Exception:
            pass
        episodes = mg.retrieve_episodes(query, limit=limit, embed_fn=embed_fn)
    else:
        episodes = mg._fallback_episodes(limit)
    return {"episodes": episodes}


# ── Benchmark ─────────────────────────────────────────────────────────────────

class BenchmarkRequest(BaseModel):
    suite: str = "all"   # all | memory | llm | tools | planner


@router.post("/benchmark")
async def run_benchmark(
    req: BenchmarkRequest,
    db: Session = Depends(get_db),
):
    """
    Trigger a benchmark run.  Returns results immediately.
    Heavy suites (llm, planner) can take 10–60 seconds.
    """
    from backend.services.memory_manager import MemoryManager

    llm     = _get_llm()
    memory  = MemoryManager(db)

    runner = BenchmarkRunner(
        db             = db,
        llm_client     = llm,
        memory_manager = memory,
        tool_executor  = _tool_executor,
    )
    results = await runner.run(suite=req.suite)
    return {
        "suite":   req.suite,
        "results": [
            {
                "suite":      r.suite,
                "passed":     r.passed(),
                "metrics":    r.metrics,
                "errors":     r.errors,
                "duration_s": r.duration_s,
            }
            for r in results
        ],
    }


@router.get("/benchmark")
async def benchmark_history(
    suite: Optional[str] = Query(default=None),
    limit: int           = Query(default=50, ge=1, le=500),
    db: Session          = Depends(get_db),
):
    """Historical benchmark results, newest first."""
    runner = BenchmarkRunner(
        db=db, llm_client=None, memory_manager=None, tool_executor=_tool_executor
    )
    return {"results": runner.history(suite=suite, limit=limit)}


@router.get("/benchmark/latest")
async def benchmark_latest(db: Session = Depends(get_db)):
    """Most recent result for each suite — suitable for a status dashboard."""
    runner = BenchmarkRunner(
        db=db, llm_client=None, memory_manager=None, tool_executor=_tool_executor
    )
    return runner.latest_per_suite()


# ── Plans ─────────────────────────────────────────────────────────────────────

@router.get("/plans")
async def list_plans(
    limit: int  = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Recent persisted plan records from the planner-executor-critic engine."""
    from sqlalchemy import text
    rows = db.execute(
        text(
            "SELECT plan_id, goal, status, steps_json, critique_json, created_at, completed_at "
            "FROM plan_records ORDER BY rowid DESC LIMIT :l"
        ),
        {"l": limit},
    ).fetchall()
    import json
    return {
        "plans": [
            {
                "plan_id":      r[0],
                "goal":         r[1],
                "status":       r[2],
                "step_count":   len(json.loads(r[3] or "[]")),
                "critique":     json.loads(r[4]) if r[4] else None,
                "created_at":   r[5],
                "completed_at": r[6],
            }
            for r in rows
        ]
    }
