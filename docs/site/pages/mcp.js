import DocsLayout from '../components/DocsLayout';
import { Callout, CodeFile, NextSteps } from '../components/Docs';

const toc = [
  { id: 'overview',    label: 'Overview' },
  { id: 'claude-desktop', label: 'Claude Desktop setup' },
  { id: 'memory',      label: 'luna-memory' },
  { id: 'web',         label: 'luna-web' },
  { id: 'workspace',   label: 'luna-workspace' },
  { id: 'github',      label: 'luna-github' },
  { id: 'google',      label: 'luna-google' },
  { id: 'microsoft',   label: 'luna-microsoft' },
  { id: 'running',     label: 'Running servers' },
];

export default function MCPPage() {
  return (
    <DocsLayout
      title="MCP Servers"
      description="Six FastMCP servers that expose Luna's memory, web tools, workspace, and cloud integrations to Claude Desktop and any MCP-compatible client."
      toc={toc}
    >
      <section>
        <h2 id="overview">Overview</h2>
        <p>
          Luna ships six{' '}
          <a href="https://modelcontextprotocol.io" target="_blank" rel="noopener noreferrer">
            Model Context Protocol
          </a>{' '}
          servers built with <strong>FastMCP</strong>. Each server exposes a focused set
          of tools and resources that any MCP-compatible client — including Claude
          Desktop — can call.
        </p>
        <table>
          <thead><tr><th>Server</th><th>Module</th><th>What it exposes</th></tr></thead>
          <tbody>
            <tr><td><code>luna-memory</code></td><td><code>backend.mcp.server_memory</code></td><td>List, search, and add facts; personality state resource.</td></tr>
            <tr><td><code>luna-web</code></td><td><code>backend.mcp.server_web</code></td><td>Web search, fetch, deep research, dataset search.</td></tr>
            <tr><td><code>luna-workspace</code></td><td><code>backend.mcp.server_workspace</code></td><td>List, read, and write files in the sandboxed workspace.</td></tr>
            <tr><td><code>luna-github</code></td><td><code>backend.mcp.server_github</code></td><td>Repos, issues, PRs, comments.</td></tr>
            <tr><td><code>luna-google</code></td><td><code>backend.mcp.server_google</code></td><td>Gmail, Google Calendar, Drive, Tasks.</td></tr>
            <tr><td><code>luna-microsoft</code></td><td><code>backend.mcp.server_microsoft</code></td><td>Outlook, Microsoft Calendar, OneDrive, To Do.</td></tr>
          </tbody>
        </table>
      </section>

      <section>
        <h2 id="claude-desktop">Claude Desktop setup</h2>
        <p>
          Add any combination of Luna's MCP servers to your Claude Desktop config file.
          On Windows: <code>%APPDATA%\Claude\claude_desktop_config.json</code>.
          On macOS: <code>~/Library/Application Support/Claude/claude_desktop_config.json</code>.
        </p>
        <CodeFile label="claude_desktop_config.json — all six servers">
          <pre><code>{`{
  "mcpServers": {
    "luna-memory": {
      "command": "python",
      "args": ["-m", "backend.mcp.server_memory"],
      "cwd": "C:/path/to/Luna"
    },
    "luna-web": {
      "command": "python",
      "args": ["-m", "backend.mcp.server_web"],
      "cwd": "C:/path/to/Luna"
    },
    "luna-workspace": {
      "command": "python",
      "args": ["-m", "backend.mcp.server_workspace"],
      "cwd": "C:/path/to/Luna"
    },
    "luna-github": {
      "command": "python",
      "args": ["-m", "backend.mcp.server_github"],
      "cwd": "C:/path/to/Luna"
    },
    "luna-google": {
      "command": "python",
      "args": ["-m", "backend.mcp.server_google"],
      "cwd": "C:/path/to/Luna"
    },
    "luna-microsoft": {
      "command": "python",
      "args": ["-m", "backend.mcp.server_microsoft"],
      "cwd": "C:/path/to/Luna"
    }
  }
}`}</code></pre>
        </CodeFile>
        <Callout type="tip">
          You don't need to run all six. Add only the servers whose tools you want
          available in Claude Desktop.
        </Callout>
      </section>

      <section>
        <h2 id="memory">luna-memory</h2>
        <p>Gives Claude Desktop read/write access to Luna's fact store and personality state.</p>

        <h3>Resources</h3>
        <table>
          <thead><tr><th>URI</th><th>Returns</th></tr></thead>
          <tbody>
            <tr><td><code>memory://facts</code></td><td>JSON array of the 100 most recent facts.</td></tr>
            <tr><td><code>memory://personality</code></td><td>JSON object of the current personality state row.</td></tr>
          </tbody>
        </table>

        <h3>Tools</h3>
        <table>
          <thead><tr><th>Tool</th><th>Args</th><th>Description</th></tr></thead>
          <tbody>
            <tr>
              <td><code>list_facts</code></td>
              <td><code>limit?</code>, <code>category?</code></td>
              <td>List stored facts, optionally filtered by category.</td>
            </tr>
            <tr>
              <td><code>search_facts</code></td>
              <td><code>query</code>, <code>limit?</code></td>
              <td>Full-text search across fact content.</td>
            </tr>
            <tr>
              <td><code>add_fact</code></td>
              <td><code>content</code>, <code>category</code>, <code>importance?</code></td>
              <td>Store a new fact with optional importance (default 0.7).</td>
            </tr>
          </tbody>
        </table>

        <h3>Configuration</h3>
        <p>No extra env vars needed — reads Luna's SQLite database directly.</p>
      </section>

      <section>
        <h2 id="web">luna-web</h2>
        <p>Exposes Luna's web research stack to Claude Desktop.</p>

        <h3>Tools</h3>
        <table>
          <thead><tr><th>Tool</th><th>Args</th><th>Description</th></tr></thead>
          <tbody>
            <tr>
              <td><code>web_search</code></td>
              <td><code>query</code></td>
              <td>DuckDuckGo search — returns numbered results with snippets.</td>
            </tr>
            <tr>
              <td><code>web_fetch</code></td>
              <td><code>url</code></td>
              <td>Fetch a URL and return readable text content.</td>
            </tr>
            <tr>
              <td><code>web_research</code></td>
              <td><code>query</code></td>
              <td>Search + fetch top sources → cited research context.</td>
            </tr>
            <tr>
              <td><code>dataset_search</code></td>
              <td><code>query</code></td>
              <td>Search Kaggle, UCI, Hugging Face, data.gov, NOAA, World Bank.</td>
            </tr>
          </tbody>
        </table>

        <h3>Configuration</h3>
        <p>No API key required — uses DuckDuckGo. Configure <code>BRAVE_SEARCH_API_KEY</code> in <code>.env</code> for higher-quality results.</p>
      </section>

      <section>
        <h2 id="workspace">luna-workspace</h2>
        <p>
          Sandboxed file access to Luna's workspace directory (<code>data/workspace/</code>).
          All paths are restricted to the workspace root — paths that escape are rejected.
        </p>

        <h3>Resources</h3>
        <table>
          <thead><tr><th>URI template</th><th>Returns</th></tr></thead>
          <tbody>
            <tr><td><code>{'workspace://{path}'}</code></td><td>Content of the file at <code>path</code> relative to workspace root.</td></tr>
          </tbody>
        </table>

        <h3>Tools</h3>
        <table>
          <thead><tr><th>Tool</th><th>Args</th><th>Description</th></tr></thead>
          <tbody>
            <tr>
              <td><code>workspace_list</code></td>
              <td><code>path?</code></td>
              <td>List files and directories. Empty path = workspace root.</td>
            </tr>
            <tr>
              <td><code>workspace_read</code></td>
              <td><code>path</code></td>
              <td>Read a text file from the workspace.</td>
            </tr>
            <tr>
              <td><code>workspace_write</code></td>
              <td><code>path</code>, <code>content</code></td>
              <td>Write or overwrite a text file. Parent dirs created automatically.</td>
            </tr>
          </tbody>
        </table>

        <h3>Configuration</h3>
        <CodeFile label=".env">
          <pre><code>{`WORKSPACE_ROOT=data/workspace   # default — relative to Luna root`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="github">luna-github</h2>
        <p>GitHub integration via the GitHub REST API.</p>

        <h3>Tools</h3>
        <table>
          <thead><tr><th>Tool</th><th>Args</th><th>Description</th></tr></thead>
          <tbody>
            <tr><td><code>list_repos</code></td><td>none</td><td>Your repositories, sorted by last updated.</td></tr>
            <tr><td><code>list_issues</code></td><td><code>repo</code>, <code>state?</code></td><td>Issues in a repo (<code>"owner/repo"</code> format).</td></tr>
            <tr><td><code>create_issue</code></td><td><code>repo</code>, <code>title</code>, <code>body?</code></td><td>Create a new issue.</td></tr>
            <tr><td><code>list_prs</code></td><td><code>repo</code>, <code>state?</code></td><td>Pull requests in a repo.</td></tr>
            <tr><td><code>get_pr</code></td><td><code>repo</code>, <code>number</code></td><td>Full PR details including diff.</td></tr>
            <tr><td><code>add_comment</code></td><td><code>repo</code>, <code>issue_number</code>, <code>body</code></td><td>Comment on an issue or PR.</td></tr>
          </tbody>
        </table>

        <h3>Configuration</h3>
        <CodeFile label=".env">
          <pre><code>{`GITHUB_TOKEN=ghp_...   # Personal access token with repo scope`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="google">luna-google</h2>
        <p>Google Workspace integration — Gmail, Calendar, Drive, and Tasks.</p>

        <h3>Tools</h3>
        <table>
          <thead><tr><th>Service</th><th>Tool</th><th>Description</th></tr></thead>
          <tbody>
            <tr><td>Gmail</td><td><code>gmail_search</code></td><td>Search messages (Gmail query syntax).</td></tr>
            <tr><td>Gmail</td><td><code>gmail_send</code></td><td>Send email to a recipient.</td></tr>
            <tr><td>Gmail</td><td><code>gmail_read</code></td><td>Read full message by ID.</td></tr>
            <tr><td>Calendar</td><td><code>calendar_list_events</code></td><td>Events in a date range.</td></tr>
            <tr><td>Calendar</td><td><code>calendar_create_event</code></td><td>Create an event with title, start, end.</td></tr>
            <tr><td>Drive</td><td><code>drive_list</code></td><td>List files in Drive.</td></tr>
            <tr><td>Drive</td><td><code>drive_read</code></td><td>Read a Drive file by ID.</td></tr>
            <tr><td>Tasks</td><td><code>tasks_list</code></td><td>List task lists and tasks.</td></tr>
            <tr><td>Tasks</td><td><code>tasks_create</code></td><td>Create a task.</td></tr>
          </tbody>
        </table>

        <h3>Configuration</h3>
        <CodeFile label=".env">
          <pre><code>{`GOOGLE_WORKSPACE_ACCESS_TOKEN=ya29...   # OAuth 2.0 access token
# or
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="microsoft">luna-microsoft</h2>
        <p>Microsoft 365 integration via Microsoft Graph — Outlook, Calendar, OneDrive, To Do.</p>

        <h3>Tools</h3>
        <table>
          <thead><tr><th>Service</th><th>Tool</th><th>Description</th></tr></thead>
          <tbody>
            <tr><td>Outlook</td><td><code>outlook_search</code></td><td>Search Outlook messages.</td></tr>
            <tr><td>Outlook</td><td><code>outlook_send</code></td><td>Send email via Outlook.</td></tr>
            <tr><td>Calendar</td><td><code>ms_calendar_list</code></td><td>List calendar events in a date range.</td></tr>
            <tr><td>Calendar</td><td><code>ms_calendar_create</code></td><td>Create a calendar event.</td></tr>
            <tr><td>OneDrive</td><td><code>onedrive_list</code></td><td>List files in OneDrive.</td></tr>
            <tr><td>OneDrive</td><td><code>onedrive_read</code></td><td>Read a file from OneDrive.</td></tr>
            <tr><td>To Do</td><td><code>todo_list</code></td><td>List task lists and tasks.</td></tr>
            <tr><td>To Do</td><td><code>todo_create</code></td><td>Create a task in a list.</td></tr>
          </tbody>
        </table>

        <h3>Configuration</h3>
        <CodeFile label=".env">
          <pre><code>{`MICROSOFT_WORKSPACE_ACCESS_TOKEN=eyJ0...   # Microsoft Graph OAuth token
# or
MICROSOFT_CLIENT_ID=...
MICROSOFT_CLIENT_SECRET=...
MICROSOFT_TENANT_ID=...`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="running">Running servers standalone</h2>
        <p>
          Each server can be run independently as a subprocess. Claude Desktop launches
          them automatically when configured; you can also run them manually for
          development or testing:
        </p>
        <CodeFile label="terminal">
          <pre><code>{`# From the Luna root directory:
python -m backend.mcp.server_memory
python -m backend.mcp.server_web
python -m backend.mcp.server_workspace
python -m backend.mcp.server_github
python -m backend.mcp.server_google
python -m backend.mcp.server_microsoft`}</code></pre>
        </CodeFile>
        <Callout type="note">
          MCP servers communicate over stdio — they're not HTTP servers and don't bind
          a port. The FastMCP library handles the JSON-RPC transport automatically.
        </Callout>

        <h3>Adding a new MCP server</h3>
        <CodeFile label="backend/mcp/server_example.py">
          <pre><code>{`from mcp.server.fastmcp import FastMCP

mcp = FastMCP("luna-example")

@mcp.tool()
def greet(name: str) -> str:
    """Say hello."""
    return f"Hello, {name}!"

@mcp.resource("example://hello")
def hello_resource() -> str:
    """A static greeting resource."""
    return "Hello from Luna!"

if __name__ == "__main__":
    mcp.run()`}</code></pre>
        </CodeFile>
        <p>
          Add it to <code>claude_desktop_config.json</code> using the same pattern as
          the other servers. No registration in Luna's code is required — MCP servers
          are standalone processes.
        </p>
      </section>

      <NextSteps items={[
        { href: '/services/memory-manager', label: 'Service', title: 'Memory Manager', desc: 'The memory service that luna-memory exposes over MCP.' },
        { href: '/services/tool-runner',    label: 'Service', title: 'Tool Runner', desc: 'The same web tools used by luna-web are available in the tool runner.' },
        { href: '/sdk-overview',            label: 'Guide',   title: 'SDK Overview', desc: 'Other ways to integrate Luna with external applications.' },
      ]} />
    </DocsLayout>
  );
}
