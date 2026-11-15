"""Voice pipeline state enum."""
from enum import Enum


class VoiceState(str, Enum):
    IDLE       = "idle"        # disabled
    LISTENING  = "listening"   # wake word detection
    FOLLOWUP   = "followup"    # follow-up window (already awake)
    ACTIVE     = "active"      # command recording in progress
    PROCESSING = "processing"  # transcribing + querying LLM
    SPEAKING   = "speaking"    # TTS output playing
