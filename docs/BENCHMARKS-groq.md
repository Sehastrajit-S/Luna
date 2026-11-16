# Luna Benchmark Results

> **Run:** 2026-05-21 23:10 UTC  
> **Hardware:** NVIDIA GeForce RTX 3060  12288 MB VRAM  (driver 596.21)  
> **CPU:** Intel64 Family 6 Model 151 Stepping 2, GenuineIntel  31.8 GB RAM  
> **OS:** Windows 11  
> **Model:** `llama-3.3-70b-versatile`  provider: `groq`  
> **Runs per probe:** 3  (cold call reported separately; warm stats exclude it)

## Summary

| Metric | Value | Notes |
|--------|-------|-------|
| LLM TTFT (warm, p50) | **494 ms** | first token latency |
| LLM TTFT (warm, p95) | 610.9 ms | tail latency |
| Sustained throughput | **210 tok/s** | long-form prompts only |
| Memory retrieval p50 | N/A | ChromaDB vector search |
| Tool success rate    | 0% | safe tools only |

## LLM Latency

> Throughput (tok/s) is only reported for long-form prompts (50+ output tokens).
> Short prompts measure TTFT responsiveness, not decode speed.

### Distribution (warm calls, all probes)

| Metric | Value |
|--------|-------|
| TTFT mean | 494 ms  (p50 482  p95 611  sd 43) |
| Total mean | 702 ms  (p50 502  p95 1233  sd 281) |
| Throughput | 210 tok/s  (p50 210  p95 225  sd 8) |

### Per-prompt

| Probe | Cold TTFT | Warm TTFT (mean) | Warm Total (mean) | tok/s |
|-------|-----------|------------------|-------------------|-------|
| echo | 477 ms | 481 ms | 491 ms | N/A (short) |
| arithmetic | 517 ms | 472 ms | 473 ms | N/A (short) |
| short-list | 474 ms | 463 ms | 490 ms | N/A (short) |
| medium | 516 ms | 566 ms | 1161 ms | 212 tok/s |
| long | 508 ms | 490 ms | 894 ms | 209 tok/s |

## Memory Retrieval

| Metric | Value |
|--------|-------|
| Facts in DB | 0 |
| Hit rate | N/A (< 10 facts) |
| Retrieval latency | N/A |

## Tool Execution

**Overall success rate:** 0%

| Tool | Success Rate | Latency (mean) | p95 |
|------|-------------|----------------|-----|

## System

| | |
|---|---|
| Accelerator | NVIDIA GeForce RTX 3060 |
| VRAM total | 12288 MB |
| VRAM used (at run) | 3530 MB |
| Temperature | 49 C |
| Driver | 596.21 |
| CPU | Intel64 Family 6 Model 151 Stepping 2, GenuineIntel |
| RAM | 31.8 GB |
| OS | Windows 11 |
| Model | `llama-3.3-70b-versatile` |
| Provider | groq |

---

## Rerunning

```bash
python scripts/run_benchmark.py
python scripts/run_benchmark.py --suite llm --runs 5
```
