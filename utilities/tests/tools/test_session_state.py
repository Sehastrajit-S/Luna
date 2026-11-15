import asyncio
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ENCODER_REPLY = """Here's the encoder:

```python
ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

def encode_base62(n: int, length: int = 7) -> str:
    out = []
    while n:
        n, r = divmod(n, 62)
        out.append(ALPHABET[r])
    return "".join(reversed(out)).rjust(length, "0")

def decode_base62(code: str) -> int:
    return sum(ALPHABET.index(c) * 62 ** i for i, c in enumerate(reversed(code)))
```
"""


def _db():
    from backend.models.database import Base
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _conversation(db, turns):
    """turns: list of (user, luna). Records artifacts the way finalize does."""
    from backend.models.database import Conversation, Message
    from backend.services.session_state import record_artifacts

    conv = Conversation()
    db.add(conv)
    db.commit()
    for user, luna in turns:
        db.add(Message(conversation_id=conv.id, role="user", content=user))
        reply = Message(conversation_id=conv.id, role="assistant", content=luna)
        db.add(reply)
        db.commit()
        record_artifacts(db, conv.id, reply.id, user, luna)
    return conv


class SessionStateTests(unittest.TestCase):
    def test_code_blocks_are_recorded_with_their_names_and_turn(self) -> None:
        from backend.models.database import ConversationArtifact

        db = _db()
        conv = _conversation(db, [("We're building Snip.", "Got it."),
                                  ("Write the base62 encoder", ENCODER_REPLY),
                                  ("thanks", "Anytime.")])
        rows = db.query(ConversationArtifact).filter_by(conversation_id=conv.id).all()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].names, "encode_base62, decode_base62")
        self.assertEqual((rows[0].language, rows[0].turn), ("python", 2))

    def test_one_line_snippets_are_not_artifacts(self) -> None:
        from backend.models.database import ConversationArtifact

        db = _db()
        _conversation(db, [("reverse a string?", "Use:\n```python\ns[::-1]\n```")])
        self.assertEqual(db.query(ConversationArtifact).count(), 0)

    def test_pinned_block_indexes_code_and_includes_what_the_user_refers_to(self) -> None:
        from backend.services.session_state import session_state_block

        db = _db()
        conv = _conversation(db, [("Write the base62 encoder", ENCODER_REPLY)] +
                             [(f"filler question {i}", f"filler answer {i}") for i in range(20)])
        plain = session_state_block(db, conv.id, "what's a good name for a cat?")
        self.assertIn("[turn 1] python: encode_base62, decode_base62", plain)
        self.assertNotIn("def encode_base62", plain)                      # index only
        by_name = session_state_block(db, conv.id, "make encode_base62 handle negative numbers")
        self.assertIn("def encode_base62", by_name)
        by_reference = session_state_block(db, conv.id, "refactor the encoder you wrote earlier to use a class")
        self.assertIn("def encode_base62", by_reference)
        self.assertEqual(session_state_block(db, _conversation(db, [("hi", "Hey.")]).id, "hi"), "")

    def test_search_finds_turns_that_left_the_window(self) -> None:
        from backend.services.session_state import search_conversation

        db = _db()
        conv = _conversation(db, [("Our cache TTL is 24 hours and codes are 7 characters.", "Noted.")] +
                             [(f"explain topic {i}", f"topic {i} explained") for i in range(40)])
        found = search_conversation(db, conv.id, "cache TTL")
        self.assertTrue(found.startswith("[turn 1, User]"))
        self.assertIn("24 hours", found)
        self.assertIn("Nothing in this conversation matches", search_conversation(db, conv.id, "kubernetes"))

    def test_search_tool_runs_through_the_executor(self) -> None:
        from backend.services.tool_runner import execute_tool_call

        db = _db()
        conv = _conversation(db, [("Write the base62 encoder", ENCODER_REPLY)])
        result = asyncio.run(execute_tool_call({"tool": "search_conversation", "args": {"query": "base62 alphabet"}},
                                               db, conv.id))
        self.assertIn("ALPHABET", result)

    def test_facts_are_append_only_deduplicated_and_pinned_first(self) -> None:
        from backend.services.session_state import add_session_facts, session_state_block

        db = _db()
        conv = _conversation(db, [("We're building Snip on FastAPI.", "Got it.")])
        self.assertEqual(add_session_facts(db, conv.id, ["Project name: Snip", "Cache: Redis, 24-hour TTL"]), 2)
        self.assertEqual(add_session_facts(db, conv.id, ["project name - Snip", "Codes: 7-character base62"]), 1)
        block = session_state_block(db, conv.id, "what's next?")
        facts_at = block.index("Facts and decisions so far")
        self.assertLess(facts_at, block.index("- Cache: Redis, 24-hour TTL"))
        self.assertIn("- Codes: 7-character base62", block)
        self.assertEqual(block.count("Snip"), 1)

    def test_turns_out_of_the_window_are_listed_in_order(self) -> None:
        from backend.services.session_state import session_state_block

        db = _db()
        topics = ["TCP congestion control", "B-tree indexes"] + [f"topic number {i}" for i in range(28)]
        conv = _conversation(db, [(f"Explain {t} in about 300 words.", "…") for t in topics])
        block = session_state_block(db, conv.id, "what was the second topic I asked about?")
        self.assertIn("- [turn 1] Explain TCP congestion control", block)
        self.assertIn("- [turn 2] Explain B-tree indexes", block)
        self.assertNotIn("topic number 27", block)                # still in the visible window

    def test_search_is_a_core_read_only_tool(self) -> None:
        from backend.services.agent_loop.tool_selection import select_tools
        from backend.services.tool_registry import get_tool

        self.assertIn("search_conversation", select_tools("hello"))
        self.assertTrue(get_tool("search_conversation").read_only)


if __name__ == "__main__":
    unittest.main(verbosity=2)
