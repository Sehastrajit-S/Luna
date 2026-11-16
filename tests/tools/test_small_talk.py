import unittest
from datetime import datetime


class SmallTalkClassifierTests(unittest.TestCase):
    def test_pure_small_talk_is_detected(self) -> None:
        from server.services.command_parser.small_talk import classify_small_talk

        cases = {
            "Hi": "greeting",
            "hiii": "greeting",
            "Heyyy Luna!": "greeting",
            "hello there": "greeting",
            "yo": "greeting",
            "what's up": "greeting",
            "Good morning": "morning",
            "hi good morning luna 👋": "morning",
            "gm": "morning",
            "good afternoon": "afternoon",
            "Good evening!": "evening",
            "good night": "night",
            "gn": "night",
            "thanks!": "thanks",
            "Thank you so much": "thanks",
            "ty": "thanks",
            "bye": "farewell",
            "see ya": "farewell",
            "cool": "ack",
            "sounds good": "ack",
            "hey Sehas": "greeting",
        }
        for message, expected in cases.items():
            with self.subTest(message=message):
                self.assertEqual(classify_small_talk(message, user_name="Sehas"), expected)

    def test_real_requests_still_go_to_the_model(self) -> None:
        from server.services.command_parser.small_talk import classify_small_talk

        for message in (
            "hi, can you check my email",
            "good morning, what's on my calendar today",
            "how are you",
            "hey what's the weather",
            "thanks, now open spotify",
            "ok",
            "yes",
            "sure",
            "okay do it",
            "hi " * 30,
            "",
        ):
            with self.subTest(message=message):
                self.assertIsNone(classify_small_talk(message))

    def test_ack_after_a_question_is_an_answer_not_small_talk(self) -> None:
        from server.services.command_parser.small_talk import classify_small_talk

        self.assertIsNone(classify_small_talk("cool", prev_assistant="Want me to open it in your browser?"))
        self.assertEqual(classify_small_talk("cool", prev_assistant="Opened it in your browser."), "ack")
        # Greetings and thanks are unambiguous even after a question.
        self.assertEqual(classify_small_talk("thanks", prev_assistant="Anything else?"), "thanks")

    def test_replies_are_time_aware_and_personal(self) -> None:
        from server.services.command_parser.small_talk import small_talk_reply

        morning = small_talk_reply("greeting", "Sehas", now=datetime(2026, 9, 23, 8, 0))
        late = small_talk_reply("greeting", "Sehas", now=datetime(2026, 9, 23, 1, 30))
        self.assertTrue("morning" in morning.lower() or "what's" in morning.lower())
        self.assertIn("Sehas", morning)
        self.assertTrue("late" in late.lower() or "sleep" in late.lower())
        self.assertNotIn("friend", small_talk_reply("thanks", "friend").lower())
        for kind in ("morning", "afternoon", "evening", "night", "thanks", "ack", "farewell"):
            self.assertTrue(small_talk_reply(kind, "Sehas"))


class SmallTalkPipelineTests(unittest.TestCase):
    def test_fast_path_sets_response_without_llm(self) -> None:
        from types import SimpleNamespace
        from unittest import mock
        from server.services.chat_pipeline import stage_small_talk

        ctx = SimpleNamespace(user_message="good morning", conv=SimpleNamespace(id=1), db=None,
                              small_talk=False, dispatched=False, direct_command_type=None,
                              prev_luna=None, full_response="", full_response_parts=[], attachment_ids=[])
        with mock.patch.object(stage_small_talk, "_previous_assistant_message", return_value="Hi!"), \
             mock.patch("server.services.llm.ollama.stream_chat") as stream, \
             mock.patch("server.services.llm.ollama.complete") as complete:
            handled = stage_small_talk.answer_small_talk(ctx)
        self.assertTrue(handled)
        self.assertTrue(ctx.small_talk and ctx.dispatched)
        self.assertEqual(ctx.direct_command_type, "small_talk:morning")
        self.assertTrue(ctx.full_response)
        stream.assert_not_called()
        complete.assert_not_called()

    def test_small_talk_with_a_file_goes_to_the_model(self) -> None:
        from types import SimpleNamespace
        from unittest import mock
        from server.services.chat_pipeline import stage_small_talk

        ctx = SimpleNamespace(user_message="thanks", conv=SimpleNamespace(id=1), db=None,
                              small_talk=False, dispatched=False, attachment_ids=["a" * 32])
        with mock.patch.object(stage_small_talk, "_previous_assistant_message", return_value=""):
            self.assertFalse(stage_small_talk.answer_small_talk(ctx))
        self.assertFalse(ctx.dispatched)


if __name__ == "__main__":
    unittest.main(verbosity=2)
