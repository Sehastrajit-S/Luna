import DocsLayout from '../../components/DocsLayout';
import { Callout, CodeFile, NextSteps } from '../../components/Docs';

const toc = [
  { id: 'overview',    label: 'Overview' },
  { id: 'provider',    label: 'LLM provider' },
  { id: 'coding',      label: 'Coding agent' },
  { id: 'status',      label: 'Provider status' },
  { id: 'settings-api', label: 'Settings API' },
];

export default function UISettingsPage() {
  return (
    <DocsLayout
      title="Settings UI"
      description="SettingsView component — configure LLM provider, coding model, and see live provider status from the frontend."
      toc={toc}
    >
      <section>
        <h2 id="overview">Overview</h2>
        <p>
          <code>SettingsView</code> (<code>components/Settings/SettingsView.tsx</code>)
          is the in-app configuration panel. It reads the current settings from
          <code>GET /api/settings/coding</code> and saves changes via
          <code>POST /api/settings/coding</code>. Changes take effect on the next
          request — no restart required for model or provider changes.
        </p>
        <Callout type="note">
          SettingsView does not manage the <code>.env</code> file directly — it calls
          the backend which updates the running settings object. To persist changes
          across restarts, update <code>.env</code> manually.
        </Callout>
      </section>

      <section>
        <h2 id="provider">LLM provider</h2>
        <p>
          The provider dropdown shows all eight supported providers. The selected
          provider updates <code>LLM_PROVIDER</code> at runtime.
        </p>
        <table>
          <thead><tr><th>Option</th><th>Provider</th></tr></thead>
          <tbody>
            <tr><td>Ollama (local)</td><td><code>ollama</code></td></tr>
            <tr><td>Anthropic Claude</td><td><code>anthropic</code></td></tr>
            <tr><td>Groq</td><td><code>groq</code></td></tr>
            <tr><td>Google Gemini</td><td><code>google</code></td></tr>
            <tr><td>OpenAI / Compatible</td><td><code>openai-compatible</code></td></tr>
            <tr><td>Mistral AI</td><td><code>mistral</code></td></tr>
            <tr><td>Cohere</td><td><code>cohere</code></td></tr>
            <tr><td>NVIDIA NIM</td><td><code>nvidia-nim</code></td></tr>
          </tbody>
        </table>
        <p>
          After selecting a provider, a model name field appears pre-filled with the
          currently configured model. Change it to override the default.
        </p>
      </section>

      <section>
        <h2 id="coding">Coding agent settings</h2>
        <p>
          The coding agent can use a different provider from the main chat — set
          <strong>Coding provider</strong> to "Same as chat" to inherit, or pick an
          independent provider (e.g. use Groq for fast chat but a local Ollama
          coding model for code generation).
        </p>
        <table>
          <thead><tr><th>Setting</th><th>Default</th><th>Description</th></tr></thead>
          <tbody>
            <tr><td>Coding provider</td><td>Same as chat</td><td>Independent LLM provider for the coding agent.</td></tr>
            <tr><td>Coding model</td><td><code>qwen2.5-coder:7b</code></td><td>Model name for coding requests.</td></tr>
            <tr><td>Max iterations</td><td>10</td><td>Maximum tool-call iterations per coding request.</td></tr>
            <tr><td>Shell timeout</td><td>30</td><td>Seconds before <code>code_run_shell</code> times out.</td></tr>
          </tbody>
        </table>
      </section>

      <section>
        <h2 id="status">Provider status</h2>
        <p>
          Each provider card shows a live status indicator fetched from the backend.
          A green checkmark means the provider is configured and reachable; red means
          the API key is missing or the endpoint is down.
        </p>
        <CodeFile label="GET /api/settings/coding — providers field">
          <pre><code>{`{
  "providers": {
    "ollama":            { "label": "Ollama (local)",      "configured": true  },
    "anthropic":         { "label": "Anthropic Claude",    "configured": true  },
    "groq":              { "label": "Groq",                "configured": false },
    "google":            { "label": "Google Gemini",       "configured": false },
    "openai-compatible": { "label": "OpenAI / Compatible", "configured": false }
  }
}`}</code></pre>
        </CodeFile>
        <p>Click the refresh icon to re-probe provider connectivity without leaving the settings panel.</p>
      </section>

      <section>
        <h2 id="settings-api">Settings API</h2>
        <table>
          <thead><tr><th>Endpoint</th><th>Method</th><th>Description</th></tr></thead>
          <tbody>
            <tr>
              <td><code>/api/settings/coding</code></td>
              <td>GET</td>
              <td>Returns current LLM and coding-agent settings + provider status.</td>
            </tr>
            <tr>
              <td><code>/api/settings/coding</code></td>
              <td>POST</td>
              <td>Update settings. Body: partial <code>CodingSettings</code> object.</td>
            </tr>
          </tbody>
        </table>
        <CodeFile label="POST /api/settings/coding — example body">
          <pre><code>{`{
  "llm_provider": "anthropic",
  "anthropic_model": "claude-sonnet-4-6",
  "coding_provider": "ollama",
  "coding_model": "qwen2.5-coder:14b"
}`}</code></pre>
        </CodeFile>
      </section>

      <NextSteps items={[
        { href: '/sdk-overview',    label: 'Guide',     title: 'SDK Overview', desc: 'Full .env reference for all provider configurations.' },
        { href: '/ui/sidebar',      label: 'Component', title: 'Sidebar', desc: 'The sidebar navigates to the settings view.' },
        { href: '/services/llm',    label: 'Service',   title: 'LLM Service', desc: 'How provider configuration maps to LLMClient behaviour.' },
      ]} />
    </DocsLayout>
  );
}
