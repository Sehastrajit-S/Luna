"""OpenClaw-style local skill discovery for Luna.

Skill folder layout
-------------------
skills/<name>/
    skill.json      — metadata (id, name, description, permissions, tools)
    SKILL.md        — shared base instructions (used when no UI variant exists)
    cli.md          — CLI/terminal-specific output rules (appended for CLI context)
    electron.md     — Electron desktop UI-specific output rules (appended for UI context)

The UI variant file is appended after SKILL.md so base instructions always apply.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal

from backend.config import BASE_DIR, DATA_DIR

SKILL_DIRS = [BASE_DIR / "skills", DATA_DIR / "workspace" / "skills"]

UIVariant = Literal["electron", "cli", "channel"]


def _read_skill(folder: Path, ui: UIVariant = "electron") -> dict[str, Any] | None:
    md = folder / "SKILL.md"
    meta_file = folder / "skill.json"
    if not md.exists() and not meta_file.exists():
        return None

    meta: dict[str, Any] = {}
    if meta_file.exists():
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except Exception:
            meta = {}

    base_body = md.read_text(encoding="utf-8", errors="replace") if md.exists() else ""

    # Load UI-specific override file and append it to the base instructions
    ui_file = folder / f"{ui}.md"
    if not ui_file.exists() and ui == "channel":
        ui_file = folder / "cli.md"  # channels fall back to cli rules
    ui_body = ui_file.read_text(encoding="utf-8", errors="replace") if ui_file.exists() else ""

    body = (base_body + "\n\n" + ui_body).strip() if ui_body else base_body

    title = meta.get("name") or folder.name
    description = meta.get("description")
    if not description:
        for line in base_body.splitlines():
            clean = line.strip("# ").strip()
            if clean:
                description = clean
                break

    return {
        "id": meta.get("id") or folder.name,
        "name": title,
        "description": description or "",
        "permissions": meta.get("permissions", []),
        "tools": meta.get("tools", []),
        "trigger": meta.get("trigger") or None,
        "keywords": [str(k).lower() for k in meta.get("keywords", []) if str(k).strip()],
        "lookup": isinstance(meta.get("search"), dict),   # runnable via use_skill (skill runtime)
        "path": str(folder),
        "body": body[:4000],
    }


def list_skills(ui: UIVariant = "electron") -> list[dict[str, Any]]:
    skills: list[dict[str, Any]] = []
    for root in SKILL_DIRS:
        root.mkdir(parents=True, exist_ok=True)
        for folder in sorted(
            [p for p in root.iterdir() if p.is_dir()],
            key=lambda p: p.name.lower(),
        ):
            skill = _read_skill(folder, ui=ui)
            if skill:
                skills.append(skill)
    return skills


_STOPWORDS = {
    "with", "from", "that", "this", "into", "when", "your", "such", "their", "them", "than",
    "then", "what", "using", "through", "files", "file", "tools", "tool", "luna", "luna's",
    "needed", "exactly", "requests", "handles", "decide", "other", "like", "work", "works",
}
_WORD_RE = re.compile(r"[a-z0-9][a-z0-9+#.-]{2,}")


def _stem(word: str) -> str:
    return word[:5]


def _skill_terms(skill: dict[str, Any]) -> set[str]:
    text = " ".join([skill.get("id", "").replace("-", " "), skill.get("name", ""), skill.get("description", "")]).lower()
    words = {w for w in _WORD_RE.findall(text) if len(w) >= 4 and w not in _STOPWORDS}
    return {_stem(w) for w in words}


def is_skill_relevant(skill: dict[str, Any], message: str) -> bool:
    """Cheap lexical match between a message and a skill's name/description/keywords."""
    lower = (message or "").lower()
    if not lower.strip():
        return False
    if any(re.search(rf"\b{re.escape(k)}\b", lower) for k in skill.get("keywords") or []):
        return True
    message_stems = {_stem(w) for w in _WORD_RE.findall(lower) if len(w) >= 4 and w not in _STOPWORDS}
    return len(message_stems & _skill_terms(skill)) >= 2


def get_skills_prompt(ui: UIVariant = "electron", message: str | None = None) -> str:
    """Skills section of the system prompt.

    Progressive disclosure: every skill is listed with its one-line
    description, but full workflow instructions are only included for skills
    relevant to `message` — sending every skill's instructions on every turn
    cost thousands of tokens of context. Pass message=None to include all.
    """
    skills = list_skills(ui=ui)
    if not skills:
        return "No local skills are installed yet."
    lines = [
        "Installed local skills:",
        "When a user request matches a skill, follow that skill's workflow before using tools.",
    ]
    for skill in skills:
        perms = ", ".join(skill.get("permissions") or []) or "none"
        tools = ", ".join(skill.get("tools") or []) or "none"
        trigger = skill.get("trigger")
        if trigger:
            # Command-only skills run through the dispatcher, not the model —
            # omit their workflow so it is never applied to ordinary messages.
            lines.append(
                f"- {skill['id']}: {skill['description']} Runs ONLY when the user's message starts "
                f"with {trigger}; never use it or its tools otherwise. If the user seems to want it, "
                f"tell them to type {trigger} <topic>."
            )
            continue
        if skill.get("lookup"):
            # The runtime carries this skill's sources and answer format; the
            # model only needs to know when to hand the request over.
            lines.append(f"- {skill['id']}: {skill['description']} Run it with use_skill.")
            continue
        lines.append(f"- {skill['id']}: {skill['description']} (permissions: {perms}; tools: {tools})")
        body = (skill.get("body") or "").strip()
        if body and (message is None or is_skill_relevant(skill, message)):
            excerpt = body[:1200].strip()
            lines.append(f"  Instructions:\n{excerpt}")
    return "\n".join(lines)
