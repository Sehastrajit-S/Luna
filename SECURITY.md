# Security Policy

## Supported versions

Security fixes are applied to the latest commit on `main`. There are no versioned release branches at this time.

## Reporting a vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Report privately by emailing the maintainer or using [GitHub's private vulnerability reporting](https://github.com/Sehastrajit-S/Luna/security/advisories/new).

Include:

- Affected commit or version
- Clear steps to reproduce
- Expected vs. actual impact
- Relevant logs with all secrets and personal data removed

You will receive an acknowledgement within 72 hours. If a fix is warranted, a patch will be prepared before any public disclosure.

## Scope

Areas of particular concern:

| Area | Risk |
|---|---|
| JWT secret exposure | Auth bypass for Business variant |
| LLM prompt injection via user input | Unintended tool execution |
| Path traversal in workspace write tools | Arbitrary file write |
| Insecure deserialization in SSE event handling | Client-side code execution |
| Hardcoded secrets in `.env.example` | Credential exposure |
| Third-party channel webhooks (Telegram, Slack, Discord) | Unauthenticated message injection |

## What is not in scope

- Denial-of-service via local Ollama resource exhaustion (local deployment, no auth)
- Issues that require physical access to the machine running Luna
- Vulnerabilities in upstream dependencies — report those directly to the dependency maintainer

## Secret handling for contributors

Never commit:

- `.env` files or any file containing real API keys, tokens, or passwords
- Local databases (`*.db`, `*.sqlite`) which may contain chat history or memory
- `spotify_token.json`, `audio_prefs.json`, or any runtime-generated credential file
- Chat logs, personality state, or generated memory stores

The `.gitignore` blocks these by default. If you accidentally commit a secret, rotate it immediately — git history is public.

## Dependency security

Run `npm audit` and `pip-audit` (or `pip install pip-audit && pip-audit`) before opening PRs that add or upgrade dependencies. Pin versions in `requirements.txt` and `package.json` rather than using open ranges.
