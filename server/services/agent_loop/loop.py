"""The agent loop: model → tool calls → results → model, until the model answers.

Same shape as Claude Code / Codex:
  - tools are offered as JSON Schemas and called natively (structured tool_calls);
  - each call is validated against its schema and permission-checked;
  - several calls in one step run in parallel when they are read-only
    (writes run one at a time, in the order the model gave them);
  - every result goes back to the model as a `role: tool` message, and the
    model decides the next step — more tools, or the final answer.

Events are yielded as they happen so the UI can show each step live.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import AsyncGenerator

from server.config import settings
from server.services.agent_loop.grounding import required_calls
from server.services.agent_loop.tool_selection import TOOL_SEARCH, search_tools, select_tools, tool_search_spec
from server.services.llm.context_window import estimate_tokens, fit_context
from server.services.llm.tool_calling import AssistantTurn, ToolCall, chat_step, tool_result_message
from server.services.permission_manager import permission_manager
from server.services.response_formatter import format_luna_response, strip_cards
from server.services.tool_registry import get_tool, model_tool_spec, validate_tool_args

logger = logging.getLogger(__name__)

_CARDS_RE = re.compile(r"<!--luna-cards:.*?-->", re.DOTALL)
_ERROR_PREFIXES = ("error", "failed", "unknown tool", "i couldn't", "github error", "event creation failed")
_ACT_NUDGE = ("You said you would do that but didn't call a tool, so nothing happened. "
              "Call the right tool now, or answer directly if no tool is needed.")
_EMPTY_NUDGE = "Your last reply was empty. Answer the user's message now, in plain text, outside any <think> tags."
_FINAL_NUDGE = "You've used the tool budget for this request. Answer the user now with what you have; no more tools."


@dataclass
class ToolOutcome:
    call: ToolCall
    content: str
    is_error: bool = False


def _is_error(text: str) -> bool:
    return (text or "").strip().lower().startswith(_ERROR_PREFIXES)


def _summary(text: str, limit: int = 160) -> str:
    flat = " ".join(strip_cards(text or "").split())
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"


_CARD_WORD_RE = re.compile(r"[a-z0-9]{3,}")


def _relevant_cards(comments: list[str], answer: str) -> str:
    """Cards whose item the final answer actually mentions.

    A lookup can return cards for things the answer ends up dismissing (a
    search for "Laya" surfaced a massager); showing those is worse than none.
    """
    from server.services.skill_runtime.runner import embed_cards

    answer_words = set(_CARD_WORD_RE.findall((answer or "").lower()))
    kept: list[dict] = []
    for comment in comments:
        try:
            cards = json.loads(comment[len("<!--luna-cards:"):-len("-->")])
        except (ValueError, TypeError):
            continue
        for card in cards if isinstance(cards, list) else []:
            words = set(_CARD_WORD_RE.findall(str(card.get("title", "")).lower()))
            if words and len(words & answer_words) >= min(2, len(words)) and card not in kept:
                kept.append(card)
    return embed_cards("", kept).strip() if kept else ""


_TIMED_TOOLS = {"create_task", "create_event"}


def _with_skill_ids(spec: dict) -> dict:
    """use_skill may only name an installed lookup skill: list them as an enum
    (with what each is for) so the model can't pick a non-lookup skill."""
    from server.services.skill_runtime.registry import load_search_skills

    skills = load_search_skills()
    if not skills:
        return spec
    fn = spec["function"]
    params = fn["parameters"]
    skill_prop = {
        **params["properties"]["skill"],
        "enum": [s.id for s in skills],
        "description": "Which web lookup: " + "; ".join(f"{s.id} = {s.description.split('.')[0][:70]}" for s in skills),
    }
    return {**spec, "function": {**fn, "parameters": {**params, "properties": {**params["properties"], "skill": skill_prop}}}}


def _live_spec(spec: dict) -> dict:
    """Fill in what the static schema can't know: the installed lookup skills for
    use_skill, and the current local time next to date arguments (small models
    resolve "tonight" / "Friday" far better when the anchor sits in the schema)."""
    fn = spec["function"]
    if fn["name"] == "use_skill":
        return _with_skill_ids(spec)
    if fn["name"] not in _TIMED_TOOLS:
        return spec
    now = datetime.now()
    # The model put "next Tuesday" on a Monday when it had to count days itself;
    # a ready-made table of the coming week leaves nothing to count.
    week = ", ".join(f"{d:%A} = {d:%Y-%m-%d}" for d in (now + timedelta(days=i) for i in range(1, 8)))
    anchor = (f"Now it is {now:%A %Y-%m-%d %H:%M} local time "
              f"(tonight = {now:%Y-%m-%d}, tomorrow = {now + timedelta(days=1):%Y-%m-%d}). "
              f"Coming days: {week}.")
    return {**spec, "function": {**fn, "description": f"{fn['description']}. {anchor}"}}


_WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
_WEEKDAY_RE = re.compile(r"\b(" + "|".join(_WEEKDAYS) + r")\b", re.IGNORECASE)


def _weekday_mismatch(user_message: str, name: str, args: dict) -> str | None:
    """The user named one weekday but the date argument falls on another: say which date is right."""
    named = {m.lower() for m in _WEEKDAY_RE.findall(user_message or "")}
    value = str(args.get("datetime" if name == "create_event" else "due") or "")
    if len(named) != 1 or not value:
        return None
    try:
        when = datetime.fromisoformat(value.replace("Z", ""))
    except ValueError:
        return None
    wanted = _WEEKDAYS.index(named.pop())
    if when.weekday() == wanted:
        return None
    today = datetime.now()
    ahead = (wanted - today.weekday()) % 7 or 7
    right = today + timedelta(days=ahead)
    return (f"Error: the user said {_WEEKDAYS[wanted].title()}, but {when:%Y-%m-%d} is a {when:%A}. "
            f"The coming {_WEEKDAYS[wanted].title()} is {right:%Y-%m-%d} "
            f"(or {right + timedelta(days=7):%Y-%m-%d} if they mean the week after). Call again with the right date.")


_SAID_WHEN_RE = re.compile(
    r"\b(?:\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)|\d{1,2}:\d{2}|noon|midnight|morning|afternoon|evening|"
    r"tonight|today|tomorrow|day\s+after|weekend|next\s+(?:week|month)|in\s+\d+\s+(?:minutes?|hours?|days?|weeks?)|"
    r"\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}|o'?clock|"
    + "|".join(_WEEKDAYS) +
    r"|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+\d{1,2})\b", re.IGNORECASE)


def _unstated_time(user_turns: list[str], name: str, args: dict) -> str | None:
    """A date the user never gave is the model's guess: ask instead of saving it.

    "Set up a meeting with John" became a 9:00 AM event nobody chose.
    """
    if any(_SAID_WHEN_RE.search(t or "") for t in user_turns):
        return None
    if name == "create_event":
        return ("Error: the user hasn't said when this is. Don't guess a date or time — "
                "ask them when, in one short question, and save it after they answer.")
    if args.get("due"):
        return ("Error: the user gave no due date or time, so don't invent one. "
                "Call create_task again without `due`, or ask them when it's due.")
    return None


_SAVE_CLAIM_RE = re.compile(r"\b(?:scheduled|added|saved|booked|created|set\s+for|remind(?:er)?)\b", re.IGNORECASE)


def _with_saved(text: str, saved: list[str], titles: list[str]) -> str:
    """The reply states what the database holds, not what the model says it did.

    The model wrote "scheduled for next Tuesday" over a row saved on Monday; the
    read-back lines from save_and_verify replace its sentences about the save.
    """
    from server.services.command_parser.schedule import CLAIM_RE

    lowered = [t.lower() for t in titles if t]
    kept = []
    for sentence in re.split(r"(?<=[.!?])\s+", (text or "").strip()):
        s = sentence.lower()
        if not sentence.strip() or CLAIM_RE.search(sentence) or (
                _SAVE_CLAIM_RE.search(sentence) and (any(t in s for t in lowered) or not lowered)):
            continue
        kept.append(sentence)
    rest = " ".join(kept).strip()
    lines = "\n".join(saved)
    return f"{rest}\n\n{lines}" if rest else lines


def _clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    head = text[: int(limit * 0.8)]
    tail = text[-int(limit * 0.15):]
    return f"{head}\n…[{len(text) - len(head) - len(tail)} characters omitted]…\n{tail}"


class AgentLoop:
    def __init__(self, ctx, messages: list[dict]):
        self.ctx = ctx
        self.base_messages = messages          # conversation incl. the latest user message
        self.active = select_tools(ctx.user_message, getattr(ctx, "history", None))
        self.seen: dict[str, str] = {}          # call signature → result (repeat detection)
        self.cards: list[str] = []              # result cards from lookups, re-attached to the answer
        self.tools_used: list[str] = []
        self.tool_errors = 0
        self.streamed = False
        self.events: asyncio.Queue = asyncio.Queue()
        self.auto_calls = 0                     # calls the loop ran itself before the model's first step
        self.saved: list[str] = []              # read-back lines from create_task / create_event
        self.saved_titles: list[str] = []

    # ── tool specs ────────────────────────────────────────────────────────────
    def tool_specs(self) -> list[dict]:
        specs = [_live_spec(s) for s in (model_tool_spec(n) for n in self.active) if s]
        search = tool_search_spec(self.active)
        return specs + ([search] if search else [])

    # ── running one call ──────────────────────────────────────────────────────
    async def _execute(self, call: ToolCall) -> ToolOutcome:
        name = call.name
        if name == TOOL_SEARCH:
            query = str(call.args.get("query", ""))
            found = search_tools(query, self.active)
            self.active.extend(found)
            if not found:
                # The model looked for create_task while it was loaded, got "no
                # matching tools", and told the user it couldn't create tasks.
                loaded = search_tools(query, [], among=self.active)
                if loaded:
                    return ToolOutcome(call, "Already available — call it now: " + ", ".join(loaded))
                return ToolOutcome(call, "No matching tools. Answer with the tools you have.")
            lines = [f"- {n}: {get_tool(n).description}" for n in found]
            return ToolOutcome(call, "Loaded these tools; you can call them now:\n" + "\n".join(lines))

        args = call.args                         # validated in _run_one
        signature = f"{name}:{json.dumps(args, sort_keys=True)}"
        if signature in self.seen:
            return ToolOutcome(call, "You already made this exact call; its result is above. "
                                     "Use it, or try something different.")

        try:
            if name in ("use_skill", "web_search"):
                content = await self._lookup(name, args)
            else:
                from server.services.tool_runner import execute_tool_call
                content = await execute_tool_call({"tool": name, "args": args}, self.ctx.db, self.ctx.conv.id)
        except Exception as e:                   # a tool must never take the loop down
            logger.error("Tool %s failed: %s", name, e, exc_info=True)
            content = f"Error: {name} failed: {e}"

        content = str(content if content is not None else "")
        if name == "google_workspace" and args.get("service") == "gmail":
            from server.services.chat_pipeline.stage_tools import gmail_widget_from_result
            self.ctx.gmail_widget_cmd = gmail_widget_from_result(content) or self.ctx.gmail_widget_cmd
        self.seen[signature] = content
        return ToolOutcome(call, content, _is_error(content))

    async def _lookup(self, name: str, args: dict) -> str:
        """Web lookups go through the skill runtime (grounded, link-checked)."""
        from server.services.chat_pipeline.stage_dispatch import _search_answer_context
        from server.services.skill_runtime import get_search_skill, pick_search_skill, run_search_skill, run_web_search

        request = str(args.get("request") or args.get("query") or "").strip()
        history = getattr(self.ctx, "history", None) or []
        skill = get_search_skill(str(args.get("skill", ""))) if name == "use_skill" else None
        skill = skill or pick_search_skill(f"{self.ctx.user_message} {request}")
        context, documents = await _search_answer_context(self.ctx, history, self.ctx.user_message)
        if skill:
            run = await run_search_skill(skill, request or self.ctx.user_message, history, documents=documents, context=context)
        else:
            run = await run_web_search(request or self.ctx.user_message, history, context=context, candidate=request or None)
        answer = run.answer or run.results_text or "No results."
        self.cards.extend(_CARDS_RE.findall(answer))
        return _CARDS_RE.sub("", answer).strip()

    async def _permitted(self, call: ToolCall) -> str | None:
        """None when the call may run, else the reason it may not (sent to the model)."""
        if call.name == TOOL_SEARCH:
            return None
        decision, message, confirm_id = permission_manager.check(call.name, call.args)
        if decision == "allow":
            return None
        if decision == "block":
            return f"Blocked: {message}"
        await self.events.put({
            "type": "confirmation_required", "confirm_id": confirm_id, "message": message,
            "tool": call.name, "args": call.args, "call_id": call.id,
        })
        from server.services.chat_pipeline.stage_tools import _wait_for_confirmation
        approved = await _wait_for_confirmation(confirm_id, timeout_seconds=settings.agent_confirm_timeout_s)
        await self.events.put({"type": "confirmation_resolved", "confirm_id": confirm_id, "approved": approved})
        return None if approved else "The user declined this action. Don't retry it; tell them it wasn't done."

    def _validate(self, call: ToolCall) -> ToolOutcome | None:
        if call.name == TOOL_SEARCH:
            return None
        args, error = validate_tool_args(call.name, call.args)
        if error:
            tool = get_tool(call.name)
            hint = f" Expected arguments: {json.dumps(tool.input_schema)}" if tool else ""
            return ToolOutcome(call, f"Error: {error}.{hint}", True)
        call.args = args
        if call.name in _TIMED_TOOLS:
            history = getattr(self.ctx, "history", None) or []
            turns = [m.get("content", "") for m in history if m.get("role") == "user"][-2:] + [self.ctx.user_message]
            problem = (_unstated_time(turns, call.name, args)
                       or _weekday_mismatch(self.ctx.user_message, call.name, args))
            if problem:
                return ToolOutcome(call, problem, True)
        if call.name == "use_skill":
            from server.services.skill_runtime.registry import get_search_skill, load_search_skills
            if get_search_skill(str(args.get("skill", ""))) is None:
                ids = ", ".join(s.id for s in load_search_skills())
                return ToolOutcome(call, f"Error: '{args.get('skill')}' is not a lookup skill. "
                                         f"Use one of: {ids} — or web_search for anything else.", True)
        return None

    async def _run_one(self, call: ToolCall) -> ToolOutcome:
        outcome = self._validate(call)
        if outcome is None:
            denied = await self._permitted(call)
            outcome = ToolOutcome(call, denied, True) if denied else await self._execute(call)
        self.tool_errors += int(outcome.is_error)
        if call.name in _TIMED_TOOLS and not outcome.is_error and not outcome.content.startswith("I couldn't"):
            self.saved.append(outcome.content)
            self.saved_titles.append(str(call.args.get("title") or ""))
        await self.events.put({
            "type": "tool_result", "call_id": call.id, "tool": call.name,
            "ok": not outcome.is_error, "summary": _summary(outcome.content),
        })
        return outcome

    async def run_calls(self, calls: list[ToolCall]) -> list[ToolOutcome]:
        """Consecutive read-only calls run concurrently; anything with side effects runs alone, in order."""
        outcomes: list[ToolOutcome] = []
        batch: list[ToolCall] = []

        async def flush() -> None:
            if batch:
                outcomes.extend(await asyncio.gather(*(self._run_one(c) for c in batch)))
                batch.clear()

        for call in calls:
            tool = get_tool(call.name)
            if call.name == TOOL_SEARCH or (tool and tool.read_only):
                batch.append(call)
            else:
                await flush()
                outcomes.append(await self._run_one(call))
        await flush()
        return outcomes

    # ── context budget inside the loop ────────────────────────────────────────
    def _fit_steps(self, messages: list[dict], tools: list[dict]) -> None:
        """Clip the oldest tool results to stubs when the run outgrows the window."""
        budget = settings.llm_context_window - settings.llm_max_output_tokens - estimate_tokens(json.dumps(tools))
        total = lambda: sum(estimate_tokens(str(m.get("content", ""))) + 6 for m in messages)
        for m in messages:
            if total() <= budget:
                return
            if m.get("role") == "tool" and not str(m.get("content", "")).startswith("[clipped"):
                m["content"] = f"[clipped earlier result of {m.get('tool_name')}: {_summary(m['content'], 200)}]"

    # ── the loop ──────────────────────────────────────────────────────────────
    async def run(self) -> AsyncGenerator[dict, None]:
        ctx = self.ctx
        tools = self.tool_specs()
        reserve = settings.llm_max_output_tokens + estimate_tokens(json.dumps(tools)) + 1500
        await self._condense_long_message(reserve)
        fitted = fit_context(ctx.system_prompt, self.base_messages, context_window=settings.llm_context_window,
                             max_output_tokens=reserve, summary=ctx.conversation_summary)
        messages = [{"role": "system", "content": fitted.system_prompt}] + fitted.messages
        stream_tokens = bool(ctx.voice or ctx.cli)
        final: AssistantTurn | None = None
        nudged = False

        try:
            # Requests only a tool can answer (volume, specs, a file's contents,
            # arithmetic, "forget …"): the model skipped these tools and invented
            # answers, so the calls run first and the model answers from their results.
            required = self._missing_reads()
            if required:
                logger.info("Running required reads before the model: %s", [c.name for c in required])
                async for event in self._run_reads(required, messages, step=0):
                    yield event
                self.auto_calls = len(self.tools_used)

            for step in range(1, settings.agent_max_steps + 1):
                tools = self.tool_specs()
                self._fit_steps(messages, tools)
                model = asyncio.create_task(self._model_step(messages, tools, stream_tokens))
                async for event in self._pump(model):
                    yield event
                turn = model.result()
                logger.info("Agent model step %d: %d messages, prompt %d tokens (window %d), %d tool call(s)",
                            step, len(messages), turn.prompt_tokens, settings.llm_context_window, len(turn.tool_calls))
                if turn.prompt_tokens >= settings.llm_context_window - 16:
                    logger.warning("Prompt filled the whole window; the model server may have truncated it")
                if not turn.tool_calls and not nudged and self._announces_action(turn.content):
                    # "Let me check that" with no call: the model meant to act. Tell it to.
                    nudged = True
                    logger.info("Model announced an action without a tool call; nudging it to call the tool")
                    messages += [turn.as_message(), {"role": "user", "content": _ACT_NUDGE}]
                    continue
                if not turn.tool_calls:
                    final = turn
                    break

                messages.append(turn.as_message())
                for call in turn.tool_calls:
                    self.tools_used.append(call.name)
                    logger.info("Agent step %d: %s(%s)", step, call.name, json.dumps(call.args)[:300])
                    yield {"type": "tool_call", "call_id": call.id, "tool": call.name, "args": call.args, "step": step}
                running = asyncio.create_task(self.run_calls(turn.tool_calls))
                async for event in self._pump(running):
                    yield event
                limit = settings.agent_tool_result_chars
                for outcome in running.result():
                    messages.append(tool_result_message(outcome.call, _clip(outcome.content, limit)))

            if final is None:                    # step budget spent: one last answer, no tools
                logger.info("Agent loop hit %d steps; asking for a final answer", settings.agent_max_steps)
                messages.append({"role": "user", "content": _FINAL_NUDGE})
                model = asyncio.create_task(self._model_step(messages, None, stream_tokens))
                async for event in self._pump(model):
                    yield event
                final = model.result()

            if not format_luna_response(final.content or "").strip():
                # An empty answer (e.g. everything inside <think>…</think>, which
                # is stripped) must never reach the user. Ask once more, no tools.
                logger.warning("Model gave an empty answer (raw %d chars: %r); asking again",
                               len(final.content or ""), (final.content or "")[:200])
                messages += [final.as_message(), {"role": "user", "content": _EMPTY_NUDGE}]
                model = asyncio.create_task(self._model_step(messages, None, stream_tokens))
                async for event in self._pump(model):
                    yield event
                final = model.result()
        except Exception as e:
            logger.error("Agent loop failed: %s", e, exc_info=True)
            yield {"type": "error", "message": f"The model request failed: {e}"}
            final = AssistantTurn(content=f"I couldn't finish that: the model request failed ({e}).")

        text = format_luna_response(final.content or "")
        if self.saved:
            text = _with_saved(text, self.saved, self.saved_titles)
        cards = _relevant_cards(self.cards, text)
        if cards:
            text = f"{text}\n\n{cards}" if text else cards
        ctx.full_response = text
        ctx.had_tool_call = bool(self.tools_used)
        ctx.tool_succeeded = bool(self.tools_used)
        ctx.reply_streamed = self.streamed
        ctx.tools_used = list(self.tools_used)
        ctx.tool_errors = self.tool_errors
        ctx.tool_outputs = list(self.seen.values())
        yield {"type": "agent_done", "steps": len(self.tools_used), "tools": self.tools_used}

    async def _condense_long_message(self, reserve: int) -> None:
        """A paste bigger than the room left for it would be middle-clipped by
        fit_context, dropping whatever sat in the middle. Keep its start and end
        and the middle parts most relevant to the question instead."""
        if not self.base_messages:
            return
        from server.services.files.retrieval import condense_long_text

        latest = self.base_messages[-1]
        content = str(latest.get("content", ""))
        system = estimate_tokens(self.ctx.system_prompt) + estimate_tokens(self.ctx.conversation_summary or "")
        room = settings.llm_context_window - reserve - system
        if estimate_tokens(content) <= room * 0.7:
            return
        target_chars = max(4000, int(room * 0.6) * 4)
        condensed, kept, total = await condense_long_text(content, target_chars)
        if total:
            logger.info("Long message condensed: %d -> %d chars (%d of %d middle parts kept)",
                        len(content), len(condensed), kept, total)
            self.base_messages = self.base_messages[:-1] + [{**latest, "content": condensed}]

    def _missing_reads(self) -> list[ToolCall]:
        """Calls this request needs (reads, or an explicit "forget …") that haven't run yet."""
        from server.services.tool_registry import TOOL_REGISTRY

        attached = bool(getattr(self.ctx, "attachment_ids", None))
        calls = []
        for name, args in required_calls(self.ctx.user_message):
            if name in TOOL_REGISTRY and name not in self.tools_used and not (attached and name == "workspace_read"):
                calls.append(ToolCall(id=f"call_{uuid.uuid4().hex[:12]}", name=name, args=args))
        return calls

    async def _run_reads(self, calls: list[ToolCall], messages: list[dict], step: int) -> AsyncGenerator[dict, None]:
        """Run reads on the model's behalf, shown and recorded like its own calls."""
        for call in calls:
            if call.name not in self.active:
                self.active.append(call.name)
            self.tools_used.append(call.name)
            yield {"type": "tool_call", "call_id": call.id, "tool": call.name, "args": call.args, "step": step}
        messages.append(AssistantTurn(content="", tool_calls=calls).as_message())
        running = asyncio.create_task(self.run_calls(calls))
        async for event in self._pump(running):
            yield event
        for outcome in running.result():
            messages.append(tool_result_message(outcome.call, _clip(outcome.content, settings.agent_tool_result_chars)))

    def _announces_action(self, content: str) -> bool:
        """A short reply that only promises a lookup/action, with nothing done yet."""
        # Reads the loop ran up front (grounding) don't count: "let me check"
        # right after them is still a promise, not an answer.
        if self.tools_used[self.auto_calls:] or getattr(self.ctx, "attachment_ids", None):
            return False
        from server.services.chat_pipeline.stage_tools import _promises_lookup
        return _promises_lookup(content or "", "")

    async def _model_step(self, messages: list[dict], tools: list[dict] | None, stream_tokens: bool) -> AssistantTurn:
        held: list[str] = []
        decided = {"stream": None}

        async def on_token(token: str) -> None:
            # Hold the first characters: a reply that opens with "{" or "<tool_call>"
            # is a tool call written as text, not words for the user.
            if decided["stream"] is None:
                held.append(token)
                start = "".join(held).lstrip()
                if len(start) < 12:
                    return
                decided["stream"] = not start.startswith(("{", "<tool_call>", "[{"))
                if decided["stream"]:
                    self.streamed = True
                    await self.events.put({"type": "message_part", "content": "".join(held)})
                return
            if decided["stream"]:
                await self.events.put({"type": "message_part", "content": token})

        temperature = 0.5 if self.ctx.cli else 0.6
        turn = await chat_step(messages, tools, temperature=temperature, on_token=on_token if stream_tokens else None)
        if stream_tokens and decided["stream"] is None and held and not turn.tool_calls:
            self.streamed = True
            await self.events.put({"type": "message_part", "content": "".join(held)})
        return turn

    async def _pump(self, task: asyncio.Task) -> AsyncGenerator[dict, None]:
        """Yield events (tokens, confirmations, results) while the task runs."""
        while True:
            getter = asyncio.ensure_future(self.events.get())
            done, _ = await asyncio.wait({task, getter}, return_when=asyncio.FIRST_COMPLETED)
            if getter in done:
                yield getter.result()
                continue
            getter.cancel()                      # a cancelled get() never takes an item
            break
        while not self.events.empty():
            yield self.events.get_nowait()


async def run_agent_loop(ctx, messages: list[dict]) -> AsyncGenerator[dict, None]:
    async for event in AgentLoop(ctx, messages).run():
        yield event
