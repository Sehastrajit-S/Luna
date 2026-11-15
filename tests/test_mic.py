"""
Microphone diagnostic — run this directly:
    python test_mic.py

Shows RMS bar + live Vosk transcript so you can confirm
the mic is working before using it inside Luna.
"""
import json
import queue
import sys
from pathlib import Path

# ── 1. sounddevice ────────────────────────────────────────────────────────────
try:
    import sounddevice as sd
    import numpy as np
except ImportError:
    print("[ERROR] sounddevice or numpy not installed.")
    print("        pip install sounddevice numpy")
    sys.exit(1)

print("=" * 60)
print("  Luna mic diagnostic")
print("=" * 60)

# List all devices
print("\nAll audio devices:")
print(sd.query_devices())

try:
    dev = sd.query_devices(kind='input')
    print(f"\nDefault input : {dev['name']}")
    print(f"Max channels  : {dev['max_input_channels']}")
    print(f"Default SR    : {dev['default_samplerate']}")
except Exception as e:
    print(f"\n[ERROR] No input device found: {e}")
    print("Check Windows Settings → Privacy & Security → Microphone")
    sys.exit(1)

# ── 2. Try opening the stream ─────────────────────────────────────────────────
print("\nOpening mic at 16 kHz …", end=" ", flush=True)
test_q: queue.Queue[bytes] = queue.Queue()

def _cb(indata, frames, t, status):
    if status:
        print(f"\n[mic status] {status}")
    test_q.put(bytes(indata))

try:
    stream = sd.RawInputStream(
        samplerate=16000, channels=1,
        dtype="int16", blocksize=4000,
        callback=_cb,
    )
    stream.start()
    print("OK")
except sd.PortAudioError as e:
    print(f"\n[ERROR] {e}")
    print("→ Open Windows Settings → Privacy & Security → Microphone")
    print("  and make sure Python is allowed.")
    sys.exit(1)

# ── 3. Optional Vosk ──────────────────────────────────────────────────────────
vosk_rec = None
model_path = Path("data/vosk-model")
try:
    from vosk import Model, KaldiRecognizer
    if model_path.exists():
        vosk_rec = KaldiRecognizer(Model(str(model_path)), 16000)
        print(f"Vosk model loaded from {model_path} — transcript will show below.\n")
    else:
        print(f"Vosk model not found at {model_path} — RMS only.\n")
except ImportError:
    print("Vosk not installed — RMS only.\n")

print("Speak into your mic.  Ctrl+C to stop.\n")

# ── 4. Live loop ──────────────────────────────────────────────────────────────
try:
    while True:
        chunk = test_q.get()
        audio = np.frombuffer(chunk, dtype=np.int16).astype(np.float32)
        rms   = float(np.sqrt(np.mean(audio ** 2)))
        filled = min(30, int(rms / 80))
        bar = "█" * filled + "░" * (30 - filled)

        if vosk_rec:
            if vosk_rec.AcceptWaveform(chunk):
                text = json.loads(vosk_rec.Result()).get("text", "").strip()
                if text:
                    print(f"\r✓ {text:<55}")
            else:
                partial = json.loads(vosk_rec.PartialResult()).get("partial", "").strip()
                print(f"\r[{bar}] {rms:5.0f}  {partial:<30}", end="", flush=True)
        else:
            print(f"\r[{bar}] RMS {rms:5.0f}", end="", flush=True)

except KeyboardInterrupt:
    stream.stop()
    stream.close()
    print("\n\nDone.")
