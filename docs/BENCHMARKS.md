# Luna Benchmark Results

> **Run:** 2026-05-22 01:05 UTC  
> **Hardware:** NVIDIA GeForce RTX 3060  12288 MB VRAM  (driver 596.21)  
> **CPU:** Intel64 Family 6 Model 151 Stepping 2, GenuineIntel  31.8 GB RAM  
> **OS:** Windows 11  
> **Model:** `qcwind/qwen3-8b-instruct-Q4-K-M:latest`  provider: `ollama`  
> **Runs per probe:** 3  (cold call tracked separately; warm stats exclude it)

## Regressions vs previous run

- [memory] retrieval latency regressed +32%  (599.1 → 790.3)

## Before vs After Luna Engine

> **Baseline** = raw LLM call with no system prompt and no memory retrieval.  
> **Luna Engine** = full pipeline: memory retrieval → context injection → LLM call.  
> Overhead is the cost Luna adds; context quality is what it buys.

| Metric | Raw LLM (Baseline) | Luna Engine | Overhead |
|--------|-------------------:|------------:|----------|
| TTFT p50 | **692 ms** | **1258 ms** | +567 ms (+82%) |
| TTFT p95 | 712 ms | 1312 ms | +600 ms (+84%) |
| TTFT mean | 689 ms | 1256 ms | +567 ms (+82%) |
| Sustained tok/s | **47 tok/s** | **41 tok/s** | decode speed unaffected |
| Memory retrieval | — | 566 ms avg | included in overhead |
| Context quality | plain | memory-augmented | ✓ user history injected |
| Tool success rate | — | 100% | tools require engine |
| Routing accuracy | — | 67% | tool selection |
| Quality score | — | 88% | instruction following |

## Summary

| Suite | Key Metric | Value | Notes |
|-------|-----------|-------|-------|
| Baseline LLM | TTFT p50 | **692 ms** | raw provider, no Luna overhead |
| Baseline LLM | Throughput | **47 tok/s** | long-form generation |
| Luna Engine | TTFT p50 | **1258 ms** | includes memory retrieval |
| Luna Engine | Retrieval | 566 ms avg | ChromaDB vector search |
| Memory | Hit rate | N/A (< 10 facts) | category-matched facts |
| Memory | Latency p50 | 852 ms | retrieval only |
| Tools | Success rate | 100% | safe tools only |
| Agent | Routing accuracy | 67% | correct tool selected |
| Agent | Planning p50 | 1204 ms | tool selection latency |
| Voice | TTS p50 | 662 ms | edge-tts generation |
| Voice | STT | available | vosk |
| Quality | Instruction score | 88% | 8-probe battery |
| System | Peak RAM delta | 0.0 MB | inference overhead |
| System | VRAM delta | 49 MB | model VRAM usage |

## Baseline LLM Performance (Raw Provider)

> No system prompt. No memory. No Luna overhead.
> This is the maximum possible speed for the configured provider.

| Metric | Mean | p50 | p95 | stddev |
|--------|------|-----|-----|--------|
| TTFT | 689 ms | 692 ms | 712 ms | 15 ms |
| Total latency | 1704 ms | 911 ms | 4525 ms | 1282 ms |
| Throughput | 47 tok/s | 57 tok/s | 62 tok/s | 13 tok/s |

### Per-probe

| Probe | Cold TTFT | Warm TTFT (mean) | Warm Total (mean) | tok/s |
|-------|-----------|-----------------|-------------------|-------|
| echo | 3334 ms | 700 ms | 718 ms | N/A (short) |
| arithmetic | 3347 ms | 698 ms | 755 ms | N/A (short) |
| short-list | 3314 ms | 693 ms | 903 ms | N/A (short) |
| medium | 3328 ms | 684 ms | 3983 ms | 48 tok/s |
| long | 3315 ms | 668 ms | 2162 ms | 47 tok/s |

## Luna Engine Performance (Full Pipeline)

> System prompt + memory retrieval + context injection + LLM call.
> TTFT and total include the ChromaDB retrieval overhead.

| Metric | Mean | p50 | p95 |
|--------|------|-----|-----|
| TTFT (engine) | 1256 ms | 1258 ms | 1312 ms |
| Total (engine) | 2279 ms | 1565 ms | 4658 ms |
| Memory retrieval | 566 ms | 568 ms | 582 ms |

### Per-probe (engine)

| Probe | Retrieval | TTFT (engine) | Total (engine) | tok/s |
|-------|-----------|--------------|----------------|-------|
| echo | 560 ms | 1241 ms | 1258 ms | N/A (short) |
| arithmetic | 567 ms | 1260 ms | 1312 ms | N/A (short) |
| short-list | 568 ms | 1262 ms | 1558 ms | N/A (short) |
| medium | 569 ms | 1246 ms | 4186 ms | 44 tok/s |
| long | 566 ms | 1271 ms | 3082 ms | 39 tok/s |

## Memory Retrieval

- **Facts in DB:** 0
- **Hit rate:** N/A (< 10 facts — run more conversations)
- **Retrieval latency (mean):** 790 ms
- **Retrieval latency (p95):** 1005 ms

| Query | p50 | p95 |
|-------|-----|-----|
| my name | 561 ms | 566 ms |
| my job | 609 ms | 1005 ms |
| my hobbies | 856 ms | 878 ms |
| where I live | 869 ms | 921 ms |
| food preference | 833 ms | 852 ms |
| close contacts | 914 ms | 964 ms |

> Re-run after 10+ conversations for quality metrics.

## Tool Execution

**Overall success rate:** 100%

| Tool | Success | Latency (mean) | p95 |
|------|---------|----------------|-----|
| workspace_list | 100% | 3 ms | 3 ms |
| web_search | 100% | 1384 ms | 1635 ms |

## Agent Tool Routing

**Routing accuracy:** 67%  (2/3 correct)
**Planning latency p50:** 1204 ms

| Request | Expected Tool | Pass Rate |
|---------|--------------|-----------|
| list my workspace files | workspace_list | SKIP |
| search the web for latest AI news | web_search | 100% |
| what are my tasks for today | list_tasks | SKIP |
| remember that my favorite color is blue | save_fact | SKIP |
| open spotify and play jazz | spotify_play | 100% |
| launch chrome | launch_app | 0% |

## Voice Pipeline

| TTS Metric | Value |
|------------|-------|
| Mean latency | 672 ms |
| p50 latency | 662 ms |
| p95 latency | 788 ms |
| Chars per sample | 53 |

> STT (vosk): available — live microphone required for full STT benchmark.

## Instruction Quality

**Overall score:** 88%  (8-probe battery)

| Probe | Description | Pass Rate | Sample Output |
|-------|-------------|-----------|---------------|
| exact-output | exact output compliance | 100% | `42` |
| structured-list | structured list compliance | 100% | `Apple   Banana   Orange` |
| persona | persona consistency | 0% | `I am Qwen, a large-scale language model designed to assist w` |
| factuality | basic factuality | 100% | `4` |
| negation | negation instruction following | 100% | `Hi there! How are you?` |
| json-format | JSON format compliance | 100% | ````json {   "name": "ExampleApp",   "version": "1.0.0" } ```` |
| counting | sequential counting | 100% | `1 2 3 4 5` |
| long-context | long-context retention | 100% | `Soft white clouds drift by,   Whispering secrets to the sky—` |

## System Resources

| Metric | Idle | Peak (during inference) | Delta |
|--------|------|------------------------|-------|
| RAM | 147.0 MB | 147.0 MB | +0.0 MB |
| CPU | 11.0% | 57.1% | avg 1.7% during inference |
| VRAM | 8737 MB | 8786 MB | +49 MB |

## Hardware

| | |
|---|---|
| Accelerator | NVIDIA GeForce RTX 3060 |
| VRAM total | 12288 MB |
| VRAM used (at run) | 3469 MB |
| Temperature | 47 C |
| Driver | 596.21 |
| CPU | Intel64 Family 6 Model 151 Stepping 2, GenuineIntel |
| RAM | 31.8 GB |
| OS | Windows 11 |
| Model | `qcwind/qwen3-8b-instruct-Q4-K-M:latest` |
| Provider | ollama |

---

## Rerunning

```bash
# Full suite (all 8 benchmarks)
python scripts/run_benchmark.py

# Before vs after comparison only
python scripts/run_benchmark.py --suite baseline,engine

# Single suite, more runs for stability
python scripts/run_benchmark.py --suite quality --runs 5

# Different provider
python scripts/run_benchmark.py --provider groq --model llama-3.3-70b-versatile
python scripts/run_benchmark.py --provider anthropic --model claude-sonnet-4-5
```
