"""LLM-based tool result summarisation for chat pipeline."""
from datetime import datetime


async def verify_tool_result(tool_name: str, args: dict, result: str, user_message: str = "",
                             context: str = "", guidelines: str = "") -> str:
    """Ask the LLM to produce a natural-language summary of the tool result.

    context: what the user already shared (recent turns, attached documents) —
    needed for follow-ups like "links for these" or "which fits me best".
    guidelines: the matching skill's answer instructions (skills/<id>/SKILL.md).
    """
    from backend.services.llm import ollama
    from backend.services.response_formatter import ensure_references

    if tool_name in ("web_search", "web_research", "web_fetch", "browser_read"):
        query_hint = user_message or args.get("query") or args.get("url", "")
        # Follow-ups ("I mean the new one") only make sense with the resolved query.
        searched = args.get("queries") or ([args["query"]] if args.get("query") else [])
        if user_message and searched and "; ".join(searched).strip().lower() != user_message.strip().lower():
            query_hint = f"{user_message}\n(Searched for: {'; '.join(searched)})"
        # This call does not see the main system prompt, so without the clock it
        # trusts whatever date a web page mentions ("today is Thursday").
        now = datetime.now()
        context_block = f"What the user has already shared (use it to tailor the answer):\n{context}\n\n" if context else ""
        if guidelines:
            # Use-case specifics come from the skill, never from this file.
            context_block += f"How to answer this kind of request:\n{guidelines[:2500]}\n\n"
        prompt = (
            f"Current local date and time: {now:%A, %B} {now.day}, {now.year}, {now:%I:%M %p}. "
            "Treat this as ground truth; never take today's date or day from the web results.\n\n"
            f"{context_block}"
            f"The user asked: {query_hint}\n\n"
            f"Web results:\n{result}\n\n"
            "Answer the user's question thoroughly. Rules:\n"
            "- Use bullet points or numbered lists when there are multiple items\n"
            "- Include specific names, dates, numbers — no vague generalities\n"
            "- Do NOT say 'according to' or 'based on' — just answer directly\n"
            "- For news queries: list each story with a one-sentence summary\n"
            "- For comparison/explanation queries: give a clear structured answer\n"
            "- LINKS: only use URLs that appear in the web results above, copied exactly. Never invent, guess or "
            "shorten a URL. Put each item's link next to it as a markdown link: **[Item name](URL)**\n"
            "- One entry per result: never list the same link twice. Skip results that don't match what was "
            "asked for (e.g. generic search or listing pages when the user wants specific items)\n"
            "- If an item the user asked about has no matching result, say you couldn't find a link for it "
            "instead of substituting a different page\n"
            "- When the user asks for a judgment (fit, ranking, recommendation), base it on what they shared and "
            "the specific result, and say briefly why\n"
            "- End with a References section preserving ALL numbered source URLs from the results\n"
            "- If results are empty or unhelpful, say so and suggest rephrasing\n"
            "- Talk to the user directly (\"you\", \"your\"). Never narrate them in the third person (\"The user is "
            "asking…\") and don't title the answer after the task (\"# Product Search: …\"); start with the answer"
        )
        full = ""
        async for token in ollama.stream_chat(
            [{"role": "user", "content": prompt}],
            "You are Luna, a sharp personal AI. Write well-structured markdown. Be specific and complete.",
        ):
            full += token
        return ensure_references(full.strip(), result)[:9000]

    if tool_name == "dataset_search":
        query_hint = user_message or args.get("query", "")
        prompt = (
            f"The user is looking for datasets on: {query_hint}\n\n"
            f"Dataset search results (from Kaggle, UCI, Hugging Face, data.gov, NOAA, World Bank):\n{result}\n\n"
            "Present the best datasets found. For each one include:\n"
            "- **Dataset name** — source (e.g. Kaggle, UCI)\n"
            "- One-sentence description\n"
            "- Direct URL\n\n"
            "Group by source. Skip sources with no useful results. "
            "Be specific — use the exact dataset names and URLs from the results above. "
            "End with a short recommendation on which dataset best fits the user's need."
        )
        full = ""
        async for token in ollama.stream_chat(
            [{"role": "user", "content": prompt}],
            "You are Luna. Present search results as a clean, actionable list. Use markdown.",
        ):
            full += token
        return full.strip()[:5000]

    if tool_name in ("github_list_repos", "github_list_issues", "github_list_prs", "github_get_pr", "github_summarize_user_pr"):
        if result.startswith("GitHub error:"):
            return result
        prompt = (
            f"Tool '{tool_name}' returned:\n{result}\n\n"
            f"User asked: {user_message}\n\n"
            "Present this GitHub data in a clean, readable markdown list. Include repo/issue/PR names, numbers, status, changed files, and URLs when present."
        )
        full = ""
        async for token in ollama.stream_chat(
            [{"role": "user", "content": prompt}],
            "You are Luna. Format GitHub data clearly.",
        ):
            full += token
        return full.strip()[:3000]

    if tool_name in ("get_system_info", "get_volume", "get_brightness", "get_clipboard"):
        prompt = (
            f"Tool '{tool_name}' returned: {result}\n"
            f"User asked: {user_message}\n"
            "Report this information naturally in 1-2 sentences."
        )
        full = ""
        async for token in ollama.stream_chat(
            [{"role": "user", "content": prompt}], "You are Luna. Be brief."
        ):
            full += token
        return full.strip().split("\n")[0][:200]

    prompt = (
        f"Tool '{tool_name}' result: {result[:300]}. "
        "One short sentence confirming what happened, as Luna. No preamble."
    )
    full = ""
    async for token in ollama.stream_chat([{"role": "user", "content": prompt}], "You are Luna. Be brief."):
        full += token
    return full.strip().split("\n")[0][:120]
