"""Fixes from the live chat eval: invented answers, wrong weekday, false
"saved/forgot" claims, lossy or ungrounded memories."""
import asyncio
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest import mock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from tests.tools import _bootstrap  # noqa: F401


def _session():
    from backend.models.database import Base
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


class CalculatorTests(unittest.TestCase):
    def test_exact_arithmetic(self) -> None:
        from backend.services.calculator import calculate
        self.assertEqual(calculate("17*23"), "17*23 = 391")
        self.assertEqual(calculate("17 x 23"), "17 x 23 = 391")
        self.assertEqual(calculate("15% of 80"), "15% of 80 = 12")
        self.assertEqual(calculate("sqrt(144) + 2^3"), "sqrt(144) + 2^3 = 20")
        self.assertEqual(calculate("1,200 / 3"), "1,200 / 3 = 400")

    def test_rejects_code_and_bad_input(self) -> None:
        from backend.services.calculator import calculate
        for expr in ("__import__('os').system('dir')", "open('x')", "a + 1", "9**99999", "1/0", ""):
            self.assertTrue(calculate(expr).startswith("Error"), expr)


class RequiredCallsTests(unittest.TestCase):
    def calls(self, message):
        from backend.services.agent_loop.grounding import required_calls
        return required_calls(message)

    def test_live_state_questions_need_their_read(self) -> None:
        self.assertEqual(self.calls("What's my current system volume?"), [("get_volume", {})])
        self.assertEqual(self.calls("How much RAM and what CPU does this computer have?"), [("get_system_info", {})])
        self.assertEqual(self.calls("what's on my clipboard"), [("get_clipboard", {})])

    def test_changing_state_is_not_a_read(self) -> None:
        self.assertEqual(self.calls("Turn the volume up to 100%"), [])
        self.assertEqual(self.calls("set brightness to 40"), [])

    def test_file_questions_read_the_file(self) -> None:
        self.assertEqual(self.calls("Read the README.md in the Luna workspace and tell me the first heading"),
                         [("workspace_read", {"path": "README.md"})])
        self.assertEqual(self.calls("I updated notes.md yesterday"), [])          # mentions a file, asks nothing

    def test_arithmetic_is_calculated(self) -> None:
        self.assertEqual(self.calls("What's 17 times 23?"), [("calculate", {"expression": "17*23"})])
        self.assertEqual(self.calls("how much is 120 divided by 8"), [("calculate", {"expression": "120/8"})])
        self.assertEqual(self.calls("Schedule it on 2026-10-13"), [])

    def test_changing_facts_are_looked_up(self) -> None:
        q = "What's the latest stable version of Python?"
        self.assertEqual(self.calls(q), [("web_search", {"query": q})])
        self.assertEqual(self.calls("who won the 2026 world cup?")[0][0], "web_search")
        self.assertEqual(self.calls("Who won the 2018 FIFA World Cup?"), [])                # settled past: no lookup
        self.assertEqual(self.calls("what's the latest on the 2018 data breach case?")[0][0], "web_search")
        self.assertEqual(self.calls("what's my latest task?"), [])                          # personal
        self.assertEqual(self.calls("what's the weather right now?"), [])                    # live data section
        self.assertEqual(self.calls("Explain how a V8 engine works"), [])                    # stable knowledge

    def test_forget_is_a_command_not_a_mention(self) -> None:
        self.assertEqual(self.calls("Forget everything you know about my dog."), [("forget_memory", {"about": "my dog"})])
        self.assertEqual(self.calls("please forget my old address"), [("forget_memory", {"about": "my old address"})])
        self.assertEqual(self.calls("I always forget my keys"), [])


class NewsTests(unittest.TestCase):
    ITEMS = [
        {"source": "BBC World", "title": "Leaders meet for climate summit in Geneva", "link": "https://bbc.co.uk/a"},
        {"source": "Reuters", "title": "Nvidia shares rise after record quarter", "link": "https://reuters.com/b"},
        {"source": "NPR", "title": "Storm warnings issued along the east coast", "link": "https://npr.org/c"},
    ]

    def test_general_news_runs_daily_news(self) -> None:
        from backend.services.agent_loop.grounding import is_general_news, required_calls
        for q in ("What's the news today?", "Give me today's headlines", "what's happening in the world"):
            self.assertEqual(required_calls(q), [("daily_news", {"topic": ""})], q)
            self.assertTrue(is_general_news(q), q)
        self.assertEqual(required_calls("Any news about Nvidia?"), [("daily_news", {"topic": "Nvidia"})])
        self.assertFalse(is_general_news("latest news on Nvidia"))     # topic news stays with news-search
        self.assertEqual(required_calls("did you save my news preferences?"), [])

    def run_news(self, *args):
        from backend.services.dashboard import news
        with mock.patch.object(news, "get_news", new=mock.AsyncMock(return_value=self.ITEMS)):
            return asyncio.run(news.daily_news(*args))

    def test_headlines_are_numbered_with_source_and_link(self) -> None:
        out = self.run_news("", 2)
        self.assertTrue(out.startswith("Today's top headlines"))
        self.assertIn("1. Leaders meet for climate summit in Geneva — BBC World (https://bbc.co.uk/a)", out)
        self.assertIn("2. Nvidia shares rise", out)
        self.assertNotIn("Storm", out)

    def test_topic_filter_and_fallback_to_search(self) -> None:
        out = self.run_news("nvidia")
        self.assertIn("Nvidia shares rise", out)
        self.assertIn("news-search", out)                              # only 1 match: point to a real search
        self.assertNotIn("climate", out)


class ScheduleTests(unittest.TestCase):
    def test_wrong_weekday_is_sent_back_with_the_right_date(self) -> None:
        from backend.services.agent_loop.loop import _weekday_mismatch
        today = datetime.now()
        tuesday = today + timedelta(days=(1 - today.weekday()) % 7 or 7)
        monday = tuesday - timedelta(days=1)
        error = _weekday_mismatch("Schedule Quillon sync next Tuesday at 3pm", "create_event",
                                  {"datetime": f"{monday:%Y-%m-%d}T15:00"})
        self.assertIn(f"{tuesday:%Y-%m-%d}", error)
        self.assertIsNone(_weekday_mismatch("Schedule Quillon sync next Tuesday at 3pm", "create_event",
                                            {"datetime": f"{tuesday:%Y-%m-%d}T15:00"}))
        self.assertIsNone(_weekday_mismatch("remind me tomorrow", "create_task", {"due": f"{monday:%Y-%m-%d}T09:00"}))

    def test_unstated_time_is_asked_not_guessed(self) -> None:
        from backend.services.agent_loop.loop import _unstated_time
        event = {"title": "Sync with John", "datetime": "2026-10-12T09:00"}
        self.assertIn("ask them when", _unstated_time(["Set up a meeting with John"], "create_event", event))
        self.assertIsNone(_unstated_time(["Set up a meeting with John", "Thursday at 2"], "create_event", event))
        self.assertIsNone(_unstated_time(["meeting with John tomorrow 3pm"], "create_event", event))
        self.assertIsNone(_unstated_time(["add a task to buy milk"], "create_task", {"title": "Buy milk"}))
        self.assertIn("without `due`", _unstated_time(["add a task to buy milk"], "create_task",
                                                      {"title": "Buy milk", "due": "2026-10-10T09:00"}))

    def test_tool_spec_lists_the_coming_week(self) -> None:
        from backend.services.agent_loop.loop import _live_spec
        from backend.services.tool_registry import model_tool_spec
        description = _live_spec(model_tool_spec("create_event"))["function"]["description"]
        nxt = datetime.now() + timedelta(days=1)
        self.assertIn(f"{nxt:%A} = {nxt:%Y-%m-%d}", description)

    def test_reply_states_the_saved_row_not_the_models_claim(self) -> None:
        from backend.services.agent_loop.loop import _with_saved
        saved = ["Added “Quillon sync” to your calendar — Monday, Oct 12 at 3:00 PM."]
        text = _with_saved('The meeting "Quillon sync" is scheduled for next Tuesday at 3:00 PM.', saved, ["Quillon sync"])
        self.assertEqual(text, saved[0])
        text = _with_saved("Node 22 is the current LTS. I've added a task for the upgrade.", ["Added task “Upgrade”."], ["Upgrade"])
        self.assertEqual(text, "Node 22 is the current LTS.\n\nAdded task “Upgrade”.")


class ToolSearchTests(unittest.TestCase):
    def test_finds_tools_that_are_already_loaded(self) -> None:
        from backend.services.agent_loop.tool_selection import search_tools
        active = ["web_search", "create_task"]
        self.assertNotIn("create_task", search_tools("create_task", active))
        self.assertEqual(search_tools("create_task", [], among=active), ["create_task"])


class MemoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = _session()

    def _fact(self, content, active=True):
        from backend.models.database import Fact
        fact = Fact(category="relationship", content=content, confidence=1.0, is_active=active)
        self.db.add(fact)
        self.db.commit()
        return fact

    def _memory(self):
        from backend.services.memory_manager import MemoryManager
        memory = MemoryManager(self.db)
        memory._get_collection = mock.MagicMock(return_value=mock.MagicMock(get=mock.MagicMock(return_value={})))
        return memory

    def test_forget_follows_names_from_matched_facts(self) -> None:
        dog = self._fact("User has a dog named Quillon")
        age = self._fact("Quillon is 4 years old")
        meet = self._fact("Weekly sync is on Tuesday")
        allergy = self._fact("User is allergic to cashews")
        forgotten = self._memory().forget("my dog")
        self.assertCountEqual(forgotten, [dog.content, age.content])
        self.db.refresh(meet); self.db.refresh(allergy)
        self.assertTrue(meet.is_active and allergy.is_active)

    def test_forget_with_no_subject_forgets_nothing(self) -> None:
        self._fact("User has a dog named Quillon")
        self.assertEqual(self._memory().forget("everything you know"), [])

    def test_forget_memory_tool_reads_back(self) -> None:
        from backend.services.tool_runner import execute_tool_call
        self._fact("User has a dog named Quillon")
        with mock.patch("backend.services.memory_manager.MemoryManager._get_collection",
                        return_value=mock.MagicMock(get=mock.MagicMock(return_value={}))):
            out = asyncio.run(execute_tool_call({"tool": "forget_memory", "args": {"about": "my dog"}}, self.db, 1))
            none = asyncio.run(execute_tool_call({"tool": "forget_memory", "args": {"about": "my car"}}, self.db, 1))
        self.assertTrue(out.startswith("Forgot 1 memory"))
        self.assertIn("nothing to forget", none)

    def test_recall_skips_inactive_facts(self) -> None:
        from backend.services.memory_manager import MemoryManager
        gone = self._fact("User has a dog named Quillon", active=False)
        kept = self._fact("User is allergic to cashews")
        col = mock.MagicMock()
        col.count.return_value = 2
        col.query.return_value = {
            "documents": [[gone.content, kept.content]], "distances": [[0.1, 0.2]],
            "metadatas": [[{"type": "fact", "fact_id": gone.id}, {"type": "fact", "fact_id": kept.id}]]}
        memory = MemoryManager(self.db)
        memory._get_collection = mock.MagicMock(return_value=col)
        with mock.patch.object(memory, "_embed", new=mock.AsyncMock(return_value=[0.1])):
            found = asyncio.run(memory.retrieve_relevant("pets", n=4))
        recalled = found["short_term"] + found["long_term"]
        self.assertIn(kept.content, recalled)
        self.assertNotIn(gone.content, recalled)

    def test_fact_quotes_must_come_from_the_user(self) -> None:
        from backend.services.fact_extractor import _quote_is_grounded, _user_text
        convo = "User: schedule Quillon sync next Tuesday\nLuna: Your meeting is scheduled for next Tuesday at 3 PM."
        users = _user_text(convo)
        self.assertTrue(_quote_is_grounded("schedule Quillon sync next Tuesday", users))
        self.assertFalse(_quote_is_grounded("scheduled for next Tuesday at 3 PM", users))
        self.assertEqual(_user_text("User: line one\nline two\nLuna: hi"), "line one\nline two\n")


if __name__ == "__main__":
    unittest.main(verbosity=2)
