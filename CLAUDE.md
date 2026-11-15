# Luna Claude Instructions

Luna is an AI agent platform, not just a chatbot. Treat product work through the lens of a user delegating multi-app workflows to an AI employee.

## Product Direction

Target workflow:

```text
User:
Find the bug from yesterday,
check the related Jira ticket,
look at the PR,
read the Slack discussion,
create a fix,
run tests,
and open a PR.
```

The expected agent behavior is to plan the work, gather context across tools, make the code change, verify it, and hand back a concise result with links or IDs for the artifacts it touched.

## Existing Capabilities

Use these existing Luna pieces before adding new abstractions:

- Agent/planner: `server/services/planner/`, `server/services/task_planner.py`, `server/services/agent_tasks.py`
- Tool router and permissions: `server/services/tool_registry.py`, `server/services/tool_runner/`, `server/services/permission_manager.py`, `server/services/audit_log.py`
- Memory: `server/services/memory_manager/`, `server/services/memory_graph/`, `server/mcp/server_memory.py`
- Coding agent: `server/services/coding/`, `server/skills/coding-agent/`
- GitHub: `server/services/github.py`, `server/mcp/server_github.py`
- Google Workspace/Gmail/Drive/Calendar: `server/services/workspace_integrations/google.py`, `server/mcp/server_google.py`, `server/skills/workspace-suite/`
- Microsoft 365: `server/services/workspace_integrations/microsoft.py`, `server/mcp/server_microsoft.py`
- Slack channel ingestion/replies: `server/routers/channels.py`, `server/services/channel_bridge.py`
- MCP servers: `server/mcp/`
- Observability primitives: audit log, telemetry, health routes, and tool result verification.

## Current Gaps For The AI Employee Vision

Do not claim these are complete unless you have implemented and tested them:

- Jira connector
- Salesforce connector
- Notion connector
- Generic database connector
- Internal API connector framework
- Slack search/history MCP tool beyond the existing channel bridge
- End-to-end PR creation from code changes
- Kubernetes deployment manifests
- Dedicated agent evaluation harness for cross-tool workflows

When a user asks for one of these, implement the smallest production-grade connector or workflow slice needed. Use OAuth or scoped tokens, typed request/response models, permission gates for writes, audit logs for all external actions, and tests around auth failure, missing scopes, and provider errors.

## Claude Desktop MCP Setup

Luna already exposes FastMCP servers that Claude Desktop can launch over stdio. Use this config as the local Windows default for this checkout:

```json
{
  "mcpServers": {
    "luna-memory": {
      "command": "python",
      "args": ["-m", "server.mcp.server_memory"],
      "cwd": "E:/Luna"
    },
    "luna-web": {
      "command": "python",
      "args": ["-m", "server.mcp.server_web"],
      "cwd": "E:/Luna"
    },
    "luna-workspace": {
      "command": "python",
      "args": ["-m", "server.mcp.server_workspace"],
      "cwd": "E:/Luna"
    },
    "luna-github": {
      "command": "python",
      "args": ["-m", "server.mcp.server_github"],
      "cwd": "E:/Luna"
    },
    "luna-google": {
      "command": "python",
      "args": ["-m", "server.mcp.server_google"],
      "cwd": "E:/Luna"
    },
    "luna-microsoft": {
      "command": "python",
      "args": ["-m", "server.mcp.server_microsoft"],
      "cwd": "E:/Luna"
    }
  }
}
```

Claude Desktop config paths:

- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`

Required credentials live in `.env`. Never commit `.env`.

## Implementation Rules For Enterprise Connectors

- Prefer MCP-compatible tool boundaries for external systems so Claude Desktop and Luna can share the same integrations.
- Put provider-specific API code under `server/services/` or a clear provider subpackage.
- Put HTTP routes under `server/routers/` only when the Luna app needs to expose UI or webhook endpoints.
- Add tool definitions to `server/services/tool_registry.py` only for tools the Luna chat runtime should call directly.
- Add MCP servers under `server/mcp/server_<provider>.py` when Claude Desktop should call the provider directly.
- For OAuth providers, persist only the minimum needed token material and refresh through a service layer. Redact secrets in logs and user-facing errors.
- Mark write actions as risky and route them through the existing confirmation/permission flow.
- Add audit log entries for external reads and writes that include provider, action, target IDs, and outcome.
- Keep provider errors actionable: distinguish not configured, expired token, missing scope, rate limited, not found, and upstream failure.

## Agent Workflow Standard

For multi-app tasks, implement or use this loop:

1. Clarify only if the repo, project, account, or destructive action is ambiguous.
2. Plan the task into observable steps.
3. Pull context from systems of record in priority order: issue/ticket, PR/diff, discussion, docs, code, logs.
4. Store durable facts or task state only when it will help future sessions.
5. Make the smallest code or data change that solves the task.
6. Run the most relevant tests or checks.
7. Open or update the external artifact only after verification.
8. Return a concise summary with files changed, tests run, and links/IDs.

## Verification

Use the repo's existing checks first:

```bash
npm run test:smoke
npm run test:tools
npm run build --workspace=frontend
```

For backend-only changes, also run targeted Python tests or import checks when available. For docs-only Claude instruction changes, `git diff --check` is sufficient.

## Coding Conventions

- Python imports: standard library, third party, local, with blank lines between groups.
- FastAPI I/O should be async.
- Validate all user-provided paths against the configured workspace root.
- Do not silently swallow SSE or provider errors; surface a structured error event or HTTP error.
- Avoid broad rewrites. Keep changes close to the connector, tool, route, or UI surface requested.
