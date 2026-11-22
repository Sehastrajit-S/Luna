"""Live, read-only view of Luna's memory in your browser.

    .venv/Scripts/python scripts/memory_viewer.py            → http://127.0.0.1:8798

The page updates the moment Luna learns, reinforces, refines, replaces, merges,
expires or forgets a memory. The database is opened read-only and Luna's vector
store is never touched: similarity links come from embedding the facts here,
with the same embedding model Luna uses.

Options: --port N, --db PATH (default: Luna's configured SQLite file), --no-open,
--no-similarity (skip embeddings).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import queue
import sqlite3
import sys
import threading
import time
import webbrowser
from collections import deque
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
PAGE = Path(__file__).with_name("memory_viewer.html")

FACT_COLUMNS = ("id", "category", "content", "confidence", "importance", "source", "memory_type", "is_active",
                "is_private", "expires_at", "superseded_by", "source_conversation_id", "created_at", "updated_at")
LINK_COLUMNS = ("id", "fact_id_a", "fact_id_b", "relationship", "confidence", "note", "created_at")
TIME_FIELDS = ("expires_at", "created_at", "updated_at")
SIMILAR_DISTANCE = 0.35        # cosine distance under which two facts get a similarity link
SIMILAR_PER_FACT = 3
POLL_SECONDS = 0.5


def database_path(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    from server.config import settings
    url = (settings.db_url or "").strip()
    if url and not url.startswith("sqlite"):
        sys.exit("The memory viewer reads SQLite only, and db_url points at another database.")
    return Path(url.split(":///", 1)[1]) if url else Path(settings.db_path)


def iso(value) -> str | None:
    """Database times are naive UTC; send them as ISO with a Z."""
    if not value:
        return None
    try:
        when = datetime.fromisoformat(str(value).replace("T", " "))
    except ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return when.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def short(text: str, n: int = 90) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[: n - 1] + "…"


class MemoryState:
    def __init__(self, db_path: Path, similarity: bool) -> None:
        self.db_path = db_path
        self.lock = threading.Lock()
        self.facts: dict[int, dict] = {}
        self.links: list[dict] = []
        self.conversations: dict[int, str] = {}
        self.changes: deque[dict] = deque(maxlen=400)
        self.similar: list[list] = []
        self.status = "starting"
        self.embed_status = "on" if similarity else "off"
        self.version = 0
        self.listeners: set[queue.Queue] = set()
        self._conn: sqlite3.Connection | None = None
        self._data_version = None
        self._loaded = False
        self._embeddings: dict[str, list[float]] = {}
        self._embed_wake = threading.Event()
        if similarity:
            threading.Thread(target=self._embed_worker, daemon=True).start()

    # ── Reading ──────────────────────────────────────────────────────────────
    def _connect(self) -> sqlite3.Connection:
        if not self.db_path.exists():
            raise sqlite3.OperationalError(f"no database at {self.db_path}")
        conn = sqlite3.connect(f"file:{self.db_path.as_posix()}?mode=ro", uri=True, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _read(self) -> tuple[dict[int, dict], list[dict], dict[int, str]]:
        c = self._conn
        facts = {}
        for row in c.execute(f"SELECT {', '.join(FACT_COLUMNS)} FROM facts"):
            f = dict(row)
            for k in TIME_FIELDS:
                f[k] = iso(f[k])
            f["is_active"] = bool(f["is_active"])
            f["is_private"] = bool(f["is_private"])
            facts[f["id"]] = f
        links = []
        for row in c.execute(f"SELECT {', '.join(LINK_COLUMNS)} FROM fact_relationships"):
            link = dict(row)
            link["created_at"] = iso(link["created_at"])
            links.append(link)
        ids = sorted({f["source_conversation_id"] for f in facts.values() if f["source_conversation_id"]})
        convs = {}
        if ids:
            marks = ",".join("?" * len(ids))
            for row in c.execute(f"SELECT id, title FROM conversations WHERE id IN ({marks})", ids):
                convs[row["id"]] = row["title"] or ""
        return facts, links, convs

    def watch(self) -> None:
        """Re-read whenever another connection (Luna) commits to the database."""
        while True:
            try:
                if self._conn is None:
                    self._conn = self._connect()
                    self._data_version = None
                version = self._conn.execute("PRAGMA data_version").fetchone()[0]
                if version != self._data_version:
                    self._data_version = version
                    self.refresh()
                if self.status != "live":
                    self.status = "live"
                    self._publish()
            except sqlite3.Error as e:
                if self._conn is not None:
                    try:
                        self._conn.close()
                    except sqlite3.Error:
                        pass
                self._conn = None
                message = f"can't read the database: {e}"
                if self.status != message:
                    self.status = message
                    self._publish()
                time.sleep(2)
            time.sleep(POLL_SECONDS)

    def refresh(self) -> None:
        facts, links, convs = self._read()
        with self.lock:
            if self._loaded and facts == self.facts and links == self.links and convs == self.conversations:
                return
            if self._loaded:
                for change in reversed(self._diff(self.facts, facts, self.links, links)):
                    self.changes.appendleft(change)
            else:
                self.changes.extend(self._history(facts, links))
                self._loaded = True
            self.facts, self.links, self.conversations = facts, links, convs
        self._embed_wake.set()
        self._publish()

    # ── What changed ─────────────────────────────────────────────────────────
    @staticmethod
    def _history(facts: dict[int, dict], links: list[dict]) -> list[dict]:
        """Before the viewer was running: the latest activity, from timestamps."""
        events = []
        for f in facts.values():
            if f["created_at"]:
                events.append({"at": f["created_at"], "kind": "learned", "fact_id": f["id"],
                               "text": short(f["content"]), "earlier": True})
            retired = not f["is_active"] and f["superseded_by"]
            if f["updated_at"] and f["created_at"] and (retired or f["updated_at"] > f["created_at"]):
                kind = "replaced" if retired else "updated"
                events.append({"at": f["updated_at"], "kind": kind, "fact_id": f["id"], "text": short(f["content"]),
                               "other_id": f["superseded_by"], "earlier": True})
        merged = {l["fact_id_a"] for l in links if l["relationship"] == "confirms"}
        for e in events:
            if e["kind"] == "replaced" and e["fact_id"] in merged:
                e["kind"] = "merged"
        events.sort(key=lambda e: e["at"], reverse=True)
        return events[:60]

    @staticmethod
    def _diff(old: dict[int, dict], new: dict[int, dict], old_links: list[dict], new_links: list[dict]) -> list[dict]:
        at = now_iso()
        out: list[dict] = []
        link_ids = {link["id"] for link in old_links}
        fresh_links = {(l["fact_id_a"], l["fact_id_b"]): l for l in new_links if l["id"] not in link_ids}

        def add(kind, fact, text, **extra):
            out.append({"at": at, "kind": kind, "fact_id": fact["id"], "text": text, **extra})

        for fid, f in new.items():
            before = old.get(fid)
            if before is None:
                add("learned", f, short(f["content"]))
                continue
            count = len(out)
            if before["is_active"] and not f["is_active"]:
                link = fresh_links.get((fid, f["superseded_by"])) if f["superseded_by"] else None
                if f["superseded_by"] and link and link["relationship"] == "confirms":
                    add("merged", f, short(f["content"]), other_id=f["superseded_by"], note=link.get("note"))
                elif f["superseded_by"]:
                    contra = fresh_links.get((f["superseded_by"], fid))
                    add("replaced", f, short(f["content"]), other_id=f["superseded_by"],
                        note=(contra or {}).get("note"))
                elif f["expires_at"] and f["expires_at"] <= at:
                    add("expired", f, short(f["content"]))
                else:
                    add("forgotten", f, short(f["content"]))
            elif not before["is_active"] and f["is_active"]:
                add("restored", f, short(f["content"]))
            if before["content"] != f["content"]:
                add("refined", f, short(f["content"]), before=short(before["content"]))
            if (f["confidence"] or 0) > (before["confidence"] or 0) + 1e-9:
                add("reinforced", f, short(f["content"]),
                    detail=f"confidence {before['confidence'] or 0:.2f} → {f['confidence']:.2f}")
            elif (f["confidence"] or 0) < (before["confidence"] or 0) - 1e-9:
                add("weakened", f, short(f["content"]),
                    detail=f"confidence {before['confidence'] or 0:.2f} → {f['confidence']:.2f}")
            if abs((f["importance"] or 0) - (before["importance"] or 0)) > 1e-9:
                add("importance", f, short(f["content"]),
                    detail=f"importance {before['importance'] or 0:.2f} → {f['importance'] or 0:.2f}")
            if before["category"] != f["category"]:
                add("recategorised", f, short(f["content"]), detail=f"{before['category']} → {f['category']}")
            if before["is_private"] != f["is_private"]:
                add("private" if f["is_private"] else "unprivate", f, short(f["content"]))
            if before["memory_type"] != f["memory_type"]:
                add("kept", f, short(f["content"]), detail=f"{before['memory_type']} → {f['memory_type']}")
            if len(out) == count and f["is_active"] and (f["updated_at"] or "") > (before["updated_at"] or ""):
                add("confirmed", f, short(f["content"]))      # said again; already fully trusted
        for fid, f in old.items():
            if fid not in new:
                add("deleted", f, short(f["content"]))
        return out

    # ── Similarity (own embeddings; Luna's vector store is never opened) ────
    def _embed_worker(self) -> None:
        loop = asyncio.new_event_loop()
        try:
            from server.services.llm import ollama
        except Exception as e:                       # noqa: BLE001 - shown on the page
            self.embed_status = f"off: {e}"
            self._publish()
            return
        while True:
            self._embed_wake.wait()
            self._embed_wake.clear()
            with self.lock:
                texts = {f["content"] for f in self.facts.values() if f["content"]}
            missing = [t for t in texts if t not in self._embeddings]
            if missing:
                self.embed_status = f"embedding {len(missing)}…"
                self._publish()
            failed = None
            for text in missing:
                try:
                    vector = loop.run_until_complete(ollama.embed(text))
                except Exception as e:               # noqa: BLE001 - shown on the page
                    failed = str(e) or e.__class__.__name__
                    break
                if vector:
                    self._embeddings[text] = vector
                else:
                    failed = "the embedding model returned nothing"
                    break
            self._compute_similar()
            self.embed_status = f"off: {short(failed, 80)}" if failed else "on"
            self._publish()
            if failed:
                time.sleep(15)
                self._embed_wake.set()               # try again later

    def _compute_similar(self) -> None:
        import numpy as np
        with self.lock:
            items = [(fid, f["content"]) for fid, f in self.facts.items() if f["content"] in self._embeddings]
        if len(items) < 2:
            self.similar = []
            return
        matrix = np.array([self._embeddings[t] for _, t in items], dtype=float)
        matrix /= np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-12
        distance = 1.0 - matrix @ matrix.T
        np.fill_diagonal(distance, 9.0)
        pairs: dict[tuple[int, int], float] = {}
        for i in range(len(items)):
            for j in np.argsort(distance[i])[:SIMILAR_PER_FACT]:
                d = float(distance[i, j])
                if d <= SIMILAR_DISTANCE:
                    a, b = sorted((items[i][0], items[int(j)][0]))
                    pairs[(a, b)] = round(d, 3)
        self.similar = [[a, b, d] for (a, b), d in pairs.items()]

    # ── Publishing ───────────────────────────────────────────────────────────
    def snapshot(self) -> str:
        with self.lock:
            return json.dumps({
                "version": self.version,
                "db": str(self.db_path),
                "status": self.status,
                "similarity": self.embed_status,
                "server_time": now_iso(),
                "facts": list(self.facts.values()),
                "links": self.links,
                "similar": self.similar,
                "conversations": {str(k): v for k, v in self.conversations.items()},
                "changes": list(self.changes),
            })

    def _publish(self) -> None:
        with self.lock:
            self.version += 1
        payload = self.snapshot()
        for q in list(self.listeners):
            try:
                q.put_nowait(payload)
            except queue.Full:
                pass


def make_handler(state: MemoryState):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args) -> None:        # quiet
            pass

        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:                    # noqa: N802
            path = self.path.split("?", 1)[0]
            if path in ("/", "/index.html"):
                self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
            elif path == "/api/state":
                self._send(200, state.snapshot().encode(), "application/json")
            elif path == "/events":
                self._events()
            else:
                self._send(404, b"not found", "text/plain")

        def _events(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            q: queue.Queue = queue.Queue(maxsize=4)
            state.listeners.add(q)
            try:
                payload = state.snapshot()
                while True:
                    self.wfile.write(f"data: {payload}\n\n".encode())
                    self.wfile.flush()
                    while True:
                        try:
                            payload = q.get(timeout=15)
                            while not q.empty():         # only the latest state matters
                                payload = q.get_nowait()
                            break
                        except queue.Empty:
                            self.wfile.write(b": ping\n\n")
                            self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
                pass
            finally:
                state.listeners.discard(q)

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description="Live, read-only view of Luna's memory.")
    parser.add_argument("--port", type=int, default=8798)
    parser.add_argument("--db", help="SQLite file (default: Luna's configured database)")
    parser.add_argument("--no-open", action="store_true", help="don't open a browser")
    parser.add_argument("--no-similarity", action="store_true", help="skip embeddings and similarity links")
    args = parser.parse_args()

    state = MemoryState(database_path(args.db), similarity=not args.no_similarity)
    threading.Thread(target=state.watch, daemon=True).start()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(state))
    server.daemon_threads = True
    url = f"http://127.0.0.1:{args.port}"
    print(f"Luna memory viewer: {url}  (read-only: {state.db_path})  Ctrl+C to stop")
    if not args.no_open:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
