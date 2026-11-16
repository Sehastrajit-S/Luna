"""Sentiment assessment and implicit reward computation."""
import re


def _label(value: float, labels: dict) -> str:
    for (lo, hi), text in labels.items():
        if lo <= value < hi:
            return text
    return list(labels.values())[-1]


def compute_time_mood(hour: int) -> tuple[str, float]:
    if 5 <= hour < 9:
        return "happy", 0.65
    elif 9 <= hour < 14:
        return "neutral", 0.5
    elif 14 <= hour < 17:
        return "curious", 0.55
    elif 17 <= hour < 20:
        return "warm", 0.6
    elif 20 <= hour < 23:
        return "thoughtful", 0.65
    else:
        return "melancholic", 0.55


_INTENSIFIER_RE = re.compile(
    r'\b(very|really|so|extremely|absolutely|totally|super|incredibly|genuinely)\b', re.I
)
_NEGATION_RE = re.compile(
    r"\b(not|never|no|don'?t|can'?t|won'?t|isn'?t|wasn'?t|barely|hardly|neither|nor)\b", re.I
)
_POS_WORDS = [
    "happy", "great", "amazing", "love", "excited", "glad", "wonderful", "awesome",
    "perfect", "fantastic", "good", "nice", "thanks", "appreciate", "enjoy", "fun",
    "pleased", "delighted", "thrilled", "relieved", "proud", "content", "hopeful",
    "motivated", "energized", "confident", "peaceful", "grateful", "better",
]
_NEG_WORDS = [
    "sad", "tired", "stressed", "angry", "upset", "worried", "anxious", "depressed",
    "bad", "hate", "terrible", "awful", "frustrated", "exhausted", "miserable",
    "annoyed", "disappointed", "scared", "overwhelmed", "hopeless", "dread",
    "struggling", "stuck", "lost", "broken", "failed", "failing", "nervous",
    "drained", "burnout", "sick", "pain", "hurt", "ugh", "ugh",
]


def assess_user_sentiment(text: str) -> float:
    """Sentiment score: -1.0 to 1.0. Handles negation, intensity, and word boundaries."""
    lower = text.lower()
    intensity = 1.6 if _INTENSIFIER_RE.search(lower) else 1.0
    has_negation = bool(_NEGATION_RE.search(lower))

    p = sum(1 for w in _POS_WORDS if re.search(rf'\b{w}\b', lower))
    n = sum(1 for w in _NEG_WORDS if re.search(rf'\b{w}\b', lower))

    # Negation flips the dominant polarity ("not happy" → negative, "not bad" → positive)
    if has_negation:
        if p > n:
            p, n = 0, p
        elif n > p:
            n, p = 0, n

    if p + n == 0:
        return 0.0
    raw = (p - n) / (p + n + 1)
    return round(max(-1.0, min(1.0, raw * intensity)), 2)


def compute_implicit_reward(
    luna_response: str,
    user_next_msg: str,
    tool_succeeded: bool = False,
    task_completed: bool = False,
    user_interrupted_tts: bool = False,
    is_repeat_request: bool = False,
    manual_correction: bool = False,
) -> float:
    """
    Estimate how positively the user received Luna's response.
    Returns -1.0 (bad) to 1.0 (great).
    Skips noisy low-signal messages (< 3 words or pure acknowledgment).
    """
    low = user_next_msg.lower().strip()
    words = low.split()

    _NOISE = {"ok", "okay", "k", "mm", "hmm", "yeah", "yep", "yup",
              "sure", "alright", "fine", "got it", "cool", "nice"}
    if len(words) < 3 and (not words or words[0] in _NOISE):
        return 0.0

    strong_pos = [
        "thank", "thanks", "thank you", "that's right", "you're right",
        "exactly", "perfect", "love that", "love it", "great", "amazing",
        "correct", "yes exactly", "you got it", "that's it", "that's what i",
    ]
    strong_neg = [
        "wrong", "that's wrong", "not right", "incorrect", "no that's not",
        "not what i", "that's not what", "stop", "that's not it",
        "you misunderstood",
    ]
    medium_pos = [
        "interesting", "tell me more", "really?", "wow", "nice", "cool",
        "good point", "oh that's", "i like that",
    ]
    medium_neg = ["nevermind", "never mind", "forget it", "too long", "boring",
                  "whatever", "i said", "i already said", "i told you"]

    pos_score = (
        sum(0.5 for p in strong_pos if p in low) +
        sum(0.25 for p in medium_pos if p in low)
    )
    neg_score = (
        sum(0.5 for n in strong_neg if n in low) +
        sum(0.25 for n in medium_neg if n in low)
    )

    len_ratio = min(len(user_next_msg) / max(len(luna_response) * 0.3, 50), 1.5)
    len_score = (len_ratio - 0.5) * 0.4

    event_score = 0.0
    if tool_succeeded:
        event_score += 0.3
    if task_completed:
        event_score += 0.4
    if user_interrupted_tts:
        event_score -= 0.4
    if is_repeat_request:
        event_score -= 0.5
    if manual_correction:
        event_score -= 0.6

    total = len_score + pos_score - neg_score + event_score
    return round(max(-1.0, min(1.0, total)), 3)
