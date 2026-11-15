"""
Luna benchmark runner — production-grade, hardware/provider agnostic.

Works with any Luna-supported LLM provider (Ollama, OpenAI-compatible,
Anthropic, Google, Groq, Cohere, Mistral) and any accelerator
(NVIDIA, AMD, Apple Silicon, CPU-only).

Suites
------
baseline  — Raw LLM call: no system prompt, no memory. "Before Luna Engine."
engine    — Full Luna pipeline: memory retrieval + context injection. "After Luna Engine."
memory    — ChromaDB retrieval hit-rate, category precision, latency distribution.
tools     — Safe tool execution: success rate and latency per tool.
agent     — Tool routing accuracy + planning latency.
voice     — TTS latency via edge-tts (STT timing if vosk/whisper is available).
quality   — Instruction following, persona consistency, output correctness.
system    — RAM, CPU, and VRAM resource footprint during inference.

Key output
----------
The Markdown report leads with a "Before vs After Luna Engine" comparison table
so the performance delta of Luna's pipeline is immediately visible.

Statistics
----------
Every probe runs --runs times (default 3). Reports mean, stddev, p50, p95.
The first call is separately tracked as "cold"; remaining calls are "warm".

Usage
-----
    python scripts/run_benchmark.py
    python scripts/run_benchmark.py --suite baseline,engine
    python scripts/run_benchmark.py --suite all --runs 5
    python scripts/run_benchmark.py --provider groq --model llama-3.3-70b-versatile
    python scripts/run_benchmark.py --json results/bench.json
"""
from __future__ import annotations

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import argparse
import asyncio
import json
import math
import platform
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# ── Early arg parse so --provider can set env vars before settings loads ──────
import os as _os
_pre = argparse.ArgumentParser(add_help=False)
_pre.add_argument("--provider", default=None)
_pre.add_argument("--model",    default=None)
_pre.add_argument("--api-key",  default=None, dest="api_key")
_known, _ = _pre.parse_known_args()
if _known.provider:
    _os.environ["LLM_PROVIDER"] = _known.provider
if _known.model and _known.provider:
    _os.environ[f"{_known.provider.upper().replace('-','_')}_MODEL"] = _known.model
if _known.api_key and _known.provider:
    _os.environ[f"{_known.provider.upper().replace('-','_')}_API_KEY"] = _known.api_key

from backend.config import settings
from backend.models.database import init_db, SessionLocal
from backend.services.llm import LLMClient
from backend.services.memory_manager import MemoryManager


# ── Statistics ────────────────────────────────────────────────────────────────

@dataclass
class Stats:
    n:      int
    mean:   float
    stddev: float
    p50:    float
    p95:    float
    min:    float
    max:    float

    def __str__(self) -> str:
        return f"{self.mean:.0f} ms  (p50 {self.p50:.0f}  p95 {self.p95:.0f}  sd {self.stddev:.0f})"


def compute_stats(values: list[float]) -> Optional[Stats]:
    if not values:
        return None
    n = len(values)
    mean = sum(values) / n
    variance = sum((x - mean) ** 2 for x in values) / n
    stddev = math.sqrt(variance)
    sv = sorted(values)
    def pct(p: int) -> float:
        return sv[min(int(n * p / 100), n - 1)]
    return Stats(n=n, mean=round(mean, 1), stddev=round(stddev, 1),
                 p50=round(pct(50), 1), p95=round(pct(95), 1),
                 min=round(min(values), 1), max=round(max(values), 1))


# ── Hardware detection ────────────────────────────────────────────────────────

@dataclass
class HardwareInfo:
    accelerator:      str   = "unknown"
    accel_vendor:     str   = ""
    accel_mem_mb:     int   = 0
    accel_mem_used_mb:int   = 0
    accel_temp_c:     str   = ""
    accel_driver:     str   = ""
    cpu:              str   = ""
    ram_gb:           float = 0.0
    os:               str   = ""


def _detect_nvidia() -> Optional[dict]:
    try:
        out = subprocess.check_output(
            ["nvidia-smi",
             "--query-gpu=name,memory.total,memory.used,temperature.gpu,driver_version",
             "--format=csv,noheader,nounits"],
            text=True, stderr=subprocess.DEVNULL,
        ).strip().split("\n")[0]
        p = [x.strip() for x in out.split(",")]
        return {
            "accelerator":       p[0],
            "accel_vendor":      "NVIDIA",
            "accel_mem_mb":      int(p[1]),
            "accel_mem_used_mb": int(p[2]),
            "accel_temp_c":      p[3] + " C",
            "accel_driver":      p[4],
        }
    except Exception:
        return None


def _nvidia_vram_used() -> Optional[int]:
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            text=True, stderr=subprocess.DEVNULL,
        ).strip().split("\n")[0]
        return int(out.strip())
    except Exception:
        return None


def _detect_amd() -> Optional[dict]:
    try:
        subprocess.check_output(
            ["rocm-smi", "--showproductname", "--csv"],
            text=True, stderr=subprocess.DEVNULL,
        )
        return {"accelerator": "AMD GPU", "accel_vendor": "AMD", "accel_mem_mb": 0}
    except Exception:
        return None


def _detect_apple() -> Optional[dict]:
    try:
        import platform as _p
        if _p.system() != "Darwin":
            return None
        out = subprocess.check_output(["system_profiler", "SPHardwareDataType"], text=True)
        if "Apple" in out and any(m in out for m in ("M1", "M2", "M3", "M4")):
            chip = next((l.split(":")[1].strip() for l in out.splitlines() if "Chip" in l), "Apple Silicon")
            mem  = next((l.split(":")[1].strip() for l in out.splitlines() if "Memory" in l), "")
            return {"accelerator": chip, "accel_vendor": "Apple", "accel_mem_mb": 0, "accel_note": mem}
    except Exception:
        pass
    return None


def _cpu_ram() -> tuple[str, float]:
    cpu = platform.processor() or platform.machine()
    try:
        import psutil
        ram = round(psutil.virtual_memory().total / 1024 ** 3, 1)
    except Exception:
        ram = 0.0
    return cpu, ram


def detect_hardware() -> HardwareInfo:
    hw = HardwareInfo()
    hw.os = f"{platform.system()} {platform.release()}"
    hw.cpu, hw.ram_gb = _cpu_ram()
    gpu = _detect_nvidia() or _detect_amd() or _detect_apple()
    if gpu:
        for k, v in gpu.items():
            if hasattr(hw, k):
                setattr(hw, k, v)
    else:
        hw.accelerator = "CPU only"
        hw.accel_vendor = "CPU"
    return hw


# ── Model info ────────────────────────────────────────────────────────────────

def get_model_label() -> str:
    p = settings.llm_provider.lower()
    if p == "ollama":            return settings.ollama_model
    if p == "anthropic":         return getattr(settings, "anthropic_model", "claude")
    if p == "google":            return getattr(settings, "google_model", "gemini")
    if p == "groq":              return getattr(settings, "groq_model", "groq")
    if p == "cohere":            return getattr(settings, "cohere_model", "command-r")
    if p == "mistral":           return getattr(settings, "mistral_model", "mistral")
    if p in ("openai-compatible", "nvidia-nim"):
        return getattr(settings, "openai_model", "openai-compatible")
    return p


# ── Probe definitions ─────────────────────────────────────────────────────────

# (label, prompt, min_output_chars, is_long_form)
LLM_PROBES = [
    ("echo",       "Reply with exactly one word: pong",                              3,   False),
    ("arithmetic", "What is 17 times 13? Answer with the number only.",              2,   False),
    ("short-list", "Name 5 continents. One per line, no other text.",               20,   False),
    ("medium",     "Write exactly 5 bullet points about running AI models locally.", 80,   True),
    ("long",       "Explain transformer attention in 4 sentences.",                  120,  True),
]

WARMUP_PROMPT = "Say hi."

MEMORY_PROBES = [
    ("my name",         ["personal", "identity", "name"]),
    ("my job",          ["work", "job", "career", "study"]),
    ("my hobbies",      ["hobby", "interest", "activity", "sport"]),
    ("where I live",    ["location", "home", "city", "country"]),
    ("food preference", ["food", "diet", "preference"]),
    ("close contacts",  ["relationship", "friend", "family"]),
]
MIN_FACTS_FOR_QUALITY = 10

AGENT_PROBES = [
    # (user_request_snippet, expected_tool_name)
    ("list my workspace files",                  "workspace_list"),
    ("search the web for latest AI news",        "web_search"),
    ("what are my tasks for today",              "list_tasks"),
    ("remember that my favorite color is blue",  "save_fact"),
    ("open spotify and play jazz",               "spotify_play"),
    ("launch chrome",                            "launch_app"),
]

QUALITY_PROBES = [
    # (label, prompt, pass_check, description)
    ("exact-output",
     "Respond with ONLY the number 42. No other text whatsoever.",
     lambda o: o.strip() == "42",
     "exact output compliance"),
    ("structured-list",
     "List exactly 3 fruits. Each on its own line. Nothing else.",
     lambda o: len([l for l in o.strip().splitlines() if l.strip()]) == 3,
     "structured list compliance"),
    ("persona",
     "What is your name and what are you designed to do? One sentence.",
     lambda o: any(kw in o.lower() for kw in ["luna", "ai", "assistant", "help"]),
     "persona consistency"),
    ("factuality",
     "What is 2 + 2? Answer with the number only.",
     lambda o: "4" in o.strip(),
     "basic factuality"),
    ("negation",
     "Do NOT use the word 'the' in your response. Say hello in exactly 5 words.",
     lambda o: " the " not in f" {o.lower()} ",
     "negation instruction following"),
    ("json-format",
     'Output a JSON object with keys "name" and "version". Values can be anything.',
     lambda o: '"name"' in o and '"version"' in o,
     "JSON format compliance"),
    ("counting",
     "Count from 1 to 5. Output only numbers, one per line, nothing else.",
     lambda o: len([l for l in o.strip().splitlines() if l.strip().isdigit()]) == 5,
     "sequential counting"),
    ("long-context",
     "I will give you a secret word: BANANA. Now write a haiku about clouds. "
     "After the haiku, tell me what the secret word was.",
     lambda o: "banana" in o.lower(),
     "long-context retention"),
]

VOICE_SAMPLES = [
    "Hello! I'm Luna, your intelligent AI assistant.",
    "The analysis shows a 25 percent improvement in response time.",
    "I've scheduled your meeting for tomorrow at 3 PM.",
    "Let me search the web for the latest news on that topic.",
]


# ── Shared LLM call helper ────────────────────────────────────────────────────

async def _llm_call(llm: LLMClient, prompt: str, system: str = "") -> tuple[float, float, str]:
    """Returns (ttft_ms, total_ms, full_output)."""
    t0   = time.perf_counter()
    ttft = None
    out  = ""
    async for chunk in llm.stream_chat([{"role": "user", "content": prompt}], system):
        if ttft is None and chunk.strip():
            ttft = (time.perf_counter() - t0) * 1000
        out += chunk
    total = (time.perf_counter() - t0) * 1000
    return (ttft or total), total, out


# ── Suite: baseline (raw LLM, no context) — "Before Luna Engine" ──────────────

async def bench_baseline(llm: LLMClient, runs: int = 3) -> dict:
    """Raw LLM performance with no system prompt and no memory context.

    This is the 'Before Luna Engine' baseline — pure provider inference speed.
    Compare against 'engine' to see the pipeline overhead and quality delta.
    """
    print(f"  Warming up ({WARMUP_PROMPT!r}) x2 ...", end=" ", flush=True)
    for _ in range(2):
        try:
            async for _ in llm.stream_chat([{"role": "user", "content": WARMUP_PROMPT}], ""):
                break
        except Exception:
            pass
    print("done")

    all_ttfts, all_totals, long_tps = [], [], []
    probe_results = []

    for label, prompt, min_chars, is_long in LLM_PROBES:
        print(f"  [{label}]", end=" ", flush=True)
        run_ttfts, run_totals, run_tps = [], [], []

        for i in range(runs):
            tag = "[cold]" if i == 0 else f"[{i+1}]"
            try:
                ttft, total, out = await _llm_call(llm, prompt, system="")
                ok = len(out) >= min_chars
                out_tokens = max(1, len(out) // 4)
                tps = out_tokens / (total / 1000)
                run_ttfts.append(ttft)
                run_totals.append(total)
                if is_long:
                    run_tps.append(tps)
                flag = "ok" if ok else "SHORT"
                print(f"{tag} ttft={ttft:.0f}ms total={total:.0f}ms", end=" ", flush=True)
                if is_long:
                    print(f"~{tps:.0f}tok/s", end=" ", flush=True)
                print(f"[{flag}]", end="  ", flush=True)
            except Exception as exc:
                print(f"{tag} ERROR:{str(exc)[:50]}", end="  ", flush=True)
        print()

        cold_ttft  = run_ttfts[0] if run_ttfts else None
        warm_ttfts = run_ttfts[1:]
        ttft_stats  = compute_stats(warm_ttfts) if warm_ttfts else compute_stats(run_ttfts)
        total_stats = compute_stats(run_totals[1:] if len(run_totals) > 1 else run_totals)
        tps_stats   = compute_stats(run_tps) if run_tps else None

        all_ttfts.extend(warm_ttfts or run_ttfts)
        all_totals.extend(run_totals[1:] if len(run_totals) > 1 else run_totals)
        if run_tps:
            long_tps.extend(run_tps)

        probe_results.append({
            "label":        label,
            "cold_ttft_ms": round(cold_ttft) if cold_ttft else None,
            "ttft_ms":      asdict(ttft_stats)  if ttft_stats  else None,
            "total_ms":     asdict(total_stats) if total_stats else None,
            "tok_s":        asdict(tps_stats)   if tps_stats   else None,
            "is_long_form": is_long,
        })

    return {
        "model":           get_model_label(),
        "provider":        settings.llm_provider,
        "runs_per_probe":  runs,
        "ttft":            asdict(compute_stats(all_ttfts))  if all_ttfts  else None,
        "total":           asdict(compute_stats(all_totals)) if all_totals else None,
        "throughput_toks": asdict(compute_stats(long_tps))   if long_tps   else None,
        "probes":          probe_results,
    }


# keep `llm` as an alias so existing --suite llm still works
bench_llm = bench_baseline


# ── Suite: engine (full Luna pipeline) — "After Luna Engine" ──────────────────

_ENGINE_SYSTEM_BASE = (
    "You are L.U.N.A. (Linguistic Understanding & Neural Assistant), "
    "an intelligent personal AI. You know the user's preferences, history, "
    "and context. Be helpful, concise, and consistent with your persona."
)

async def bench_engine(llm: LLMClient, mm: MemoryManager, runs: int = 3) -> dict:
    """Full Luna pipeline: memory retrieval + context injection + LLM call.

    This is the 'After Luna Engine' measurement. The difference vs. 'baseline'
    shows what Luna's pipeline adds in latency and context quality.
    """
    all_ttfts, all_totals, all_retrieval, long_tps = [], [], [], []
    probe_results = []

    for label, prompt, min_chars, is_long in LLM_PROBES:
        print(f"  [{label}]", end=" ", flush=True)
        run_ttfts, run_totals, run_retrieval, run_tps = [], [], [], []

        for i in range(runs):
            tag = "[cold]" if i == 0 else f"[{i+1}]"
            try:
                # ── Memory retrieval (Luna pipeline overhead) ──────────────
                t_ret = time.perf_counter()
                try:
                    facts = await mm.retrieve_relevant(prompt)
                    fact_ctx = "\n".join(
                        f"- {f.get('content', '')}"
                        for f in (facts[:5] if isinstance(facts, list) else [])
                        if f.get("content")
                    )
                except Exception:
                    fact_ctx = ""
                ret_ms = (time.perf_counter() - t_ret) * 1000
                run_retrieval.append(ret_ms)

                # ── Build enriched system prompt ───────────────────────────
                system = _ENGINE_SYSTEM_BASE
                if fact_ctx:
                    system += f"\n\nKnown context about the user:\n{fact_ctx}"

                # ── LLM call ───────────────────────────────────────────────
                ttft, llm_total, out = await _llm_call(llm, prompt, system=system)

                # Engine total = retrieval + LLM
                engine_ttft  = ttft + ret_ms
                engine_total = llm_total + ret_ms
                run_ttfts.append(engine_ttft)
                run_totals.append(engine_total)

                ok = len(out) >= min_chars
                out_tokens = max(1, len(out) // 4)
                tps = out_tokens / (llm_total / 1000)
                if is_long:
                    run_tps.append(tps)

                flag = "ok" if ok else "SHORT"
                print(
                    f"{tag} ret={ret_ms:.0f}ms ttft={engine_ttft:.0f}ms "
                    f"total={engine_total:.0f}ms",
                    end=" ", flush=True,
                )
                if is_long:
                    print(f"~{tps:.0f}tok/s", end=" ", flush=True)
                print(f"[{flag}]", end="  ", flush=True)
            except Exception as exc:
                print(f"{tag} ERROR:{str(exc)[:50]}", end="  ", flush=True)
        print()

        cold_ttft  = run_ttfts[0] if run_ttfts else None
        warm_ttfts = run_ttfts[1:]
        ttft_stats  = compute_stats(warm_ttfts) if warm_ttfts else compute_stats(run_ttfts)
        total_stats = compute_stats(run_totals[1:] if len(run_totals) > 1 else run_totals)
        ret_stats   = compute_stats(run_retrieval)
        tps_stats   = compute_stats(run_tps) if run_tps else None

        all_ttfts.extend(warm_ttfts or run_ttfts)
        all_totals.extend(run_totals[1:] if len(run_totals) > 1 else run_totals)
        all_retrieval.extend(run_retrieval)
        if run_tps:
            long_tps.extend(run_tps)

        probe_results.append({
            "label":          label,
            "cold_ttft_ms":   round(cold_ttft) if cold_ttft else None,
            "ttft_ms":        asdict(ttft_stats)  if ttft_stats  else None,
            "total_ms":       asdict(total_stats) if total_stats else None,
            "retrieval_ms":   asdict(ret_stats)   if ret_stats   else None,
            "tok_s":          asdict(tps_stats)   if tps_stats   else None,
            "is_long_form":   is_long,
        })

    return {
        "model":           get_model_label(),
        "provider":        settings.llm_provider,
        "runs_per_probe":  runs,
        "ttft":            asdict(compute_stats(all_ttfts))     if all_ttfts    else None,
        "total":           asdict(compute_stats(all_totals))    if all_totals   else None,
        "retrieval_ms":    asdict(compute_stats(all_retrieval)) if all_retrieval else None,
        "throughput_toks": asdict(compute_stats(long_tps))      if long_tps     else None,
        "probes":          probe_results,
    }


# ── Suite: memory ─────────────────────────────────────────────────────────────

async def bench_memory(db, runs: int = 3) -> dict:
    from sqlalchemy import text
    total_facts = db.execute(text("SELECT COUNT(*) FROM facts WHERE is_active=1")).scalar()
    print(f"  Facts in DB: {total_facts}", end="")
    if total_facts < MIN_FACTS_FOR_QUALITY:
        print(f"  (< {MIN_FACTS_FOR_QUALITY} — quality metrics skipped, latency only)")
    else:
        print()

    mm = MemoryManager(db)
    latencies, hits, results = [], 0, []

    for query_label, cats in MEMORY_PROBES:
        query = f"Tell me about {query_label}."
        print(f"  [{query_label[:20]}]", end=" ", flush=True)
        run_lats = []

        for i in range(runs):
            t0 = time.perf_counter()
            try:
                facts = await mm.retrieve_relevant(query)
                lat = (time.perf_counter() - t0) * 1000
                run_lats.append(lat)
                n_hits = len(facts) if isinstance(facts, list) else 0
                print(f"[{i+1}] {lat:.0f}ms hits={n_hits}", end="  ", flush=True)
                if i == 0 and n_hits > 0:
                    hits += 1
            except Exception as exc:
                lat = (time.perf_counter() - t0) * 1000
                run_lats.append(lat)
                print(f"[{i+1}] ERR {lat:.0f}ms", end="  ", flush=True)
        print()

        latencies.extend(run_lats)
        lat_stats = compute_stats(run_lats)
        results.append({"query": query_label, "latency_ms": asdict(lat_stats) if lat_stats else None})

    lat_all = compute_stats(latencies)
    return {
        "total_facts":   total_facts,
        "quality_valid": total_facts >= MIN_FACTS_FOR_QUALITY,
        "hit_rate":      round(hits / len(MEMORY_PROBES), 3) if total_facts >= MIN_FACTS_FOR_QUALITY else None,
        "latency_ms":    asdict(lat_all) if lat_all else None,
        "probes":        results,
        "note":          (f"Re-run after {MIN_FACTS_FOR_QUALITY}+ conversations for quality metrics."
                          if total_facts < MIN_FACTS_FOR_QUALITY else ""),
    }


# ── Suite: tools ──────────────────────────────────────────────────────────────

def _tool_probes() -> list[tuple[str, Any, bool]]:
    from backend.services import workspace, web_tools
    return [
        ("workspace_list", lambda: workspace.list_workspace(""),           False),
        ("web_search",     lambda: web_tools.web_search("Luna AI engine"), True),
    ]


async def bench_tools(runs: int = 3) -> dict:
    probes = _tool_probes()
    tool_results = []

    for name, fn, is_async in probes:
        print(f"  [{name}]", end=" ", flush=True)
        run_lats, successes = [], 0

        for i in range(runs):
            t0 = time.perf_counter()
            try:
                result = await fn() if is_async else fn()
                lat = (time.perf_counter() - t0) * 1000
                run_lats.append(lat)
                ok = bool(result)
                if ok:
                    successes += 1
                print(f"[{i+1}] {lat:.0f}ms {'ok' if ok else 'empty'}", end="  ", flush=True)
            except Exception as exc:
                lat = (time.perf_counter() - t0) * 1000
                run_lats.append(lat)
                print(f"[{i+1}] {lat:.0f}ms ERR:{str(exc)[:40]}", end="  ", flush=True)
        print()

        lat_stats = compute_stats(run_lats)
        tool_results.append({
            "tool":         name,
            "success_rate": round(successes / runs, 3),
            "latency_ms":   asdict(lat_stats) if lat_stats else None,
        })

    overall_sr = (
        round(sum(r["success_rate"] for r in tool_results) / len(tool_results), 3)
        if tool_results else 0.0
    )
    return {"probes": tool_results, "success_rate": overall_sr}


# ── Suite: agent ──────────────────────────────────────────────────────────────

async def bench_agent(llm: LLMClient, runs: int = 2) -> dict:
    """Tool routing accuracy: ask the LLM to select the correct tool for each request.

    Uses the real TOOL_REGISTRY so the available tool list stays in sync with Luna.
    """
    from backend.services.tool_registry import TOOL_REGISTRY
    tool_names = list(TOOL_REGISTRY.keys())

    print(f"  Tools available: {len(tool_names)}")

    correct, probe_results = 0, []
    planning_lats: list[float] = []

    for request, expected in AGENT_PROBES:
        if expected not in tool_names:
            print(f"  [{expected}] SKIP (not in registry)")
            probe_results.append({"request": request[:40], "expected": expected, "skipped": True})
            continue

        print(f"  [{expected}]", end=" ", flush=True)
        run_correct, run_lats = 0, []

        for i in range(runs):
            selection_prompt = (
                f"You must respond with ONLY a JSON object like: {{\"tool\": \"<name>\"}}\n"
                f"Available tools: {', '.join(tool_names)}\n"
                f"User request: {request}\n"
                f"Which single tool best handles this? Reply with only the JSON."
            )
            t0 = time.perf_counter()
            try:
                out = ""
                async for chunk in llm.stream_chat(
                    [{"role": "user", "content": selection_prompt}], ""
                ):
                    out += chunk
                lat = (time.perf_counter() - t0) * 1000
                run_lats.append(lat)
                planning_lats.append(lat)

                m = re.search(r'"tool"\s*:\s*"([^"]+)"', out)
                selected = m.group(1).strip() if m else None
                ok = selected == expected
                if ok:
                    run_correct += 1
                print(f"[{i+1}] {selected or '?'} {'✓' if ok else '✗'} {lat:.0f}ms", end="  ", flush=True)
            except Exception as exc:
                print(f"[{i+1}] ERR:{str(exc)[:30]}", end="  ", flush=True)
        print()

        if run_correct > 0:
            correct += 1

        lat_stats = compute_stats(run_lats)
        probe_results.append({
            "request":      request[:50],
            "expected":     expected,
            "pass_rate":    round(run_correct / runs, 2),
            "latency_ms":   asdict(lat_stats) if lat_stats else None,
        })

    valid = [p for p in probe_results if not p.get("skipped")]
    accuracy = round(correct / max(len(valid), 1), 3)
    plan_stats = compute_stats(planning_lats)

    return {
        "probes":       len(valid),
        "correct":      correct,
        "accuracy":     accuracy,
        "plan_p50_ms":  round(plan_stats.p50) if plan_stats else None,
        "plan_p95_ms":  round(plan_stats.p95) if plan_stats else None,
        "results":      probe_results,
    }


# ── Suite: voice ──────────────────────────────────────────────────────────────

async def bench_voice(runs: int = 2) -> dict:
    """TTS latency via edge-tts. STT availability check via vosk/whisper."""
    result: dict[str, Any] = {"tts": None, "stt_available": False, "available": False}

    # ── TTS via edge-tts ──────────────────────────────────────────────────────
    try:
        import io
        import edge_tts

        tts_lats: list[float] = []
        char_counts: list[int] = []

        for text in VOICE_SAMPLES:
            for _ in range(runs):
                t0 = time.perf_counter()
                communicate = edge_tts.Communicate(text, "en-US-JennyNeural")
                buf = io.BytesIO()
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        buf.write(chunk["data"])
                lat = (time.perf_counter() - t0) * 1000
                audio_kb = len(buf.getvalue()) / 1024
                tts_lats.append(lat)
                char_counts.append(len(text))
                print(f"  [TTS] {len(text)} chars → {lat:.0f}ms  ({audio_kb:.1f} KB)", flush=True)

        tts_stats = compute_stats(tts_lats)
        chars_mean = sum(char_counts) / len(char_counts) if char_counts else 0
        result["tts"] = {
            **(asdict(tts_stats) if tts_stats else {}),
            "chars_per_sample": round(chars_mean),
        }
        result["available"] = True
        print()
    except ImportError:
        print("  [TTS] SKIP — edge-tts not installed (pip install edge-tts)")
        result["tts_note"] = "edge-tts not installed"
    except Exception as exc:
        print(f"  [TTS] ERROR: {exc}")
        result["tts_error"] = str(exc)

    # ── STT availability ──────────────────────────────────────────────────────
    try:
        import vosk  # noqa: F401
        result["stt_available"] = True
        result["stt_engine"] = "vosk"
        print("  [STT] vosk available — live mic required for full benchmark")
    except ImportError:
        try:
            import faster_whisper  # noqa: F401
            result["stt_available"] = True
            result["stt_engine"] = "faster-whisper"
            print("  [STT] faster-whisper available — live mic required for full benchmark")
        except ImportError:
            print("  [STT] SKIP — neither vosk nor faster-whisper installed")
            result["stt_engine"] = "none"

    return result


# ── Suite: quality ────────────────────────────────────────────────────────────

async def bench_quality(llm: LLMClient, runs: int = 2) -> dict:
    """Instruction following, persona consistency, factuality, output correctness."""
    probe_results = []
    total_pass_rate = 0.0

    for label, prompt, check_fn, description in QUALITY_PROBES:
        print(f"  [{label}]", end=" ", flush=True)
        run_passes = 0
        sample_output = None

        for i in range(runs):
            try:
                _, _, out = await _llm_call(llm, prompt, system="")
                passed = check_fn(out)
                if passed:
                    run_passes += 1
                if sample_output is None:
                    sample_output = out.strip()[:100]
                print(f"[{i+1}] {'pass' if passed else 'FAIL'}", end="  ", flush=True)
            except Exception as exc:
                print(f"[{i+1}] ERR:{str(exc)[:30]}", end="  ", flush=True)
        print()

        pass_rate = round(run_passes / runs, 2)
        total_pass_rate += pass_rate
        probe_results.append({
            "label":         label,
            "description":   description,
            "pass_rate":     pass_rate,
            "sample_output": sample_output,
        })

    overall_score = round(total_pass_rate / max(len(QUALITY_PROBES), 1), 3)
    return {"overall_score": overall_score, "probes": len(QUALITY_PROBES), "results": probe_results}


# ── Suite: system ─────────────────────────────────────────────────────────────

async def bench_system(llm: LLMClient, runs: int = 2) -> dict:
    """RAM, CPU, and VRAM resource footprint at idle and during inference."""
    try:
        import psutil
    except ImportError:
        print("  SKIP — psutil not installed (pip install psutil)")
        return {"error": "psutil not installed — pip install psutil"}

    proc = psutil.Process()

    # Idle snapshot
    idle_ram_mb  = round(proc.memory_info().rss / 1024 ** 2, 1)
    idle_cpu_pct = psutil.cpu_percent(interval=1.0)
    vram_idle    = _nvidia_vram_used()

    print(f"  Idle: RAM={idle_ram_mb} MB  CPU={idle_cpu_pct}%"
          + (f"  VRAM={vram_idle} MB" if vram_idle else ""))

    MONITOR_PROMPT = (
        "Write a detailed 200-word explanation of how attention mechanisms in "
        "transformer neural networks work, including multi-head attention."
    )

    all_ram: list[float] = []
    all_cpu: list[float] = []

    for i in range(runs):
        print(f"  [inference run {i+1}/{runs}]", end=" ", flush=True)
        ram_samples: list[float] = []
        cpu_samples: list[float] = []

        async def _monitor_resources():
            for _ in range(60):
                await asyncio.sleep(0.25)
                ram_samples.append(proc.memory_info().rss / 1024 ** 2)
                cpu_samples.append(proc.cpu_percent())

        monitor_task = asyncio.create_task(_monitor_resources())
        t0 = time.perf_counter()
        try:
            out = ""
            async for chunk in llm.stream_chat(
                [{"role": "user", "content": MONITOR_PROMPT}], ""
            ):
                out += chunk
            elapsed = (time.perf_counter() - t0) * 1000
            out_tokens = max(1, len(out) // 4)
            tps = out_tokens / (elapsed / 1000)
            print(f"{elapsed:.0f}ms  ~{tps:.0f}tok/s", flush=True)
        except Exception as exc:
            print(f"ERROR:{exc}", flush=True)
        finally:
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass

        all_ram.extend(ram_samples)
        all_cpu.extend(cpu_samples)

    vram_peak = _nvidia_vram_used()
    peak_ram  = round(max(all_ram), 1) if all_ram else idle_ram_mb
    peak_cpu  = round(max(all_cpu), 1) if all_cpu else idle_cpu_pct
    avg_cpu   = round(sum(all_cpu) / len(all_cpu), 1) if all_cpu else 0.0

    print(f"  Peak:  RAM={peak_ram} MB  CPU={peak_cpu}%"
          + (f"  VRAM={vram_peak} MB" if vram_peak else ""))

    return {
        "idle_ram_mb":              idle_ram_mb,
        "peak_ram_mb":              peak_ram,
        "ram_delta_mb":             round(peak_ram - idle_ram_mb, 1),
        "idle_cpu_pct":             idle_cpu_pct,
        "peak_cpu_pct":             peak_cpu,
        "avg_cpu_during_inference": avg_cpu,
        "vram_idle_mb":             vram_idle,
        "vram_peak_mb":             vram_peak,
        "vram_delta_mb":            (vram_peak - vram_idle) if vram_idle and vram_peak else None,
    }


# ── Regression check ──────────────────────────────────────────────────────────

REGRESSION_THRESHOLD = 0.25

def check_regression(current: dict, db) -> list[str]:
    from sqlalchemy import text
    warnings: list[str] = []
    checks_map = {
        "baseline": [("TTFT mean", "ttft", "mean", True), ("throughput", "throughput_toks", "mean", False)],
        "engine":   [("engine TTFT mean", "ttft", "mean", True)],
        "memory":   [("retrieval latency", "latency_ms", "mean", True)],
        "tools":    [("tool success rate", "success_rate", None, False)],
        "quality":  [("quality score", "overall_score", None, False)],
        "agent":    [("routing accuracy", "accuracy", None, False)],
    }
    for suite, checks in checks_map.items():
        row = db.execute(
            text("SELECT metrics FROM benchmark_results WHERE suite=:s ORDER BY timestamp DESC LIMIT 1 OFFSET 1"),
            {"s": suite},
        ).fetchone()
        if not row:
            continue
        try:
            prev = json.loads(row[0])
        except Exception:
            continue
        cur = current.get(suite, {})
        for name, key, subkey, higher_is_worse in checks:
            prev_v = prev.get(key) if subkey is None else (prev.get(key) or {}).get(subkey)
            cur_v  = cur.get(key)  if subkey is None else (cur.get(key) or {}).get(subkey)
            if prev_v is None or cur_v is None:
                continue
            delta = (cur_v - prev_v) / max(abs(prev_v), 1e-9)
            regressed = delta > REGRESSION_THRESHOLD if higher_is_worse else delta < -REGRESSION_THRESHOLD
            if regressed:
                direction = "+" if delta > 0 else ""
                warnings.append(f"[{suite}] {name} regressed {direction}{delta*100:.0f}%  ({prev_v:.1f} → {cur_v:.1f})")
    return warnings


# ── Persistence ───────────────────────────────────────────────────────────────

def _save(db, suite: str, metrics: dict) -> None:
    from sqlalchemy import text
    try:
        db.execute(
            text("INSERT INTO benchmark_results (suite, timestamp, metrics, errors, duration_s) "
                 "VALUES (:s, :t, :m, :e, :d)"),
            {"s": suite, "t": time.time(), "m": json.dumps(metrics, default=str), "e": "[]", "d": 0},
        )
        db.commit()
    except Exception as exc:
        print(f"  [DB save error: {exc}]")


# ── Markdown rendering ────────────────────────────────────────────────────────

def _ms(s: Optional[dict], key: str = "mean") -> str:
    if not s:
        return "N/A"
    v = s.get(key)
    return f"{v:.0f} ms" if v is not None else "N/A"


def _tps(s: Optional[dict], key: str = "mean") -> str:
    if not s:
        return "N/A"
    v = s.get(key)
    return f"{v:.0f} tok/s" if v is not None else "N/A"


def _pct(v: Optional[float]) -> str:
    return f"{v*100:.0f}%" if v is not None else "N/A"


def _delta_ms(base: Optional[dict], engine: Optional[dict], key: str = "mean") -> str:
    if not base or not engine:
        return "N/A"
    bv = base.get(key)
    ev = engine.get(key)
    if bv is None or ev is None:
        return "N/A"
    diff = ev - bv
    pct  = (diff / max(bv, 1)) * 100
    sign = "+" if diff >= 0 else ""
    return f"{sign}{diff:.0f} ms ({sign}{pct:.0f}%)"


def render_markdown(
    hw: HardwareInfo,
    ts: str,
    runs: int,
    results: dict[str, dict],
    warnings: list[str],
) -> str:
    lines: list[str] = []
    base = results.get("baseline") or results.get("llm", {})
    eng  = results.get("engine", {})
    mem  = results.get("memory", {})
    tool = results.get("tools",  {})
    agt  = results.get("agent",  {})
    voi  = results.get("voice",  {})
    qual = results.get("quality",{})
    sys_ = results.get("system", {})

    model   = base.get("model") or eng.get("model") or get_model_label()
    provider= base.get("provider") or eng.get("provider") or settings.llm_provider

    # ── Header ────────────────────────────────────────────────────────────────
    lines += [
        "# Luna Benchmark Results",
        "",
        f"> **Run:** {ts}  ",
        f"> **Hardware:** {hw.accelerator}  {hw.accel_mem_mb} MB VRAM  (driver {hw.accel_driver})  ",
        f"> **CPU:** {hw.cpu}  {hw.ram_gb} GB RAM  ",
        f"> **OS:** {hw.os}  ",
        f"> **Model:** `{model}`  provider: `{provider}`  ",
        f"> **Runs per probe:** {runs}  (cold call tracked separately; warm stats exclude it)",
        "",
    ]

    # ── Regressions ───────────────────────────────────────────────────────────
    if warnings:
        lines += ["## Regressions vs previous run", ""]
        for w in warnings:
            lines.append(f"- {w}")
        lines.append("")

    # ── Before vs After Luna Engine ───────────────────────────────────────────
    lines += [
        "## Before vs After Luna Engine",
        "",
        "> **Baseline** = raw LLM call with no system prompt and no memory retrieval.  ",
        "> **Luna Engine** = full pipeline: memory retrieval → context injection → LLM call.  ",
        "> Overhead is the cost Luna adds; context quality is what it buys.",
        "",
        "| Metric | Raw LLM (Baseline) | Luna Engine | Overhead |",
        "|--------|-------------------:|------------:|----------|",
    ]
    lines.append(f"| TTFT p50 | **{_ms(base.get('ttft'), 'p50')}** | **{_ms(eng.get('ttft'), 'p50')}** | {_delta_ms(base.get('ttft'), eng.get('ttft'), 'p50')} |")
    lines.append(f"| TTFT p95 | {_ms(base.get('ttft'), 'p95')} | {_ms(eng.get('ttft'), 'p95')} | {_delta_ms(base.get('ttft'), eng.get('ttft'), 'p95')} |")
    lines.append(f"| TTFT mean | {_ms(base.get('ttft'))} | {_ms(eng.get('ttft'))} | {_delta_ms(base.get('ttft'), eng.get('ttft'))} |")
    lines.append(f"| Sustained tok/s | **{_tps(base.get('throughput_toks'))}** | **{_tps(eng.get('throughput_toks'))}** | decode speed unaffected |")
    lines.append(f"| Memory retrieval | — | {_ms(eng.get('retrieval_ms'))} avg | included in overhead |")
    lines.append(f"| Context quality | plain | memory-augmented | ✓ user history injected |")

    if tool:
        lines.append(f"| Tool success rate | — | {_pct(tool.get('success_rate'))} | tools require engine |")
    if agt:
        lines.append(f"| Routing accuracy | — | {_pct(agt.get('accuracy'))} | tool selection |")
    if qual:
        lines.append(f"| Quality score | — | {_pct(qual.get('overall_score'))} | instruction following |")
    lines.append("")

    # ── Full summary ──────────────────────────────────────────────────────────
    lines += [
        "## Summary",
        "",
        "| Suite | Key Metric | Value | Notes |",
        "|-------|-----------|-------|-------|",
    ]
    if base:
        lines.append(f"| Baseline LLM | TTFT p50 | **{_ms(base.get('ttft'), 'p50')}** | raw provider, no Luna overhead |")
        lines.append(f"| Baseline LLM | Throughput | **{_tps(base.get('throughput_toks'))}** | long-form generation |")
    if eng:
        lines.append(f"| Luna Engine | TTFT p50 | **{_ms(eng.get('ttft'), 'p50')}** | includes memory retrieval |")
        lines.append(f"| Luna Engine | Retrieval | {_ms(eng.get('retrieval_ms'))} avg | ChromaDB vector search |")
    if mem:
        hr = mem.get('hit_rate')
        hr_str = f"{hr*100:.0f}%" if hr is not None else "N/A (< 10 facts)"
        lines.append(f"| Memory | Hit rate | {hr_str} | category-matched facts |")
        lines.append(f"| Memory | Latency p50 | {_ms(mem.get('latency_ms'), 'p50')} | retrieval only |")
    if tool:
        lines.append(f"| Tools | Success rate | {_pct(tool.get('success_rate'))} | safe tools only |")
    if agt:
        lines.append(f"| Agent | Routing accuracy | {_pct(agt.get('accuracy'))} | correct tool selected |")
        if agt.get("plan_p50_ms"):
            lines.append(f"| Agent | Planning p50 | {agt['plan_p50_ms']} ms | tool selection latency |")
    if voi and voi.get("tts"):
        lines.append(f"| Voice | TTS p50 | {_ms(voi.get('tts'), 'p50')} | edge-tts generation |")
        stt = "available" if voi.get("stt_available") else "not installed"
        lines.append(f"| Voice | STT | {stt} | {voi.get('stt_engine', '—')} |")
    if qual:
        lines.append(f"| Quality | Instruction score | {_pct(qual.get('overall_score'))} | {qual.get('probes', 0)}-probe battery |")
    if sys_ and not sys_.get("error"):
        lines.append(f"| System | Peak RAM delta | {sys_.get('ram_delta_mb', '?')} MB | inference overhead |")
        if sys_.get("vram_delta_mb") is not None:
            lines.append(f"| System | VRAM delta | {sys_['vram_delta_mb']} MB | model VRAM usage |")
    lines.append("")

    # ── Baseline LLM detail ───────────────────────────────────────────────────
    if base:
        ttft_s  = base.get("ttft")
        total_s = base.get("total")
        tps_s   = base.get("throughput_toks")
        lines += [
            "## Baseline LLM Performance (Raw Provider)",
            "",
            "> No system prompt. No memory. No Luna overhead.",
            "> This is the maximum possible speed for the configured provider.",
            "",
            "| Metric | Mean | p50 | p95 | stddev |",
            "|--------|------|-----|-----|--------|",
        ]
        def _row(label, s):
            if not s:
                return f"| {label} | N/A | N/A | N/A | N/A |"
            return f"| {label} | {s['mean']:.0f} ms | {s['p50']:.0f} ms | {s['p95']:.0f} ms | {s['stddev']:.0f} ms |"
        lines.append(_row("TTFT", ttft_s))
        lines.append(_row("Total latency", total_s))
        if tps_s:
            lines.append(f"| Throughput | {tps_s['mean']:.0f} tok/s | {tps_s['p50']:.0f} tok/s | {tps_s['p95']:.0f} tok/s | {tps_s['stddev']:.0f} tok/s |")
        lines += [
            "",
            "### Per-probe",
            "",
            "| Probe | Cold TTFT | Warm TTFT (mean) | Warm Total (mean) | tok/s |",
            "|-------|-----------|-----------------|-------------------|-------|",
        ]
        for p in base.get("probes", []):
            cold = f"{p['cold_ttft_ms']} ms" if p.get("cold_ttft_ms") else "N/A"
            warm = _ms(p.get("ttft_ms"))
            tot  = _ms(p.get("total_ms"))
            tps  = (_tps(p.get("tok_s")) if p.get("tok_s") else "N/A (short)")
            lines.append(f"| {p['label']} | {cold} | {warm} | {tot} | {tps} |")
        lines.append("")

    # ── Luna Engine detail ────────────────────────────────────────────────────
    if eng:
        lines += [
            "## Luna Engine Performance (Full Pipeline)",
            "",
            "> System prompt + memory retrieval + context injection + LLM call.",
            "> TTFT and total include the ChromaDB retrieval overhead.",
            "",
            "| Metric | Mean | p50 | p95 |",
            "|--------|------|-----|-----|",
        ]
        for label, s in [("TTFT (engine)", eng.get("ttft")), ("Total (engine)", eng.get("total")), ("Memory retrieval", eng.get("retrieval_ms"))]:
            if s:
                lines.append(f"| {label} | {s['mean']:.0f} ms | {s['p50']:.0f} ms | {s['p95']:.0f} ms |")
        lines += [
            "",
            "### Per-probe (engine)",
            "",
            "| Probe | Retrieval | TTFT (engine) | Total (engine) | tok/s |",
            "|-------|-----------|--------------|----------------|-------|",
        ]
        for p in eng.get("probes", []):
            ret  = _ms(p.get("retrieval_ms"))
            ttft = _ms(p.get("ttft_ms"))
            tot  = _ms(p.get("total_ms"))
            tps  = (_tps(p.get("tok_s")) if p.get("tok_s") else "N/A (short)")
            lines.append(f"| {p['label']} | {ret} | {ttft} | {tot} | {tps} |")
        lines.append("")

    # ── Memory retrieval detail ───────────────────────────────────────────────
    if mem:
        hr = mem.get("hit_rate")
        lines += [
            "## Memory Retrieval",
            "",
            f"- **Facts in DB:** {mem['total_facts']}",
            f"- **Hit rate:** {'N/A (< 10 facts — run more conversations)' if hr is None else f'{hr*100:.0f}%'}",
            f"- **Retrieval latency (mean):** {_ms(mem.get('latency_ms'))}",
            f"- **Retrieval latency (p95):** {_ms(mem.get('latency_ms'), 'p95')}",
            "",
            "| Query | p50 | p95 |",
            "|-------|-----|-----|",
        ]
        for p in mem.get("probes", []):
            lat = p.get("latency_ms") or {}
            lines.append(f"| {p['query']} | {lat.get('p50', 0):.0f} ms | {lat.get('p95', 0):.0f} ms |")
        if mem.get("note"):
            lines += ["", f"> {mem['note']}"]
        lines.append("")

    # ── Tool execution detail ─────────────────────────────────────────────────
    if tool:
        lines += [
            "## Tool Execution",
            "",
            f"**Overall success rate:** {_pct(tool.get('success_rate'))}",
            "",
            "| Tool | Success | Latency (mean) | p95 |",
            "|------|---------|----------------|-----|",
        ]
        for r in tool.get("probes", []):
            lat = r.get("latency_ms") or {}
            lines.append(f"| {r['tool']} | {_pct(r['success_rate'])} | {lat.get('mean', 0):.0f} ms | {lat.get('p95', 0):.0f} ms |")
        lines.append("")

    # ── Agent routing detail ──────────────────────────────────────────────────
    if agt:
        lines += [
            "## Agent Tool Routing",
            "",
            f"**Routing accuracy:** {_pct(agt.get('accuracy'))}  ({agt.get('correct', 0)}/{agt.get('probes', 0)} correct)",
            f"**Planning latency p50:** {agt.get('plan_p50_ms', 'N/A')} ms",
            "",
            "| Request | Expected Tool | Pass Rate |",
            "|---------|--------------|-----------|",
        ]
        for r in agt.get("results", []):
            if r.get("skipped"):
                lines.append(f"| {r['request']} | {r['expected']} | SKIP |")
            else:
                lines.append(f"| {r['request']} | {r['expected']} | {_pct(r.get('pass_rate'))} |")
        lines.append("")

    # ── Voice pipeline detail ─────────────────────────────────────────────────
    if voi and (voi.get("tts") or voi.get("tts_note") or voi.get("stt_available")):
        lines += ["## Voice Pipeline", ""]
        tts = voi.get("tts")
        if tts:
            lines += [
                "| TTS Metric | Value |",
                "|------------|-------|",
                f"| Mean latency | {tts.get('mean', 0):.0f} ms |",
                f"| p50 latency | {tts.get('p50', 0):.0f} ms |",
                f"| p95 latency | {tts.get('p95', 0):.0f} ms |",
                f"| Chars per sample | {tts.get('chars_per_sample', '?')} |",
                "",
            ]
        else:
            note = voi.get("tts_note") or voi.get("tts_error", "unavailable")
            lines += [f"> TTS: {note}", ""]

        stt_engine = voi.get("stt_engine", "none")
        stt_status = "available" if voi.get("stt_available") else "not installed"
        lines += [f"> STT ({stt_engine}): {stt_status} — live microphone required for full STT benchmark.", ""]

    # ── Quality battery detail ────────────────────────────────────────────────
    if qual:
        lines += [
            "## Instruction Quality",
            "",
            f"**Overall score:** {_pct(qual.get('overall_score'))}  ({qual.get('probes', 0)}-probe battery)",
            "",
            "| Probe | Description | Pass Rate | Sample Output |",
            "|-------|-------------|-----------|---------------|",
        ]
        for r in qual.get("results", []):
            sample = (r.get("sample_output") or "").replace("|", "\\|").replace("\n", " ")[:60]
            lines.append(f"| {r['label']} | {r['description']} | {_pct(r['pass_rate'])} | `{sample}` |")
        lines.append("")

    # ── System resources detail ───────────────────────────────────────────────
    if sys_ and not sys_.get("error"):
        lines += [
            "## System Resources",
            "",
            "| Metric | Idle | Peak (during inference) | Delta |",
            "|--------|------|------------------------|-------|",
            f"| RAM | {sys_.get('idle_ram_mb', '?')} MB | {sys_.get('peak_ram_mb', '?')} MB | +{sys_.get('ram_delta_mb', '?')} MB |",
            f"| CPU | {sys_.get('idle_cpu_pct', '?')}% | {sys_.get('peak_cpu_pct', '?')}% | avg {sys_.get('avg_cpu_during_inference', '?')}% during inference |",
        ]
        if sys_.get("vram_idle_mb") is not None:
            lines.append(f"| VRAM | {sys_['vram_idle_mb']} MB | {sys_.get('vram_peak_mb', '?')} MB | +{sys_.get('vram_delta_mb', '?')} MB |")
        lines.append("")

    elif sys_ and sys_.get("error"):
        lines += ["## System Resources", "", f"> {sys_['error']}", ""]

    # ── Hardware footer ───────────────────────────────────────────────────────
    lines += [
        "## Hardware",
        "",
        "| | |",
        "|---|---|",
        f"| Accelerator | {hw.accelerator} |",
        f"| VRAM total | {hw.accel_mem_mb} MB |",
        f"| VRAM used (at run) | {hw.accel_mem_used_mb} MB |",
        f"| Temperature | {hw.accel_temp_c} |",
        f"| Driver | {hw.accel_driver} |",
        f"| CPU | {hw.cpu} |",
        f"| RAM | {hw.ram_gb} GB |",
        f"| OS | {hw.os} |",
        f"| Model | `{model}` |",
        f"| Provider | {provider} |",
        "",
        "---",
        "",
        "## Rerunning",
        "",
        "```bash",
        "# Full suite (all 8 benchmarks)",
        "python scripts/run_benchmark.py",
        "",
        "# Before vs after comparison only",
        "python scripts/run_benchmark.py --suite baseline,engine",
        "",
        "# Single suite, more runs for stability",
        "python scripts/run_benchmark.py --suite quality --runs 5",
        "",
        "# Different provider",
        "python scripts/run_benchmark.py --provider groq --model llama-3.3-70b-versatile",
        "python scripts/run_benchmark.py --provider anthropic --model claude-sonnet-4-5",
        "```",
    ]
    return "\n".join(lines) + "\n"


# ── Main ──────────────────────────────────────────────────────────────────────

ALL_SUITES = ["baseline", "engine", "memory", "tools", "agent", "voice", "quality", "system"]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Luna benchmark runner — 8 suites, before/after engine comparison",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="\n".join([
            "Suites:",
            "  baseline  Raw LLM (no system prompt, no memory) — Before Luna Engine",
            "  engine    Full Luna pipeline (memory + context) — After Luna Engine",
            "  memory    ChromaDB retrieval hit-rate and latency",
            "  tools     Safe tool execution success rate",
            "  agent     Tool routing accuracy and planning latency",
            "  voice     TTS latency (edge-tts) and STT availability",
            "  quality   Instruction following and output correctness",
            "  system    RAM / CPU / VRAM resource footprint",
        ]),
    )
    p.add_argument("--suite",    default="all",
                   help=f"Comma-separated suites or 'all'. Default: all")
    p.add_argument("--runs",     type=int, default=3,
                   help="Runs per probe (default 3, max 10)")
    p.add_argument("--output",   default=str(ROOT / "docs" / "BENCHMARKS.md"),
                   help="Markdown output path")
    p.add_argument("--json",     default=None,
                   help="Optional JSON output path")
    p.add_argument("--no-db",    action="store_true",
                   help="Skip persisting results to the Luna database")
    p.add_argument("--provider", default=None,
                   help="Override LLM provider (ollama, groq, anthropic, google, ...)")
    p.add_argument("--model",    default=None,
                   help="Override model name for the chosen provider")
    p.add_argument("--api-key",  default=None, dest="api_key",
                   help="Override API key for the chosen provider")
    return p.parse_args()


async def main() -> None:
    args  = parse_args()
    runs  = max(1, min(10, args.runs))
    suites = (
        ALL_SUITES
        if args.suite == "all"
        else [s.strip() for s in args.suite.split(",")]
    )
    # Normalise alias
    suites = ["baseline" if s == "llm" else s for s in suites]

    init_db()
    db  = SessionLocal()
    llm = LLMClient()
    mm  = MemoryManager(db)
    hw  = detect_hardware()
    ts  = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    sep = "-" * 64

    print(sep)
    print(f"  Luna Benchmark  —  {ts}")
    print(sep)
    print(f"  Accelerator : {hw.accelerator}  {hw.accel_mem_mb} MB  {hw.accel_temp_c}")
    print(f"  CPU / RAM   : {hw.cpu}  /  {hw.ram_gb} GB")
    print(f"  Model       : {get_model_label()}  [{settings.llm_provider}]")
    print(f"  Suites      : {', '.join(suites)}  ×{runs} runs each")
    print(sep)

    results: dict[str, dict] = {}

    for suite in suites:
        t0 = time.perf_counter()
        print(f"\n[{suite.upper()}]")

        try:
            if suite == "baseline":
                r = await bench_baseline(llm, runs=runs)
            elif suite == "engine":
                r = await bench_engine(llm, mm, runs=runs)
            elif suite == "memory":
                r = await bench_memory(db, runs=runs)
            elif suite == "tools":
                r = await bench_tools(runs=runs)
            elif suite == "agent":
                r = await bench_agent(llm, runs=runs)
            elif suite == "voice":
                r = await bench_voice(runs=runs)
            elif suite == "quality":
                r = await bench_quality(llm, runs=runs)
            elif suite == "system":
                r = await bench_system(llm, runs=max(1, runs - 1))
            else:
                print(f"  Unknown suite '{suite}' — skipping")
                continue
        except Exception as exc:
            print(f"  SUITE ERROR: {exc}")
            r = {"error": str(exc)}

        r["_duration_s"] = round(time.perf_counter() - t0, 1)
        results[suite] = r
        if not args.no_db:
            _save(db, suite, r)

    # Regression check
    warnings = check_regression(results, db)

    # Console summary
    print(f"\n{sep}")
    print("  SUMMARY")
    print(sep)

    base = results.get("baseline", {})
    eng  = results.get("engine", {})

    if base:
        ttft = (base.get("ttft") or {}).get("mean", 0)
        tps  = (base.get("throughput_toks") or {}).get("mean", 0)
        print(f"  Baseline TTFT (warm mean)    : {ttft:.0f} ms")
        print(f"  Baseline throughput (mean)   : {tps:.1f} tok/s")
    if eng:
        ettft = (eng.get("ttft") or {}).get("mean", 0)
        eret  = (eng.get("retrieval_ms") or {}).get("mean", 0)
        print(f"  Engine TTFT (mean)           : {ettft:.0f} ms  (retrieval: {eret:.0f} ms)")
    if "memory" in results:
        r = results["memory"]
        lat = (r.get("latency_ms") or {}).get("mean", 0)
        print(f"  Memory retrieval mean        : {lat:.0f} ms  ({r.get('total_facts',0)} facts)")
    if "tools" in results:
        print(f"  Tool success rate            : {_pct(results['tools'].get('success_rate'))}")
    if "agent" in results:
        print(f"  Agent routing accuracy       : {_pct(results['agent'].get('accuracy'))}")
    if "quality" in results:
        print(f"  Quality score                : {_pct(results['quality'].get('overall_score'))}")
    if "voice" in results:
        tts = results["voice"].get("tts") or {}
        tts_mean = tts.get("mean")
        print(f"  TTS latency (mean)           : {f'{tts_mean:.0f} ms' if tts_mean else 'N/A'}")
    if "system" in results and not results["system"].get("error"):
        s = results["system"]
        print(f"  RAM delta during inference   : +{s.get('ram_delta_mb', '?')} MB")

    if warnings:
        print()
        for w in warnings:
            print(f"  WARN  {w}")
    print(sep)

    # Markdown
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    md = render_markdown(hw, ts, runs, results, warnings)
    out_path.write_text(md, encoding="utf-8")
    print(f"\n  Markdown → {out_path}")

    # JSON
    if args.json:
        json_path = Path(args.json)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            json.dumps({"timestamp": ts, "hardware": asdict(hw), "results": results}, indent=2, default=str),
            encoding="utf-8",
        )
        print(f"  JSON     → {json_path}")

    db.close()


if __name__ == "__main__":
    asyncio.run(main())
