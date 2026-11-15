import DocsLayout from '../../components/DocsLayout';
import { Callout, CodeFile, NextSteps } from '../../components/Docs';

const toc = [
  { id: 'overview',     label: 'Overview' },
  { id: 'voice-orb',    label: 'VoiceOrb' },
  { id: 'states',       label: 'Voice states' },
  { id: 'phone-mic',    label: 'PhoneMic' },
  { id: 'voice-api',    label: 'Voice endpoints' },
];

export default function UIVoicePage() {
  return (
    <DocsLayout
      title="Voice UI"
      description="VoiceOrb and PhoneMic — animated voice state indicators and the full-screen phone-style microphone interface."
      toc={toc}
    >
      <section>
        <h2 id="overview">Overview</h2>
        <p>
          Luna has two voice UI components. <code>VoiceOrb</code> is a compact animated
          indicator that can be embedded anywhere. <code>PhoneMic</code> is the
          full-screen voice interaction view shown when the user activates phone mode.
        </p>
        <table>
          <thead><tr><th>Component</th><th>File</th><th>Use case</th></tr></thead>
          <tbody>
            <tr><td><code>VoiceOrb</code></td><td><code>components/Voice/VoiceOrb.tsx</code></td><td>Embedded in ChatWindow; also used in the dashboard header.</td></tr>
            <tr><td><code>PhoneMic</code></td><td><code>components/Voice/PhoneMic.tsx</code></td><td>Full-screen voice interface triggered from the sidebar.</td></tr>
          </tbody>
        </table>
      </section>

      <section>
        <h2 id="voice-orb">VoiceOrb</h2>
        <p>
          An animated dual-ring orb that reflects the current voice pipeline state.
          Outer and inner rings rotate at speeds keyed to the state; a pulse scale
          animation gives visual feedback during speaking.
        </p>
        <CodeFile label="props">
          <pre><code>{`interface VoiceOrbProps {
  size?:      number      // diameter in px — default 36
  showLabel?: boolean     // show status subtitle below the orb
  onToggle?:  () => void  // override the default voice-toggle action
}`}</code></pre>
        </CodeFile>
        <CodeFile label="usage">
          <pre><code>{`import { VoiceOrb } from './components/Voice/VoiceOrb'

// Compact mode in the chat header
<VoiceOrb size={28} />

// Larger with subtitle label
<VoiceOrb size={56} showLabel />`}</code></pre>
        </CodeFile>

        <h3>State sync</h3>
        <p>
          VoiceOrb opens a persistent SSE connection to <code>GET /api/voice/events</code>
          and updates its state whenever the backend sends a <code>voice_state</code> event.
          It polls <code>GET /api/voice/state</code> on mount to set the initial state.
        </p>
      </section>

      <section>
        <h2 id="states">Voice states</h2>
        <table>
          <thead><tr><th>State</th><th>Label</th><th>Visual</th></tr></thead>
          <tbody>
            <tr><td><code>idle</code></td><td>voice off</td><td>Static — no rotation, no pulse.</td></tr>
            <tr><td><code>listening</code></td><td>sleeping</td><td>Static — wake-word detection mode.</td></tr>
            <tr><td><code>followup</code></td><td>listening...</td><td>Slow outer rotation, gentle pulse.</td></tr>
            <tr><td><code>active</code></td><td>listening...</td><td>Fast rotation, strong pulse.</td></tr>
            <tr><td><code>processing</code></td><td>thinking...</td><td>Medium rotation, rhythmic pulse.</td></tr>
            <tr><td><code>speaking</code></td><td>speaking...</td><td>Rapid rotation, large pulse (scale 1.22).</td></tr>
          </tbody>
        </table>
        <p>
          The backend controls state transitions. The frontend only reflects what it receives
          via SSE — it never sets voice state directly.
        </p>
      </section>

      <section>
        <h2 id="phone-mic">PhoneMic</h2>
        <p>
          A full-screen voice interaction view styled like a phone call UI. Shows a large
          VoiceOrb, the current transcript, Luna's response, and controls to end the call.
          Activated from the sidebar by switching to the <code>voice</code> view.
        </p>
        <p>Key interactions:</p>
        <ul>
          <li>Tap the orb to toggle listening on/off.</li>
          <li>Luna's streamed text response appears below the orb in real-time.</li>
          <li>A waveform animation plays during speech.</li>
          <li>End-call button returns to the chat view and stops the voice pipeline.</li>
        </ul>
        <CodeFile label="usage">
          <pre><code>{`import { PhoneMic } from './components/Voice/PhoneMic'

// Shown when activeView === 'voice' in the store
{activeView === 'voice' && <PhoneMic />}`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="voice-api">Voice endpoints</h2>
        <table>
          <thead><tr><th>Endpoint</th><th>Method</th><th>Description</th></tr></thead>
          <tbody>
            <tr><td><code>/api/voice/state</code></td><td>GET</td><td>Current voice state string.</td></tr>
            <tr><td><code>/api/voice/events</code></td><td>GET (SSE)</td><td>State change stream — sends <code>voice_state</code> events.</td></tr>
            <tr><td><code>/api/voice/toggle</code></td><td>POST</td><td>Toggle voice pipeline on/off.</td></tr>
            <tr><td><code>/api/voice/stream</code></td><td>POST</td><td>Submit audio data for processing.</td></tr>
          </tbody>
        </table>
      </section>

      <NextSteps items={[
        { href: '/ui/chat',     label: 'Component', title: 'Chat UI', desc: 'ChatWindow embeds VoiceOrb inline.' },
        { href: '/ui/sidebar',  label: 'Component', title: 'Sidebar', desc: 'The sidebar navigates to PhoneMic view.' },
        { href: '/api-reference', label: 'Reference', title: 'API Reference', desc: 'Voice endpoint specifications.' },
      ]} />
    </DocsLayout>
  );
}
