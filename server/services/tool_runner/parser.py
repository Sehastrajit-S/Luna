"""JSON tool call extraction and stripping from LLM response text."""
import json
import logging

logger = logging.getLogger(__name__)


def _scan_json_object(text: str, start: int) -> int | None:
    """Return index of the closing '}' matching text[start], or None."""
    depth = 0
    in_string = False
    escape = False
    i = start
    while i < len(text):
        c = text[i]
        if escape:
            escape = False
        elif c == '\\' and in_string:
            escape = True
        elif c == '"':
            in_string = not in_string
        elif not in_string:
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    return None


def parse_tool_call_json(response: str) -> dict | None:
    """Extract the first tool_call JSON block from an LLM response."""
    i = 0
    while i < len(response):
        if response[i] != '{':
            i += 1
            continue
        end = _scan_json_object(response, i)
        if end is None:
            break
        candidate = response[i:end + 1]
        if '"tool_call"' in candidate:
            try:
                obj = json.loads(candidate)
                tc = obj.get("tool_call")
                if tc and "tool" in tc:
                    return tc
            except (json.JSONDecodeError, ValueError):
                pass
        i += 1

    bracket_marker = '[TOOL_CALL:'
    idx = response.find(bracket_marker)
    while idx != -1:
        brace_start = response.find('{', idx + len(bracket_marker))
        if brace_start == -1:
            break
        end = _scan_json_object(response, brace_start)
        if end is not None:
            try:
                tc = json.loads(response[brace_start:end + 1])
                if "tool" in tc:
                    return tc
            except (json.JSONDecodeError, ValueError):
                pass
        idx = response.find(bracket_marker, idx + 1)
    return None


def strip_tool_call_json(response: str) -> str:
    """Remove tool_call JSON blocks from visible text."""
    result = response
    bracket_marker = '[TOOL_CALL:'
    idx = result.find(bracket_marker)
    while idx != -1:
        brace_start = result.find('{', idx + len(bracket_marker))
        if brace_start == -1:
            break
        end = _scan_json_object(result, brace_start)
        if end is not None:
            close_bracket = result.find(']', end)
            if close_bracket != -1:
                result = result[:idx] + ' ' + result[close_bracket + 1:]
                idx = result.find(bracket_marker)
                continue
        idx = result.find(bracket_marker, idx + 1)

    out: list[str] = []
    i = 0
    while i < len(result):
        if result[i] != '{':
            out.append(result[i])
            i += 1
            continue
        end = _scan_json_object(result, i)
        if end is None:
            out.append(result[i])
            i += 1
            continue
        candidate = result[i:end + 1]
        if '"tool_call"' in candidate:
            try:
                obj = json.loads(candidate)
                if obj.get("tool_call") and "tool" in obj["tool_call"]:
                    out.append(' ')
                    i = end + 1
                    continue
            except (json.JSONDecodeError, ValueError):
                pass
        out.append(result[i])
        i += 1
    return ''.join(out).strip()
