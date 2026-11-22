from __future__ import annotations

import inspect
import unittest

from tests.tools import _bootstrap  # noqa: F401


class RegistryToolTests(unittest.TestCase):
    def test_every_registered_tool_has_a_dispatch_handler(self) -> None:
        from server.services.tool_runner import execute_tool_call
        from server.services.tool_registry import TOOL_REGISTRY

        source = inspect.getsource(execute_tool_call)
        missing = [
            name for name in TOOL_REGISTRY
            if f'"{name}"' not in source and not (
                name.startswith("github_") and 'tool_name.startswith("github_")' in source
            )
        ]
        self.assertEqual(missing, [])

    def test_every_registered_tool_has_a_dedicated_tester_or_skip_reason(self) -> None:
        from server.services.tool_registry import TOOL_REGISTRY

        covered = {
            "launch_app", "close_app", "list_apps",
            "list_open_apps",  # test_app_resolution.py
            "open_website",  # test_browser_open.py
            "message_contact", "open_chat",  # test_messaging.py
            "read_website",  # test_site_reader.py
            "brief_messages",  # test_messages_brief.py
            "project_read_file", "claude_code", "check_claude_code",  # test_projects.py
            "spotify_play", "spotify_pause", "spotify_next", "spotify_prev", "spotify_queue",
            "switch_audio",
            "create_task", "create_event",
            "take_screenshot", "find_text_on_screen", "get_active_window", "click_at", "type_text",
            "browse_url", "web_search", "use_skill", "web_research", "dataset_search", "web_fetch", "web_download_file",
            "browser_open", "browser_read",
            "workspace_read", "workspace_write", "workspace_read_base64", "workspace_write_base64",
            "list_skills", "create_agent_task", "search_conversation",
            "get_volume", "set_volume", "mute_audio", "unmute_audio",
            "get_brightness", "set_brightness", "lock_screen", "turn_off_display", "sleep_system",
            "get_clipboard", "set_clipboard", "get_system_info",
            "calculate", "save_memory", "forget_memory", "daily_news",  # test_grounding.py
            "compare_store_prices",  # test_store_prices.py
            "github_list_repos", "github_list_issues", "github_create_issue", "github_comment",
            "github_list_prs", "github_get_pr", "github_summarize_user_pr", "github_create_pr",
            "slack_search_messages", "slack_channel_history",
            "jira_search_issues", "jira_get_issue",
            "enterprise_bugfix_workflow",
            "google_workspace", "microsoft_workspace",
            "code_read_file", "code_write_file", "code_list_files", "code_search", "code_run_shell",
            "code_edit_file", "code_delete_file", "code_rename_file", "code_web_search", "code_web_fetch",
        }
        self.assertEqual(set(TOOL_REGISTRY) - covered, set())


if __name__ == "__main__":
    unittest.main(verbosity=2)
