"""JSON tool-call and plan parsers for the coding agent."""
from __future__ import annotations

import json

from backend.services.coding.prompts import PLAN_RE


def _scan_json_object(text: str, start: int) -> int | None:
    depth = 0
    in_string = False
    escape = False
    i = start
    while i < len(text):
        c = text[i]
        if escape:
            escape = False
        elif c == "\\" and in_string:
            escape = True
        elif c == '"':
            in_string = not in_string
        elif not in_string:
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    return None


def parse_tool_call(response: str) -> dict | None:
    i = 0
    while i < len(response):
        if response[i] != "{":
            i += 1
            continue
        end = _scan_json_object(response, i)
        if end is None:
            break
        candidate = response[i : end + 1]
        if '"tool_call"' in candidate:
            try:
                obj = json.loads(candidate)
                tc = obj.get("tool_call")
                if tc and "tool" in tc:
                    return tc
            except Exception:
                pass
        i += 1
    return None


def strip_tool_call(text: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(text):
        if text[i] != "{":
            out.append(text[i])
            i += 1
            continue
        end = _scan_json_object(text, i)
        if end is None:
            out.append(text[i])
            i += 1
            continue
        candidate = text[i : end + 1]
        if '"tool_call"' in candidate or '"plan"' in candidate:
            try:
                obj = json.loads(candidate)
                if obj.get("tool_call") or obj.get("plan"):
                    out.append(" ")
                    i = end + 1
                    continue
            except Exception:
                pass
        out.append(text[i])
        i += 1
    return "".join(out).strip()


def extract_plan(text: str) -> dict | None:
    """Find and parse the first {"plan": {...}} block in text."""
    m = PLAN_RE.search(text)
    if not m:
        return None
    try:
        obj = json.loads(m.group(1))
        if "steps" in obj:
            return obj
    except Exception:
        pass
    return None


def strip_plan(text: str) -> str:
    """Remove the plan JSON block from visible text."""
    return PLAN_RE.sub("", text).strip()
