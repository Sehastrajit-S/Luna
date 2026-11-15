"""Working state of a conversation, kept outside the chat history.

A coding agent survives compaction because the real state lives on disk (files,
git, the todo list) and it simply looks again. A chat assistant's state — the
decisions made, the code it wrote — lives only in the conversation, so once old
turns are summarized, "the function you wrote earlier" is gone.

This module keeps that state where it can be re-read every turn:
  - code blocks Luna writes are stored as artifacts (with their function/class names);
  - facts and decisions are appended (never rewritten) whenever the summary runs;
  - each turn gets a pinned block: the facts, an index of code artifacts, the
    full code the user is referring to, the user's earlier requests in order
    (for turns out of the window), and the attached files;
  - search_conversation finds anything in the whole conversation, including
    turns that have left the context window.
"""
from __future__ import annotations

import re
from collections import Counter

from sqlalchemy.orm import Session

from backend.models.database import Attachment, ConversationArtifact, Message

_CODE_BLOCK_RE = re.compile(r"```([\w+#.-]*)[^\n]*\n(.*?)```", re.DOTALL)
_NAME_RES = (
    re.compile(r"^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)", re.M),                       # python
    re.compile(r"^\s*class\s+([A-Za-z_]\w*)", re.M),                                   # python / js / ts / java
    re.compile(r"\bfunction\s+([A-Za-z_$][\w$]*)"),                                    # js
    re.compile(r"^\s*(?:export\s+)?(?:const|let)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\(", re.M),  # arrow fns
    re.compile(r"^\s*func\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)", re.M),                   # go
    re.compile(r"^\s*(?:pub\s+)?fn\s+([A-Za-z_]\w*)", re.M),                           # rust
    re.compile(r"^\s*CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[\"`]?(\w+)", re.M | re.I),  # sql
    re.compile(r"^\s*@(?:app|router)\.(?:get|post|put|patch|delete)\(\s*[\"']([^\"']+)", re.M),  # routes
)
_REFERS_BACK_RE = re.compile(
    r"\b(?:you\s+wrote|you\s+made|earlier|before|previous(?:ly)?|above|from\s+(?:step|turn)|the\s+(?:same|last)"
    r"|that\s+(?:function|class|code|endpoint|schema|model|module|query|script)"
    r"|the\s+(?:function|class|code|endpoint|schema|models?|encoder|module|query|script|worker|tests?)\b"
    r"|(?:update|change|refactor|fix|extend|modify|rewrite)\s+(?:it|the|that|this|our))",
    re.IGNORECASE,
)
_WORD_RE = re.compile(r"[a-z_][a-z0-9_]{2,}")
_STOP = frozenset("the and for with that this you your our was were what which how does from into have has are not".split())

MIN_CODE_LINES = 2
INDEX_LIMIT = 12
FULL_CODE_CHARS = 5000
MAX_FACTS = 30
MAX_EARLIER = 40          # older user turns listed in the pinned block
EARLIER_CHARS = 80


def _names(code: str) -> list[str]:
    found: list[str] = []
    for pattern in _NAME_RES:
        for name in pattern.findall(code):
            if name not in found:
                found.append(name)
    return found[:8]


def _turn_number(db: Session, conversation_id: int, before_message_id: int | None = None) -> int:
    q = db.query(Message).filter(Message.conversation_id == conversation_id, Message.role == "user")
    if before_message_id:
        q = q.filter(Message.id < before_message_id)
    return q.count()


def record_artifacts(db: Session, conversation_id: int, message_id: int | None, user_message: str, reply: str) -> int:
    """Store the code blocks in a reply. Returns how many were stored."""
    blocks = [(lang.lower(), code.strip("\n")) for lang, code in _CODE_BLOCK_RE.findall(reply or "")]
    blocks = [(lang, code) for lang, code in blocks if code.count("\n") + 1 >= MIN_CODE_LINES]
    if not blocks:
        return 0
    turn = _turn_number(db, conversation_id, message_id)
    title = " ".join((user_message or "").split())[:120]
    for lang, code in blocks:
        db.add(ConversationArtifact(
            conversation_id=conversation_id, message_id=message_id, turn=turn, kind="code",
            language=lang or None, names=", ".join(_names(code)) or None, title=title, content=code,
        ))
    db.commit()
    return len(blocks)


def _fact_key(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 1}


def add_session_facts(db: Session, conversation_id: int, facts: list[str]) -> int:
    """Append new facts/decisions; skip ones already recorded (append-only, never rewritten)."""
    existing = [_fact_key(a.content) for a in db.query(ConversationArtifact)
                .filter(ConversationArtifact.conversation_id == conversation_id, ConversationArtifact.kind == "fact")]
    turn = _turn_number(db, conversation_id)
    added = 0
    for fact in facts:
        key = _fact_key(fact)
        if not key or any(len(key & old) >= 0.8 * min(len(key), len(old)) for old in existing):
            continue
        db.add(ConversationArtifact(conversation_id=conversation_id, turn=turn, kind="fact", content=fact))
        existing.append(key)
        added += 1
    if added:
        db.commit()
    return added


def _words(text: str) -> set[str]:
    return {w for w in _WORD_RE.findall((text or "").lower()) if w not in _STOP}


def _artifact_score(artifact: ConversationArtifact, message: str, words: set[str]) -> float:
    names = [n.strip() for n in (artifact.names or "").split(",") if n.strip()]
    score = sum(3.0 for n in names if n.lower() in message.lower())
    score += len(words & (_words(artifact.title) | _words(artifact.names or "") | {(artifact.language or "")}))
    return score


def _earlier_requests(db: Session, conversation_id: int) -> list[str]:
    """User messages that have scrolled out of the history window, in order.

    Built straight from the stored messages (no model), so "what was the second
    thing I asked?" is a lookup — a rewritten summary kept only recent topics.
    """
    from backend.config import settings

    users = (db.query(Message.content).filter(Message.conversation_id == conversation_id, Message.role == "user")
             .order_by(Message.id).all())
    visible_turns = max(1, settings.max_conversation_history // 2)
    older = users[:-visible_turns] if len(users) > visible_turns else []
    lines = []
    for turn, (content,) in enumerate(older, start=1):
        text = " ".join((content or "").split())
        lines.append(f"- [turn {turn}] {text[:EARLIER_CHARS]}{'…' if len(text) > EARLIER_CHARS else ''}")
    if len(lines) > MAX_EARLIER:
        keep_head = MAX_EARLIER // 4
        lines = lines[:keep_head] + [f"- …{len(lines) - MAX_EARLIER} more (use search_conversation)"] + \
                lines[-(MAX_EARLIER - keep_head):]
    return lines


def session_state_block(db: Session, conversation_id: int, user_message: str) -> str:
    """The pinned "working state" section for this turn ("" when there's nothing)."""
    artifacts = (db.query(ConversationArtifact)
                 .filter(ConversationArtifact.conversation_id == conversation_id, ConversationArtifact.kind == "code")
                 .order_by(ConversationArtifact.id.desc()).limit(40).all())
    facts = (db.query(ConversationArtifact)
             .filter(ConversationArtifact.conversation_id == conversation_id, ConversationArtifact.kind == "fact")
             .order_by(ConversationArtifact.id).limit(MAX_FACTS).all())
    files = (db.query(Attachment).filter(Attachment.conversation_id == conversation_id, Attachment.status == "ready")
             .order_by(Attachment.created_at).all())
    if not artifacts and not files and not facts and not _earlier_requests(db, conversation_id):
        return ""

    lines = ["## Working state of this conversation (kept outside the chat, always current)"]
    if facts:
        lines.append("Facts and decisions so far (stay consistent with these unless the user changes them):")
        lines.extend(f"- {f.content}" for f in facts)
    if artifacts:
        lines.append("Code you wrote earlier in this chat (newest first):")
        for a in artifacts[:INDEX_LIMIT]:
            what = a.names or "snippet"
            lines.append(f"- [turn {a.turn}] {a.language or 'code'}: {what} — for \"{(a.title or '')[:70]}\"")
        if len(artifacts) > INDEX_LIMIT:
            lines.append(f"- …and {len(artifacts) - INDEX_LIMIT} older snippets (find them with search_conversation).")

        words = _words(user_message)
        ranked = sorted(artifacts, key=lambda a: (-_artifact_score(a, user_message, words), -a.id))
        refers_back = bool(_REFERS_BACK_RE.search(user_message or ""))
        wanted = [a for a in ranked if _artifact_score(a, user_message, words) >= 3]
        if not wanted and refers_back:
            wanted = ranked[:1] if _artifact_score(ranked[0], user_message, words) > 0 else artifacts[:1]
        shown, used = [], 0
        for a in wanted[:3]:
            if used + len(a.content) > FULL_CODE_CHARS and shown:
                break
            shown.append(a)
            used += len(a.content)
        if shown:
            lines.append("\nThe code the user is referring to (reuse its names and structure; don't reinvent it):")
            for a in shown:
                lines.append(f"[turn {a.turn}] {a.names or a.language or 'code'}\n```{a.language or ''}\n"
                             f"{a.content[:FULL_CODE_CHARS]}\n```")
    earlier = _earlier_requests(db, conversation_id)
    if earlier:
        lines.append("Earlier in this chat, before the messages you can see (turn: what the user asked):")
        lines.extend(earlier)
    if files:
        lines.append("Files attached in this chat: " + ", ".join(f.filename for f in files[:10]))
    lines.append("Anything older that isn't shown here or in the summary: call search_conversation before answering "
                 "from memory.")
    return "\n".join(lines)


def search_conversation(db: Session, conversation_id: int, query: str, limit: int = 5) -> str:
    """Best-matching earlier messages and code in this conversation, with turn numbers."""
    words = _words(query)
    if not words:
        return "Give search_conversation a few keywords (names, topics, numbers)."
    messages = (db.query(Message).filter(Message.conversation_id == conversation_id)
                .order_by(Message.id).all())
    turn, scored = 0, []
    for m in messages:
        if m.role == "user":
            turn += 1
        text = m.content or ""
        low = text.lower()
        counts = Counter(w for w in _WORD_RE.findall(low) if w in words)
        if not counts:
            continue
        score = len(counts) * 2 + min(sum(counts.values()), 10) * 0.2
        scored.append((score, turn, m.role, text))
    if not scored:
        return f"Nothing in this conversation matches: {query}"
    scored.sort(key=lambda s: -s[0])
    out = []
    for score, turn, role, text in scored[:limit]:
        low = text.lower()
        first = min((low.find(w) for w in words if low.find(w) >= 0), default=0)
        start = max(0, first - 250)
        excerpt = text[start:start + 900].strip()
        who = "User" if role == "user" else "Luna"
        out.append(f"[turn {turn}, {who}] {'…' if start else ''}{excerpt}{'…' if start + 900 < len(text) else ''}")
    return "\n\n".join(out)
