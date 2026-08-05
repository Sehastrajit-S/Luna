"""LLM-based tool result summarisation for chat pipeline."""


async def verify_tool_result(tool_name: str, args: dict, result: str, user_message: str = "") -> str:
    """Ask the LLM to produce a natural-language summary of the tool result."""
    from backend.services.llm import ollama
    from backend.services.response_formatter import ensure_references

    if tool_name in ("web_search", "web_research", "web_fetch", "browser_read"):
        query_hint = user_message or args.get("query") or args.get("url", "")
        prompt = (
            f"The user asked: {query_hint}\n\n"
            f"Web results:\n{result}\n\n"
            "Answer the user's question thoroughly. Rules:\n"
            "- Use bullet points or numbered lists when there are multiple items\n"
            "- Include specific names, dates, numbers — no vague generalities\n"
            "- Do NOT say 'according to' or 'based on' — just answer directly\n"
            "- For news queries: list each story with a one-sentence summary\n"
            "- For comparison/explanation queries: give a clear structured answer\n"
            "- End with a References section preserving ALL numbered source URLs from the results\n"
            "- If results are empty or unhelpful, say so and suggest rephrasing"
        )
        full = ""
        async for token in ollama.stream_chat(
            [{"role": "user", "content": prompt}],
            "You are Luna, a sharp personal AI. Write well-structured markdown. Be specific and complete.",
        ):
            full += token
        return ensure_references(full.strip(), result)[:5000]

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
