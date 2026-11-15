"""Away/farewell detection for user departure signals."""

_AWAY_TRIGGERS = frozenset({
    "leaving", "i'm leaving", "im leaving", "heading out", "going out",
    "going to work", "brb", "be right back", "be back", "gotta go", "got to go",
    "gotta run", "got to run", "see you later", "see ya", "i'll be back",
    "ill be back", "stepping out", "going home", "going to the", "i'm out",
    "im out", "i'm going", "im going", "on my way out", "out for a bit",
    "running errands", "going for a walk", "going to get",
    "going to bed", "going to sleep", "heading to bed", "heading to sleep",
    "off to bed", "off to sleep", "goodnight", "good night", "gonna sleep",
    "gonna go to bed", "time to sleep", "time to go to bed", "hitting the bed",
    "hitting the sack", "calling it a night",
})

_HEDGE_WORDS = frozenset({
    "thinking", "think", "considering", "might", "may", "maybe", "perhaps",
    "probably", "wondering", "wonder", "not sure", "kind of", "kinda",
    "sort of", "sorta", "planning", "plan", "want to", "wanna", "would",
    "should", "could", "feel like", "feel like going",
})

_FAREWELL_PHRASES = frozenset({
    "sleep well", "rest well", "good night", "goodnight", "sweet dreams",
    "night night", "rest up", "get some rest", "have a good sleep",
})


def user_is_leaving(msg: str) -> bool:
    lower = msg.lower().strip()
    for phrase in _AWAY_TRIGGERS:
        if phrase not in lower:
            continue
        idx = lower.find(phrase)
        before = lower[:idx]
        if any(h in before for h in _HEDGE_WORDS):
            continue
        return True
    return False


def response_is_farewell(response: str) -> bool:
    lower = response.lower()
    return any(p in lower for p in _FAREWELL_PHRASES)
