from __future__ import annotations

import unittest

from tests.tools import _bootstrap  # noqa: F401


class AppLauncherToolTests(unittest.TestCase):
    def test_profile_catalog_is_available(self) -> None:
        from backend.services.app_launcher import APP_PROFILES, list_app_profiles, list_known_apps

        profiles = list_app_profiles()
        known = list_known_apps()
        self.assertGreaterEqual(len(APP_PROFILES), 20)
        self.assertIn("profiles", profiles)
        self.assertGreaterEqual(len(profiles["profiles"]), 20)
        self.assertIn("sticky notes", known)

    def test_common_app_discovery_does_not_launch(self) -> None:
        from backend.services.app_launcher import find_app

        for app in ("calculator", "terminal", "vscode", "spotify"):
            with self.subTest(app=app):
                ok, target = find_app(app)
                self.assertIsInstance(ok, bool)
                self.assertIsInstance(target, str)


if __name__ == "__main__":
    unittest.main(verbosity=2)
