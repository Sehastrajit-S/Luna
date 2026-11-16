import Link from 'next/link';
import DocsLayout from '../components/DocsLayout';
import { Callout, CodeFile, Steps, Step, NextSteps } from '../components/Docs';

const toc = [
  { id: 'use',     label: 'Record a meeting' },
  { id: 'minutes', label: 'What you get' },
  { id: 'files',   label: 'Where it\'s saved' },
  { id: 'how',     label: 'How it works' },
  { id: 'api',     label: 'API' },
  { id: 'limits',  label: 'Limits' },
];

export default function MeetingMode() {
  return (
    <DocsLayout
      title="Meeting mode"
      description="Record a meeting, get a timestamped transcript, and have Luna write the minutes."
      toc={toc}
    >
      <section>
        <h2 id="use">Record a meeting</h2>
        <Steps>
          <Step num="1" title="Start">
            <p>Click <strong>+</strong> in the message box and choose <strong>Meeting mode</strong>. The screen clears to a single orb.</p>
          </Step>
          <Step num="2" title="Talk">
            <p>The orb pulses with the audio and shows the elapsed time. Audio is uploaded in chunks as you go, so a long meeting isn't lost if the tab closes.</p>
          </Step>
          <Step num="3" title="Stop">
            <p>Click the orb, or press <strong>Stop</strong>. Luna transcribes the recording and writes the minutes, usually within seconds of a short meeting ending.</p>
          </Step>
        </Steps>
        <figure className="doc-figure" style={{ maxWidth: 320, marginLeft: 'auto', marginRight: 'auto' }}>
          <img src="/screenshots/meeting-recording.png" alt="Meeting mode: a single glowing orb with a timer while recording" />
          <figcaption>While recording there's nothing on screen but the orb.</figcaption>
        </figure>
      </section>

      <section>
        <h2 id="minutes">What you get</h2>
        <ul>
          <li><strong>A title</strong> suggested from what was discussed.</li>
          <li><strong>Summary</strong> of the meeting in a few sentences.</li>
          <li><strong>Discussion</strong>: the main points, topic by topic.</li>
          <li><strong>Decisions</strong> that were made.</li>
          <li><strong>Action items</strong> as a checklist, with an owner when one was named.</li>
          <li><strong>Open questions</strong> left for next time.</li>
          <li><strong>The full transcript</strong> with timestamps.</li>
        </ul>
        <figure className="doc-figure" style={{ maxWidth: 360, marginLeft: 'auto', marginRight: 'auto' }}>
          <img src="/screenshots/meeting-minutes.png" alt="Meeting minutes with summary, decisions and action items" />
          <figcaption>The minutes open in chat when processing finishes.</figcaption>
        </figure>
      </section>

      <section>
        <h2 id="files">Where it's saved</h2>
        <p>Each meeting gets its own folder in the workspace and shows up in the <Link href="/library">Library</Link>:</p>
        <CodeFile label="workspace/meetings/<id>/">
          <pre><code>{`recording.webm    # the audio
transcript.md     # timestamped transcript
minutes.md        # the minutes
_meeting.json     # status, title, timings`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="how">How it works</h2>
        <ul>
          <li>Transcription runs locally with faster-whisper (the same model as <Link href="/voice">voice</Link>, set by <code>stt_model</code>). Nothing leaves your server unless you chose a cloud model.</li>
          <li>Long transcripts are summarized in parts, then combined, so they fit any model's context window.</li>
          <li>The minutes are written by whichever AI model you've chosen in Settings.</li>
        </ul>
      </section>

      <section>
        <h2 id="api">API</h2>
        <table>
          <thead><tr><th>Method</th><th>Path</th><th>Does</th></tr></thead>
          <tbody>
            <tr><td><code>POST</code></td><td><code>/api/meetings</code></td><td>Start a meeting; returns its id</td></tr>
            <tr><td><code>PUT</code></td><td><code>/api/meetings/{'{id}'}/audio?seq=N</code></td><td>Upload audio chunk N</td></tr>
            <tr><td><code>POST</code></td><td><code>/api/meetings/{'{id}'}/finish</code></td><td>Stop and start processing</td></tr>
            <tr><td><code>GET</code></td><td><code>/api/meetings/{'{id}'}</code></td><td>Status, transcript and minutes</td></tr>
            <tr><td><code>GET</code></td><td><code>/api/meetings</code></td><td>List meetings</td></tr>
          </tbody>
        </table>
      </section>

      <section>
        <h2 id="limits">Limits</h2>
        <Callout type="note" title="No speaker labels yet">
          <p>The transcript doesn't say who said what, so action-item owners are only filled in when someone is named in the conversation.</p>
        </Callout>
        <p>Tell people they're being recorded before you start.</p>
      </section>

      <NextSteps items={[
        { href: '/library', label: 'Files', title: 'Library', desc: 'Find recordings, transcripts and minutes.' },
        { href: '/voice', label: 'Speech', title: 'Voice', desc: 'Speech-to-text models and settings.' },
      ]} />
    </DocsLayout>
  );
}
