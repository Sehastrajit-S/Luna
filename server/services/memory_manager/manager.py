"""MemoryManager: SQLite facts, ChromaDB vector search, conversation context."""
import asyncio
import json as _json
import logging
import re as _re
from datetime import datetime, timedelta, timezone
from typing import Optional

import chromadb
from chromadb.config import Settings as ChromaSettings
from sqlalchemy.orm import Session

from server.config import settings
from server.models.database import Conversation, Fact, Message
from server.services.llm import ollama

logger = logging.getLogger(__name__)

_FORGET_STOPWORDS = frozenset({
    "the", "and", "you", "your", "know", "about", "everything", "anything", "all", "that", "this", "what",
    "forget", "remember", "memory", "memories", "please", "user", "user's", "luna", "my", "mine", "stuff",
    "things", "info", "information", "details", "delete", "erase", "remove", "wipe", "from",
    # Never expand a forget to every fact sharing a day or month name.
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "january", "february",
    "march", "april", "may", "june", "july", "august", "september", "october", "november", "december",
})


# ── Memory quality rules ──────────────────────────────────────────────────────

# Default importance by category, used when nothing better is known. Facts saved
# before importance was extracted all carry the old flat default (0.5).
_CATEGORY_IMPORTANCE = {"personal": 0.8, "relationship": 0.8, "health": 0.75, "goal": 0.6}
_LEGACY_IMPORTANCE = 0.5

# How fast a memory's recency score fades, per day. Who you are and who is in
# your life don't go stale; what happened last week does.
_RECENCY_DECAY = {"personal": 0.0, "relationship": 0.0, "health": 0.005,
                  "preference": 0.01, "behavior": 0.01, "goal": 0.05}
_DEFAULT_DECAY = 0.15

# Near neighbours worth comparing for duplicates. Embedding distance alone can't
# tell a duplicate from a change ("lives in Porto" vs "lives in Lisbon" sit as close
# as two paraphrases), so a close neighbour is only merged by the word rule below;
# paraphrases are left to the background LLM check.
DUPLICATE_DISTANCE = 0.2

_FILLER = frozenset({
    "user", "a", "an", "the", "is", "are", "was", "were", "be", "been", "has", "have", "had", "of", "to",
    "in", "on", "at", "and", "for", "with", "named", "called", "their", "they", "them", "who", "which",
    "that", "as", "by", "s",
})
_NEGATION = frozenset({
    "not", "no", "never", "dont", "doesnt", "didnt", "isnt", "wasnt", "arent", "cant", "cannot", "wont",
    "longer", "anymore", "stopped", "quit", "former", "formerly", "ex", "used", "without", "but", "hate",
    "hates", "dislike", "dislikes",
})


def effective_importance(category: str | None, importance: float | None) -> float:
    """A fact's importance, with untouched legacy defaults raised for core categories."""
    if importance is None or importance == _LEGACY_IMPORTANCE:
        return max(_LEGACY_IMPORTANCE, _CATEGORY_IMPORTANCE.get(category or "", _LEGACY_IMPORTANCE))
    return float(importance)


def recency_score(category: str | None, age_days: float) -> float:
    rate = _RECENCY_DECAY.get(category or "", _DEFAULT_DECAY)
    return 1.0 / (1.0 + max(0.0, age_days) * rate)


def _fact_words(text: str) -> list[str]:
    """The words that carry a fact's meaning, in order, lightly normalised."""
    text = (text or "").lower().replace("’", "'").replace("'s ", " ").replace("'", "")
    words = []
    for w in _re.findall(r"[a-z0-9]+", text):
        if w in _FILLER:
            continue
        if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        words.append(w)
    return words


def fact_relation(new: str, old: str) -> str | None:
    """How a new fact relates to an existing one, judged only on safe cases:

    "same"    — the new fact says nothing the old one doesn't (equal, or the old is
                the new one with more detail added at the end)
    "refines" — the new fact is the old one with more detail added at the end
    None      — anything else, including any added negation ("no longer", "not"),
                which may be a change of fact and needs the contradiction check.
    """
    a, b = _fact_words(new), _fact_words(old)
    if not a or not b:
        return None
    if a == b or (set(a) == set(b) and len(a) == len(b)):
        return "same"
    shorter, longer = (a, b) if len(a) < len(b) else (b, a)
    # A one-word stem ("dog") is too thin to tell "has a dog" from "dog walker is Sam".
    if len(shorter) < 2 or longer[:len(shorter)] != shorter or set(longer[len(shorter):]) & _NEGATION:
        return None
    return "same" if shorter is a else "refines"


def _as_timestamp(value: datetime | None) -> float | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.timestamp()


class MemoryManager:
    def __init__(self, db: Session):
        self.db = db
        self._client: Optional[chromadb.PersistentClient] = None
        self._collection = None

    def _get_collection(self):
        if self._collection is None:
            self._client = chromadb.PersistentClient(
                path=settings.chroma_path,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            # Scope the collection name by embedding provider so switching
            # providers (different embedding dimensions) can never collide
            # with an existing collection again — "luna_memories" stays the
            # default/Ollama collection so existing history is untouched.
            provider = settings.embedding_provider.strip().lower()
            name = "luna_memories" if provider != "openai-compatible" else "luna_memories_openai"
            self._collection = self._client.get_or_create_collection(
                name=name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    async def _embed(self, text: str) -> list[float]:
        return await ollama.embed(text)

    async def store_fact(
        self,
        content: str,
        category: str,
        conversation_id: Optional[int] = None,
        confidence: float = 1.0,
        importance: Optional[float] = None,
        source: str = "inferred",
        expires_at=None,
        is_private: bool = False,
        memory_type: str = "long",
        expires_in_days: Optional[float] = None,
    ) -> int:
        content = " ".join((content or "").split())
        if importance is None:
            importance = _CATEGORY_IMPORTANCE.get(category, _LEGACY_IMPORTANCE)
        importance = min(1.0, max(0.0, float(importance)))
        if expires_at is None:
            if expires_in_days is not None:
                expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
            elif memory_type == "persistent":
                expires_at = datetime.utcnow() + timedelta(days=3)
            elif memory_type == "short":
                expires_at = datetime.utcnow() + timedelta(days=30)

        self._expire_stale_facts()

        embedding: list[float] = []
        try:
            embedding = await self._embed(content) or []
        except Exception as e:                      # still save the fact; recall falls back to SQL
            logger.warning("Could not embed new fact: %s", e)

        match, relation = self._find_duplicate(content, category, embedding)
        if match is not None:
            self._reinforce(match, importance)
            if relation == "refines":
                # Same fact with more detail: keep one row, holding the fuller wording.
                match.content = content
                self.db.commit()
                self._index_fact(match, embedding)
            else:
                self.db.commit()
            return match.id

        fact = Fact(
            category=category,
            content=content,
            confidence=confidence,
            importance=importance,
            source=source,
            expires_at=expires_at,
            is_private=is_private,
            source_conversation_id=conversation_id,
            memory_type=memory_type,
        )
        self.db.add(fact)
        self.db.commit()
        self.db.refresh(fact)
        self._index_fact(fact, embedding)

        if embedding:
            try:
                asyncio.create_task(
                    self._bg_llm_contradiction_check(fact.id, content, category, conversation_id, embedding)
                )
            except RuntimeError as e:
                logger.debug("Could not schedule contradiction check: %s", e)

        return fact.id

    def _reinforce(self, fact: Fact, importance: float) -> None:
        """The user said it again: trust it more, and keep it fresh."""
        fact.confidence = min(1.0, (fact.confidence or 0.0) + 0.1)
        fact.importance = max(effective_importance(fact.category, fact.importance), importance)
        fact.updated_at = datetime.utcnow()
        if (fact.memory_type == "persistent" and fact.confidence >= 0.9
                and fact.created_at
                and (datetime.utcnow() - fact.created_at).days >= 2):
            fact.memory_type = "long"
            fact.expires_at  = None

    def _find_duplicate(self, content: str, category: str, embedding: list[float]) -> tuple[Optional[Fact], Optional[str]]:
        """An active fact in the same category that this one repeats or refines."""
        # A word-for-word repeat, even of a fact whose embedding never got saved.
        words = _fact_words(content)
        for fact in self.db.query(Fact).filter(Fact.is_active == True, Fact.category == category):
            if _fact_words(fact.content) == words:
                return fact, "same"
        candidates: list[Fact] = []
        if embedding:
            try:
                col = self._get_collection()
                count = col.count()
                if count:
                    res = col.query(
                        query_embeddings=[embedding],
                        n_results=min(5, count),
                        where={"$and": [{"type": "fact"}, {"category": category}]},
                        include=["metadatas", "distances"],
                    )
                    ids = [int(m["fact_id"]) for m, d in zip(res.get("metadatas", [[]])[0], res.get("distances", [[]])[0])
                           if m and m.get("fact_id") and d <= DUPLICATE_DISTANCE]
                    if ids:
                        by_id = {f.id: f for f in self.db.query(Fact).filter(
                            Fact.id.in_(ids), Fact.is_active == True, Fact.category == category)}
                        candidates = [by_id[i] for i in ids if i in by_id]
            except Exception as e:
                logger.warning("Duplicate check against the vector store failed: %s", e)
        for fact in candidates:
            relation = fact_relation(content, fact.content)
            if relation:
                return fact, relation
        return None, None

    def _index_fact(self, fact: Fact, embedding: list[float]) -> None:
        if not embedding:
            return
        try:
            self._get_collection().upsert(
                ids=[f"fact_{fact.id}"],
                embeddings=[embedding],
                documents=[fact.content],
                metadatas=[{
                    "type": "fact",
                    "category": fact.category,
                    "fact_id": fact.id,
                    "importance": effective_importance(fact.category, fact.importance),
                    "created_at": datetime.utcnow().timestamp(),
                }],
            )
        except (chromadb.errors.ChromaError, OSError, ValueError) as e:
            logger.warning("Failed to store fact embedding (fact_id=%d): %s", fact.id, e)
        except Exception as e:
            logger.error("Unexpected error storing fact embedding: %s", e, exc_info=True)

    def _expire_stale_facts(self):
        now     = datetime.utcnow()
        expired = (
            self.db.query(Fact)
            .filter(Fact.is_active == True, Fact.expires_at != None, Fact.expires_at <= now)
            .all()
        )
        for f in expired:
            f.is_active = False
        if expired:
            self.db.commit()

    async def _bg_llm_contradiction_check(
        self,
        new_fact_id: int,
        content: str,
        category: str,
        conversation_id,
        embedding: Optional[list[float]] = None,
    ):
        """Compare a new fact with its closest neighbours. If it says the same thing
        in other words, fold it into the existing fact; if it replaces one, retire
        the old one and leave a note so Luna can mention the change."""
        from server.models.database import FactRelationship, SessionLocal
        from server.services.contradiction_store import add as _store_note

        db = SessionLocal()
        try:
            embedding = embedding or await self._embed(content)
            if not embedding:
                return
            col = self._get_collection()
            if col.count() < 2:
                return

            n = min(8, col.count())
            results = col.query(
                query_embeddings=[embedding],
                n_results=n,
                include=["documents", "metadatas", "distances"],
            )
            docs      = results["documents"][0]
            metas     = results["metadatas"][0]
            distances = results["distances"][0]

            candidates = []
            for doc, meta, dist in zip(docs, metas, distances):
                fid = meta.get("fact_id")
                if not fid or int(fid) == new_fact_id or dist > 0.65:
                    continue
                fact_obj = db.query(Fact).filter_by(id=int(fid), is_active=True).first()
                if fact_obj:
                    candidates.append((int(fid), doc, fact_obj))

            if not candidates:
                return

            # No list numbering: models answer with the position instead of the ID.
            pairs  = "\n".join(f"- ID {fid}: {doc}" for fid, doc, _ in candidates)
            prompt = (
                f'New fact: "{content}"\n\n'
                f"Existing facts:\n{pairs}\n\n"
                "Compare the new fact with the existing facts and pick at most one:\n"
                '- "same": an existing fact already says this, maybe in other words, and the new fact '
                "adds no new information.\n"
                '- "contradicts": the new fact replaces an existing one — they cannot both be true now '
                "(moved city, changed job, stopped liking something).\n"
                "Otherwise relation is null. Facts that merely add something new are null.\n\n"
                'Reply ONLY with JSON: {"id": <existing ID or null>, "relation": "same" | "contradicts" | null, '
                '"note": "<one sentence reason or empty>"}'
            )
            raw = await ollama.complete(
                prompt,
                system="You compare memories about a user. Output only valid JSON. No commentary.",
                temperature=0.05,
            )

            m = _re.search(r'\{[^{}]*\}', raw, _re.DOTALL)
            if not m:
                logger.info("Memory check for fact %d gave no JSON; keeping both facts.", new_fact_id)
                return
            result   = _json.loads(m.group())
            relation = result.get("relation")
            other_id = result.get("id")
            if other_id is None and result.get("contradicts_id"):          # older reply shape
                other_id, relation = result.get("contradicts_id"), "contradicts"
            note     = str(result.get("note", "") or "").strip()

            if not other_id or relation not in ("same", "contradicts"):
                return
            other_id = int(other_id)
            if other_id not in {fid for fid, _, _ in candidates}:
                logger.info("Memory check named fact %d, which wasn't offered; ignoring.", other_id)
                return
            old_fact = db.query(Fact).filter_by(id=other_id, is_active=True).first()
            new_fact = db.query(Fact).filter_by(id=new_fact_id, is_active=True).first()
            if not old_fact or not new_fact:
                return

            if relation == "same":
                if old_fact.category != new_fact.category:
                    logger.info("Memory check called facts %d and %d the same across categories; keeping both.",
                                new_fact_id, other_id)
                    return
                # Fold the repeat into the fact Luna already had.
                self._reinforce(old_fact, effective_importance(new_fact.category, new_fact.importance))
                new_fact.is_active = False
                new_fact.superseded_by = other_id
                db.add(FactRelationship(fact_id_a=new_fact_id, fact_id_b=other_id,
                                        relationship="confirms", confidence=0.8, note=note))
                db.commit()
                try:
                    col.delete(ids=[f"fact_{new_fact_id}"])
                except (chromadb.errors.ChromaError, OSError) as e:
                    logger.warning("Failed to delete merged fact from ChromaDB: %s", e)
                return

            contradicts_id     = other_id
            old_content        = old_fact.content
            old_fact.is_active = False
            old_fact.superseded_by = new_fact_id
            db.add(FactRelationship(
                fact_id_a=new_fact_id,
                fact_id_b=contradicts_id,
                relationship="contradicts",
                confidence=0.9,
                note=note,
            ))
            db.commit()

            try:
                col.delete(ids=[f"fact_{contradicts_id}"])
            except (chromadb.errors.ChromaError, OSError) as e:
                logger.warning("Failed to delete superseded fact from ChromaDB: %s", e)

            _store_note(
                f'Memory just updated: you previously knew "{old_content}" '
                f'but that has been superseded by "{content}". '
                "If it comes up naturally, acknowledge the change briefly — don't force it.",
                conversation_id=conversation_id,
            )

        except (_json.JSONDecodeError, ValueError, TypeError) as e:
            logger.debug("Contradiction check parse error: %s", e)
        except Exception as e:
            logger.error("Contradiction check failed for fact %d: %s", new_fact_id, e, exc_info=True)
            try:
                db.rollback()
            except Exception:
                pass
        finally:
            db.close()

    async def store_conversation_summary(self, summary: str, conversation_id: int):
        try:
            embedding = await self._embed(summary)
            if embedding:
                col = self._get_collection()
                col.upsert(
                    ids=[f"conv_{conversation_id}"],
                    embeddings=[embedding],
                    documents=[summary],
                    metadatas=[{
                        "type": "conversation",
                        "conversation_id": conversation_id,
                        "created_at": datetime.utcnow().timestamp(),
                    }],
                )
        except (chromadb.errors.ChromaError, OSError, ValueError) as e:
            logger.warning("Failed to store conversation summary embedding (conv %d): %s", conversation_id, e)

    async def retrieve_relevant(self, query: str, n: int = None) -> dict[str, list[str]]:
        n    = n or settings.memory_retrieval_count
        half = max(n // 2, 2)

        try:
            embedding = await self._embed(query)
            if not embedding:
                return {"short_term": [], "long_term": self._fallback_facts()}

            col   = self._get_collection()
            count = col.count()
            if count == 0:
                return {"short_term": [], "long_term": self._fallback_facts()}

            candidates = min(n * 4, count, 24)
            results    = col.query(
                query_embeddings=[embedding],
                n_results=candidates,
                include=["documents", "metadatas", "distances"],
            )
            docs      = results.get("documents", [[]])[0]
            distances = results.get("distances",  [[]])[0]
            metas     = results.get("metadatas",  [[]])[0]

            # A deleted or forgotten fact keeps its vector until cleaned up;
            # only facts still active in the database may be recalled.
            # The database, not the vector metadata, has the current importance and
            # when the fact was last confirmed.
            fact_ids = [m.get("fact_id") for m in metas if m and m.get("type") == "fact" and m.get("fact_id")]
            active = {f.id: f for f in self.db.query(Fact).filter(
                Fact.id.in_(fact_ids), Fact.is_active == True)} if fact_ids else {}

            now         = datetime.now(timezone.utc).timestamp()
            THIRTY_DAYS = 30 * 86_400

            scored: list[tuple[str, float, float]] = []
            for doc, dist, meta in zip(docs, distances, metas):
                meta = meta or {}
                if dist >= 0.8:
                    continue
                if meta.get("type") == "fact":
                    fact = active.get(meta.get("fact_id"))
                    if fact is None:
                        continue
                    category   = fact.category
                    importance = effective_importance(category, fact.importance)
                    seen       = _as_timestamp(fact.updated_at or fact.created_at)
                else:
                    category   = meta.get("type")
                    importance = meta.get("importance", _LEGACY_IMPORTANCE)
                    seen       = None
                created    = seen or meta.get("created_at", now - THIRTY_DAYS)
                semantic   = 1.0 - dist
                age_days   = max(0.0, (now - created) / 86_400)
                recency    = recency_score(category, age_days)
                score      = semantic * 0.55 + recency * 0.25 + importance * 0.20
                scored.append((doc, score, age_days))

            scored.sort(key=lambda x: x[1], reverse=True)

            short_term = [d for d, _, age in scored if age <  2][:half]
            long_term  = [d for d, _, age in scored if age >= 2][:half]
            return {"short_term": short_term, "long_term": long_term}

        except (chromadb.errors.ChromaError, OSError, ValueError) as e:
            logger.warning("Memory retrieval failed, using fallback facts: %s", e)
            return {"short_term": [], "long_term": self._fallback_facts()}
        except Exception as e:
            # Embedding providers can fail independently of chat (for example
            # a hosted provider rate limit). Never block the conversation on
            # optional semantic memory.
            logger.warning("Memory provider failed, using fallback facts: %s", e)
            return {"short_term": [], "long_term": self._fallback_facts()}

    def forget(self, about: str) -> list[str]:
        """Deactivate every memory about a subject and drop its vectors.

        Matches facts by the subject's words, then by the names those facts
        mention ("my dog" finds "User has a dog named Quillon", and "Quillon"
        then finds "Quillon is 4 years old"). Episode summaries that mention
        them are removed from semantic memory too. Returns what was forgotten.
        """
        words = [w for w in _re.findall(r"[a-z0-9']+", (about or "").lower())
                 if len(w) > 2 and w not in _FORGET_STOPWORDS]
        if not words:
            return []
        active = self.db.query(Fact).filter(Fact.is_active == True).all()

        def mentions(text: str, terms: set[str]) -> bool:
            low = text.lower()
            return any(_re.search(rf"\b{_re.escape(t)}\w*\b", low) for t in terms)

        terms = set(words)
        matched = [f for f in active if mentions(f.content, terms)]
        # Names inside the matched facts (not their first word, which is capitalised anyway).
        names = {n.lower() for f in matched for n in _re.findall(r"\b[A-Z][a-z]{2,}\b", f.content.split(" ", 1)[-1])
                 if n.lower() not in _FORGET_STOPWORDS}
        if names:
            terms |= names
            matched = [f for f in active if mentions(f.content, terms)]
        for fact in matched:
            fact.is_active = False
        self.db.commit()

        try:
            col = self._get_collection()
            ids = [f"fact_{f.id}" for f in matched]
            got = col.get(include=["documents", "metadatas"])
            for doc_id, doc, meta in zip(got.get("ids", []), got.get("documents", []), got.get("metadatas", [])):
                if doc_id not in ids and (meta or {}).get("type") != "fact" and mentions(doc or "", terms):
                    ids.append(doc_id)
            if ids:
                col.delete(ids=ids)
        except Exception as e:                   # SQL already forgot; vectors are filtered by is_active
            logger.warning("Could not remove forgotten memories from the vector store: %s", e)
        return [f.content for f in matched]

    def _fallback_facts(self) -> list[str]:
        now   = datetime.utcnow()
        facts = (
            self.db.query(Fact)
            .filter(
                Fact.is_active  == True,
                Fact.is_private == False,
                (Fact.expires_at == None) | (Fact.expires_at > now),
            )
            .order_by(Fact.importance.desc(), Fact.updated_at.desc())
            .limit(settings.memory_retrieval_count)
            .all()
        )
        return [f.content for f in facts]

    def get_core_facts(self) -> list[str]:
        now     = datetime.utcnow()
        personal = (
            self.db.query(Fact)
            .filter(
                Fact.category.in_(['personal', 'preference', 'relationship']),
                Fact.is_active  == True,
                Fact.is_private == False,
                (Fact.expires_at == None) | (Fact.expires_at > now),
            )
            .all()
        )
        # Most important first; among equals, the ones confirmed most often.
        personal.sort(key=lambda f: (effective_importance(f.category, f.importance), f.confidence or 0.0),
                      reverse=True)
        return [f.content for f in personal[:10]]

    def _promote_routines(self) -> int:
        cutoff     = datetime.utcnow() - timedelta(days=2)
        candidates = (
            self.db.query(Fact)
            .filter(
                Fact.is_active    == True,
                Fact.memory_type  == "persistent",
                Fact.confidence   >= 0.85,
                Fact.created_at   <= cutoff,
            )
            .all()
        )
        promoted = 0
        for f in candidates:
            f.memory_type = "long"
            f.expires_at  = None
            promoted      += 1
        if promoted:
            self.db.commit()
        return promoted

    async def compact_facts(self) -> int:
        self._promote_routines()

        categories = ['personal', 'preference', 'relationship', 'context', 'behavior']
        removed    = 0

        for cat in categories:
            facts = (
                self.db.query(Fact)
                .filter(
                    Fact.category    == cat,
                    Fact.is_active   == True,
                    Fact.memory_type == "long",
                )
                .order_by(Fact.importance.desc(), Fact.updated_at.desc())
                .all()
            )
            if len(facts) < 2:
                continue

            numbered = "\n".join(f"{i+1}. {f.content}" for i, f in enumerate(facts))
            prompt   = (
                f"These are long-term memory facts about a user in category '{cat}'.\n\n"
                f"{numbered}\n\n"
                "Task: merge any duplicates or near-duplicates into a single clean statement. "
                "Keep facts that are genuinely distinct. "
                "Reply ONLY with a JSON array of merged fact strings. "
                'Example: ["User prefers dark mode", "User is a software engineer"]'
            )

            try:
                raw = await ollama.complete(
                    prompt,
                    system="You are a precise memory curator. Output only valid JSON arrays. No commentary.",
                    temperature=0.1,
                )
                m = _re.search(r'\[.*?\]|\[.*\]', raw, _re.DOTALL)
                if not m:
                    continue
                merged: list[str] = _json.loads(m.group())
                if not isinstance(merged, list) or len(merged) >= len(facts):
                    continue

                best_importance = max(f.importance for f in facts)
                best_confidence = max(f.confidence for f in facts)
                col = self._get_collection()
                for f in facts:
                    f.is_active = False
                    try:
                        eid      = f"fact_{f.id}"
                        existing = col.get(ids=[eid])
                        if existing and existing.get("ids"):
                            col.delete(ids=[eid])
                    except Exception:
                        pass
                removed += len(facts) - len(merged)

                for content in merged:
                    content = content.strip()
                    if not content:
                        continue
                    new_fact = Fact(
                        category=cat, content=content,
                        confidence=best_confidence, importance=best_importance,
                        source="compaction", memory_type="long",
                    )
                    self.db.add(new_fact)
                    self.db.flush()
                    try:
                        embedding = await self._embed(content)
                        if embedding:
                            col = self._get_collection()
                            col.add(
                                ids=[f"fact_{new_fact.id}"],
                                embeddings=[embedding],
                                documents=[content],
                                metadatas=[{"type": "fact", "category": cat,
                                            "fact_id": new_fact.id,
                                            "importance": best_importance,
                                            "created_at": datetime.utcnow().timestamp()}],
                            )
                    except Exception:
                        pass

                self.db.commit()
            except Exception:
                self.db.rollback()
                continue

        return removed

    def get_all_facts(self, category: Optional[str] = None) -> list[Fact]:
        q = self.db.query(Fact).filter(Fact.is_active == True)
        if category:
            q = q.filter(Fact.category == category)
        return q.order_by(Fact.updated_at.desc()).all()

    def get_upcoming_agenda(self) -> str:
        from server.models.database import CalendarEvent, Task
        now      = datetime.utcnow()
        tomorrow = now + timedelta(days=1)

        tasks = (
            self.db.query(Task)
            .filter(Task.completed == False, Task.due_date <= tomorrow)
            .order_by(Task.due_date)
            .limit(5)
            .all()
        )
        events = (
            self.db.query(CalendarEvent)
            .filter(CalendarEvent.start_datetime >= now, CalendarEvent.start_datetime <= tomorrow)
            .order_by(CalendarEvent.start_datetime)
            .limit(5)
            .all()
        )

        lines = []
        for e in events:
            lines.append(f"- Event: {e.title} at {e.start_datetime.strftime('%H:%M')}")
        for t in tasks:
            due = t.due_date.strftime("%b %d") if t.due_date else "no date"
            lines.append(f"- Task [{t.priority}]: {t.title} (due {due})")
        return "\n".join(lines) if lines else "Nothing scheduled in the next 24 hours."

    def get_recent_conversation(self, conversation_id: int, limit: int = None) -> list[dict]:
        limit = limit or settings.max_conversation_history
        msgs  = (
            self.db.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
            .all()
        )
        return [{"role": m.role, "content": m.content} for m in reversed(msgs)]

    def get_conversation_context(self, conversation_id: int, limit: int = None) -> str:
        conversation = self.db.query(Conversation).filter(Conversation.id == conversation_id).first()
        messages     = self.get_recent_conversation(conversation_id, limit or settings.max_conversation_history)
        if not messages:
            if conversation and conversation.summary:
                return f"- Earlier summary: {conversation.summary}"
            return "- No recent messages yet."

        lines = []
        if conversation and conversation.summary:
            lines.append(f"- Earlier summary: {conversation.summary}")
        for msg in messages:
            role    = "User" if msg["role"] == "user" else "Luna"
            content = " ".join(msg["content"].split())
            if len(content) > 300:
                content = content[:297].rstrip() + "..."
            lines.append(f"- {role}: {content}")
        return "\n".join(lines)
