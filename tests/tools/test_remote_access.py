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
OWNER = "owner@example.com"
PHONE_TS_IP = "100.74.251.51"
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
        trusted = mock.patch.object(access, "trusted_logins", mock.AsyncMock(return_value=frozenset({OWNER})))
        trusted.start()
        self.addCleanup(trusted.stop)
        self.addCleanup(self._tmp.cleanup)

    def _client(self, client_host: str = "127.0.0.1", server_host: str = "127.0.0.1", **kwargs) -> TestClient:
        # server_host is the address the connection arrived on (Luna binds 127.0.0.1 by default).
        return TestClient(_app(**kwargs), base_url=f"http://{server_host}", client=(client_host, 50000))

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
        res = self._client().get("/api/settings", headers={"Tailscale-User-Login": "someone-else@example.com"})
        self.assertEqual(res.status_code, 401)

    def test_owner_device_via_tailscale_needs_no_token(self) -> None:
        # tailscaled passes on the remote device's tailnet IP as the client address.
        res = self._client(PHONE_TS_IP).get("/api/settings", headers={**PROXIED, "Tailscale-User-Login": OWNER.upper()})
        self.assertEqual(res.status_code, 200)

    def test_other_tailnet_user_still_needs_token(self) -> None:
        headers = {**PROXIED, "Tailscale-User-Login": "guest@example.com"}
        self.assertEqual(self._client().get("/api/settings", headers=headers).status_code, 401)
        self.assertEqual(self._client().get("/api/settings", headers={**headers, "X-Luna-Token": TOKEN}).status_code, 200)

    def test_funnel_traffic_is_never_trusted_by_identity(self) -> None:
        headers = {**PROXIED, "Tailscale-User-Login": OWNER, "Tailscale-Funnel-Request": "?1"}
        self.assertEqual(self._client().get("/api/settings", headers=headers).status_code, 401)

    def test_identity_header_on_direct_network_connection_is_ignored(self) -> None:
        # With host=0.0.0.0 a device can connect straight to the LAN/tailnet address
        # and forge the header; only connections arriving on loopback come via tailscaled.
        for device in ("192.168.1.20", PHONE_TS_IP):
            res = self._client(device, server_host="192.168.1.5").get(
                "/api/settings", headers={**PROXIED, "Tailscale-User-Login": OWNER})
            self.assertEqual(res.status_code, 401, device)

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

    def test_hello_reports_whether_caller_is_authorized(self) -> None:
        from server.main import app
        client = TestClient(app, base_url="http://127.0.0.1", client=(PHONE_TS_IP, 50000))
        with mock.patch.object(access, "trusted_logins", mock.AsyncMock(return_value=frozenset({OWNER}))):
            stranger = client.get("/api/remote/hello", headers=PROXIED).json()
            owner = client.get("/api/remote/hello", headers={**PROXIED, "Tailscale-User-Login": OWNER}).json()
            local = client.get("/api/remote/hello").json()
        self.assertTrue(stranger["luna"])
        self.assertEqual((stranger["authorized"], stranger["via"]), (False, None))
        self.assertEqual((owner["authorized"], owner["via"]), (True, "tailscale"))
        self.assertEqual(local["via"], "local")


class TailscaleIdentityTests(unittest.TestCase):
    STATUS = '{"Self": {"UserID": 42}, "User": {"42": {"LoginName": "Owner@Example.com"}}}'

    def _load(self, **overrides):
        from server.services import tailscale_identity as ti
        values = {"tailscale_trust_owner": True, "tailscale_trusted_logins": "", **overrides}
        done = mock.Mock(stdout=self.STATUS)
        with mock.patch.multiple(ti.settings, **values), \
             mock.patch.object(ti.shutil, "which", return_value="tailscale"), \
             mock.patch.object(ti.subprocess, "run", return_value=done):
            return ti._load()

    def test_owner_login_is_trusted(self) -> None:
        self.assertEqual(self._load(), frozenset({"owner@example.com"}))

    def test_extra_logins_and_owner_opt_out(self) -> None:
        logins = self._load(tailscale_trust_owner=False, tailscale_trusted_logins="Friend@Example.com, ")
        self.assertEqual(logins, frozenset({"friend@example.com"}))

    def test_no_tailscale_means_no_identity_trust(self) -> None:
        from server.services import tailscale_identity as ti
        with mock.patch.object(ti.shutil, "which", return_value=None):
            self.assertEqual(ti._owner_login(), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
