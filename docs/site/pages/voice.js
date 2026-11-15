import DocsLayout from '../components/DocsLayout';
import { Callout, CodeFile, NextSteps } from '../components/Docs';

const toc = [
  { id: 'overview',     label: 'Overview' },
  { id: 'stt',          label: 'Speech-to-text' },
  { id: 'wake-word',    label: 'Wake word' },
  { id: 'push-to-talk', label: 'Push-to-talk' },
  { id: 'tts',          label: 'Text-to-speech' },
  { id: 'emotion',      label: 'Emotion detection' },
  { id: 'troubleshoot', label: 'Troubleshooting' },
];

export default function Voice() {
  return (
    <DocsLayout
      title="Voice"
      description="Configure speech-to-text, wake-word detection, push-to-talk, TTS voice selection, and emotion analysis."
      toc={toc}
    >
      <section>
        <h2 id="overview">Overview</h2>
        <p>
          Luna's voice pipeline is fully local. Audio is captured by your microphone, transcribed on-device
          with <strong>faster-whisper</strong>, processed by the LLM, and spoken back with <strong>pyttsx3</strong>.
          No audio leaves your machine.
        </p>

        <p>The pipeline runs as the <code>voice_runtime</code> background process (<code>backend/processes/voice_runtime/</code>)
        and exposes its state through <code>/api/voice/</code>. The frontend's <code>VoiceOrb</code> component
        connects to this state and drives the animated listening indicator.</p>

        <Callout type="info" title="Microphone permission">
          <p>The Electron shell requests microphone access on first launch. On Windows you may also need
          to enable microphone access for desktop apps in <strong>Settings → Privacy → Microphone</strong>.</p>
        </Callout>
      </section>

      <section>
        <h2 id="stt">Speech-to-text (STT)</h2>
        <p>
          Luna uses <strong>faster-whisper</strong> — a CTranslate2-optimised Whisper implementation —
          for transcription. It runs entirely on your CPU or GPU.
        </p>

        <h3>Model selection</h3>
        <p>faster-whisper auto-downloads the model on first use. The default is <code>base</code>. Change it in <code>.env</code>:</p>

        <CodeFile label=".env">
          <pre><code>{`# Options: tiny, base, small, medium, large-v2, large-v3
whisper_model=base`}</code></pre>
        </CodeFile>

        <table>
          <thead><tr><th>Model</th><th>RAM</th><th>Speed</th><th>Accuracy</th></tr></thead>
          <tbody>
            <tr><td><code>tiny</code></td><td>~200 MB</td><td>Very fast</td><td>Low — good for clear speech</td></tr>
            <tr><td><code>base</code></td><td>~400 MB</td><td>Fast</td><td>Good — recommended default</td></tr>
            <tr><td><code>small</code></td><td>~500 MB</td><td>Moderate</td><td>Better — noisy environments</td></tr>
            <tr><td><code>medium</code></td><td>~1.5 GB</td><td>Slow</td><td>High — multiple speakers</td></tr>
          </tbody>
        </table>

        <Callout type="tip" title="GPU acceleration">
          <p>faster-whisper can use CUDA if <code>torch</code> with CUDA support is installed. Set
          <code>whisper_device=cuda</code> in <code>.env</code> to enable it. Falls back to CPU silently.</p>
        </Callout>
      </section>

      <section>
        <h2 id="wake-word">Wake word</h2>
        <p>
          Luna listens continuously in the background for a wake word. When detected, it begins capturing
          the following utterance and sends it to the STT model.
        </p>

        <CodeFile label=".env">
          <pre><code>{`# Enable wake-word detection
wake_word_enabled=true

# The word or phrase Luna listens for (case-insensitive)
wake_word=hey luna`}</code></pre>
        </CodeFile>

        <p>The wake-word detector runs on a lightweight energy-based heuristic — it does not send audio
        to the LLM until the wake word is confidently detected. This keeps CPU usage near zero while idle.</p>

        <Callout type="warn" title="False positives">
          <p>In noisy environments, short wake words like <em>"luna"</em> may trigger unexpectedly. Use a
          longer phrase like <em>"hey luna"</em> or <em>"okay luna"</em> to reduce false positives.</p>
        </Callout>
      </section>

      <section>
        <h2 id="push-to-talk">Push-to-talk</h2>
        <p>
          Push-to-talk is always available in the frontend regardless of wake-word settings. Hold the
          microphone button in the <code>InputBar</code> to record, release to transcribe and send.
        </p>

        <p>The recording indicator uses the <code>VoiceOrb</code> component
        (<code>frontend/src/components/Voice/VoiceOrb.tsx</code>) which animates based on audio amplitude
        from the <code>useVoiceRecorder</code> hook.</p>

        <Callout type="tip" title="Keyboard shortcut">
          <p>While the chat input is focused, hold <strong>Space</strong> to trigger push-to-talk.</p>
        </Callout>
      </section>

      <section>
        <h2 id="tts">Text-to-speech (TTS)</h2>
        <p>
          Luna speaks responses using <strong>pyttsx3</strong>, which wraps your OS's native TTS engine —
          SAPI5 on Windows, NSSpeechSynthesizer on macOS, and eSpeak on Linux.
        </p>

        <CodeFile label=".env">
          <pre><code>{`# Enable TTS
tts_enabled=true

# Speaking rate (words per minute). Default is 150.
tts_rate=150

# Voice index — 0 is your first system voice, 1 is the second, etc.
tts_voice_index=0`}</code></pre>
        </CodeFile>

        <h3>Listing available voices</h3>
        <p>To find available voice indices on your system, run:</p>

        <CodeFile label="Python">
          <pre><code>{`import pyttsx3
engine = pyttsx3.init()
for i, voice in enumerate(engine.getProperty('voices')):
    print(i, voice.name, voice.languages)`}</code></pre>
        </CodeFile>

        <p>Set <code>tts_voice_index</code> to the index of your preferred voice in <code>.env</code>.</p>

        <Callout type="info" title="Installing more voices on Windows">
          <p>Go to <strong>Settings → Time &amp; language → Speech → Add voices</strong> to install
          additional high-quality neural TTS voices. They will appear in the pyttsx3 voice list.</p>
        </Callout>
      </section>

      <section>
        <h2 id="emotion">Emotion detection</h2>
        <p>
          Luna analyses the emotional tone of transcribed speech to update the personality engine.
          The analysis runs in <code>backend/services/voice.py</code> using keyword heuristics and
          sentiment scoring — no external model is required.
        </p>
        <p>Detected emotions influence the <code>emotional_support</code> dimension of the personality
        state, causing Luna to respond with more or less empathy based on your current mood.</p>
      </section>

      <section>
        <h2 id="troubleshoot">Troubleshooting</h2>

        <h3>Voice says "off" in the UI</h3>
        <ul>
          <li>Check that <code>tts_enabled=true</code> is set in <code>.env</code>.</li>
          <li>Check microphone permissions in the OS and in Electron.</li>
          <li>Open the backend logs and look for <code>Microphone opened OK</code>. If absent, the audio device initialisation failed.</li>
          <li>Try a different audio device by setting <code>audio_device_index</code> in <code>.env</code>.</li>
        </ul>

        <h3>Wake word never triggers</h3>
        <ul>
          <li>Confirm <code>wake_word_enabled=true</code> in <code>.env</code>.</li>
          <li>Check the backend log for <code>[voice_runtime] listening for wake word</code>.</li>
          <li>Speak clearly and at a normal volume — the detector needs a minimum energy threshold.</li>
        </ul>

        <h3>TTS not speaking</h3>
        <ul>
          <li>Confirm <code>tts_enabled=true</code>.</li>
          <li>On Windows, check that a SAPI5 voice is installed. Run the listing snippet above to verify.</li>
          <li>If pyttsx3 raises an error, try <code>pip install pyttsx3 --upgrade</code>.</li>
        </ul>
      </section>

      <NextSteps items={[
        { href: '/memory',         label: 'Feature',  title: 'Memory system',   desc: 'How voice interactions update the memory and personality systems.' },
        { href: '/environment',    label: 'Config',   title: 'Environment',     desc: 'Full reference for all voice-related .env keys.' },
        { href: '/troubleshooting',label: 'Support',  title: 'Troubleshooting', desc: 'All common issues in one place.' },
      ]} />
    </DocsLayout>
  );
}
