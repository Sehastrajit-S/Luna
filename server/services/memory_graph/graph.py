"""MemoryGraph: fact graph traversal and episodic memory."""
from __future__ import annotations

import json
from collections import deque
from datetime import datetime, timezone
from typing import Any, Callable, Optional

import chromadb
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.config import DATA_DIR
from backend.services.memory_graph.models import FactNode, GraphEdge


class MemoryGraph:
    """
    Wraps the SQLAlchemy session for graph operations over facts +
    ChromaDB for episodic semantic retrieval.

    One instance per request (same lifecycle as MemoryManager).
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self._chroma: Optional[chromadb.Collection] = None

    def _episodes_col(self) -> chromadb.Collection:
        if self._chroma is None:
            client = chromadb.PersistentClient(path=str(DATA_DIR / "chroma"))
            self._chroma = client.get_or_create_collection(
                "luna_episodes",
                metadata={"hnsw:space": "cosine"},
            )
        return self._chroma

    # ── Graph traversal ───────────────────────────────────────────────────────

    def get_related_facts(
        self,
        fact_id: int,
        max_depth: int = 2,
        rel_types: Optional[list[str]] = None,
    ) -> list[FactNode]:
        """BFS from fact_id through FactRelationship edges. Returns reachable active facts."""
        visited: set[int] = {fact_id}
        queue: deque[tuple[int, int]] = deque([(fact_id, 0)])
        result: list[FactNode] = []

        rel_clause = ""
        base_params: dict[str, Any] = {}
        if rel_types:
            placeholders = ", ".join(f":rt{i}" for i in range(len(rel_types)))
            rel_clause = f"AND fr.relationship IN ({placeholders})"
            base_params = {f"rt{i}": r for i, r in enumerate(rel_types)}

        while queue:
            current_id, depth = queue.popleft()
            if depth >= max_depth:
                continue

            params = {**base_params, "cid": current_id}
            rows = self.db.execute(
                text(f"""
                    SELECT f.id, f.content, f.category, f.confidence, f.importance
                    FROM fact_relationships fr
                    JOIN facts f ON f.id = CASE
                        WHEN fr.fact_id_a = :cid THEN fr.fact_id_b
                        ELSE fr.fact_id_a
                    END
                    WHERE (fr.fact_id_a = :cid OR fr.fact_id_b = :cid)
                      AND f.is_active = 1
                      {rel_clause}
                """),
                params,
            ).fetchall()

            for row in rows:
                nid = row[0]
                if nid not in visited:
                    visited.add(nid)
                    result.append(
                        FactNode(
                            id=nid,
                            content=row[1],
                            category=row[2],
                            confidence=float(row[3] or 0.8),
                            importance=float(row[4] or 0.5),
                        )
                    )
                    queue.append((nid, depth + 1))

        return result

    def link_facts(
        self,
        fact_a: int,
        fact_b: int,
        relation: str,
        confidence: float = 0.8,
        note: str = "",
    ) -> None:
        """Upsert a typed edge between two facts."""
        existing = self.db.execute(
            text(
                "SELECT id FROM fact_relationships "
                "WHERE (fact_id_a = :a AND fact_id_b = :b) "
                "   OR (fact_id_a = :b AND fact_id_b = :a)"
            ),
            {"a": fact_a, "b": fact_b},
        ).fetchone()

        if existing:
            self.db.execute(
                text(
                    "UPDATE fact_relationships "
                    "SET relationship = :r, confidence = :c "
                    "WHERE id = :id"
                ),
                {"r": relation, "c": confidence, "id": existing[0]},
            )
        else:
            self.db.execute(
                text(
                    "INSERT INTO fact_relationships "
                    "(fact_id_a, fact_id_b, relationship, confidence, note, created_at) "
                    "VALUES (:a, :b, :r, :c, :n, :ts)"
                ),
                {
                    "a": fact_a, "b": fact_b, "r": relation,
                    "c": confidence, "n": note,
                    "ts": datetime.now(timezone.utc),
                },
            )
        self.db.commit()

    def get_subgraph(
        self,
        seed_fact_ids: list[int],
        max_depth: int = 2,
    ) -> dict:
        """Return a JSON-serialisable subgraph dict (nodes + edges)."""
        all_nodes: dict[int, FactNode] = {}

        for seed in seed_fact_ids:
            for node in self.get_related_facts(seed, max_depth=max_depth):
                all_nodes[node.id] = node

        all_ids = list(all_nodes.keys()) + seed_fact_ids
        edges: list[dict] = []
        if all_ids:
            placeholders = ", ".join(str(i) for i in set(all_ids))
            rows = self.db.execute(
                text(
                    f"SELECT fact_id_a, fact_id_b, relationship, confidence "
                    f"FROM fact_relationships "
                    f"WHERE fact_id_a IN ({placeholders}) AND fact_id_b IN ({placeholders})"
                )
            ).fetchall()
            edges = [{"a": r[0], "b": r[1], "rel": r[2], "conf": round(float(r[3] or 0.8), 2)} for r in rows]

        return {
            "nodes": [
                {"id": n.id, "content": n.content, "category": n.category,
                 "confidence": n.confidence, "importance": n.importance}
                for n in all_nodes.values()
            ],
            "edges": edges,
        }

    def find_clusters(self) -> list[list[int]]:
        """Return connected components of the active fact graph via Union-Find."""
        rows = self.db.execute(
            text(
                "SELECT fr.fact_id_a, fr.fact_id_b "
                "FROM fact_relationships fr "
                "JOIN facts a ON a.id = fr.fact_id_a "
                "JOIN facts b ON b.id = fr.fact_id_b "
                "WHERE a.is_active = 1 AND b.is_active = 1"
            )
        ).fetchall()

        parent: dict[int, int] = {}

        def find(x: int) -> int:
            parent.setdefault(x, x)
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]

        def union(x: int, y: int) -> None:
            parent[find(x)] = find(y)

        for a, b in rows:
            union(a, b)

        clusters: dict[int, list[int]] = {}
        for node in list(parent):
            root = find(node)
            clusters.setdefault(root, []).append(node)

        return [c for c in clusters.values() if len(c) > 1]

    # ── Episodic memory ───────────────────────────────────────────────────────

    def store_episode(
        self,
        conversation_id: int,
        summary: str,
        key_fact_ids: list[int],
        key_entities: list[str],
        embed_fn: Optional[Callable[[str], list[float]]] = None,
    ) -> None:
        """Persist a conversation episode and embed its summary for later retrieval."""
        importance = min(1.0, 0.3 + len(key_fact_ids) * 0.07)
        ts = datetime.now(timezone.utc).isoformat()

        self.db.execute(
            text(
                "INSERT OR REPLACE INTO episodes "
                "(conversation_id, summary, key_fact_ids, key_entities, importance, created_at) "
                "VALUES (:cid, :s, :f, :e, :i, :ts)"
            ),
            {
                "cid": conversation_id,
                "s":   summary,
                "f":   json.dumps(key_fact_ids),
                "e":   json.dumps(key_entities),
                "i":   importance,
                "ts":  ts,
            },
        )
        self.db.commit()

        if embed_fn is None:
            return
        try:
            embedding = embed_fn(summary)
            col = self._episodes_col()
            col.upsert(
                ids=[f"ep_{conversation_id}"],
                embeddings=[embedding],
                documents=[summary],
                metadatas=[{
                    "conversation_id": conversation_id,
                    "importance":      importance,
                    "entities":        json.dumps(key_entities[:20]),
                }],
            )
        except Exception:
            pass

    def retrieve_episodes(
        self,
        query: str,
        limit: int = 5,
        embed_fn: Optional[Callable[[str], list[float]]] = None,
    ) -> list[dict]:
        """Return relevant past episodes ordered by semantic similarity to query."""
        if embed_fn is not None:
            try:
                col = self._episodes_col()
                if col.count() == 0:
                    return self._fallback_episodes(limit)
                embedding = embed_fn(query)
                results = col.query(
                    query_embeddings=[embedding],
                    n_results=min(limit, col.count()),
                )
                docs  = results.get("documents", [[]])[0]
                metas = results.get("metadatas", [[]])[0]
                return [
                    {
                        "summary":         d,
                        "conversation_id": m.get("conversation_id"),
                        "importance":      m.get("importance", 0.5),
                        "entities":        json.loads(m.get("entities", "[]")),
                    }
                    for d, m in zip(docs, metas)
                ]
            except Exception:
                pass

        return self._fallback_episodes(limit)

    def _fallback_episodes(self, limit: int) -> list[dict]:
        rows = self.db.execute(
            text(
                "SELECT conversation_id, summary, key_entities, importance "
                "FROM episodes ORDER BY importance DESC, created_at DESC LIMIT :l"
            ),
            {"l": limit},
        ).fetchall()
        return [
            {
                "summary":         r[1],
                "conversation_id": r[0],
                "importance":      r[3],
                "entities":        json.loads(r[2] or "[]"),
            }
            for r in rows
        ]

    def get_episode_facts(self, conversation_id: int) -> list[int]:
        """Return the fact IDs linked to a stored episode."""
        row = self.db.execute(
            text("SELECT key_fact_ids FROM episodes WHERE conversation_id = :cid"),
            {"cid": conversation_id},
        ).fetchone()
        if not row:
            return []
        try:
            return json.loads(row[0] or "[]")
        except Exception:
            return []
