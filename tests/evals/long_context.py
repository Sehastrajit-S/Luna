"""Long-context eval: does Luna hold facts and find needles far past its context window?

One conversation, driven well past the model's 16k-token window:
  1. plant four facts in turn 1;
  2. ~30 filler turns asking for long explanations (grows history, triggers the
     rolling summary and context fitting);
  3. recall probes at intervals (facts from turn 1, and "what was my 2nd topic");
  4. a tool call deep into the chat;
  5. needle-in-a-haystack: one long pasted message (~8k and ~20k tokens) with a
     passphrase hidden in the middle.
Writes results to long_context_results.json and prints a summary. Run it against an
isolated instance (python -m tests.evals.run), never the live backend: every
message becomes the shared active conversation, which the desktop app follows.
"""
import json
import os
import random
import sys
import time

import httpx

API = os.environ.get("LUNA_API", "http://127.0.0.1:8898") + "/api/chat"
OUT = sys.argv[1] if len(sys.argv) > 1 else "long_context_results.json"

FACTS = {"codename": "BLUEFIN", "region": "eu-north-7", "budget": "4,820", "codeword": "marmalade"}
PLANT = ("For this session, please remember four project details: the project codename is BLUEFIN, "
         "the deploy region is eu-north-7, the test budget is $4,820, and the reviewer's code word is "
         "'marmalade'. Just confirm you've got them.")
FACT_PROBE = ("Quick check without looking anything up: what are the project codename, the deploy region, "
              "the test budget and the reviewer's code word I gave you at the start of this chat?")
TOPICS = [
    "how TCP congestion control works (slow start, AIMD, fast recovery)",
    "how a B-tree index speeds up database lookups",
    "the difference between processes and threads in an operating system",
    "how public-key cryptography and TLS handshakes work",
    "how garbage collection works in the JVM",
    "how transformers use self-attention",
    "how DNS resolution works end to end",
    "the CAP theorem with real database examples",
    "how CPU caches and cache coherence work",
    "how Git stores commits, trees and blobs",
    "how a compiler turns source code into machine code",
    "how Kubernetes schedules pods",
    "how HTTP/2 differs from HTTP/1.1",
    "how Raft consensus elects a leader",
    "how virtual memory and page tables work",
    "how React's reconciliation algorithm works",
    "how bloom filters work and where they're used",
    "how gradient descent and backpropagation train a neural network",
    "how OAuth 2.0 authorization code flow works",
    "how LSM trees work in databases like RocksDB",
    "how the Linux kernel handles system calls",
    "how CDNs cache and invalidate content",
    "how containers isolate processes with namespaces and cgroups",
    "how SSDs handle wear leveling",
    "how event loops work in Node.js",
    "how MapReduce processes large datasets",
    "how WebSockets keep a connection open",
    "how rate limiters like token bucket work",
]


def send(client, message, conv_id):
    started = time.time()
    text, tools, errors = "", [], []
    with client.stream("POST", f"{API}/stream", json={"message": message, "conversation_id": conv_id}, timeout=900) as r:
        for line in r.iter_lines():
            if not line.startswith("data:"):
                continue
            ev = json.loads(line[5:])
            kind = ev.get("type")
            if kind == "meta":
                conv_id = ev.get("conversation_id") or conv_id
            elif kind == "message_part":
                text += ("\n\n" if text else "") + ev.get("content", "")
            elif kind == "tool_call":
                tools.append(ev["tool"])
            elif kind == "error":
                errors.append(ev.get("message", ""))
    return conv_id, text.strip(), tools, errors, round(time.time() - started, 1)


def fact_score(reply):
    low = reply.lower().replace("$", "")
    return {k: v.lower() in low for k, v in FACTS.items()}


def haystack(target_tokens, needle):
    random.seed(7)
    words = ("system network latency buffer cache request server client packet schedule memory thread "
             "queue storage index cluster replica shard token stream record batch commit").split()
    sentences = []
    while sum(len(s) for s in sentences) < target_tokens * 4:
        sentences.append(" ".join(random.choice(words) for _ in range(14)).capitalize() + ".")
    sentences.insert(len(sentences) // 2, needle)
    return " ".join(sentences)


def main():
    results = {"turns": [], "probes": [], "needles": []}
    with httpx.Client() as client:
        client.post(f"{API}/context", json={"active_conversation_id": None})
        conv = None

        def turn(label, message):
            nonlocal conv
            conv, reply, tools, errors, secs = send(client, message, conv)
            row = {"n": len(results["turns"]) + 1, "label": label, "secs": secs, "chars_in": len(message),
                   "chars_out": len(reply), "tools": tools, "errors": errors, "reply": reply[:600]}
            results["turns"].append(row)
            print(f"[{row['n']:>2}] {label:<14} {secs:>6.1f}s out={len(reply):>5} tools={tools} errors={errors}", flush=True)
            json.dump({**results, "conversation_id": conv}, open(OUT, "w", encoding="utf-8"), indent=2)
            return reply

        turn("plant", PLANT)
        for i, topic in enumerate(TOPICS, start=1):
            turn(f"filler {i}", f"Explain {topic} in about 300 words.")
            if i in (8, 18, 28):
                reply = turn("fact probe", FACT_PROBE)
                results["probes"].append({"after_filler": i, "kind": "facts", "score": fact_score(reply), "reply": reply[:400]})
                print("     facts:", fact_score(reply), flush=True)
            if i == 20:
                reply = turn("topic probe", "Without looking anything up: what was the second topic I asked you to explain in this chat?")
                ok = "b-tree" in reply.lower() or "btree" in reply.lower()
                results["probes"].append({"after_filler": i, "kind": "second topic (B-tree)", "score": ok, "reply": reply[:400]})
                print("     second topic recalled:", ok, flush=True)

        turn("late tool", "What's my system volume right now?")

        for size in (8000, 20000):
            needle = f"The vault passphrase for test {size} is copper-lantern-{size // 1000}."
            reply = turn(f"needle {size // 1000}k",
                         "Here is a long log dump:\n\n" + haystack(size, needle) +
                         f"\n\nQuestion: what is the vault passphrase for test {size} mentioned in the log above? "
                         "If you can't find it, say so.")
            found = f"copper-lantern-{size // 1000}" in reply.lower()
            results["needles"].append({"tokens": size, "found": found, "reply": reply[:400]})
            print(f"     needle {size} found: {found}", flush=True)

        reply = turn("final probe", FACT_PROBE)
        results["probes"].append({"after_filler": "end", "kind": "facts", "score": fact_score(reply), "reply": reply[:400]})
        print("     facts:", fact_score(reply), flush=True)

    results["conversation_id"] = conv
    json.dump(results, open(OUT, "w", encoding="utf-8"), indent=2)
    print("conversation_id", conv)


if __name__ == "__main__":
    main()
