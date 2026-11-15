import unittest
from types import SimpleNamespace


LONG_REVIEW = "\n\n".join([
    "Here's my review of your resume:",
    "**Technical skills** - comprehensive and well organized.",
    "**Experience** - clear, but add metrics to show impact.",
    "**Projects** - strong; lead with the outcome.",
    "**Formatting** - ATS friendly, dates are consistent.",
    "**Top fixes** - quantify results, trim the summary, tailor keywords.",
    "Overall: 7.5/10.",
])


class ResponseLengthTests(unittest.TestCase):
    def test_formatter_never_drops_paragraphs(self) -> None:
        from backend.services.response_formatter import format_luna_response

        out = format_luna_response(LONG_REVIEW)
        for paragraph in LONG_REVIEW.split("\n\n"):
            self.assertIn(paragraph, out)

    def test_long_unbroken_reply_keeps_every_sentence(self) -> None:
        from backend.services.response_formatter import format_luna_response

        text = " ".join(f"Sentence number {i} has a few words in it." for i in range(12))
        out = format_luna_response(text)
        self.assertIn("Sentence number 0", out)
        self.assertIn("Sentence number 11", out)

    def test_text_chat_streams_the_whole_answer(self) -> None:
        from backend.services.chat_pipeline.stages import _build_visible_response_events

        ctx = SimpleNamespace(full_response=LONG_REVIEW, cli=False, had_tool_call=False, voice=False)
        rendered = "".join(_build_visible_response_events(ctx))
        self.assertIn("Overall: 7.5/10.", rendered)
        self.assertIn("Top fixes", rendered)

    def test_voice_replies_stay_short(self) -> None:
        from backend.services.chat_pipeline.stages import _build_visible_response_events

        ctx = SimpleNamespace(full_response=LONG_REVIEW, cli=False, had_tool_call=False, voice=True)
        rendered = "".join(_build_visible_response_events(ctx))
        self.assertNotIn("Overall: 7.5/10.", rendered)


if __name__ == "__main__":
    unittest.main(verbosity=2)
