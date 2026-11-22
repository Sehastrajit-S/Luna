"""Remote control: device discovery, which devices can take tasks, relaying a
task's stream and confirmations, provider errors, and the audit trail."""
from __future__ import annotations

import asyncio
import json
import unittest
from unittest import mock

from tests.tools import _bootstrap  # noqa: F401

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.routers import remote as remote_router
from server.services import remote_devices as rd

LAPTOP = "laptop.tail1.ts.net"
DESK = "desk.tail1.ts.net"
PHONE = "phone.tail1.ts.net"
STRANGER = "friends-pc.tail1.ts.net"

STATUS = {
    "BackendState": "Running",
    "Self": {"HostName": "this-pc", "DNSName": "this-pc.tail1.ts.net.", "UserID": 1},
    "Peer": {
        "a": {"HostName": "laptop", "DNSName": LAPTOP + ".", "OS": "windows", "Online": True},
        "b": {"HostName": "desk", "DNSName": DESK + ".", "OS": "linux", "Online": True},
        "c": {"HostName": "phone", "DNSName": PHONE + ".", "OS": "android", "Online": True},
        "d": {"HostName": "friend", "DNSName": STRANGER + ".", "OS": "macOS", "Online": True},
        "e": {"HostName": "old", "DNSName": "old.tail1.ts.net.", "OS": "linux", "Online": False},
    },
}


def sse(*events: dict) -> bytes:
    return "".join(f"data: {json.dumps(e)}\n\n" for e in events).encode()


class FakeTailnet:
    """Plays every device: hello probes, chat streams and confirmations."""

    def __init__(self):
        self.tasks: list[tuple[str, dict]] = []
        self.confirms: list[tuple[str, str, dict]] = []
        self.stream_events = [
            {"type": "meta", "conversation_id": 41},
            {"type": "message_part", "content": "Locked "},
            {"type": "message_part", "content": "the screen."},
            {"type": "done", "conversation_id": 41, "route": "tool"},
        ]
        self.stream_status = 200
        self.confirm_ok = True

    def handler(self, request: httpx.Request) -> httpx.Response:
        host, path = request.url.host, request.url.path
        if path == "/api/remote/hello":
            if host == LAPTOP or host == DESK:
                return httpx.Response(200, json={"luna": True, "name": host.split(".")[0].upper(), "authorized": True, "via": "tailscale"})
            if host == STRANGER:
                return httpx.Response(200, json={"luna": True, "name": "friend", "authorized": False, "via": None})
            raise httpx.ConnectError("refused", request=request)
        if path == "/api/chat/stream":
            self.tasks.append((host, json.loads(request.content)))
            if host == DESK:
                raise httpx.ConnectError("went to sleep", request=request)
            return httpx.Response(self.stream_status, content=sse(*self.stream_events), headers={"content-type": "text/event-stream"})
        if path.startswith("/api/chat/confirm/"):
            self.confirms.append((host, path.rsplit("/", 1)[1], json.loads(request.content)))
            return httpx.Response(200, json={"ok": self.confirm_ok})
        return httpx.Response(404)


def make(net: FakeTailnet, status=STATUS, problem="") -> rd.RemoteDevices:
    return rd.RemoteDevices(status_reader=lambda: (status, problem), transport=httpx.MockTransport(net.handler))


class Base(unittest.TestCase):
    def setUp(self):
        self.audit = []
        patcher = mock.patch.object(rd, "record_audit", side_effect=lambda action, **kw: self.audit.append((action, kw)))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.net = FakeTailnet()

    def run_async(self, coro):
        return asyncio.run(coro)


class DiscoveryTests(Base):
    def test_lists_this_computer_first_then_controllable_devices(self):
        devices, problem = self.run_async(make(self.net).list())
        self.assertEqual(problem, "")
        ids = [d.id for d in devices]
        self.assertEqual(ids[0], rd.SELF_ID)
        self.assertTrue(devices[0].is_self and devices[0].controllable)
        self.assertEqual(set(ids[1:3]), {LAPTOP, DESK})            # controllable next
        self.assertNotIn("old.tail1.ts.net", ids)                   # offline devices are left out
        by_id = {d.id: d for d in devices}
        self.assertEqual(by_id[LAPTOP].name, "LAPTOP")              # name from the device's own Luna
        self.assertFalse(by_id[PHONE].luna)
        self.assertIn("isn't running", by_id[PHONE].reason)
        self.assertTrue(by_id[STRANGER].luna)
        self.assertFalse(by_id[STRANGER].controllable)
        self.assertIn("doesn't trust", by_id[STRANGER].reason)

    def test_iphone_named_localhost_uses_its_tailnet_name(self):
        status = {**STATUS, "Peer": {"x": {"HostName": "localhost", "DNSName": "iphone181.tail1.ts.net.", "OS": "iOS", "Online": True}}}
        devices, _ = self.run_async(make(self.net, status=status).list())
        self.assertEqual(devices[1].name, "iphone181")

    def test_public_view_hides_urls(self):
        devices, _ = self.run_async(make(self.net).list())
        for d in devices:
            self.assertNotIn("url", d.public())
            self.assertIn("controllable", d.public())

    def test_without_tailscale_only_this_computer(self):
        devices, problem = self.run_async(make(self.net, status={}, problem="Tailscale isn't installed.").list())
        self.assertEqual([d.id for d in devices], [rd.SELF_ID])
        self.assertIn("isn't installed", problem)

    def test_results_are_cached_until_refresh(self):
        calls = []
        devices = rd.RemoteDevices(status_reader=lambda: calls.append(1) or (STATUS, ""), transport=httpx.MockTransport(self.net.handler))
        self.run_async(devices.list())
        self.run_async(devices.list())
        self.assertEqual(len(calls), 1)
        self.run_async(devices.list(refresh=True))
        self.assertEqual(len(calls), 2)


class TargetingTests(Base):
    def test_only_discovered_controllable_devices_can_be_targeted(self):
        devices = make(self.net)
        self.assertEqual(self.run_async(devices.get(LAPTOP)).url, f"https://{LAPTOP}:8899")
        for target, kind in [(PHONE, "offline"), (STRANGER, "not_authorized"),
                             ("evil.example.com", "not_found"), ("127.0.0.1:22", "not_found")]:
            with self.subTest(target=target):
                with self.assertRaises(rd.DeviceError) as caught:
                    self.run_async(devices.get(target))
                self.assertEqual(caught.exception.kind, kind)

    def test_this_computer_is_reached_over_loopback(self):
        me = self.run_async(make(self.net).get(rd.SELF_ID))
        self.assertTrue(me.url.startswith("http://127.0.0.1:"))


class TaskTests(Base):
    def collect(self, devices, device_id, message, conversation_id=None):
        async def go():
            device = await devices.get(device_id)
            return [e async for e in devices.run_task(device, message, conversation_id)]
        return self.run_async(go())

    def test_relays_the_devices_stream_and_audits_it(self):
        events = self.collect(make(self.net), LAPTOP, "  lock   the screen ")
        self.assertEqual([e["type"] for e in events], ["meta", "message_part", "message_part", "done"])
        self.assertEqual(self.net.tasks, [(LAPTOP, {"message": "lock the screen", "standalone": True})])
        action, kw = self.audit[-1]
        self.assertEqual(action, "remote_device_task")
        self.assertEqual(kw["status"], "ok")
        self.assertEqual(kw["args"]["device"], LAPTOP)
        self.assertEqual(kw["result"], "Locked\n\nthe screen.")

    def test_follow_up_continues_the_devices_conversation(self):
        self.collect(make(self.net), LAPTOP, "and mute it", conversation_id=41)
        self.assertEqual(self.net.tasks[-1][1], {"message": "and mute it", "standalone": True, "conversation_id": 41})

    def test_unreachable_device_ends_with_offline_error(self):
        events = self.collect(make(self.net), DESK, "open spotify")
        self.assertEqual(events[-1]["type"], "error")
        self.assertEqual(events[-1]["kind"], "offline")
        self.assertEqual(self.audit[-1][1]["status"], "error")

    def test_rejected_token_is_not_authorized(self):
        self.net.stream_status = 401
        events = self.collect(make(self.net), LAPTOP, "lock")
        self.assertEqual(events, [{"type": "error", "kind": "not_authorized", "message": mock.ANY}])

    def test_other_upstream_failure(self):
        self.net.stream_status = 500
        events = self.collect(make(self.net), LAPTOP, "lock")
        self.assertEqual(events[-1]["kind"], "upstream")

    def test_stream_cut_off_before_done(self):
        self.net.stream_events = [{"type": "message_part", "content": "Work"}]
        events = self.collect(make(self.net), LAPTOP, "lock")
        self.assertEqual(events[-1]["kind"], "upstream")
        self.assertIn("before finishing", events[-1]["message"])
        self.assertEqual(self.audit[-1][1]["status"], "error")

    def test_confirmation_is_relayed_to_the_device(self):
        devices = make(self.net)
        laptop = self.run_async(devices.get(LAPTOP))
        self.assertTrue(self.run_async(devices.confirm(laptop, "ab12cd34", True)))
        self.assertEqual(self.net.confirms, [(LAPTOP, "ab12cd34", {"approved": True})])
        self.assertEqual(self.audit[-1][0], "remote_device_confirm")
        self.net.confirm_ok = False   # the device already gave up waiting
        self.assertFalse(self.run_async(devices.confirm(laptop, "ab12cd34", False)))


class RouterTests(Base):
    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(remote_router, "remote_devices", make(self.net))
        patcher.start()
        self.addCleanup(patcher.stop)
        app = FastAPI()
        app.include_router(remote_router.router)
        self.client = TestClient(app)

    def test_devices_endpoint(self):
        body = self.client.get("/api/remote/devices").json()
        self.assertIsNone(body["tailscale"])
        self.assertEqual(body["devices"][0]["id"], "self")
        self.assertTrue(all("url" not in d for d in body["devices"]))

    def test_task_streams_sse_with_device_header(self):
        with self.client.stream("POST", f"/api/remote/devices/{LAPTOP}/task", json={"message": "lock the screen"}) as res:
            self.assertEqual(res.status_code, 200)
            events = [json.loads(line[5:]) for line in res.iter_lines() if line.startswith("data:")]
        self.assertEqual(events[0], {"type": "device", "id": LAPTOP, "name": "LAPTOP"})
        self.assertEqual(events[-1]["type"], "done")

    def test_task_errors(self):
        res = self.client.post("/api/remote/devices/evil.example.com/task", json={"message": "x"})
        self.assertEqual((res.status_code, res.json()["detail"]["kind"]), (404, "not_found"))
        res = self.client.post(f"/api/remote/devices/{STRANGER}/task", json={"message": "x"})
        self.assertEqual((res.status_code, res.json()["detail"]["kind"]), (403, "not_authorized"))
        res = self.client.post(f"/api/remote/devices/{LAPTOP}/task", json={"message": "   "})
        self.assertEqual(res.status_code, 422)
        self.assertEqual(self.net.tasks, [])

    def test_confirm_endpoint(self):
        ok = self.client.post(f"/api/remote/devices/{LAPTOP}/confirm/ab12cd34", json={"approved": False})
        self.assertEqual(ok.json(), {"ok": True, "approved": False})
        bad = self.client.post(f"/api/remote/devices/{LAPTOP}/confirm/..%2Fsettings", json={"approved": True})
        self.assertIn(bad.status_code, (404, 422))
        self.net.confirm_ok = False
        gone = self.client.post(f"/api/remote/devices/{LAPTOP}/confirm/ab12cd34", json={"approved": True})
        self.assertEqual((gone.status_code, gone.json()["detail"]["kind"]), (410, "expired"))
        self.assertEqual(len(self.net.confirms), 2)


if __name__ == "__main__":
    unittest.main()
