"""Remote access: requests through a proxy (tailscale serve) need Luna's token;
local apps on the same machine don't."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.tools import _bootstrap  # noqa: F401

from starlette.applications import Starlette
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from server.core import access
from server.services import settings_store

TOKEN = "s3cret-token"
PROXIED = {"X-Forwarded-Host": "my-pc.tailnet.ts.net:8899", "X-Forwarded-For": "100.101.102.103"}


async def _ok(request):
    return JSONResponse({"ok": True})


async def _page(request):
    return PlainTextResponse("<html></html>")


def _app(require_token_on_lan: bool = False) -> Starlette:
    app = Starlette(routes=[
        Route("/api/settings", _ok, methods=["GET", "OPTIONS"]),
        Route("/api/system/health", _ok),
        Route("/api/channels/slack", _ok, methods=["POST"]),
        Route("/api/voice/events", _ok),
        Route("/", _page),
    ])
    app.add_middleware(access.RemoteAccessMiddleware, require_token_on_lan=require_token_on_lan)
    return app


class RemoteAccessTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        token_path = Path(self._tmp.name) / "local_api_token"
        token_path.write_text(TOKEN, encoding="utf-8")
        patcher = mock.patch.object(settings_store, "TOKEN_PATH", token_path)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._tmp.cleanup)

    def _client(self, client_host: str = "127.0.0.1", **kwargs) -> TestClient:
        return TestClient(_app(**kwargs), client=(client_host, 50000))

    def test_local_request_needs_no_token(self) -> None:
        self.assertEqual(self._client().get("/api/settings").status_code, 200)

    def test_proxied_request_without_token_is_rejected(self) -> None:
        res = self._client().get("/api/settings", headers=PROXIED)
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()["code"], "remote_token_required")

    def test_proxied_request_with_wrong_token_is_rejected(self) -> None:
        res = self._client().get("/api/settings", headers={**PROXIED, "X-Luna-Token": "nope"})
        self.assertEqual(res.status_code, 401)

    def test_proxied_request_with_token_header_passes(self) -> None:
        res = self._client().get("/api/settings", headers={**PROXIED, "X-Luna-Token": TOKEN})
        self.assertEqual(res.status_code, 200)

    def test_token_in_query_string_works_for_event_streams(self) -> None:
        res = self._client().get(f"/api/voice/events?luna_token={TOKEN}", headers=PROXIED)
        self.assertEqual(res.status_code, 200)

    def test_any_tailscale_header_marks_request_remote(self) -> None:
        res = self._client().get("/api/settings", headers={"Tailscale-User-Login": "me@example.com"})
        self.assertEqual(res.status_code, 401)

    def test_public_routes_stay_open_through_proxy(self) -> None:
        client = self._client()
        self.assertEqual(client.get("/api/system/health", headers=PROXIED).status_code, 200)
        self.assertEqual(client.post("/api/channels/slack", headers=PROXIED).status_code, 200)
        self.assertEqual(client.get("/", headers=PROXIED).status_code, 200)

    def test_cors_preflight_passes_without_token(self) -> None:
        res = self._client().options("/api/settings", headers=PROXIED)
        self.assertEqual(res.status_code, 200)

    def test_lan_clients_are_open_by_default(self) -> None:
        self.assertEqual(self._client("192.168.1.20").get("/api/settings").status_code, 200)

    def test_lan_clients_need_token_when_enabled(self) -> None:
        lan = self._client("192.168.1.20", require_token_on_lan=True)
        self.assertEqual(lan.get("/api/settings").status_code, 401)
        self.assertEqual(lan.get("/api/settings", headers={"X-Luna-Token": TOKEN}).status_code, 200)
        local = self._client("127.0.0.1", require_token_on_lan=True)
        self.assertEqual(local.get("/api/settings").status_code, 200)

    def test_rejects_when_server_has_no_token_file(self) -> None:
        with mock.patch.object(settings_store, "TOKEN_PATH", Path(self._tmp.name) / "missing" / "token"):
            res = self._client().get("/api/settings", headers={**PROXIED, "X-Luna-Token": ""})
        self.assertEqual(res.status_code, 401)


class ServerWiringTests(unittest.TestCase):
    def test_main_app_installs_remote_access_middleware(self) -> None:
        from server.main import app
        self.assertIn(access.RemoteAccessMiddleware, [m.cls for m in app.user_middleware])


if __name__ == "__main__":
    unittest.main(verbosity=2)
