"""Response formatting utilities — text shaping, reference extraction, command stripping."""
import re

_CMD_RE = r"\[(?:LAUNCH|TASK|EVENT|SPOTIFY|BROWSE|MAP|WIDGET):[^\]]+\]"
_CARDS_COMMENT_RE = re.compile(r"\s*<!--luna-cards:.*?-->", re.DOTALL)


def strip_cards(text: str) -> str:
    """Remove embedded result cards for surfaces that only show text (CLI, voice, chat bridges)."""
    return _CARDS_COMMENT_RE.sub("", text or "")


def format_luna_response(response: str) -> str:
    """Split casual Luna replies into small chat chunks. Commands are always preserved.

    This only re-flows text — it never drops content. It used to keep just the
    first two paragraphs, which silently cut long answers (a full review arrived
    as its one-line intro). Reply length belongs in the prompt.
    """
    text = response.strip()
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    # No ellipses in Luna's prose, but code keeps its "..." (Depends(...), stubs).
    text = re.sub(r"(```.*?(?:```|$))|\.{3,}", lambda m: m.group(1) or "", text, flags=re.DOTALL).strip()

    commands = re.findall(_CMD_RE, text)
    visible = re.sub(r"\s*" + _CMD_RE, "", text).strip()

    def _reattach(formatted_visible: str) -> str:
        if commands:
            return f"{formatted_visible}\n{' '.join(commands)}"
        return formatted_visible

    if not visible or "\n\n" in visible:
        return _reattach(visible)
    if "```" in visible or re.search(r"^\s*[-*]\s+", visible, re.MULTILINE):
        return _reattach(visible)

    sentences = re.split(r"(?<=[.!?])\s+", visible)
    sentences = [s.strip() for s in sentences if s.strip()]
    if len(sentences) == 2 and len(sentences[0].split()) <= 4:
        return _reattach("\n\n".join(sentences))
    if len(sentences) >= 3 and len(sentences[0].split()) <= 4:
        return _reattach(f"{sentences[0]}\n\n{' '.join(sentences[1:])}")
    if len(visible.split()) <= 22:
        return _reattach(visible)

    chunks: list[str] = []
    current: list[str] = []
    current_words = 0
    for sentence in sentences:
        words = len(sentence.split())
        if current and current_words + words > 12:
            chunks.append(" ".join(current).strip())
            current = [sentence]
            current_words = words
        else:
            current.append(sentence)
            current_words += words
    if current:
        chunks.append(" ".join(current).strip())

    if len(chunks) <= 1:
        return _reattach(visible)
    return _reattach("\n\n".join(chunks))


def _extract_references_section(text: str) -> str:
    match = re.search(r"References:\s*(.*)$", text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        source = re.search(r"Source:\s*(https?://\S+)", text)
        return f"References:\n[1] {source.group(1)}" if source else ""
    refs = []
    for line in match.group(1).splitlines():
        clean = line.strip()
        if re.match(r"^\[\d+\]\s+.+https?://", clean):
            refs.append(clean)
    return "References:\n" + "\n".join(refs[:6]) if refs else ""


def _strip_reference_noise(answer: str) -> str:
    """Remove malformed inline source lists before adding canonical references."""
    if not answer:
        return answer
    match = re.search(r"\bReferences:\s*", answer, flags=re.IGNORECASE)
    head = answer[:match.start()] if match else answer

    clean_lines = []
    for line in head.splitlines():
        clean = line.strip()
        if re.match(r"^\d+\.\s+\[.+?\]\(https?://", clean):
            continue
        if re.match(r"^\d+\.\s+\[.+?\]\s*$", clean):
            continue
        if re.match(r"^\[\d+\]\s+.+https?://", clean):
            continue
        if re.match(r"^\d+\.\s+.+https?://", clean):
            continue
        clean_lines.append(line)
    text = "\n".join(clean_lines)
    text = re.sub(r"\s*\(https?://[^)\s]+\)", "", text)
    text = re.sub(r"\s+[A-Z][^\n.]{8,140}\s+-\s+https?://\S+\s*$", "", text)
    return text.strip()


_REF_LINE_RE = re.compile(r"^\[(\d+)\]\s+.*?\s-\s(https?://\S+)\s*$", re.MULTILINE)


def link_citations(answer: str, tool_result: str) -> str:
    """Turn bare [n] citations in the answer body into clickable links to
    source n from the search results, so every item is one click from its page."""
    urls = {n: url for n, url in _REF_LINE_RE.findall(tool_result or "")}
    if not urls or not answer:
        return answer
    split = re.search(r"\n\s*References:\s*", answer, flags=re.IGNORECASE)
    body, tail = (answer[:split.start()], answer[split.start():]) if split else (answer, "")

    def repl(match: re.Match) -> str:
        url = urls.get(match.group(1))
        return f"[{match.group(1)}]({url})" if url else match.group(0)

    # Skip [n] that is already a markdown link label: "[3](...)" or "[text][3]".
    body = re.sub(r"(?<!\])\[(\d{1,2})\](?!\()", repl, body)
    return body + tail


_RESULT_ENTRY_RE = re.compile(r"^\[(\d+)\] (.+?)\nSnippet: (.*?)\nURL: (\S+)", re.MULTILINE | re.DOTALL)
_WORD_RE = re.compile(r"[a-z0-9+#]{2,}")
_STOP = {"the", "at", "and", "for", "of", "in", "to", "a", "an", "with", "on", "by", "from", "is", "are"}


def _words(text: str) -> set[str]:
    return {w for w in _WORD_RE.findall(text.lower()) if w not in _STOP}


def attach_result_links(answer: str, tool_result: str, min_overlap: float = 0.6) -> str:
    """Give "[Item name — Source]" (a label the model wrote without its URL)
    the link of the search result whose title matches it."""
    entries = [(title, snippet, url) for _n, title, snippet, url in _RESULT_ENTRY_RE.findall(tool_result or "")]
    if not entries or not answer:
        return answer
    split = re.search(r"\n\s*References:\s*", answer, flags=re.IGNORECASE)
    body, tail = (answer[:split.start()], answer[split.start():]) if split else (answer, "")
    candidates = [(_words(title), _words(title + " " + snippet), url) for title, snippet, url in entries]

    def best_match(text: str) -> tuple[str | None, float]:
        want = _words(text)
        if len(want) < 2:
            return None, 0.0
        best_url, best = None, 0.0
        for title_words, all_words, url in candidates:
            # Title words weigh most; the snippet usually carries the source/organisation.
            score = (len(want & title_words) + 0.5 * len((want & all_words) - title_words)) / len(want)
            if score > best:
                best_url, best = url, score
        return best_url, best

    def repl(match: re.Match) -> str:
        label = match.group(1)
        if len(_words(label)) < 2:
            return match.group(0)
        url, score = best_match(label)
        # No convincing match → plain text; never a guessed link.
        return f"[{label}]({url})" if url and score >= min_overlap else label

    body = re.sub(r"(?<![\]\w])\[([^\[\]\n]{6,120})\](?![(\[])", repl, body)

    # Items the model titled in bold, or tagged with a placeholder like
    # "[Paper]" / "[Link]", but left without a URL: link them to the result
    # whose title clearly matches the item's own title.
    lines = body.split("\n")
    for i, line in enumerate(lines):
        if "](http" in line:
            continue
        title = re.search(r"\*\*([^*\n]{6,160})\*\*", line)
        context = title.group(1) if title else (lines[i - 1] if i else "")
        placeholder = re.search(r"(?<![\]\w])\[(paper|link|source|website|article|here|page|view|details)\](?!\()",
                                line, re.IGNORECASE)
        if placeholder:
            # The item's title line may already carry its link — reuse it.
            linked = re.search(r"\]\((https?://[^\s)]+)\)", context)
            url, score = (linked.group(1), 1.0) if linked else best_match(re.sub(r"\(https?://[^)]*\)", "", context))
            if url and score >= min_overlap:
                lines[i] = line[:placeholder.start()] + f"[{placeholder.group(1)}]({url})" + line[placeholder.end():]
            continue
        nearby_linked = any("](http" in l for l in lines[i + 1:i + 3] if not re.match(r"^\s*(?:[-*•]|\d+[.)]|#)", l))
        if title and not nearby_linked and re.match(r"^\s*(?:[-*•]|\d+[.)]|#{1,6})?\s*\*\*", line):
            url, score = best_match(title.group(1))
            if url and score >= 0.75:
                lines[i] = line.replace(title.group(0), f"**[{title.group(1)}]({url})**", 1)
    return "\n".join(lines) + tail


_ITEM_START_RE = re.compile(r"^\s*(?:[-*•]|\d+[.)]|#{2,6})\s+")
_MD_URL_RE = re.compile(r"\]\((https?://[^\s)]+)\)")


def dedupe_linked_items(answer: str) -> str:
    """Drop list items/sections that link to a URL an earlier item already used
    (the model often lists one result three times under reworded titles)."""
    split = re.search(r"\n\s*References:\s*", answer or "", flags=re.IGNORECASE)
    body, tail = (answer[:split.start()], answer[split.start():]) if split else (answer or "", "")
    lines = body.split("\n")
    items: list[list[str]] = [[]]
    for line in lines:
        if _ITEM_START_RE.match(line) and items[-1]:
            items.append([])
        items[-1].append(line)
    seen: set[str] = set()
    kept: list[str] = []
    for item in items:
        if not _ITEM_START_RE.match(item[0]) or item[0].lstrip().startswith("#"):
            kept.extend(item)
            continue
        first_url = next((m.group(1) for line in item[:2] for m in [_MD_URL_RE.search(line)] if m), None)
        bold = re.search(r"\*\*\[?([^*\]\n]{4,160})", item[0])
        keys = set()
        if first_url:
            keys.add(first_url.split("?")[0].rstrip("/").lower())
        if bold:
            keys.add("title:" + " ".join(re.findall(r"[a-z0-9]+", bold.group(1).lower())))
        if keys & seen:
            continue
        seen |= keys
        kept.extend(item)
    return "\n".join(kept) + tail


def ensure_references(answer: str, tool_result: str) -> str:
    answer_refs = _extract_references_section(answer)
    clean_answer = _strip_reference_noise(answer)
    if answer_refs:
        return clean_answer.rstrip() + "\n\n" + answer_refs.strip()
    refs = _extract_references_section(tool_result)
    if not refs:
        return clean_answer or answer
    return clean_answer.rstrip() + "\n\n" + refs.strip()
