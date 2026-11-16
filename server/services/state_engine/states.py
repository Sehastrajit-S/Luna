"""UserState enum, per-state response policies, and lookup constants."""
from enum import Enum


class UserState(str, Enum):
    SLEEPING       = "SLEEPING"
    JUST_WOKE_UP   = "JUST_WOKE_UP"
    AWAY           = "AWAY"
    BACK_FROM_WORK = "BACK_FROM_WORK"
    FOCUS_MODE     = "FOCUS_MODE"
    RELAXING       = "RELAXING"
    STAYING_UP     = "STAYING_UP"
    LOW_ENERGY     = "LOW_ENERGY"
    NORMAL         = "NORMAL"


STATE_POLICIES: dict[UserState, dict] = {
    UserState.SLEEPING: {
        "tone": "silent",
        "behavior": "Do not speak unless the user explicitly initiates. No proactive messages.",
        "prompt_note": (
            "The user appears to be asleep (late-night hours, no PC activity). "
            "Only respond if they directly speak to you. Be extremely brief."
        ),
    },
    UserState.JUST_WOKE_UP: {
        "tone": "calm and brief",
        "behavior": "Give a short morning summary. Avoid heavy topics or long responses.",
        "prompt_note": (
            "The user just woke up. Keep it short, warm, and grounding. "
            "Offer their schedule and top tasks without overwhelming them."
        ),
    },
    UserState.AWAY: {
        "tone": "welcoming",
        "behavior": "Welcome them back. Offer a quick summary of what happened while they were away.",
        "prompt_note": (
            "The user just came back after being away for a while. "
            "Greet them warmly and offer a brief summary if useful."
        ),
    },
    UserState.BACK_FROM_WORK: {
        "tone": "warm and low-energy",
        "behavior": "Summarize missed items only if asked. Avoid pushing tasks. Keep it easy.",
        "prompt_note": (
            "The user is back from work and may be tired. "
            "Be warm, relaxed, and low-key. Don't push tasks or ask heavy questions."
        ),
    },
    UserState.FOCUS_MODE: {
        "tone": "minimal",
        "behavior": "Only respond when spoken to. Be extremely short. No proactive interruptions.",
        "prompt_note": (
            "The user is in deep-work / focus mode. "
            "Answer only what is directly asked. Keep every response to one or two sentences max."
        ),
    },
    UserState.RELAXING: {
        "tone": "casual and playful",
        "behavior": "Match their relaxed energy. Be fun, conversational, not task-oriented.",
        "prompt_note": (
            "The user is relaxing. Match their chill energy — be casual, fun, "
            "and companionable rather than assistant-mode."
        ),
    },
    UserState.STAYING_UP: {
        "tone": "gentle but practical",
        "behavior": "Acknowledge the late hour gently. Ask once if they want focus mode or a sleep reminder.",
        "prompt_note": (
            "It is very late and the user is still active. "
            "Be gentle and grounding. Mention the time once if relevant; don't nag."
        ),
    },
    UserState.LOW_ENERGY: {
        "tone": "soft and caring",
        "behavior": "Match their low energy. Short sentences, warm tone. Don't push anything.",
        "prompt_note": (
            "The user seems low-energy or emotionally tired based on their voice. "
            "Keep responses short, soft, and caring. Don't push tasks."
        ),
    },
    UserState.NORMAL: {
        "tone": "normal",
        "behavior": "Standard conversational companion.",
        "prompt_note": "",
    },
}

# Apps that signal focused deep work
_FOCUS_APPS = frozenset({
    "code.exe", "cursor.exe", "pycharm64.exe", "idea64.exe",
    "devenv.exe", "vim.exe", "nvim.exe", "sublime_text.exe",
    "rider64.exe", "clion64.exe", "fleet.exe",
})

# Back-from-work trigger words
_WORK_WORDS = frozenset({
    "back", "home", "work", "tired", "done", "finally", "office",
    "meeting", "calls", "shift", "got off", "commute",
})
