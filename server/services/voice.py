# Backward-compat shim — all logic lives in backend.services.voice package
from backend.services.voice import *  # noqa: F401, F403
from backend.services.voice import VoiceState, VoiceService, voice_service
