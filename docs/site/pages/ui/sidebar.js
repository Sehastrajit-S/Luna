import DocsLayout from '../../components/DocsLayout';
import { Callout, CodeFile, NextSteps } from '../../components/Docs';

const toc = [
  { id: 'overview',      label: 'Overview' },
  { id: 'sidebar',       label: 'Sidebar' },
  { id: 'nav-items',     label: 'Navigation items' },
  { id: 'conversations', label: 'Conversation list' },
  { id: 'mood-display',  label: 'Mood display' },
  { id: 'titlebar',      label: 'TitleBar' },
  { id: 'away-screen',   label: 'AwayScreen' },
  { id: 'speaker-picker', label: 'SpeakerPicker' },
];

export default function UISidebarPage() {
  return (
    <DocsLayout
      title="Sidebar & Layout"
      description="Sidebar navigation, conversation list, TitleBar, AwayScreen, and SpeakerPicker — the chrome components that wrap the main content area."
      toc={toc}
    >
      <section>
        <h2 id="overview">Overview</h2>
        <p>
          The app shell is composed of four layout-level components that sit outside the
          main content panel:
        </p>
        <table>
          <thead><tr><th>Component</th><th>File</th><th>Responsibility</th></tr></thead>
          <tbody>
            <tr><td><code>Sidebar</code></td><td><code>Layout/Sidebar.tsx</code></td><td>Nav, conversation list, mood indicator, clock.</td></tr>
            <tr><td><code>TitleBar</code></td><td><code>Layout/TitleBar.tsx</code></td><td>Electron drag region + window controls (min/max/close).</td></tr>
            <tr><td><code>AwayScreen</code></td><td><code>Layout/AwayScreen.tsx</code></td><td>Overlay shown when the user is marked away.</td></tr>
            <tr><td><code>SpeakerPicker</code></td><td><code>Layout/SpeakerPicker.tsx</code></td><td>Audio output device selector.</td></tr>
          </tbody>
        </table>
      </section>

      <section>
        <h2 id="sidebar">Sidebar</h2>
        <p>
          Fixed 240 px left panel. Contains the Luna logo, navigation links, conversation
          history list, current mood emoji, live clock, and the online/offline status indicator
          for the Ollama backend.
        </p>
        <CodeFile label="usage">
          <pre><code>{`import { Sidebar } from './components/Layout/Sidebar'

// Rendered once at the app root, always visible
<Sidebar />`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="nav-items">Navigation items</h2>
        <p>
          Each nav item maps a <code>View</code> identifier to an icon and a label.
          Clicking calls <code>setView(id)</code> on the Zustand store.
        </p>
        <table>
          <thead><tr><th>View ID</th><th>Label</th><th>Icon</th></tr></thead>
          <tbody>
            <tr><td><code>chat</code></td><td>Chat</td><td>MessageCircle</td></tr>
            <tr><td><code>memory</code></td><td>Memory</td><td>Brain</td></tr>
            <tr><td><code>calendar</code></td><td>Calendar</td><td>Calendar</td></tr>
            <tr><td><code>activities</code></td><td>Activities</td><td>Activity</td></tr>
            <tr><td><code>agent</code></td><td>Agent</td><td>ShieldCheck</td></tr>
            <tr><td><code>sleep</code></td><td>Sleep</td><td>Moon</td></tr>
            <tr><td><code>train</code></td><td>Train</td><td>Dna</td></tr>
            <tr><td><code>extract</code></td><td>Extract</td><td>FlaskConical</td></tr>
            <tr><td><code>settings</code></td><td>Settings</td><td>Settings</td></tr>
          </tbody>
        </table>
        <p>Active view is highlighted with a left border accent and a dimmed background.</p>
      </section>

      <section>
        <h2 id="conversations">Conversation list</h2>
        <p>
          Below the nav links, the sidebar shows the conversation history loaded from
          <code>GET /api/conversations</code>. Each item shows the conversation title
          and a relative timestamp.
        </p>
        <p>Actions:</p>
        <ul>
          <li><strong>Click</strong> — loads the conversation into the chat view.</li>
          <li><strong>Trash icon</strong> (hover to reveal) — deletes the conversation after confirmation.</li>
          <li><strong>+ button</strong> (at the top of the list) — starts a new conversation.</li>
        </ul>
      </section>

      <section>
        <h2 id="mood-display">Mood display</h2>
        <p>
          The bottom of the sidebar shows Luna's current mood as an emoji badge,
          loaded from the <code>personality</code> field of the Zustand store.
          The store is populated by the chat hook from SSE personality update events.
        </p>
        <CodeFile label="mood emoji map">
          <pre><code>{`{
  happy:      "😊",
  playful:    "😄",
  thoughtful: "🤔",
  excited:    "✨",
  concerned:  "💙",
  warm:       "🌙",
  neutral:    "😌",
  curious:    "🔍",
  melancholic:"🌧",
}`}</code></pre>
        </CodeFile>
        <p>Defaults to the neutral emoji if personality data hasn't loaded yet.</p>
      </section>

      <section>
        <h2 id="titlebar">TitleBar</h2>
        <p>
          A 32 px draggable region at the top of the window. Contains the app name
          and, on the right, traffic-light-style window controls (minimize, maximize,
          close) implemented via <code>window.electronAPI</code>.
        </p>
        <Callout type="note">
          TitleBar is Electron-only. In the web variant (running in a browser), it
          renders as a simple header without window controls.
        </Callout>
        <CodeFile label="usage">
          <pre><code>{`import { TitleBar } from './components/Layout/TitleBar'

// Rendered at the very top of the app root, above Sidebar + content
<TitleBar />`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="away-screen">AwayScreen</h2>
        <p>
          An animated overlay that appears over the entire app when the user is marked
          away (<code>isAway === true</code> in the store). Shows the current time and
          a dismissal hint. Clicking anywhere clears the away state.
        </p>
        <p>Away state is set by:</p>
        <ul>
          <li>The command parser emitting an <code>[AWAY]</code> command (farewell detection).</li>
          <li>The scheduler's <code>state_aware_proactive()</code> function.</li>
          <li>Programmatic calls to <code>POST /api/away</code>.</li>
        </ul>
        <CodeFile label="usage">
          <pre><code>{`import { AwayScreen } from './components/Layout/AwayScreen'

// Conditionally mounted at the app root
{isAway && <AwayScreen />}`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="speaker-picker">SpeakerPicker</h2>
        <p>
          A floating panel that lists available audio output devices and lets the user
          switch the default speaker. Each device is shown with its name; clicking one
          calls the <code>switch_audio</code> tool via <code>POST /api/tools/execute</code>.
        </p>
        <p>Appears as a popover triggered from the audio icon in the chat header.</p>
        <CodeFile label="usage">
          <pre><code>{`import { SpeakerPicker } from './components/Layout/SpeakerPicker'

// Rendered as an absolute-positioned popover
{showSpeakerPicker && <SpeakerPicker onClose={() => setShowSpeakerPicker(false)} />}`}</code></pre>
        </CodeFile>
      </section>

      <NextSteps items={[
        { href: '/ui/chat',     label: 'Component', title: 'Chat UI', desc: 'The main content panel rendered to the right of the sidebar.' },
        { href: '/ui/settings', label: 'Component', title: 'Settings UI', desc: 'The settings view accessible from the sidebar nav.' },
        { href: '/ui/voice',    label: 'Component', title: 'Voice UI', desc: 'VoiceOrb embedded in the sidebar bottom area.' },
      ]} />
    </DocsLayout>
  );
}
