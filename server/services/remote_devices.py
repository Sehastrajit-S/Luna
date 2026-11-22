"""Remote control: find your devices on the tailnet and have their Luna do tasks.

A device can be controlled when it runs Luna behind `tailscale serve` on port
8899 (`luna serve --tailscale`) and trusts this machine's Tailscale account,
which it does by default when both are signed in as the same person (see
server/core/access.py). This computer is always listed and is reached over
loopback.

A task is a chat message sent to that device's own /api/chat/stream, so the
device does the work itself, with its own tools, apps and permission rules.
Its risky tools still ask for confirmation; the answer is relayed back to it.

Only devices found by discovery can be targeted (no arbitrary URLs), and every
task and confirmation is written to the audit log.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import socket
import subprocess
import time
from dataclasses import asdict, dataclass
from typing import Any, AsyncIterator, Callable, Optional

import httpx

from server.config import settings
from server.services.audit_log import record_audit

logger = logging.getLogger("luna.remote_devices")

LUNA_PORT = 8899            # the port `luna serve --tailscale` serves on
SELF_ID = "self"
PROBE_TIMEOUT_S = 3.5
CACHE_TTL_S = 20.0
TASK_TIMEOUT = httpx.Timeout(connect=8.0, read=600.0, write=15.0, pool=8.0)
MAX_MESSAGE = 4000

_WINDOWS_TAILSCALE = r"C:\Program Files\Tailscale\tailscale.exe"
_MAC_TAILSCALE = "/Applications/Tailscale.app/Contents/MacOS/Tailscale"


class DeviceError(Exception):
    """A problem the app should show as-is. kind: not_found | offline | not_authorized | upstream."""

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind
        self.message = message


@dataclass
class Device:
    id: str
    name: str
    host: str = ""
    os: str = ""
    is_self: bool = False
    luna: bool = False          # answers as a Luna server
    authorized: bool = False    # would let this machine in
    url: str = ""
    reason: str = ""            # why it can't be controlled, when it can't

    @property
    def controllable(self) -> bool:
        return self.luna and self.authorized

    def public(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("url")
        data["controllable"] = self.controllable
        return data


# ── Tailscale ────────────────────────────────────────────────────────────────

def _tailscale_binary() -> Optional[str]:
    found = shutil.which("tailscale")
    if found:
        return found
    for path in (_WINDOWS_TAILSCALE, _MAC_TAILSCALE):
        if os.path.exists(path):
            return path
    return None


def tailscale_status() -> tuple[dict, str]:
    """(status, problem). problem is '' when Tailscale is running."""
    binary = _tailscale_binary()
    if not binary:
        return {}, "Tailscale isn't installed on the computer running Luna."
    try:
        out = subprocess.run(
            [binary, "status", "--json"], capture_output=True, text=True, timeout=5, check=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ).stdout
        status = json.loads(out)
    except (OSError, subprocess.SubprocessError, ValueError) as e:
        logger.warning("Could not read Tailscale status: %s", e)
        return {}, "Couldn't read Tailscale status."
    if status.get("BackendState") != "Running":
        return {}, "Tailscale isn't connected. Open Tailscale and sign in."
    return status, ""


def _peer_name(hostname, dns: str) -> str:
    # iPhones report their hostname as "localhost"; the tailnet name is more telling.
    name = str(hostname or "").strip()
    return name if name and name.lower() != "localhost" else dns.split(".")[0]


def tailnet_peers(status: dict) -> list[Device]:
    """Online devices on the tailnet other than this one."""
    peers = []
    for p in (status.get("Peer") or {}).values():
        dns = str(p.get("DNSName") or "").rstrip(".")
        if not dns or not p.get("Online"):
            continue
        peers.append(Device(
            id=dns,
            name=_peer_name(p.get("HostName"), dns),
            host=dns,
            os=str(p.get("OS") or ""),
            url=f"https://{dns}:{LUNA_PORT}",
        ))
    return peers


# ── Devices ──────────────────────────────────────────────────────────────────

def _joined(parts: list[str]) -> str:
    """The reply as one text: the device streams one paragraph per part, without separators."""
    return "\n\n".join(p.strip() for p in parts if p.strip())


class RemoteDevices:
    """Discovery cache plus task relay. `transport` is for tests."""

    def __init__(
        self,
        status_reader: Callable[[], tuple[dict, str]] = tailscale_status,
        transport: Optional[httpx.AsyncBaseTransport] = None,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._status_reader = status_reader
        self._transport = transport
        self._clock = clock
        self._cache: Optional[tuple[float, list[Device], str]] = None
        self._lock = asyncio.Lock()

    def _client(self, timeout) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=timeout, transport=self._transport, follow_redirects=False)

    def _self_device(self) -> Device:
        return Device(
            id=SELF_ID,
            name=socket.gethostname() or "This computer",
            os={"nt": "windows", "posix": "linux"}.get(os.name, os.name),
            is_self=True,
            luna=True,
            authorized=True,
            url=f"http://127.0.0.1:{settings.port}",
        )

    async def _probe(self, client: httpx.AsyncClient, device: Device) -> Device:
        try:
            res = await client.get(f"{device.url}/api/remote/hello")
            hello = res.json() if res.status_code == 200 else {}
        except (httpx.HTTPError, ValueError):
            hello = {}
        if not hello.get("luna"):
            device.reason = "Luna isn't running here (or isn't shared with `luna serve --tailscale`)."
            return device
        device.luna = True
        device.name = str(hello.get("name") or device.name)
        device.authorized = bool(hello.get("authorized"))
        if not device.authorized:
            device.reason = "Its Luna doesn't trust this Tailscale account. Sign both in as the same person, or add this login to its tailscale_trusted_logins."
        return device

    async def list(self, refresh: bool = False) -> tuple[list[Device], str]:
        """(devices, tailscale problem). This computer first, then controllable devices, then the rest."""
        now = self._clock()
        if not refresh and self._cache and now - self._cache[0] < CACHE_TTL_S:
            return self._cache[1], self._cache[2]
        async with self._lock:
            if not refresh and self._cache and self._clock() - self._cache[0] < CACHE_TTL_S:
                return self._cache[1], self._cache[2]
            status, problem = await asyncio.to_thread(self._status_reader)
            peers = tailnet_peers(status) if status else []
            if peers:
                async with self._client(PROBE_TIMEOUT_S) as client:
                    peers = list(await asyncio.gather(*(self._probe(client, d) for d in peers)))
            peers.sort(key=lambda d: (not d.controllable, not d.luna, d.name.lower()))
            devices = [self._self_device(), *peers]
            self._cache = (self._clock(), devices, problem)
            return devices, problem

    async def get(self, device_id: str) -> Device:
        """A device from discovery that can take tasks. Re-checks once if it isn't in the cache."""
        for refresh in (False, True):
            devices, _ = await self.list(refresh=refresh)
            match = next((d for d in devices if d.id == device_id), None)
            if match and match.controllable:
                return match
        if not match:
            raise DeviceError("not_found", "That device isn't online on your tailnet.")
        raise DeviceError("not_authorized" if match.luna else "offline", match.reason)

    # ── Tasks ────────────────────────────────────────────────────────────────

    async def run_task(self, device: Device, message: str, conversation_id: Optional[int] = None) -> AsyncIterator[dict]:
        """Stream the device's chat events for `message`. Ends with a done or error event."""
        message = " ".join(message.split())[:MAX_MESSAGE]
        # standalone: its own conversation on the device, not the chat open there.
        payload: dict[str, Any] = {"message": message, "standalone": True}
        if conversation_id:
            payload["conversation_id"] = conversation_id
        audit_args = {"device": device.id, "name": device.name, "message": message[:300]}
        reply: list[str] = []
        ended = None
        try:
            async with self._client(TASK_TIMEOUT) as client:
                async with client.stream("POST", f"{device.url}/api/chat/stream", json=payload) as res:
                    if res.status_code in (401, 403):
                        raise DeviceError("not_authorized", f"{device.name} refused the task. Its Luna doesn't trust this Tailscale account.")
                    if res.status_code != 200:
                        raise DeviceError("upstream", f"{device.name} answered {res.status_code}.")
                    async for line in res.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        try:
                            event = json.loads(line[5:].strip())
                        except ValueError:
                            continue
                        if not isinstance(event, dict):
                            continue
                        kind = event.get("type")
                        if kind == "message_part":
                            reply.append(str(event.get("content") or ""))
                        elif kind in ("done", "error"):
                            ended = event
                        yield event
                    if not ended:
                        # The stream closed without a done event (the device restarted or crashed).
                        ended = {"type": "error", "kind": "upstream", "message": f"{device.name} closed the connection before finishing."}
                        yield ended
        except DeviceError as e:
            ended = {"type": "error", "kind": e.kind, "message": e.message}
            yield ended
        except httpx.TimeoutException:
            ended = {"type": "error", "kind": "offline", "message": f"{device.name} stopped answering."}
            yield ended
        except httpx.HTTPError as e:
            logger.info("Task to %s failed: %s", device.id, e)
            ended = {"type": "error", "kind": "offline", "message": f"Couldn't reach {device.name}. Is it awake and running Luna?"}
            yield ended
        finally:
            # Also runs when the app disconnects mid-task (ended is None then).
            failed = not ended or ended.get("type") == "error"
            record_audit(
                "remote_device_task",
                tool="remote_device",
                args=audit_args,
                result=((ended or {}).get("message") if failed else _joined(reply)[:300]) or ("cancelled" if not ended else None),
                risk="remote",
                status="cancelled" if not ended else ("error" if failed else "ok"),
            )

    async def confirm(self, device: Device, confirm_id: str, approved: bool) -> bool:
        """Relay a yes/no for a tool the device asked about. True when the device accepted it."""
        ok = False
        try:
            async with self._client(10.0) as client:
                res = await client.post(f"{device.url}/api/chat/confirm/{confirm_id}", json={"approved": approved})
                ok = res.status_code == 200 and bool(res.json().get("ok"))
        except (httpx.HTTPError, ValueError) as e:
            logger.info("Confirmation to %s failed: %s", device.id, e)
        record_audit(
            "remote_device_confirm",
            tool="remote_device",
            args={"device": device.id, "confirm_id": confirm_id, "approved": approved},
            status="ok" if ok else "error",
        )
        return ok


remote_devices = RemoteDevices()
