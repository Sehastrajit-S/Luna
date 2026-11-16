import unittest
from datetime import datetime


class ClockQuestionTests(unittest.TestCase):
    def test_date_questions_match(self) -> None:
        from server.services.command_parser.clock import parse_clock_question

        for prompt in (
            "Whats the day today",
            "what's the date",
            "What is the date today?",
            "what day is it",
            "what day is it today?",
            "today's date",
            "what's today's date?",
            "what's the day of the week",
            "hey what is the day today",
        ):
            with self.subTest(prompt=prompt):
                self.assertEqual(parse_clock_question(prompt), "date")

    def test_time_questions_match(self) -> None:
        from server.services.command_parser.clock import parse_clock_question

        for prompt in ("what time is it", "What's the time?", "whats the current time right now", "tell me the time"):
            with self.subTest(prompt=prompt):
                self.assertEqual(parse_clock_question(prompt), "time")

    def test_other_questions_do_not_match(self) -> None:
        from server.services.command_parser.clock import parse_clock_question

        for prompt in (
            "what time is my meeting",
            "what time is it in Tokyo",
            "what day is the election",
            "what's the date of the next SpaceX launch",
            "what day should I schedule the review",
            "the day today was rough",
            "hey",
            "",
        ):
            with self.subTest(prompt=prompt):
                self.assertIsNone(parse_clock_question(prompt))

    def test_answers_use_the_given_clock(self) -> None:
        from server.services.command_parser.clock import answer_clock_question

        now = datetime(2026, 9, 23, 10, 26)
        self.assertEqual(answer_clock_question("date", now), "Today is Wednesday, September 23, 2026.")
        self.assertEqual(answer_clock_question("time", now), "It's 10:26 AM.")
        self.assertEqual(answer_clock_question("datetime", now), "It's 10:26 AM on Wednesday, September 23, 2026.")


if __name__ == "__main__":
    unittest.main(verbosity=2)
