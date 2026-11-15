"""Deep-thread eval: one architecture + coding conversation of 32 follow-up turns.

Every turn builds on earlier decisions and code. Probes check that the
decisions from turn 1, the code from turn 5 and the recommendation from turn 6
still hold near the end. Also records routing (which path answered), refusals,
and whether later code stays on the chosen stack.
"""
import json
import os
import re
import sys
import time

import httpx

API = os.environ.get("LUNA_API", "http://127.0.0.1:8898") + "/api/chat"
OUT = sys.argv[1] if len(sys.argv) > 1 else "deep_thread_results.json"

DECISIONS = ("We're building a URL shortener called Snip. Decisions so far: FastAPI backend, PostgreSQL for storage, "
             "Redis cache with a 24-hour TTL, 7-character base62 codes, and we deploy on AWS ECS. Keep all of that "
             "in mind for the rest of this chat. First, just confirm the plan in two lines.")
RECAP = "Quick recap: which database, what cache TTL, what code length and which deploy platform did we pick at the start?"
RECAP_KEYS = {"postgres": r"postgres", "24h ttl": r"24", "7 chars": r"\b7\b|seven", "ecs": r"\becs\b"}

TURNS = [
    ("plan", DECISIONS),
    ("arch", "Sketch the high-level architecture for Snip given those choices."),
    ("schema", "Design the PostgreSQL schema for links and click events."),
    ("models", "Write the SQLAlchemy models for that schema."),
    ("encoder", "Write the base62 encoder for our 7-character codes in Python."),
    ("strategy", "Counter-based or random codes? Pick one for our setup and justify it briefly."),
    ("shorten", "Write the FastAPI POST /shorten endpoint using the models and encoder from before."),
    ("redirect", "Now the GET /{code} redirect endpoint, using the Redis cache we chose."),
    ("probe_recap_1", RECAP),
    ("invalidate", "How do we handle cache invalidation when a link is deleted?"),
    ("delete", "Add a DELETE /links/{code} endpoint consistent with the previous endpoints."),
    ("ratelimit_q", "We need rate limiting on /shorten. What approach fits our stack?"),
    ("ratelimit", "Write that rate limiter using Redis."),
    ("analytics_q", "How should we record click analytics without slowing down redirects?"),
    ("worker", "Write the background worker that writes click events into the table we designed."),
    ("probe_code", "What was the name of the function you wrote for base62 encoding, and what alphabet did it use?"),
    ("test_shorten", "Write pytest tests for the /shorten endpoint."),
    ("test_redirect", "Write tests for the redirect endpoint, including a cache hit and a cache miss."),
    ("alias_schema", "We want custom aliases. How does the schema change?"),
    ("alias_code", "Update the /shorten endpoint to accept an optional custom alias."),
    ("collisions", "Roughly, what's the collision risk for random 7-character base62 codes at 10 million links?"),
    ("ecs", "Design the ECS deployment: services, load balancer, autoscaling."),
    ("docker", "Write a Dockerfile for the FastAPI app."),
    ("probe_recap_2", "Remind me: what's the project called, and what TTL did we set for the cache?"),
    ("expiry", "How would we add expiring links? Schema change and logic."),
    ("migration", "Write the Alembic migration for the expiry column."),
    ("monitoring", "How do we monitor this in production? Key metrics and alerts."),
    ("security", "Security review: top 3 risks for Snip and how to fix each."),
    ("validation", "Write URL validation for /shorten that blocks javascript: URLs and internal IPs."),
    ("refactor", "Refactor: move the Redis logic out of the endpoints into a small cache module."),
    ("layout", "Give me the final file layout of the project."),
    ("probe_final", RECAP + " And which code generation strategy did you recommend earlier, counter-based or random?"),
]
REFUSAL_RE = re.compile(r"i (?:don't|do not) have a tool|i can't (?:write|generate|help with) (?:code|that)", re.I)
OFF_STACK_RE = re.compile(r"\b(?:mongodb|mysql|dynamodb|memcached|flask|django|express|kubernetes deployment|gke|heroku)\b", re.I)


def send(client, message, conv_id):
    started = time.time()
    text, kinds = "", set()
    with client.stream("POST", f"{API}/stream", json={"message": message, "conversation_id": conv_id}, timeout=900) as r:
        for line in r.iter_lines():
            if not line.startswith("data:"):
                continue
            ev = json.loads(line[5:])
            kinds.add(ev.get("type"))
            if ev.get("type") == "meta":
                conv_id = ev.get("conversation_id") or conv_id
            elif ev.get("type") == "message_part":
                text += ("\n\n" if text else "") + ev.get("content", "")
    return conv_id, text.strip(), sorted(k for k in kinds if k), round(time.time() - started, 1)


def main():
    results = {"turns": [], "probes": {}}
    replies = {}
    with httpx.Client() as client:
        client.post(f"{API}/context", json={"active_conversation_id": None})
        conv = None
        for n, (label, message) in enumerate(TURNS, start=1):
            conv, reply, kinds, secs = send(client, message, conv)
            replies[label] = reply
            path = ("crew" if "crew_done" in kinds or "agent_token" in kinds
                    else "coding-agent" if "coding_tool_call" in kinds else "chat")
            row = {"n": n, "label": label, "secs": secs, "chars": len(reply), "path": path,
                   "refusal": bool(REFUSAL_RE.search(reply)), "off_stack": OFF_STACK_RE.findall(reply)[:3],
                   "reply": reply[:1500]}
            results["turns"].append(row)
            flags = [f for f in (path != "chat" and path, row["refusal"] and "REFUSAL", row["off_stack"] and f"off-stack {row['off_stack']}") if f]
            print(f"[{n:>2}] {label:<14} {secs:>6.1f}s {len(reply):>5} chars {flags or ''}", flush=True)

            if label.startswith("probe_recap") or label == "probe_final":
                low = reply.lower()
                score = {k: bool(re.search(p, low)) for k, p in RECAP_KEYS.items()} if label != "probe_recap_2" else \
                        {"snip": "snip" in low, "24h ttl": bool(re.search(r"24", low))}
                if label == "probe_final":
                    rec = replies.get("strategy", "").lower()
                    chose = "counter" if rec.find("counter") != -1 and (rec.find("random") == -1 or rec.find("counter") < rec.find("random")) else "random"
                    score["same strategy as turn 6"] = chose in low
                results["probes"][label] = score
                print("     ", score, flush=True)
            if label == "probe_code":
                names = re.findall(r"def\s+(\w+)", replies.get("encoder", ""))
                score = {"function name from turn 5": bool(names) and any(nm in reply for nm in names),
                         "names_in_turn_5": names[:3]}
                results["probes"][label] = score
                print("     ", score, flush=True)
            json.dump({**results, "conversation_id": conv}, open(OUT, "w", encoding="utf-8"), indent=2)
    results["conversation_id"] = conv
    json.dump(results, open(OUT, "w", encoding="utf-8"), indent=2)
    print("conversation_id", conv)


if __name__ == "__main__":
    main()
