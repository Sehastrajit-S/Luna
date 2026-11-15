# Backward-compat shim — all logic lives in backend.services.personality package
from backend.services.personality import *  # noqa: F401, F403
from backend.services.personality import (
    MOODS,
    MOOD_EXPRESSION,
    VERBOSITY_LABELS,
    HUMOR_LABELS,
    FORMALITY_LABELS,
    assess_user_sentiment,
    compute_implicit_reward,
    classify_voice_emotion,
    PersonalityEngine,
)
