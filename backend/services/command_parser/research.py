"""Research and dataset query extraction."""
import re


RESEARCH_COMMAND = "/research"

_RESEARCH_COMMAND_RE = re.compile(r"^\s*/research(?:\s+on\b)?(?:\s+|$)", re.IGNORECASE)


def extract_direct_research_query(message: str) -> str | None:
    """Return a query only when the user explicitly runs `/research <query>`.

    Research is opt-in: keyword heuristics ("latest", "sources", "compare")
    used to fire it on ordinary questions, so plain chat never triggers it.
    """
    text = (message or "").strip()
    match = _RESEARCH_COMMAND_RE.match(text)
    if not match:
        return None
    text = text[match.end():].strip()
    if not text:
        return None

    query = re.sub(
        r"^\s*(please\s+)?(can you\s+|could you\s+|would you\s+)?"
        r"(research|investigate|look up|search for|find out about|find out|tell me about|"
        r"show me|give me)\b\s*(?:on\s+)?(?:the\s+)?(?:latest\s+|current\s+|recent\s+)?",
        "", text, flags=re.IGNORECASE,
    )
    query = re.sub(
        r"\b(and\s+)?(include|show|add|give|provide|cite|citing|with)\s+(the\s+)?"
        r"(citations?|citings?|sitations?|references?|sources?)\b.*$",
        "", query, flags=re.IGNORECASE,
    )
    query = query.strip(" .?!:;-")
    if len(query) < 3:
        query = text
    return query


_WEB_SEARCH_TRIGGER_RE = re.compile(
    r"\b(?:do\s+a\s+|run\s+a\s+)?web[\s-]?search(?:\s+for)?"
    r"|\bsearch\s+(?:the\s+)?(?:web|internet|online)(?:\s+for)?"
    r"|\b(?:look|check)\s+(?:it|this|that)?\s*up\s+online"
    r"|\bgoogle\s+(?:it|this|that|for)\b",
    re.IGNORECASE,
)


# Generic "go look this up" phrasing only. What a request is *about* (jobs,
# papers, products…) is decided by the skills' own intents in skills/*/skill.json.
_SEARCH_REQUEST_RE = re.compile(
    # "can you search and find me …", "search for …"
    r"^\s*(?:hey\s+|please\s+)?(?:can|could|would|will)\s+you\s+(?:please\s+)?(?:search|look\s+up)\b"
    r"|^\s*(?:please\s+)?(?:search|look\s+up)\s+(?:for\s+|and\s+)?\w"
    # "find me …", "ok great, look for …" — something out in the world, not the user's own files
    r"|^\s*(?:(?:ok(?:ay)?|great|cool|so|and|now|also|then|alright|hey|please|pls|can|could|would|will)[\s,]+)*"
    r"(?:you\s+)?(?:find|look\s+for|hunt\s+down|track\s+down)\s+(?:me\s+)?\w"
    # "give me links for these", "links to those", "where can I buy"
    r"|\b(?:give|send|show|share|get|find)\s+(?:me\s+)?(?:the\s+|some\s+)?(?:links?|urls?|sources?)\b"
    r"|\blinks?\s+(?:for|to)\s+(?:these|those|them|this|that|each|it|all)\b"
    r"|\bwhere\s+(?:can|do)\s+i\s+(?:find|get|buy|download|sign\s+up|apply)\b",
    re.IGNORECASE,
)
# Searching the user's own data or an attached file is not a web search.
_NOT_WEB_RE = re.compile(
    r"\b(?:my\s+)?(?:inbox|e-?mails?|gmail|outlook|calendar|drive|onedrive|contacts)\b"
    r"|\b(?:this|that|my|in\s+this|in\s+my|the\s+attached)\s+(?:pdf|file|doc(?:ument)?|attachment|"
    r"spreadsheet|sheet|deck|slides?|notes?|image|screenshot|photo|paper|article|report|contract|essay)\b"
    # "the pdf" is the user's file; "the paper that introduced X" may well be a lookup.
    r"|\b(?:in\s+)?the\s+(?:pdf|file|doc(?:ument)?|attachment|spreadsheet|sheet|deck|slides?|image|screenshot|photo)\b",
    re.IGNORECASE,
)


def refers_to_own_content(message: str) -> bool:
    """True when the message is about the user's own files or data ("this
    paper", "my inbox") rather than something to look up on the web."""
    return bool(_NOT_WEB_RE.search(message or ""))


def is_explicit_web_search_request(message: str) -> bool:
    """True for "web search …", "search the web for it", "google that", etc."""
    text = (message or "").strip()
    return bool(text) and not text.startswith("/") and bool(_WEB_SEARCH_TRIGGER_RE.search(text))


def is_search_request(message: str) -> bool:
    """Explicit web-search phrasing ("search for…", "find me…", "give me links
    for these", "where can I buy…"). Domain-specific triggers live in skills."""
    text = (message or "").strip()
    if not text or text.startswith("/"):
        return False
    if is_explicit_web_search_request(text):
        return True
    return bool(_SEARCH_REQUEST_RE.search(text)) and not _NOT_WEB_RE.search(text)


def extract_explicit_web_search_query(message: str) -> str | None:
    """Return a query when the user explicitly asks for a web search.

    Small local models often *say* they'll search and then emit nothing (or a
    made-up widget), so an explicit request runs the search directly.
    """
    text = (message or "").strip()
    if not text or text.startswith("/"):
        return None
    match = _WEB_SEARCH_TRIGGER_RE.search(text)
    if not match:
        return None

    query = (text[:match.start()] + " " + text[match.end():]).strip()
    query = re.sub(
        r"^\s*(?:hey\s+|luna,?\s+)?(?:please\s+)?(?:can|could|would|will)\s+you\s+(?:please\s+)?",
        "", query, flags=re.IGNORECASE,
    )
    query = re.sub(
        r"^\s*(?:and\s+)?(?:(?:find|tell|show|get)\s+(?:me\s+)?(?:out\s+)?(?:about\s+)?|for\s+|about\s+|on\s+)",
        "", query, flags=re.IGNORECASE,
    )
    query = re.sub(r"\s+(?:please|for me)\s*[.?!]*$", "", query, flags=re.IGNORECASE)
    query = re.sub(r"\s{2,}", " ", query).strip(" .?!:;,-")
    return query if len(query) >= 3 else None


def extract_direct_dataset_query(message: str) -> str | None:
    """Return a query when the user is asking for a dataset or data file."""
    text = (message or "").strip()
    if not text:
        return None
    match = re.search(
        r"\b(find|get|download|fetch|locate|give me|search for)\b.{0,60}"
        r"\b(dataset|data\s*set|data\s*file|training data|csv|parquet|data\s*for)\b",
        text, flags=re.IGNORECASE,
    )
    if not match:
        return None
    query = re.sub(
        r"^\s*(please\s+)?(can you\s+|could you\s+)?"
        r"(find|get|download|fetch|locate|give me|search for)\s+(me\s+)?(?:a\s+|an\s+|the\s+)?",
        "", text, flags=re.IGNORECASE,
    ).strip(" .?!:;-")
    return query if len(query) >= 3 else text
