from backend.processes.registry import ProcessDef
from backend.services.voice import voice_service


PROCESS = ProcessDef(
    id="voice_runtime",
    name="Voice runtime",
    description="Wake word listener, microphone state, and local voice loop lifecycle.",
    area="voice",
    # start=None: don't auto-start at backend launch.
    # ctranslate2 (used by faster_whisper) segfaults on CPUs without AVX2,
    # which kills the entire backend process. Voice is enabled on demand via
    # the toggle in Settings > Controls or POST /api/voice/toggle.
    start=None,
    stop=voice_service.disable,
)
