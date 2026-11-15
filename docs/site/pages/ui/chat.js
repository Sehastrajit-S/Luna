import DocsLayout from '../../components/DocsLayout';
import { Callout, CodeFile, NextSteps } from '../../components/Docs';

const toc = [
  { id: 'overview',       label: 'Overview' },
  { id: 'chatwindow',     label: 'ChatWindow' },
  { id: 'messagebubble',  label: 'MessageBubble' },
  { id: 'inputbar',       label: 'InputBar' },
  { id: 'confirmation',   label: 'ConfirmationBanner' },
  { id: 'plan-progress',  label: 'PlanProgressBar' },
  { id: 'usechat',        label: 'useChat hook' },
  { id: 'sse-events',     label: 'SSE event types' },
];

export default function UIChatPage() {
  return (
    <DocsLayout
      title="Chat UI"
      description="ChatWindow, MessageBubble, and InputBar — the core chat interface components and the useChat hook that drives them."
      toc={toc}
    >
      <section>
        <h2 id="overview">Overview</h2>
        <p>
          The chat interface is built from three composable React components that
          share state through Zustand. All chat logic lives in the{' '}
          <code>useChat</code> hook — the UI components are purely presentational.
        </p>
        <table>
          <thead><tr><th>Component</th><th>File</th><th>Responsibility</th></tr></thead>
          <tbody>
            <tr><td><code>ChatWindow</code></td><td><code>components/Chat/ChatWindow.tsx</code></td><td>Message list, VoiceOrb, confirmation banner, plan progress.</td></tr>
            <tr><td><code>MessageBubble</code></td><td><code>components/Chat/MessageBubble.tsx</code></td><td>Single message render — markdown, code blocks, widgets, copy.</td></tr>
            <tr><td><code>InputBar</code></td><td><code>components/Chat/InputBar.tsx</code></td><td>Auto-growing textarea, send button, keyboard shortcuts.</td></tr>
          </tbody>
        </table>
      </section>

      <section>
        <h2 id="chatwindow">ChatWindow</h2>
        <p>
          The root chat component. Renders the message scroll area, the inline
          <code>VoiceOrb</code> (when voice is active), an animated
          <code>ConfirmationBanner</code> for tool approval prompts, and a
          <code>PlanProgressBar</code> for multi-step coding agent tasks.
        </p>
        <CodeFile label="usage">
          <pre><code>{`import { ChatWindow } from './components/Chat/ChatWindow'

// Renders the full chat panel including InputBar and VoiceOrb
<ChatWindow />`}</code></pre>
        </CodeFile>
        <h3>Layout</h3>
        <ul>
          <li><strong>Top bar</strong> — conversation title, copy-all button, new-chat button.</li>
          <li><strong>Scroll area</strong> — auto-scrolls to bottom on new messages. Animated entry for each bubble.</li>
          <li><strong>Voice orb</strong> — appears below messages when voice is enabled.</li>
          <li><strong>InputBar</strong> — fixed to the bottom.</li>
        </ul>
        <h3>Confirmation banner</h3>
        <p>
          When the coding agent requests confirmation for a destructive tool call
          (<code>code_run_shell</code>, file overwrites, etc.), an amber banner
          slides in from the top with Yes / No buttons. Clicking calls
          <code>POST /api/confirm/{'{confirm_id}'}</code> and clears the banner.
        </p>
      </section>

      <section>
        <h2 id="messagebubble">MessageBubble</h2>
        <p>
          Renders a single chat message. Handles Luna and user roles differently:
        </p>
        <table>
          <thead><tr><th>Role</th><th>Alignment</th><th>Styling</th></tr></thead>
          <tbody>
            <tr><td><code>assistant</code></td><td>Left</td><td>Dark surface card, markdown rendered, code blocks with syntax highlight.</td></tr>
            <tr><td><code>user</code></td><td>Right</td><td>Accent bubble, plain text.</td></tr>
          </tbody>
        </table>
        <p>Luna messages support:</p>
        <ul>
          <li>Full GitHub-flavored markdown (headings, lists, blockquotes, tables).</li>
          <li>Fenced code blocks with copy button and language label.</li>
          <li>Dynamic widget rendering — charts, comparison cards, timelines injected via SSE.</li>
          <li>Tool call / tool result display (collapsible).</li>
          <li>Inline streaming — characters appear as SSE tokens arrive.</li>
        </ul>
        <CodeFile label="props">
          <pre><code>{`interface MessageBubbleProps {
  role: "user" | "assistant"
  content: string
  widgets?: Widget[]
  isStreaming?: boolean
}`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="inputbar">InputBar</h2>
        <p>
          Auto-growing textarea capped at 160 px height. Submits on
          <code>Enter</code> (Shift+Enter for a newline). Disabled while a response
          is streaming.
        </p>
        <CodeFile label="props">
          <pre><code>{`interface InputBarProps {
  onSend: (message: string) => void
  disabled?: boolean
}`}</code></pre>
        </CodeFile>
        <p>Displays a character count overlay when the input is non-empty.</p>
      </section>

      <section>
        <h2 id="confirmation">ConfirmationBanner</h2>
        <p>
          Reads <code>pendingConfirmation</code> from the Zustand store. When a
          confirmation request arrives (via SSE <code>confirm_request</code> event),
          the banner slides in with the message and Yes / No buttons.
        </p>
        <CodeFile label="store shape">
          <pre><code>{`// Set by the SSE handler when type === "confirm_request"
pendingConfirmation: {
  confirm_id: string
  message: string
} | null`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="plan-progress">PlanProgressBar</h2>
        <p>
          A thin progress bar that appears at the top of the chat when the coding
          agent sends a multi-step execution plan. Reads <code>activePlan</code>
          from the store.
        </p>
        <CodeFile label="store shape">
          <pre><code>{`activePlan: {
  current: number
  total: number
  label: string
} | null`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="usechat">useChat hook</h2>
        <p>
          All chat logic — sending messages, opening SSE streams, handling events,
          loading conversation history — lives in <code>hooks/useChat.ts</code>.
          Components call its methods; they never talk to the API directly.
        </p>
        <CodeFile label="exported interface">
          <pre><code>{`const {
  sendMessage,          // (text: string) => void
  loadConversation,     // (id: number) => Promise<void>
  newConversation,      // () => void
  isLoading,            // boolean — true while streaming
} = useChat()`}</code></pre>
        </CodeFile>
        <h3>sendMessage flow</h3>
        <ol>
          <li>Appends user message to the store and calls <code>POST /api/chat/stream</code>.</li>
          <li>Opens an SSE stream and processes each event type (see below).</li>
          <li>Appends tokens to the current assistant message in real-time.</li>
          <li>On <code>done</code>, marks streaming complete.</li>
        </ol>
      </section>

      <section>
        <h2 id="sse-events">SSE event types</h2>
        <p>
          The chat stream endpoint sends Server-Sent Events. Each event is a JSON
          object with a <code>type</code> field:
        </p>
        <table>
          <thead><tr><th>Type</th><th>Payload fields</th><th>Effect</th></tr></thead>
          <tbody>
            <tr><td><code>token</code></td><td><code>content</code></td><td>Appended to the current streaming message.</td></tr>
            <tr><td><code>tool_call</code></td><td><code>tool</code>, <code>args</code></td><td>Displayed as a collapsible tool-call block.</td></tr>
            <tr><td><code>tool_result</code></td><td><code>tool</code>, <code>result</code></td><td>Appended under the matching tool-call block.</td></tr>
            <tr><td><code>widget</code></td><td><code>kind</code>, <code>data</code></td><td>Renders a dynamic widget inline in the message.</td></tr>
            <tr><td><code>confirm_request</code></td><td><code>confirm_id</code>, <code>message</code></td><td>Sets <code>pendingConfirmation</code> → shows the banner.</td></tr>
            <tr><td><code>plan</code></td><td><code>current</code>, <code>total</code>, <code>label</code></td><td>Sets <code>activePlan</code> → shows the progress bar.</td></tr>
            <tr><td><code>command</code></td><td><code>type</code>, …</td><td>Executes a bracket command (browse, launch, Spotify, etc.).</td></tr>
            <tr><td><code>done</code></td><td>—</td><td>Closes the stream, marks message complete.</td></tr>
            <tr><td><code>error</code></td><td><code>message</code></td><td>Displays an error message in the chat.</td></tr>
          </tbody>
        </table>
      </section>

      <NextSteps items={[
        { href: '/ui/voice',    label: 'Component', title: 'Voice UI', desc: 'VoiceOrb and PhoneMic components.' },
        { href: '/ui/sidebar',  label: 'Component', title: 'Sidebar', desc: 'Navigation, conversation list, mood display.' },
        { href: '/api-reference', label: 'Reference', title: 'API Reference', desc: 'Full chat stream endpoint specification.' },
      ]} />
    </DocsLayout>
  );
}
