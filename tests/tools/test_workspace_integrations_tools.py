from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from tests.tools import _bootstrap  # noqa: F401


class WorkspaceIntegrationToolTests(unittest.TestCase):
    def test_workspace_status_lists_supported_services(self) -> None:
        from backend.main import app

        client = TestClient(app)
        response = client.get("/api/integrations/workspace/status")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("gmail", data["google"]["services"])
        self.assertIn("drive", data["google"]["services"])
        self.assertIn("mail", data["microsoft"]["services"])
        self.assertIn("teams", data["microsoft"]["services"])

    def test_google_workspace_missing_token_is_clean_error(self) -> None:
        from backend.main import app
        from backend.config import settings

        original = settings.google_workspace_access_token
        original_refresh = settings.google_workspace_refresh_token
        settings.google_workspace_access_token = ""
        settings.google_workspace_refresh_token = ""
        client = TestClient(app)
        try:
            response = client.post(
                "/api/integrations/workspace/google/drive/search_files",
                json={"query": "trashed=false", "limit": 1},
            )
        finally:
            settings.google_workspace_access_token = original
            settings.google_workspace_refresh_token = original_refresh

        self.assertEqual(response.status_code, 400)
        self.assertIn("access token is not configured", response.json()["detail"])

    def test_microsoft_workspace_missing_token_is_clean_error(self) -> None:
        from backend.main import app
        from backend.config import settings

        original = settings.microsoft_workspace_access_token
        original_refresh = settings.microsoft_workspace_refresh_token
        settings.microsoft_workspace_access_token = ""
        settings.microsoft_workspace_refresh_token = ""
        client = TestClient(app)
        try:
            response = client.post(
                "/api/integrations/workspace/microsoft/mail/search_messages",
                json={"query": "status", "limit": 1},
            )
        finally:
            settings.microsoft_workspace_access_token = original
            settings.microsoft_workspace_refresh_token = original_refresh

        self.assertEqual(response.status_code, 400)
        self.assertIn("access token is not configured", response.json()["detail"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
