from __future__ import annotations

import subprocess
import unittest

from tests.tools import _bootstrap


class CliToolTests(unittest.TestCase):
    def test_cli_entrypoint_syntax(self) -> None:
        result = subprocess.run(
            ["node", "--check", "interfaces/cli/luna.mjs"],
            cwd=_bootstrap.ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_cli_chat_handles_full_stream_event_surface(self) -> None:
        source = (_bootstrap.ROOT / "interfaces" / "cli" / "luna.mjs").read_text(encoding="utf-8")
        for marker in (
            "confirmation_required",
            "/api/chat/confirm/",
            "/api/coding/settings",
            "/api/integrations/workspace/status",
            "/api/agent/enterprise/bugfix",
            "statusCli",
            "modelCli",
            "connectAppCli",
            "updateCli",
            "configureGithubToken",
            "validateGithubToken",
            "normalizeGithubToken",
            "reloadBackendConfig",
            "/api/system/config/reload",
            "writeEnvValue",
            "github_token: ",
            "install:command",
            "npm i -g",
            "npx",
            "/model",
            "/connect_app",
            "/apps",
            "/status",
            "/skills",
            "/permissions",
            "/crew",
            "/bugfix",
            "/update",
            "plan_progress",
            "plan_done",
            "commands",
            "proactive",
            "data.type === 'token'",
            "--yes",
            "--no",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, source)

    def test_cli_chat_does_not_request_short_generation_cap(self) -> None:
        source = (_bootstrap.ROOT / "server" / "routers" / "chat.py").read_text(encoding="utf-8")
        self.assertNotIn("num_predict=192 if cli", source)
        self.assertNotIn("num_ctx=2048 if cli", source)

    def test_cli_chat_preserves_spacing_between_streamed_message_parts(self) -> None:
        source = (_bootstrap.ROOT / "server" / "services" / "chat_pipeline" / "stages.py").read_text(encoding="utf-8")
        self.assertIn('content = f"\\n\\n{part}" if ctx.cli and index > 0 else part', source)

    def test_cli_prompt_disables_markdown_bold(self) -> None:
        source = (_bootstrap.ROOT / "server" / "services" / "prompt_builder.py").read_text(encoding="utf-8")
        self.assertIn("Never output **bold**", source)

    def test_cli_visible_response_strips_markdown_bold(self) -> None:
        from types import SimpleNamespace

        from server.services.chat_pipeline.stages import _build_visible_response_events

        ctx = SimpleNamespace(
            full_response="**Summary:** fixed the issue",
            cli=True,
            had_tool_call=True,
        )

        rendered = "".join(_build_visible_response_events(ctx))
        self.assertNotIn("**", rendered)
        self.assertIn("Summary:", rendered)

    def test_chat_stream_keeps_references_when_body_has_multiple_parts(self) -> None:
        source = (_bootstrap.ROOT / "server" / "services" / "chat_pipeline" / "stages.py").read_text(encoding="utf-8")
        self.assertIn("refs_match = re.search", source)
        self.assertIn("body_parts[:_max_parts] + ([refs_text] if refs_text else [])", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
