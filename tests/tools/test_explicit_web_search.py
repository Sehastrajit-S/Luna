import unittest


class ExplicitWebSearchTests(unittest.TestCase):
    def test_explicit_requests_extract_query(self) -> None:
        from server.services.command_parser.research import extract_explicit_web_search_query

        cases = {
            "can you web search and find me what is the newest model for actions with LLM":
                "what is the newest model for actions with LLM",
            "web search newest open source TTS models": "newest open source TTS models",
            "search the web for pool pump efficiency standards": "pool pump efficiency standards",
            "Could you search online for the EU AI Act timeline please": "the EU AI Act timeline",
            "google it: best rust web framework": "best rust web framework",
            "do a web search on NAIP imagery resolution": "NAIP imagery resolution",
            "look up the Artemis III launch date online": None,
            "tell me about quantum dots, look it up online": "quantum dots",
        }
        for prompt, expected in cases.items():
            with self.subTest(prompt=prompt):
                self.assertEqual(extract_explicit_web_search_query(prompt), expected)

    def test_non_requests_do_not_trigger(self) -> None:
        from server.services.command_parser.research import extract_explicit_web_search_query

        for prompt in (
            "what is the newest model for actions with LLM",
            "search my inbox for invoices",
            "open google calendar",
            "/research web search engines",
            "web search",
            "hey",
        ):
            with self.subTest(prompt=prompt):
                self.assertIsNone(extract_explicit_web_search_query(prompt))

    def test_fabricated_search_widget_becomes_real_search(self) -> None:
        from server.services.chat_pipeline.stage_tools import _try_bracket_formats

        tc = _try_bracket_formats(
            "Sure, let's check that out.\n[WIDGET:web_search|Newest Model for Actions with LLM|Model Name: Qwen-Audio; Release Date: 2024]"
        )
        self.assertEqual(tc, {"tool": "web_search", "args": {"query": "Newest Model for Actions with LLM"}, "speak": ""})
        self.assertIsNone(_try_bracket_formats("[WIDGET:summary|EU AI Act|Key facts]"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
