# Voice Runtime Process

Owns voice lifecycle startup and shutdown:

- Wake word listener lifecycle.
- Microphone/voice loop enable and disable.
- Integration with `server/services/voice/`.

This is a lifecycle process, not a scheduled process.
