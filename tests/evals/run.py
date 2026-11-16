"""Run Luna's conversation evals against an isolated backend.

    python -m tests.evals.run                     # all suites
    python -m tests.evals.run --suite scenarios   # or: deep, long

Snapshots the real data (SQLite backup API + Chroma copy) into
.tmp/luna-eval-data, starts a second backend on port 8898 with that copy,
BACKGROUND_JOBS_ENABLED=false (no reminders or check-ins) and its own shared
conversation state, runs the suites, prints a scorecard and stops the backend.
The live backend, its chats and memory are never touched. Results land in
.tmp/evals/<suite>-<timestamp>.json.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
EVAL_DATA = ROOT / ".tmp" / "luna-eval-data"
RESULTS = ROOT / ".tmp" / "evals"
PORT = 8898
SUITES = {"scenarios": "scenarios.py", "deep": "deep_thread.py", "long": "long_context.py"}   # fastest first


def snapshot() -> None:
    shutil.rmtree(EVAL_DATA, ignore_errors=True)
    EVAL_DATA.mkdir(parents=True)
    src, dst = sqlite3.connect(DATA / "luna.db"), sqlite3.connect(EVAL_DATA / "luna.db")
    src.backup(dst)
    dst.close()
    src.close()
    if (DATA / "chroma").exists():
        shutil.copytree(DATA / "chroma", EVAL_DATA / "chroma")
    for name in ("rlhf_pairs.json", "permissions.json"):
        if (DATA / name).exists():
            shutil.copy(DATA / name, EVAL_DATA / name)


def start_backend() -> subprocess.Popen:
    env = {**os.environ, "LUNA_DATA_DIR": str(EVAL_DATA), "PORT": str(PORT), "BACKGROUND_JOBS_ENABLED": "false",
           "DECISION_LOG_ENABLED": "true"}   # logged in the eval data dir: shows each turn's route
    log = open(RESULTS / "eval-backend.log", "w", encoding="utf-8")
    proc = subprocess.Popen([sys.executable, str(ROOT / "server" / "server.py")], cwd=ROOT, env=env,
                            stdout=log, stderr=subprocess.STDOUT)
    for _ in range(120):
        try:
            if httpx.get(f"http://127.0.0.1:{PORT}/api/system/health", timeout=2).status_code == 200:
                return proc
        except httpx.HTTPError:
            pass
        if proc.poll() is not None:
            raise RuntimeError(f"Eval backend exited; see {RESULTS / 'eval-backend.log'}")
        time.sleep(1)
    proc.kill()
    raise RuntimeError("Eval backend did not become healthy in 120 s")


def scorecard(suite: str, path: Path) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if "scenarios" in data:
        rows = data["scenarios"]
        lines = [f"{suite}: {sum(r['ok'] for r in rows)}/{len(rows)} passed"]
        lines += [f"  FAIL {r['name']}: {'; '.join(r['problems'])}" for r in rows if not r["ok"]]
        return lines
    turns = data.get("turns", [])
    lines = [f"{suite}: {len(turns)} turns, median {sorted(t['secs'] for t in turns)[len(turns) // 2]:.1f}s"
             if turns else f"{suite}: no turns"]
    empty = [t["n"] for t in turns if not t.get("chars", t.get("chars_out", 1))]
    if empty:
        lines.append(f"  empty replies at turns {empty}")
    for name, score in (data.get("probes") or {}).items() if isinstance(data.get("probes"), dict) else []:
        checks = {k: v for k, v in score.items() if isinstance(v, bool)}
        lines.append(f"  {name}: {sum(checks.values())}/{len(checks)} {checks}")
    for probe in data.get("probes", []) if isinstance(data.get("probes"), list) else []:
        score = probe["score"]
        ok = sum(score.values()) if isinstance(score, dict) else int(bool(score))
        total = len(score) if isinstance(score, dict) else 1
        lines.append(f"  {probe['kind']} after {probe['after_filler']}: {ok}/{total}")
    for needle in data.get("needles", []):
        lines.append(f"  needle {needle['tokens']} tokens: {'found' if needle['found'] else 'MISSED'}")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Luna's conversation evals on an isolated backend.")
    parser.add_argument("--suite", choices=[*SUITES, "all"], default="all")
    args = parser.parse_args(argv)
    suites = list(SUITES) if args.suite == "all" else [args.suite]

    RESULTS.mkdir(parents=True, exist_ok=True)
    snapshot()
    proc = start_backend()
    report = []
    try:
        for suite in suites:
            out = RESULTS / f"{suite}-{datetime.now():%Y%m%d-%H%M%S}.json"
            print(f"running {suite} …", flush=True)
            subprocess.run([sys.executable, "-u", str(Path(__file__).with_name(SUITES[suite])), str(out)],
                           cwd=ROOT, check=False, env={**os.environ, "LUNA_API": f"http://127.0.0.1:{PORT}",
                                                       "LUNA_EVAL_DB": str(EVAL_DATA / "luna.db")})
            if out.exists():
                report += scorecard(suite, out)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
    print("\n".join(["", "Scorecard"] + report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
