"""Coding request detection patterns."""
import re

_CODING_PATTERNS = [
    r"\b(write|create|generate|build|implement|make)\b.{0,70}\b(function|class|method|component|module|script|api|endpoint|algorithm|program)\b",
    r"\b(in|using|with)\s+(python|javascript|typescript|tsx?|rust|go|java|c\+\+|cpp|c#|csharp|ruby|php|swift|kotlin|sql|bash|shell|powershell|react|vue|django|flask|fastapi|express|node)\b",
    r"\b(debug|fix|refactor|optimize|review|unit.?test)\b.{0,60}\b(code|function|class|script|file)\b",
    r"\b(explain|what does|how does)\b.{0,60}\b(this code|this function|this class|this method|this script)\b",
    r"```",
    r"\b(write|give me|show me|make me)\b.{0,40}\b(code|snippet|example|implementation)\b",
    r"\b(how (do|to|can) (i|you))\b.{0,60}\b(implement|code|write|build|program)\b",
]


def is_coding_request(message: str) -> bool:
    lower = message.lower()
    return any(re.search(p, lower) for p in _CODING_PATTERNS)
