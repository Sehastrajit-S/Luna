"""Meeting transcript → timestamped markdown → minutes (via Luna's configured model).

Long meetings don't fit one prompt: the transcript is split into parts, each
part is boiled down to notes, and the notes are merged into the minutes.
"""
from __future__ import annotations

import re
from datetime import datetime

from server.config import settings
from server.services.llm.context_window import estimate_tokens
from server.services.stt import Segment

DEFAULT_TITLE = "Meeting"
_THINK_RE = re.compile(r"<think>.*?</think>", re.S | re.I)
_TITLE_LINE_RE = re.compile(r"^\s*\**title\**\s*:\s*(.+?)\s*$", re.I)

SYSTEM = (
    "You write meeting minutes from a transcript. Use only what the transcript says: never invent "
    "names, numbers, dates or decisions. The transcript has no speaker labels: you never know who is "
    "speaking, so \"I\" and \"we\" are an unknown person. Only name someone when the transcript names "
    "them as doing the thing (\"Priya will send...\"). A name used to address someone (\"Thanks Aria\") "
    "says who is being spoken to, not who speaks next. Speech-to-text can mishear words; prefer the meaning."
)

MINUTES_PROMPT = """Write the minutes for this meeting in markdown. First line: "Title: " and a short title
(at most six words) for what the meeting was about. Then exactly these sections:

## Summary
Three to five sentences: what the meeting was about and where it landed.

## Discussion
Bullets for the main topics, each with the key points made.

## Decisions
Bullets. If nothing was decided, write "None recorded."

## Action items
A checklist, one item per line, like "- [ ] Priya: send the vendor shortlist (by Wednesday)".
The owner is the person the transcript names as doing it; for "I'll..." or "we'll..." write "Unassigned".
Leave out the due date when none was given. If there are none, write "None recorded."

## Open questions
Bullets for anything left unresolved. If none, write "None."

Meeting: {title}
{source}:
{body}
"""

NOTES_PROMPT = """This is part {part} of {total} of a meeting transcript. Write compact notes: topics discussed,
decisions, action items (who, what, when, as stated) and open questions. Keep the [hh:mm:ss] times of
decisions and action items. Notes only, no preamble.

{body}
"""


def clock(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def transcript_markdown(title: str, started_at: str, duration_s: float, segments: list[Segment]) -> str:
    when = _when(started_at)
    lines = [f"# {title}: transcript", "", f"{when} · {round(duration_s / 60) or 1} min", ""]
    lines += [f"**[{clock(s.start)}]** {s.text}" for s in segments]
    return "\n".join(lines) + "\n"


def _when(started_at: str) -> str:
    try:
        return datetime.fromisoformat(started_at).astimezone().strftime("%A, %B %d, %Y · %I:%M %p").replace(" 0", " ")
    except (TypeError, ValueError):
        return started_at or ""


def split_for_model(segments: list[Segment], budget_tokens: int) -> list[str]:
    """Transcript text in parts that each fit the model's budget."""
    parts, current, used = [], [], 0
    for seg in segments:
        line = f"[{clock(seg.start)}] {seg.text}"
        cost = estimate_tokens(line) + 1
        if current and used + cost > budget_tokens:
            parts.append("\n".join(current))
            current, used = [], 0
        current.append(line)
        used += cost
    if current:
        parts.append("\n".join(current))
    return parts


async def write_minutes(title: str, started_at: str, duration_s: float, segments: list[Segment],
                        complete=None, on_progress=None) -> tuple[str, str]:
    """(title, minutes markdown). An untitled meeting takes the model's suggested title.
    `complete(prompt, system)` defaults to Luna's model."""
    if complete is None:
        from server.services.llm import ollama
        complete = lambda prompt, system: ollama.complete(prompt=prompt, system=system, temperature=0.2)  # noqa: E731

    # Leave room for the instructions and the answer.
    budget = max(1500, int(settings.llm_context_window * 0.55))
    parts = split_for_model(segments, budget)
    if len(parts) <= 1:
        source, body = "Transcript", parts[0] if parts else ""
    else:
        notes = []
        for i, part in enumerate(parts, 1):
            notes.append(f"Part {i}:\n" + (await complete(NOTES_PROMPT.format(part=i, total=len(parts), body=part), SYSTEM)).strip())
            if on_progress:
                on_progress(i / (len(parts) + 1))
        source, body = "Notes from each part of the transcript, in order", "\n\n".join(notes)

    text = _THINK_RE.sub("", await complete(MINUTES_PROMPT.format(title=title, source=source, body=body), SYSTEM)).strip()
    suggested, text = split_title(text)
    final_title = suggested if suggested and title in ("", DEFAULT_TITLE) else title
    header = [f"# {final_title}", "", f"{_when(started_at)} · {round(duration_s / 60) or 1} min", ""]
    return final_title, "\n".join(header) + text + "\n"


def split_title(text: str) -> tuple[str | None, str]:
    """The model's "Title: ..." first line, and the rest of the minutes."""
    first, _, rest = text.partition("\n")
    match = _TITLE_LINE_RE.match(first)
    if not match:
        return None, text
    title = match.group(1).strip().strip('"*#').strip()[:80]
    return (title or None), rest.lstrip()
