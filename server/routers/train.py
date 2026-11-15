"""
RLHF training endpoint.
Generates multiple response/emotion alternatives for a user message
and stores human preference pairs for future fine-tuning.
"""
import json
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.config import DATA_DIR, settings
from backend.models.database import get_db
from backend.services.memory_manager import MemoryManager
from backend.services.personality import PersonalityEngine
from backend.services.activity_tracker import ActivityTracker
from backend.services.media_context import get_watching_context

router = APIRouter(prefix="/api/train", tags=["train"])

PAIRS_FILE = DATA_DIR / "rlhf_pairs.json"

_RESPONSE_SYSTEM = """You are generating training data for Luna, a personal AI companion.
Given a user message, write exactly 3 short response alternatives Luna might give.
Label them strictly as:
A: <response>
B: <response>
C: <response>

Rules:
- Each response must feel natural and distinctly different in approach (e.g. direct vs curious vs warm).
- Stay in Luna's voice: no assistant-speak, no emojis, no ellipses, max 2 sentences each.
- No extra explanation outside the labels.
"""

_EMOTION_SYSTEM = """You are generating emotion-tone training data for Luna, a personal AI companion.
Given a user message, write exactly 3 responses with distinctly different emotional tones.
Label them strictly as:
A: <response>  (warm / empathetic tone)
B: <response>  (direct / practical tone)
C: <response>  (casual / light tone)

Rules:
- Focus on the emotional energy of the reply, not just the content.
- Stay in Luna's voice: no assistant-speak, no emojis, no ellipses, max 2 sentences each.
- No extra explanation outside the labels.
"""


def _load_pairs() -> list:
    if PAIRS_FILE.exists():
        try:
            return json.loads(PAIRS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def _save_pairs(pairs: list):
    PAIRS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PAIRS_FILE.write_text(json.dumps(pairs, indent=2, ensure_ascii=False), encoding="utf-8")


def _parse_options(text: str) -> list[str]:
    """Extract A/B/C labelled options from LLM output."""
    options = []
    for label in ("A:", "B:", "C:"):
        idx = text.find(label)
        if idx == -1:
            continue
        start = idx + len(label)
        # Find next label or end of string
        next_idx = len(text)
        for other in ("A:", "B:", "C:"):
            if other == label:
                continue
            oi = text.find(other, start)
            if oi != -1 and oi < next_idx:
                next_idx = oi
        options.append(text[start:next_idx].strip())
    return options


async def _call_ollama(system: str, user: str) -> str:
    from backend.services.llm import ollama
    return await ollama.complete(user, system=system, temperature=0.7)


@router.post("/chat")
async def training_chat(body: dict, db: Session = Depends(get_db)):
    """
    Generate 3 response alternatives for one turn of a training conversation.
    Uses the full Luna system prompt (same memory, commands, personality) so
    every feature can be trained — Spotify, maps, tasks, etc.
    """
    import asyncio
    from backend.services.prompt_builder import build_system_prompt
    from backend.services.spotify import spotify_service

    history: list[dict] = body.get("history", [])
    message = (body.get("message") or "").strip()
    if not message:
        return {"options": []}

    memory = MemoryManager(db)
    personality = PersonalityEngine(db)
    activity_tracker = ActivityTracker(db)

    try:
        relevant_memories = await memory.retrieve_relevant(message)
    except Exception:
        relevant_memories = {"short_term": [], "long_term": []}

    recent_context = ""
    watching_context = get_watching_context().as_prompt_text()
    spotify_track = spotify_service.get_current()

    base_prompt = build_system_prompt(
        memory, personality, activity_tracker, relevant_memories,
        settings.user_name, recent_context, watching_context, spotify_track,
    )

    # Append RLHF output format instruction
    system = (
        base_prompt
        + "\n\n---\n"
        "For this training session, output your response in EXACTLY this format:\n"
        "RESPONSE: <your reply here, include any bracket commands inline as you normally would>\n"
        "LUNA_TONE: <one word from: warm/direct/curious/playful/concerned/casual/neutral>\n"
        "USER_STATE: <one word from: happy/sad/stressed/excited/bored/neutral/tired/anxious/frustrated>"
    )

    messages = [{"role": "system", "content": system}]
    messages += history
    messages.append({"role": "user", "content": message})

    def _parse_labeled(raw: str) -> dict:
        response = luna_tone = user_state = ""
        for line in raw.splitlines():
            if line.startswith("RESPONSE:"):
                response = line[len("RESPONSE:"):].strip()
            elif line.startswith("LUNA_TONE:"):
                luna_tone = line[len("LUNA_TONE:"):].strip().lower()
            elif line.startswith("USER_STATE:"):
                user_state = line[len("USER_STATE:"):].strip().lower()
        if not response:
            response = raw.strip()
        return {"response": response, "luna_tone": luna_tone or "neutral", "user_state": user_state or "neutral"}

    async def call(temperature: float) -> dict:
        from backend.services.llm import ollama
        raw = await ollama.complete(
            messages[-1]["content"],
            system="\n\n".join(m["content"] for m in messages[:-1]),
            temperature=temperature,
        )
        return _parse_labeled(raw)

    try:
        results = await asyncio.gather(
            call(0.6), call(0.85), call(1.05), return_exceptions=True
        )
        options = [r for r in results if isinstance(r, dict)]
        return {"options": options[:3]}
    except Exception as e:
        return {"options": [], "error": str(e)}


@router.post("/regenerate")
async def regenerate(body: dict):
    """Generate 2 alternative responses given the original user message + Luna's current reply."""
    message = (body.get("message") or "").strip()
    current = (body.get("current") or "").strip()
    if not message:
        return {"options": []}
    system = (
        "You are generating alternative responses for Luna, a personal AI companion.\n"
        "Given the user message and Luna's current response, write exactly 3 alternative responses "
        "that take meaningfully different approaches or tones.\n"
        "Label them strictly as:\n"
        "A: <response>\n"
        "B: <response>\n"
        "C: <response>\n\n"
        "Rules: Stay in Luna's voice — no assistant-speak, no emojis, no ellipses, max 2 sentences each. "
        "No extra explanation outside the labels."
    )
    user_text = f'User: "{message}"\nCurrent response: "{current}"\n\nWrite 3 alternatives:'
    try:
        raw = await _call_ollama(system, user_text)
        options = _parse_options(raw)[:3]
        return {"options": options}
    except Exception as e:
        return {"options": [], "error": str(e)}


@router.post("/generate")
async def generate_options(body: dict):
    message = (body.get("message") or "").strip()
    mode = body.get("mode", "response")  # "response" | "emotion"
    if not message:
        return {"options": []}
    system = _EMOTION_SYSTEM if mode == "emotion" else _RESPONSE_SYSTEM
    try:
        raw = await _call_ollama(system, message)
        options = _parse_options(raw)
        if len(options) < 2:
            # Fallback: split by newline if labels not found
            options = [line.strip() for line in raw.splitlines() if line.strip()][:3]
        return {"options": options[:3], "raw": raw}
    except Exception as e:
        return {"options": [], "error": str(e)}


def _clean_response(text: str) -> str:
    """Strip any raw LUNA_TONE/USER_STATE label noise that leaked into saved text."""
    import re as _re
    text = _re.sub(r'\s*\n?\s*LUNA_TONE:.*', '', text, flags=_re.IGNORECASE)
    text = _re.sub(r'\s*\n?\s*USER_STATE:.*', '', text, flags=_re.IGNORECASE)
    return text.strip()


@router.post("/save")
def save_preference(body: dict):
    message = body.get("message", "")
    chosen = body.get("chosen", "")
    rejected = body.get("rejected", [])
    mode = body.get("mode", "response")
    luna_tone = body.get("luna_tone", "")
    user_state = body.get("user_state", "")
    if not message or not chosen:
        return {"ok": False, "reason": "missing fields"}
    pairs = _load_pairs()
    entry: dict = {
        "id": len(pairs) + 1,
        "timestamp": datetime.utcnow().isoformat(),
        "mode": mode,
        "message": message,
        "chosen": _clean_response(chosen),
        "rejected": [_clean_response(r) for r in rejected if isinstance(r, str)],
    }
    if luna_tone:
        entry["luna_tone"] = luna_tone
    if user_state:
        entry["user_state"] = user_state
    pairs.append(entry)
    _save_pairs(pairs)
    return {"ok": True, "total": len(pairs)}


@router.get("/pairs")
def get_pairs(mode: str = None):
    pairs = _load_pairs()
    if mode:
        pairs = [p for p in pairs if p.get("mode") == mode]
    return {"pairs": pairs, "total": len(pairs)}


@router.post("/test-extraction")
async def test_extraction(body: dict):
    """Run the fact extractor on a conversation snippet and return what it would store."""
    from backend.services.fact_extractor import EXTRACTION_SYSTEM, _build_extraction_examples
    conversation = (body.get("conversation") or "").strip()
    if not conversation:
        return {"result": "[]"}
    system = EXTRACTION_SYSTEM.replace("{_extraction_examples}", _build_extraction_examples())
    try:
        raw = await _call_ollama(system, f"Extract facts from this conversation:\n\n{conversation}")
        import re
        m = re.search(r"\[.*\]", raw, re.DOTALL)
        return {"result": m.group() if m else "[]", "raw": raw}
    except Exception as e:
        return {"result": "[]", "error": str(e)}


@router.post("/save-extraction")
def save_extraction_pair(body: dict):
    """Save a fact extraction RLHF pair."""
    conversation = (body.get("conversation") or "").strip()
    chosen = (body.get("chosen") or "[]").strip()
    rejected = body.get("rejected") or []
    note = (body.get("note") or "").strip()
    if not conversation or not chosen:
        return {"ok": False, "error": "conversation and chosen required"}
    pairs = _load_pairs()
    new_id = max((p.get("id", 0) for p in pairs), default=0) + 1
    pairs.append({
        "id": new_id,
        "timestamp": datetime.utcnow().isoformat(),
        "mode": "extraction",
        "conversation": conversation,
        "chosen": chosen,
        "rejected": rejected,
        "note": note,
    })
    _save_pairs(pairs)
    return {"ok": True, "id": new_id, "total": len(pairs)}


@router.delete("/pairs/{pair_id}")
def delete_pair(pair_id: int):
    pairs = _load_pairs()
    pairs = [p for p in pairs if p.get("id") != pair_id]
    _save_pairs(pairs)
    return {"ok": True, "total": len(pairs)}
