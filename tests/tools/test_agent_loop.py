import asyncio
import re
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def _db():
    from server.models.database import Base
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _ctx(message="hi", **extra):
    return SimpleNamespace(
        db=_db(), conv=SimpleNamespace(id=1), user_message=message, history=[], system_prompt="You are Luna.",
        conversation_summary="", voice=False, cli=False, attachment_ids=[], gmail_widget_cmd=None, **extra,
    )


def _call(name, args=None, call_id=None):
    from server.services.llm.tool_calling import ToolCall
    return ToolCall(call_id or f"call_{name}", name, args or {})


def _turn(content="", calls=()):
    from server.services.llm.tool_calling import AssistantTurn
    return AssistantTurn(content=content, tool_calls=list(calls))


class ScriptedModel:
    """Stands in for chat_step: returns the scripted turns in order, records what it was sent."""

    def __init__(self, *turns):
        self.turns = list(turns)
        self.requests = []

    async def __call__(self, messages, tools, **_):
        self.requests.append({"messages": [dict(m) for m in messages], "tools": tools})
        return self.turns.pop(0)


def _run(ctx, model):
    from server.services.agent_loop.loop import AgentLoop

    async def go():
        events = []
        with mock.patch("server.services.agent_loop.loop.chat_step", new=model):
            async for event in AgentLoop(ctx, [{"role": "user", "content": ctx.user_message}]).run():
                events.append(event)
        return events
    return asyncio.run(go())


class ToolDefinitionTests(unittest.TestCase):
    def test_every_tool_has_a_json_schema_matching_its_params(self) -> None:
        from server.services.tool_registry import TOOL_REGISTRY

        for name, tool in TOOL_REGISTRY.items():
            schema = tool.input_schema
            self.assertEqual(schema.get("type"), "object", name)
            self.assertLessEqual(set(tool.params), set(schema["properties"]), name)
            self.assertLessEqual(set(schema.get("required", [])), set(schema["properties"]), name)

    def test_model_spec_is_function_calling_format(self) -> None:
        from server.services.tool_registry import model_tool_spec

        spec = model_tool_spec("create_event")
        self.assertEqual(spec["type"], "function")
        self.assertEqual(spec["function"]["name"], "create_event")
        self.assertEqual(spec["function"]["parameters"]["required"], ["title", "datetime"])

    def test_validation_coerces_and_reports(self) -> None:
        from server.services.tool_registry import validate_tool_args

        args, error = validate_tool_args("create_event", {"title": "Sync", "datetime": "2026-09-25T15:00",
                                                          "duration": "30", "extra": 1, "junk": None})
        self.assertIsNone(error)
        self.assertEqual(args, {"title": "Sync", "datetime": "2026-09-25T15:00", "duration": 30})
        self.assertIn("'datetime' is a required property", validate_tool_args("create_event", {"title": "x"})[1])
        self.assertIn("not of type 'integer'", validate_tool_args("set_volume", {"level": "loud"})[1])
        self.assertIn("unknown tool", validate_tool_args("nope", {})[1])


class ToolCallingFormatTests(unittest.TestCase):
    def test_calls_written_as_text_are_recovered(self) -> None:
        from server.services.llm.tool_calling import calls_from_text

        known = {"web_search", "create_task"}
        text, calls = calls_from_text('<tool_call>{"name": "web_search", "arguments": {"query": "x"}}</tool_call>', known)
        self.assertEqual((calls[0].name, calls[0].args), ("web_search", {"query": "x"}))
        _, calls = calls_from_text('Sure. {"tool_call": {"tool": "create_task", "args": {"title": "a"}}}', known)
        self.assertEqual(calls[0].name, "create_task")
        _, calls = calls_from_text('{"name": "rm_rf", "arguments": {}}', known)
        self.assertEqual(calls, [])
        # Seen live: the call written as a bracket tag inside the reply.
        text, calls = calls_from_text('Sure thing. Typing "Hi" now. [message_contact app="whatsapp" text="Hi Arjun" '
                                      'to="Arjun"]', known | {"message_contact"})
        self.assertEqual((calls[0].name, calls[0].args),
                         ("message_contact", {"app": "whatsapp", "text": "Hi Arjun", "to": "Arjun"}))
        self.assertNotIn("[", text)
        _, calls = calls_from_text('See [note title="x"] and [link](http://a)', known)
        self.assertEqual(calls, [])

    def test_assistant_and_tool_messages(self) -> None:
        from server.services.llm.tool_calling import tool_result_message

        call = _call("web_search", {"query": "x"})
        message = _turn("", [call]).as_message()
        self.assertEqual(message["tool_calls"][0]["function"], {"name": "web_search", "arguments": {"query": "x"}})
        self.assertEqual(tool_result_message(call, "ok"),
                         {"role": "tool", "tool_call_id": call.id, "tool_name": "web_search", "content": "ok"})


class AgentLoopTests(unittest.TestCase):
    def test_multi_step_saves_then_answers_from_the_result(self) -> None:
        from server.models.database import Task

        ctx = _ctx("add a task to call mom tomorrow at 9am")
        model = ScriptedModel(
            _turn("", [_call("create_task", {"title": "Call mom", "due": "2026-09-24T09:00"})]),
            _turn("Added “Call mom” for tomorrow at 9:00 AM."),
        )
        events = _run(ctx, model)
        self.assertEqual(ctx.db.query(Task).count(), 1)
        self.assertEqual([e["type"] for e in events], ["tool_call", "tool_result", "agent_done"])
        self.assertTrue(events[1]["ok"])
        tool_msg = model.requests[1]["messages"][-1]
        self.assertEqual(tool_msg["role"], "tool")
        self.assertIn("Added task “Call mom”", tool_msg["content"])      # the model saw the verified result
        # The reply states the row read back from the database, not the model's paraphrase of it.
        self.assertEqual(ctx.full_response, tool_msg["content"])
        self.assertEqual(ctx.tools_used, ["create_task"])

    def test_read_only_calls_run_in_parallel_and_writes_keep_order(self) -> None:
        ctx = _ctx("status please")
        order = []

        async def fake_execute(tc, db, conv_id):
            order.append(("start", tc["tool"]))
            await asyncio.sleep(0.3)
            order.append(("end", tc["tool"]))
            return f"{tc['tool']} done"

        model = ScriptedModel(
            _turn("", [_call("get_volume", call_id="a"), _call("get_brightness", call_id="b"),
                       _call("set_clipboard", {"text": "x"}, call_id="c"), _call("get_clipboard", call_id="d")]),
            _turn("All done."),
        )
        started = time.perf_counter()
        with mock.patch("server.services.tool_runner.execute_tool_call", new=fake_execute):
            _run(ctx, model)
        elapsed = time.perf_counter() - started
        # get_volume + get_brightness together (0.3s), then the write alone, then the read after it.
        self.assertLess(elapsed, 1.1)
        self.assertEqual(order[:2], [("start", "get_volume"), ("start", "get_brightness")])
        self.assertLess(order.index(("end", "set_clipboard")), order.index(("start", "get_clipboard")))
        results = [m for m in model.requests[1]["messages"] if m["role"] == "tool"]
        self.assertEqual([m["tool_call_id"] for m in results], ["a", "b", "c", "d"])   # results in call order

    def test_invalid_arguments_go_back_to_the_model(self) -> None:
        ctx = _ctx("meeting friday")
        model = ScriptedModel(_turn("", [_call("create_event", {"title": "Sync"})]), _turn("What time on Friday?"))
        events = _run(ctx, model)
        self.assertFalse(events[1]["ok"])
        self.assertIn("'datetime' is a required property", model.requests[1]["messages"][-1]["content"])
        self.assertEqual(ctx.full_response, "What time on Friday?")

    def test_repeated_call_is_not_run_twice(self) -> None:
        ctx = _ctx("volume?")
        calls = []

        async def fake_execute(tc, db, conv_id):
            calls.append(tc["tool"])
            return "40"

        model = ScriptedModel(_turn("", [_call("get_volume", call_id="1")]), _turn("", [_call("get_volume", call_id="2")]),
                              _turn("It's at 40%."))
        with mock.patch("server.services.tool_runner.execute_tool_call", new=fake_execute):
            _run(ctx, model)
        self.assertEqual(calls, ["get_volume"])
        self.assertIn("already made this exact call", model.requests[2]["messages"][-1]["content"])

    def test_step_budget_forces_a_final_answer_without_tools(self) -> None:
        from server.config import settings

        ctx = _ctx("loop forever")
        turns = [_turn("", [_call("web_fetch", {"url": f"https://example.com/{i}"})]) for i in range(3)]
        model = ScriptedModel(*turns, _turn("Here's what I found."))
        with mock.patch.object(settings, "agent_max_steps", 3), \
             mock.patch("server.services.tool_runner.execute_tool_call", new=mock.AsyncMock(return_value="page")):
            _run(ctx, model)
        self.assertIsNone(model.requests[-1]["tools"])
        self.assertEqual(ctx.full_response, "Here's what I found.")

    def test_announced_action_without_a_call_is_nudged(self) -> None:
        ctx = _ctx("what's the price of an rtx 5090")
        model = ScriptedModel(_turn("Let me check that for you."),
                              _turn("", [_call("web_fetch", {"url": "https://example.com"})]), _turn("It's $1,999."))
        # A price is looked up before the model answers (grounding); "let me check"
        # after that is still a non-answer and still gets nudged.
        with mock.patch("server.services.tool_runner.execute_tool_call", new=mock.AsyncMock(return_value="$1,999")), \
             mock.patch("server.services.agent_loop.loop.AgentLoop._lookup", new=mock.AsyncMock(return_value="$1,999")):
            _run(ctx, model)
        self.assertEqual(ctx.tools_used[0], "web_search")
        self.assertIn("didn't call a tool", model.requests[1]["messages"][-1]["content"])
        self.assertEqual(ctx.full_response, "It's $1,999.")

    def test_claimed_action_without_a_call_is_nudged(self) -> None:
        # Seen live: "Closing 'whatsapp'." copied from an earlier result, with no close_app call.
        ctx = _ctx("Close WhatsApp.")
        model = ScriptedModel(_turn("Closing 'whatsapp'.\nLet me know if you need anything else!"),
                              _turn("", [_call("list_open_apps", {})]), _turn("WhatsApp is still open."))
        with mock.patch("server.services.tool_runner.execute_tool_call", new=mock.AsyncMock(return_value="WhatsApp")):
            _run(ctx, model)
        self.assertIn("didn't call a tool this turn", model.requests[1]["messages"][-1]["content"])
        self.assertEqual(ctx.full_response, "WhatsApp is still open.")

    def test_made_up_send_is_never_shown(self) -> None:
        # Seen live: a long "Sent to … Checks: … Screenshot: …" copied from an earlier send, twice.
        fake = ("Sent to Arjun on WhatsApp: “this is from Luna”.\nChecks: WhatsApp is in front; found 'Arjun' in the "
                "chat search; message typed and checked in the message box; message shows in the chat and the "
                "message box is empty.\nScreenshot: E:\\Luna\\data\\screenshots\\x-whatsapp-sent.png")
        ctx = _ctx("Send him this is from Luna")
        model = ScriptedModel(_turn(fake), _turn(fake))
        _run(ctx, model)
        self.assertIn("didn't call a tool this turn", model.requests[1]["messages"][-1]["content"])
        self.assertTrue(ctx.full_response.startswith("I didn't actually do that"))

    def test_empty_answer_is_retried_never_shown(self) -> None:
        ctx = _ctx("design the schema")
        model = ScriptedModel(_turn("<think>links table, clicks table</think>"), _turn("Two tables: links and clicks."))
        _run(ctx, model)
        self.assertEqual(ctx.full_response, "Two tables: links and clicks.")
        self.assertIsNone(model.requests[1]["tools"])
        self.assertIn("Your last reply was empty", model.requests[1]["messages"][-1]["content"])

    def test_declined_confirmation_is_reported_to_the_model(self) -> None:
        from server.services.permission_manager import permission_manager

        ctx = _ctx("close spotify")
        model = ScriptedModel(_turn("", [_call("close_app", {"app": "spotify"})]), _turn("Okay, I left Spotify open."))
        executed = mock.AsyncMock(return_value="closed")
        with mock.patch.object(permission_manager, "check", return_value=("confirm", "Close spotify?", "c1")), \
             mock.patch("server.services.chat_pipeline.stage_tools._wait_for_confirmation",
                        new=mock.AsyncMock(return_value=False)), \
             mock.patch("server.services.tool_runner.execute_tool_call", new=executed):
            events = _run(ctx, model)
        executed.assert_not_called()
        types = [e["type"] for e in events]
        self.assertIn("confirmation_required", types)
        self.assertIn("declined", model.requests[1]["messages"][-1]["content"])

    def test_tool_search_loads_deferred_tools(self) -> None:
        ctx = _ctx("hello")
        model = ScriptedModel(_turn("", [_call("tool_search", {"query": "dataset"})]), _turn("Loaded."))
        _run(ctx, model)
        first = {t["function"]["name"] for t in model.requests[0]["tools"]}
        second = {t["function"]["name"] for t in model.requests[1]["tools"]}
        self.assertNotIn("dataset_search", first)
        self.assertIn("dataset_search", second)


class LookupQualityTests(unittest.TestCase):
    def test_skill_with_nothing_to_fan_out_uses_a_general_search(self) -> None:
        from server.services.skill_runtime import runner
        from server.services.skill_runtime.registry import get_search_skill

        skill = get_search_skill("product-search")
        general = runner.SkillRun(answer="general answer", skill_id="web")
        with mock.patch.object(runner, "extract_slots", new=mock.AsyncMock(return_value={"products": [], "budget": "", "needs": []})), \
             mock.patch.object(runner, "run_web_search", new=mock.AsyncMock(return_value=general)) as web, \
             mock.patch.object(runner.sources, "run_searches", new=mock.AsyncMock()) as searches:
            run = asyncio.run(runner.run_search_skill(skill, "learn more about jev vs Laya"))
        web.assert_awaited_once()
        searches.assert_not_called()
        self.assertEqual(run.answer, "general answer")

    def test_only_cards_the_answer_mentions_are_shown(self) -> None:
        from server.services.agent_loop.loop import _relevant_cards
        from server.services.skill_runtime.runner import embed_cards

        comment = embed_cards("", [{"title": "Laya III Personal Massager", "url": "https://a"},
                                   {"title": "Sony WH-1000XM6 Headphones", "url": "https://b"}]).strip()
        kept = _relevant_cards([comment], "The Sony WH-1000XM6 headphones are the best pick.")
        self.assertIn("Sony", kept)
        self.assertNotIn("Massager", kept)
        self.assertEqual(_relevant_cards([comment], "Neither brand makes LLMs."), "")

    def test_no_removed_links_notice_after_a_real_search(self) -> None:
        from server.services.chat_pipeline.stage_tools import strip_unverified_links

        text = "See [the guide](https://invented.example.com/deep/page)."
        self.assertIn("I removed 1 link", strip_unverified_links(text, ""))
        quiet = strip_unverified_links(text, "", notice=False)
        self.assertNotIn("I removed", quiet)
        self.assertNotIn("invented.example.com", quiet)


class LongContextTests(unittest.TestCase):
    def _haystack(self, sentences: int, needle: str) -> str:
        import random
        random.seed(7)
        words = "system network latency buffer cache request server client packet schedule memory queue".split()
        body = [" ".join(random.choice(words) for _ in range(14)).capitalize() + "." for _ in range(sentences)]
        body.insert(sentences // 2, needle)
        return "Here is a long log dump:\n\n" + " ".join(body) + "\n\nQuestion: what is the vault passphrase?"

    def test_long_paste_keeps_start_end_and_the_relevant_middle(self) -> None:
        from server.services.files import retrieval

        text = self._haystack(900, "The vault passphrase is copper-lantern-20.")
        with mock.patch.object(retrieval, "_embed_batch", new=mock.AsyncMock(return_value=None)):   # keyword ranking
            out, kept, total = asyncio.run(retrieval.condense_long_text(text, 16000))
        self.assertLessEqual(len(out), 16000)
        self.assertIn("copper-lantern-20", out)
        self.assertTrue(out.startswith("Here is a long log dump"))
        self.assertTrue(out.endswith("what is the vault passphrase?"))
        self.assertIn(f"{kept} of {total} middle parts", out)
        self.assertEqual(asyncio.run(retrieval.condense_long_text("short", 16000)), ("short", 0, 0))

    def test_long_paste_never_counts_as_a_save_request(self) -> None:
        from server.services.command_parser.schedule import wants_saved

        paste = "Schedule packet queue schedule record commit. " * 40
        self.assertFalse(wants_saved(paste, "The log shows no passphrase."))
        self.assertTrue(wants_saved("remind me to call mom at 5", "Okay."))

    def test_state_and_failure_replies_are_not_saved_as_style_examples(self) -> None:
        from server.services.chat_background import _is_style_example

        self.assertTrue(_is_style_example("How is life", "Pretty good, busy week."))
        self.assertFalse(_is_style_example("What's my screen brightness?", "I can't check your screen brightness right now"))
        self.assertFalse(_is_style_example("volume?", "Volume is at 100%."))
        self.assertFalse(_is_style_example("x" * 400, "Sure."))

    def test_user_name_must_come_from_the_user(self) -> None:
        from server.services import fact_extractor

        convo = "User: hey, I'm Sam by the way\nLuna: Nice to meet you, Sam."
        for reply, expected in (("Sam", "Sam"), ("unknown.", None), ("Luna", None), ("Orion", None)):
            with mock.patch.object(fact_extractor.ollama, "complete", new=mock.AsyncMock(return_value=reply)):
                self.assertEqual(asyncio.run(fact_extractor.extract_user_name(convo)), expected, reply)

    def test_summary_runs_every_ten_stored_messages(self) -> None:
        from server.models.database import Conversation, Message
        from server.services import chat_background

        db = _db()
        conv = Conversation(message_count=3)             # a drifted counter must not matter
        db.add(conv)
        db.commit()
        cid = conv.id
        for i in range(10):
            db.add(Message(conversation_id=cid, role="user" if i % 2 == 0 else "assistant", content=f"m{i}"))
        db.commit()
        chat_background._summarized_at.pop(cid, None)
        summarize = mock.AsyncMock(return_value="Facts:\n- codename BLUEFIN")
        with mock.patch.object(chat_background, "summarize_conversation", new=summarize), \
             mock.patch.object(chat_background, "extract_emotional_arc", new=mock.AsyncMock(return_value="")), \
             mock.patch.object(chat_background, "extract_facts_from_conversation", new=mock.AsyncMock()), \
             mock.patch.object(chat_background, "extract_session_facts",
                               new=mock.AsyncMock(return_value=["Project name: Snip"])), \
             mock.patch.object(chat_background.MemoryManager, "store_conversation_summary", new=mock.AsyncMock()):
            asyncio.run(chat_background.post_conversation_processing(db, cid, "reply", "", "question"))
            asyncio.run(chat_background.post_conversation_processing(db, cid, "reply", "", "question"))
        summarize.assert_awaited_once()                  # second call: no new messages yet
        conv = db.query(Conversation).filter_by(id=cid).first()     # the task closed its session
        self.assertIn("BLUEFIN", conv.summary)
        from server.models.database import ConversationArtifact
        facts = [a.content for a in db.query(ConversationArtifact).filter_by(conversation_id=cid, kind="fact")]
        self.assertEqual(facts, ["Project name: Snip"])  # decisions also land in the append-only state

    def test_background_work_releases_its_connection(self) -> None:
        from server.models.database import Conversation
        from server.services import chat_background

        db = _db()
        conv = Conversation()
        db.add(conv)
        db.commit()
        with mock.patch.object(chat_background, "extract_facts_from_conversation", new=mock.AsyncMock()), \
             mock.patch.object(chat_background, "_should_trigger_extraction", return_value=False):
            asyncio.run(chat_background.post_conversation_processing(db, conv.id, "reply", "", "question"))
        self.assertFalse(db.in_transaction())            # connection returned to the pool


class RoutingAndStyleTests(unittest.TestCase):
    def _ctx(self, message):
        return SimpleNamespace(user_message=message, is_business=False, attachment_ids=[])

    def test_recall_and_coding_questions_stay_in_the_chat_loop(self) -> None:
        from server.services.chat_pipeline.stage_generate import uses_special_agent

        probe = ("Quick check without looking anything up: what are the project codename, the deploy region, "
                 "the test budget and the reviewer's code word?")                     # "code" + "check" + "test"
        for message in (probe, "write a python function that shortens urls", "refactor the shorten function to be async"):
            self.assertFalse(uses_special_agent(self._ctx(message)), message)
        self.assertTrue(uses_special_agent(self._ctx("use crew mode to research and write a report on solar")))
        self.assertTrue(uses_special_agent(self._ctx("write a function in app.py in my workspace that parses CSV")))
        # A framework name isn't a file: this went to the coding agent and came back empty.
        self.assertFalse(uses_special_agent(self._ctx("Explain how event loops work in Node.js in about 300 words.")))
        self.assertFalse(uses_special_agent(self._ctx("write a React component in Next.js for a login form")))

    def test_crew_heuristic_still_available_without_the_loop(self) -> None:
        from server.services.agents import is_crew_request

        text = "research the best vector databases and then write a detailed report comparing them for me"
        self.assertTrue(is_crew_request(text))
        self.assertFalse(is_crew_request(text, explicit_only=True))

    def test_style_examples_fit_the_message(self) -> None:
        from server.services.personality.style_examples import pick_examples, examples_prompt

        self.assertEqual(pick_examples("give me a recipe for butter chicken")[0]["cat"], "knowledge")
        self.assertEqual(pick_examples("hey")[0]["user"], "hey")
        self.assertEqual(pick_examples("qwertyuiop zxcv"), [])
        self.assertLessEqual(len(pick_examples("thanks lol jk haha cool ok")), 4)
        self.assertIn("copy the tone, not the facts", examples_prompt("I'm so tired"))

    def test_curated_examples_follow_the_persona_rules(self) -> None:
        from server.services.personality.style_examples import load_examples

        banned = re.compile(r"let me know|anything else|need anything|how can i help|feel free|\.\.\.|\b(?:darling|honey|babe|dear)\b", re.I)
        examples = load_examples()
        self.assertGreaterEqual(len(examples), 50)
        for ex in examples:
            self.assertFalse(banned.search(ex["luna"]), ex["luna"])

    def test_auto_saved_pairs_are_not_shown_to_the_model(self) -> None:
        import json as _json
        import tempfile
        from server.services import prompt_builder

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rlhf_pairs.json"
            path.write_text(_json.dumps([
                {"message": "Love you!", "chosen": "You're welcome. Need anything?", "auto_generated": True},
                {"message": "hey", "chosen": "Hey, what's up?"},
            ]), encoding="utf-8")
            with mock.patch.object(prompt_builder, "DATA_DIR", Path(tmp)):
                shown = prompt_builder._load_rlhf_examples()
        self.assertIn("Hey, what's up?", shown)
        self.assertNotIn("Need anything?", shown)


class SkillChoiceTests(unittest.TestCase):
    def test_use_skill_offers_and_accepts_only_lookup_skills(self) -> None:
        ctx = _ctx("learn more about jev vs laya")
        model = ScriptedModel(_turn("", [_call("use_skill", {"skill": "dataset-builder", "request": "jev vs laya"})]),
                              _turn("", [_call("web_search", {"query": "jev vs laya"})]), _turn("They are decision models."))
        lookup = mock.AsyncMock(return_value="Jev and Laya are decision models.")
        with mock.patch("server.services.agent_loop.loop.AgentLoop._lookup", new=lookup):
            events = _run(ctx, model)
        skill_spec = next(t for t in model.requests[0]["tools"] if t["function"]["name"] == "use_skill")
        self.assertIn("product-search", skill_spec["function"]["parameters"]["properties"]["skill"]["enum"])
        self.assertNotIn("dataset-builder", skill_spec["function"]["parameters"]["properties"]["skill"]["enum"])
        self.assertFalse(events[1]["ok"])                                  # rejected, never run
        self.assertEqual(lookup.await_count, 1)                            # only the web_search ran
        self.assertIn("not a lookup skill", model.requests[1]["messages"][-1]["content"])


class SelectionAndRoutingTests(unittest.TestCase):
    def test_core_tools_groups_and_exclusions(self) -> None:
        from server.services.agent_loop.tool_selection import deferred_tools, select_tools

        plain = select_tools("add a meeting at 6pm")
        self.assertIn("create_event", plain)
        self.assertNotIn("github_list_prs", plain)
        self.assertIn("github_list_prs", select_tools("check my github PRs"))
        self.assertIn("set_volume", select_tools("turn the volume down"))
        self.assertFalse([n for n in deferred_tools(plain) if n.startswith("code_") or n == "web_research"])

    def test_multi_step_requests_skip_shortcuts(self) -> None:
        from server.services.agent_loop.routing import is_multi_step

        self.assertTrue(is_multi_step("Find the latest Ollama release, then add a task to read it tonight"))
        self.assertTrue(is_multi_step("find flights to NYC and email me the cheapest one"))
        self.assertFalse(is_multi_step("find me ML engineer jobs in Phoenix"))
        self.assertFalse(is_multi_step("search for black and white photography tips"))

    def test_desktop_loads_agent_steps(self) -> None:
        renderer = Path(__file__).resolve().parents[2] / "interfaces" / "desktop" / "src" / "renderer"
        self.assertIn('<script src="agent-steps.js"></script>', (renderer / "index.html").read_text(encoding="utf-8"))
        app = (renderer / "app.js").read_text(encoding="utf-8")
        self.assertIn("steps.handle(payload)", app)

    def test_streaming_reply_survives_switching_chats(self) -> None:
        app = (Path(__file__).resolve().parents[2] / "interfaces" / "desktop" / "src" / "renderer" / "app.js").read_text(encoding="utf-8")
        # Reopening a chat puts its still-streaming reply back, and a stream never
        # moves the user back to its own chat.
        self.assertIn("const live = streamFor(data.id)", app)
        self.assertIn("conversation.append(live.row)", app)
        self.assertIn("if (stillHere()) activeConversationId = payload.conversation_id", app)
        self.assertNotIn("activeConversationId = payload.conversation_id || activeConversationId", app)


if __name__ == "__main__":
    unittest.main(verbosity=2)
