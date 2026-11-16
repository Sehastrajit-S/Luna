import unittest

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker


class ConversationDeleteTests(unittest.TestCase):
    def test_delete_unlinks_references_instead_of_failing(self) -> None:
        from server.models.database import (
            Base, Conversation, Episode, Fact, FeedbackLog, Message,
        )
        from server.routers.chat import delete_conversation

        engine = create_engine("sqlite://")
        event.listen(engine, "connect", lambda conn, _r: conn.execute("PRAGMA foreign_keys=ON"))
        Base.metadata.create_all(engine)
        db = sessionmaker(bind=engine)()

        conv = Conversation(message_count=2)
        db.add(conv); db.commit()
        db.add_all([
            Message(conversation_id=conv.id, role="user", content="thanks"),
            Fact(category="personal", content="Likes tea", source_conversation_id=conv.id),
            FeedbackLog(conversation_id=conv.id, reward_signal=0.8),
            Episode(conversation_id=conv.id, summary="short chat"),
        ])
        db.commit()

        delete_conversation(conv.id, db=db)

        self.assertIsNone(db.query(Conversation).filter_by(id=conv.id).first())
        self.assertEqual(db.query(Message).count(), 0)
        self.assertEqual(db.query(Episode).count(), 0)
        fact = db.query(Fact).one()
        self.assertIsNone(fact.source_conversation_id)
        self.assertIsNone(db.query(FeedbackLog).one().conversation_id)


if __name__ == "__main__":
    unittest.main(verbosity=2)
