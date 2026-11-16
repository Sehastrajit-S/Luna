import asyncio
import unittest
from unittest import mock


def _conversation(turns: int, reply_chars: int = 2500) -> list[dict]:
    messages = []
    for i in range(turns):
        messages.append({"role": "user", "content": f"question {i} about topic {i}"})
        messages.append({"role": "assistant", "content": f"answer {i} " + ("x" * reply_chars) +
                         "\n\nReferences:\n[1] Src - https://example.com/" + str(i)})
    return messages


class ContextWindowTests(unittest.TestCase):
    def test_long_conversation_fits_and_keeps_pinned_content(self) -> None:
        from server.services.llm.context_window import estimate_tokens, fit_context

        system = "SYSTEM RULES " + ("r" * 30000)
        messages = _conversation(100) + [{"role": "user", "content": "I mean one that is new for actions"}]
        fitted = fit_context(system, messages, context_window=16384, max_output_tokens=1024, summary="They discussed LLM tools.")

        self.assertLessEqual(fitted.prompt_tokens, fitted.budget_tokens)
        self.assertTrue(fitted.system_prompt.startswith(system))
        self.assertIn("They discussed LLM tools.", fitted.system_prompt)
        self.assertEqual(fitted.messages[-1]["content"], "I mean one that is new for actions")
        self.assertGreater(fitted.dropped_messages, 0)
        self.assertEqual(fitted.messages[0]["role"], "user")
        total = estimate_tokens(fitted.system_prompt) + sum(estimate_tokens(m["content"]) + 6 for m in fitted.messages)
        self.assertLessEqual(total, 16384 - 1024)

    def test_old_replies_are_clipped_but_latest_reply_is_intact(self) -> None:
        from server.services.llm.context_window import fit_context

        messages = _conversation(3, reply_chars=3000) + [{"role": "user", "content": "follow up"}]
        fitted = fit_context("sys", messages, context_window=32768, max_output_tokens=1024)
        assistant = [m["content"] for m in fitted.messages if m["role"] == "assistant"]
        self.assertTrue(all("earlier reply shortened" in a and "References" not in a for a in assistant[:-1]))
        self.assertEqual(assistant[-1], messages[-2]["content"])
        self.assertEqual(fitted.shortened_messages, 2)
        self.assertEqual(fitted.dropped_messages, 0)

    def test_short_conversation_is_untouched(self) -> None:
        from server.services.llm.context_window import fit_context

        messages = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hey"}, {"role": "user", "content": "how are you"}]
        fitted = fit_context("sys", messages, context_window=16384, max_output_tokens=1024)
        self.assertEqual(fitted.messages, messages)
        self.assertEqual(fitted.system_prompt, "sys")

    def test_huge_user_message_is_clipped_not_the_system_prompt(self) -> None:
        from server.services.llm.context_window import fit_context

        system = "SYSTEM " + "s" * 8000
        fitted = fit_context(system, [{"role": "user", "content": "start " + "y" * 200000 + " end"}],
                             context_window=8192, max_output_tokens=1024)
        self.assertEqual(fitted.system_prompt, system)
        self.assertTrue(fitted.clipped_user_message)
        self.assertIn("characters omitted", fitted.messages[-1]["content"])
        self.assertTrue(fitted.messages[-1]["content"].startswith("start "))
        self.assertTrue(fitted.messages[-1]["content"].endswith(" end"))
        self.assertLessEqual(fitted.prompt_tokens, fitted.budget_tokens)


class SkillDisclosureTests(unittest.TestCase):
    def test_only_relevant_skill_instructions_are_included(self) -> None:
        from server.services.skill_manager import get_skills_prompt

        everything = get_skills_prompt(message=None)
        casual = get_skills_prompt(message="hey how was your day")
        email = get_skills_prompt(message="check my email for the invoice")

        self.assertIn("workspace-suite", casual)
        self.assertNotIn("Instructions:", casual)
        self.assertIn("Instructions:", email)
        self.assertLess(len(casual), len(everything) // 2)
        workspace_block = email.split("- workspace-suite:")[1].split("\n- ")[0]
        self.assertIn("Instructions:", workspace_block)


class SearchQueryTests(unittest.TestCase):
    HISTORY = [
        {"role": "user", "content": "can you web search and find me what is the newest model for actions with LLM"},
        {"role": "assistant", "content": "The newest models include Ollama and GPT-5.\n\nReferences:\n[1] X - https://x.com"},
    ]

    def test_self_contained_message_skips_rewrite(self) -> None:
        from server.services import search_query

        with mock.patch("server.services.llm.ollama.complete") as complete:
            q = asyncio.run(search_query.resolve_search_query("latest qwen3 release notes for tool calling", self.HISTORY))
        self.assertEqual(q, "latest qwen3 release notes for tool calling")
        complete.assert_not_called()

    def test_follow_up_is_rewritten_with_context(self) -> None:
        from server.services import search_query

        async def fake_complete(prompt, system="", temperature=0.3):
            self.assertIn("newest model for actions", prompt)
            return 'Query: "newest large action models for agents 2026"\n'

        with mock.patch("server.services.llm.ollama.complete", side_effect=fake_complete):
            q = asyncio.run(search_query.resolve_search_query("I mean one that is new for actions not chatbots", self.HISTORY))
        self.assertEqual(q, "newest large action models for agents 2026")

    def test_rewrite_failure_falls_back_to_recent_turns(self) -> None:
        from server.services import search_query

        async def boom(*_a, **_k):
            raise TimeoutError("model busy")

        with mock.patch("server.services.llm.ollama.complete", side_effect=boom):
            q = asyncio.run(search_query.resolve_search_query("I mean one that is new for actions not chatbots", self.HISTORY))
        self.assertIn("newest model for actions", q)
        self.assertIn("not chatbots", q)
        self.assertLessEqual(len(q), search_query.MAX_QUERY_CHARS)


class PromiseGuardTests(unittest.TestCase):
    def test_bare_promises_are_detected(self) -> None:
        from server.services.chat_pipeline.stage_tools import _promises_lookup

        for reply in (
            "Sure, let's check that out.",
            "Sure, let's check that out.\n[WIDGET:compare|A vs B|x|y]",
            "Let me look that up for you.",
            "I'll search for the latest on that. One moment!",
        ):
            with self.subTest(reply=reply):
                self.assertTrue(_promises_lookup(reply, "I mean one that is new for actions not chatbots"))

    def test_real_answers_and_personal_data_are_left_alone(self) -> None:
        from server.services.chat_pipeline.stage_tools import _promises_lookup

        self.assertFalse(_promises_lookup("Paris is the capital of France.", "capital of france?"))
        self.assertFalse(_promises_lookup("Let me check your calendar.", "am I free at 3?"))
        self.assertFalse(_promises_lookup("Let me check.", "any new emails?"))
        long_answer = "Let me check: " + " ".join(["detail"] * 60)
        self.assertFalse(_promises_lookup(long_answer, "explain transformers"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
