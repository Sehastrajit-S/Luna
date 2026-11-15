from __future__ import annotations

import unittest

from tests.tools import _bootstrap  # noqa: F401


class ScreenToolTests(unittest.TestCase):
    def test_safe_screen_tools_return_dicts(self) -> None:
        from backend.services.screen_perception import execute_screen_tool

        for tool_name, args in (
            ("get_active_window", {}),
            ("find_text_on_screen", {"query": "__unlikely_luna_test_text__"}),
        ):
            with self.subTest(tool_name=tool_name):
                result = execute_screen_tool(tool_name, args)
                self.assertIsInstance(result, dict)

    def test_unknown_screen_tool_reports_error(self) -> None:
        from backend.services.screen_perception import execute_screen_tool

        result = execute_screen_tool("__missing__", {})
        self.assertIn("error", result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
