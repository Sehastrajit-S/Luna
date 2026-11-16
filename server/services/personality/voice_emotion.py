"""Audio-feature-based voice emotion classifier."""


def classify_voice_emotion(
    pitch_hz: float | None,
    energy_rms: float | None,
    speech_rate_wpm: float | None,
    pause_ratio: float | None,
) -> str:
    """
    Classify emotion from audio features.
    Returns: neutral | excited | sad | angry | calm
    """
    if pitch_hz is None and energy_rms is None:
        return "neutral"

    score_excited = 0
    score_sad = 0
    score_angry = 0
    score_calm = 0

    if pitch_hz is not None:
        if pitch_hz > 220:
            score_excited += 1
        elif pitch_hz < 140:
            score_sad += 1

    if energy_rms is not None:
        if energy_rms > 800:
            score_angry += 1
            score_excited += 1
        elif energy_rms < 200:
            score_sad += 1
            score_calm += 1

    if speech_rate_wpm is not None:
        if speech_rate_wpm > 160:
            score_excited += 1
            score_angry += 1
        elif speech_rate_wpm < 100:
            score_sad += 1
            score_calm += 1

    if pause_ratio is not None:
        if pause_ratio > 0.4:
            score_sad += 1
            score_calm += 1
        elif pause_ratio < 0.15:
            score_excited += 1

    scores = {
        "excited": score_excited,
        "sad": score_sad,
        "angry": score_angry,
        "calm": score_calm,
    }
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return "neutral"
    return best
