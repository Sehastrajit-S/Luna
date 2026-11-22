"""Memory quality: duplicate merging, importance, and recall ranking."""
from __future__ import annotations

import asyncio
import json
import math
import unittest
from datetime import datetime, timedelta
from unittest import mock

from tests.tools import _bootstrap  # noqa: F401

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from server.models.database import Base, Fact, FactRelationship


class FakeCollection:
    """Just enough of a Chroma collection: upsert/delete/count/query with cosine distance."""

    def __init__(self) -> None:
        self.rows: dict[str, tuple[list[float], str, dict]] = {}

    def count(self) -> int:
        return len(self.rows)

    def upsert(self, ids, embeddings, documents, metadatas) -> None:
        for i, e, d, m in zip(ids, embeddings, documents, metadatas):
            self.rows[i] = (e, d, m)

    add = upsert

    def delete(self, ids) -> None:
        for i in ids:
            self.rows.pop(i, None)

    @staticmethod
    def _matches(meta: dict, where: dict | None) -> bool:
        if not where:
            return True
        clauses = where.get("$and", [where])
        return all(meta.get(k) == v for c in clauses for k, v in c.items())

    def query(self, query_embeddings, n_results, where=None, include=None):
        q = query_embeddings[0]

        def dist(e):
            dot = sum(a * b for a, b in zip(q, e))
            return 1 - dot / (math.hypot(*q) * math.hypot(*e))

        hits = sorted(((dist(e), i, d, m) for i, (e, d, m) in self.rows.items() if self._matches(m, where)))[:n_results]
        return {"ids": [[h[1] for h in hits]], "documents": [[h[2] for h in hits]],
                "metadatas": [[h[3] for h in hits]], "distances": [[h[0] for h in hits]]}


class MemoryTestBase(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine)
        self.db = self.Session()
        self.addCleanup(self.db.close)
        self.col = FakeCollection()
        # Every fact embeds to the same point, so every fact in the category is a
        # "close neighbour" and only the word rule decides what merges.
        self.vector = [1.0, 0.0]

    def memory(self):
        from server.services.memory_manager import MemoryManager
        memory = MemoryManager(self.db)
        memory._get_collection = mock.MagicMock(return_value=self.col)
        memory._embed = mock.AsyncMock(side_effect=lambda text: self.vector)
        return memory

    def store(self, content, category="personal", **kw):
        from server.services.memory_manager import MemoryManager
        with mock.patch.object(MemoryManager, "_bg_llm_contradiction_check", new=mock.AsyncMock()) as check:
            fact_id = asyncio.run(self.memory().store_fact(content, category, **kw))
        self.last_check = check
        return fact_id

    def active(self):
        self.db.expire_all()
        return [f.content for f in self.db.query(Fact).filter_by(is_active=True).order_by(Fact.id)]


class FactRelationTests(unittest.TestCase):
    def test_safe_merges_only(self) -> None:
        from server.services.memory_manager.manager import fact_relation
        cases = [
            ("User likes coffee", "User likes coffee.", "same"),
            ("user  LIKES coffee", "User likes coffee", "same"),
            ("User has a sister", "User has a sister named Priya", None),          # one-word stem: too thin
            ("User plays guitar", "User plays the guitar on weekends", "same"),    # old already says more
            ("User plays the guitar on weekends", "User plays guitar", "refines"),
            ("User's dog Quillon is a 3-year-old border collie", "User's dog Quillon", "refines"),
            # Changes of fact must never merge:
            ("User lives in Lisbon", "User lives in Porto", None),
            ("User no longer likes coffee", "User likes coffee", None),
            ("User likes coffee", "User doesn't like coffee", None),
            ("User likes coffee", "User likes coffee but not anymore", None),
            ("User lives in Porto", "User's sister lives in Porto", None),
            ("User's name is Sam", "User's name is Alex", None),
        ]
        for new, old, want in cases:
            self.assertEqual(fact_relation(new, old), want, (new, old))


class StoreFactTests(MemoryTestBase):
    def test_repeat_reinforces_instead_of_duplicating(self) -> None:
        first = self.store("User works as a nurse", confidence=0.7)
        again = self.store("user works as a nurse.")
        self.assertEqual(first, again)
        self.assertEqual(self.active(), ["User works as a nurse"])
        self.assertAlmostEqual(self.db.get(Fact, first).confidence, 0.8)
        self.last_check.assert_not_called()

    def test_more_detail_refines_the_existing_fact(self) -> None:
        first = self.store("User's dog Quillon", category="relationship")
        again = self.store("User's dog Quillon is a 3-year-old border collie", category="relationship")
        self.assertEqual(first, again)
        self.assertEqual(self.active(), ["User's dog Quillon is a 3-year-old border collie"])
        self.assertEqual(self.col.rows[f"fact_{first}"][1], "User's dog Quillon is a 3-year-old border collie",
                         "the vector is re-indexed with the fuller wording")

    def test_a_change_of_fact_is_kept_for_the_contradiction_check(self) -> None:
        self.store("User lives in Porto")
        new = self.store("User lives in Lisbon")
        self.assertEqual(self.active(), ["User lives in Porto", "User lives in Lisbon"])
        self.last_check.assert_called_once()
        self.assertEqual(self.last_check.call_args.args[0], new)

    def test_other_categories_and_far_neighbours_are_not_merged(self) -> None:
        self.store("User plays the guitar on weekends", category="preference")
        self.store("User plays the guitar", category="goal")
        self.assertEqual(len(self.active()), 2, "a goal is not a duplicate of a preference")
        self.store("User drinks green tea daily", category="preference")
        self.vector = [0.0, 1.0]                                     # far from everything
        self.store("User drinks green tea daily with honey", category="preference")
        self.assertEqual(len(self.active()), 4)

    def test_exact_repeat_merges_even_without_embeddings(self) -> None:
        self.vector = []
        first = self.store("User is allergic to cashews", category="health")
        self.assertEqual(self.store("User is allergic to cashews", category="health"), first)
        self.assertEqual(self.col.count(), 0)

    def test_importance_defaults_by_category(self) -> None:
        name = self.store("User's name is Alex")
        show = self.store("User is watching Severance", category="preference")
        told = self.store("User is training for a marathon", category="goal", importance=0.9)
        self.assertEqual(self.db.get(Fact, name).importance, 0.8)
        self.assertEqual(self.db.get(Fact, show).importance, 0.5)
        self.assertEqual(self.db.get(Fact, told).importance, 0.9)


class BackgroundCheckTests(MemoryTestBase):
    def run_check(self, reply: str, new_id: int):
        memory = self.memory()
        with mock.patch("server.models.database.SessionLocal", self.Session), \
                mock.patch("server.services.memory_manager.manager.ollama.complete",
                           new=mock.AsyncMock(return_value=reply)):
            new = self.db.get(Fact, new_id)
            asyncio.run(memory._bg_llm_contradiction_check(new_id, new.content, new.category, None, self.vector))
        self.db.expire_all()

    def two_facts(self, old, new):
        a = self.store(old)
        b = self.store(new)
        self.assertNotEqual(a, b)
        return a, b

    def test_paraphrase_is_folded_into_the_existing_fact(self) -> None:
        old, new = self.two_facts("User is a nurse", "User works in nursing at a hospital")
        self.run_check(json.dumps({"id": old, "relation": "same", "note": "same job"}), new)
        self.assertEqual(self.active(), ["User is a nurse"])
        self.assertEqual(self.db.get(Fact, new).superseded_by, old)
        self.assertNotIn(f"fact_{new}", self.col.rows)
        self.assertEqual(self.db.query(FactRelationship).one().relationship, "confirms")

    def test_same_never_merges_across_categories(self) -> None:
        job = self.store("User works as a nurse")
        colour = self.store("User's favourite colour is green", category="preference")
        self.run_check(json.dumps({"id": job, "relation": "same"}), colour)
        self.assertEqual(len(self.active()), 2)

    def test_prompt_lists_ids_without_positions(self) -> None:
        old, new = self.two_facts("User is a nurse", "User works in nursing")
        complete = mock.AsyncMock(return_value="{}")
        with mock.patch("server.models.database.SessionLocal", self.Session), \
                mock.patch("server.services.memory_manager.manager.ollama.complete", new=complete):
            asyncio.run(self.memory()._bg_llm_contradiction_check(new, "User works in nursing", "personal", None, self.vector))
        prompt = complete.call_args.args[0]
        self.assertIn(f"- ID {old}: User is a nurse", prompt)
        self.assertNotIn("1. ", prompt)

    def test_contradiction_retires_the_old_fact(self) -> None:
        old, new = self.two_facts("User lives in Porto", "User lives in Lisbon")
        with mock.patch("server.services.contradiction_store.add") as note:
            self.run_check(json.dumps({"id": old, "relation": "contradicts", "note": "moved"}), new)
        self.assertEqual(self.active(), ["User lives in Lisbon"])
        self.assertIn("Porto", note.call_args.args[0])

    def test_older_reply_shape_still_works(self) -> None:
        old, new = self.two_facts("User lives in Porto", "User lives in Lisbon")
        with mock.patch("server.services.contradiction_store.add"):
            self.run_check(json.dumps({"contradicts_id": old, "note": ""}), new)
        self.assertEqual(self.active(), ["User lives in Lisbon"])

    def test_unknown_id_or_no_relation_changes_nothing(self) -> None:
        old, new = self.two_facts("User lives in Porto", "User lives in Lisbon")
        self.run_check(json.dumps({"id": 999, "relation": "contradicts"}), new)
        self.run_check(json.dumps({"id": old, "relation": None}), new)
        self.run_check("not json at all", new)
        self.assertEqual(self.active(), ["User lives in Porto", "User lives in Lisbon"])


class RankingTests(MemoryTestBase):
    def test_who_you_are_does_not_fade(self) -> None:
        from server.services.memory_manager.manager import recency_score
        self.assertEqual(recency_score("personal", 365), 1.0)
        self.assertEqual(recency_score("relationship", 900), 1.0)
        self.assertGreater(recency_score("preference", 365), 0.2)
        self.assertLess(recency_score("event", 30), 0.2)
        self.assertLess(recency_score("conversation", 30), 0.2)

    def test_old_core_fact_outranks_a_recent_passing_detail(self) -> None:
        year_ago = datetime.utcnow() - timedelta(days=365)
        partner = Fact(category="relationship", content="User's partner is Sam", importance=0.5,
                       created_at=year_ago, updated_at=year_ago)
        concert = Fact(category="event", content="User went to a concert with Sam", importance=0.3)
        self.db.add_all([partner, concert])
        self.db.commit()
        self.col.query = mock.MagicMock(return_value={
            "documents": [[concert.content, partner.content]], "distances": [[0.30, 0.32]],
            "metadatas": [[{"type": "fact", "fact_id": concert.id, "importance": 0.3},
                           {"type": "fact", "fact_id": partner.id, "importance": 0.5}]]})
        self.col.upsert(["x"], [[1.0, 0.0]], ["x"], [{}])            # non-empty collection
        found = asyncio.run(self.memory().retrieve_relevant("who is Sam", n=4))
        self.assertEqual(found["long_term"][0], "User's partner is Sam")

    def test_core_facts_rank_by_importance_not_insertion(self) -> None:
        from server.services.memory_manager import MemoryManager
        for i in range(12):
            self.db.add(Fact(category="preference", content=f"User likes snack {i}", importance=0.5, confidence=1.0))
        self.db.add(Fact(category="relationship", content="User's daughter is Mia", importance=0.5, confidence=0.6))
        self.db.add(Fact(category="personal", content="User is allergic to peanuts", importance=0.95, confidence=0.9))
        self.db.commit()
        core = MemoryManager(self.db).get_core_facts()
        self.assertEqual(core[:2], ["User is allergic to peanuts", "User's daughter is Mia"])
        self.assertEqual(len(core), 10)


class ExtractionImportanceTests(MemoryTestBase):
    def test_extractor_passes_importance_through(self) -> None:
        from server.services.fact_extractor import extract_facts_from_conversation
        reply = json.dumps([
            {"category": "personal", "content": "User is allergic to peanuts", "quote": "allergic to peanuts",
             "confidence": 0.95, "importance": 0.97, "memory_type": "long"},
            {"category": "preference", "content": "User is watching Severance", "quote": "watching Severance",
             "confidence": 0.9, "importance": "high", "memory_type": "short", "expires_in_days": 30},
        ])
        memory = self.memory()
        with mock.patch("server.services.fact_extractor.ollama.complete", new=mock.AsyncMock(return_value=reply)), \
                mock.patch.object(type(memory), "_bg_llm_contradiction_check", new=mock.AsyncMock()):
            asyncio.run(extract_facts_from_conversation(
                "User: I'm allergic to peanuts and watching Severance\nLuna: Noted!", self.db, 1, memory))
        got = {f.content: f.importance for f in self.db.query(Fact)}
        self.assertEqual(got, {"User is allergic to peanuts": 0.97, "User is watching Severance": 0.5})


if __name__ == "__main__":
    unittest.main()
