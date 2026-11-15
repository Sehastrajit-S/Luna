"""Permission policy for Luna tool execution."""
from __future__ import annotations

import json
import uuid
from typing import Literal

from backend.config import DATA_DIR
from backend.services.tool_registry import RiskLevel, get_tool

Decision = Literal["allow", "confirm", "block"]
PolicyMode = Literal["allow", "confirm", "block"]

_pending: dict[str, dict] = {}
_POLICY_PATH = DATA_DIR / "permissions.json"


class PermissionManager:
    def __init__(self):
        self._policy: dict[str, PolicyMode] = self._load_policy()

    def _load_policy(self) -> dict[str, PolicyMode]:
        if not _POLICY_PATH.exists():
            return {}
        try:
            raw = json.loads(_POLICY_PATH.read_text(encoding="utf-8"))
            return {str(k): v for k, v in raw.items() if v in ("allow", "confirm", "block")}
        except Exception:
            return {}

    def _save_policy(self) -> None:
        _POLICY_PATH.write_text(json.dumps(self._policy, indent=2, ensure_ascii=True), encoding="utf-8")

    def _default_mode(self, risk: RiskLevel) -> PolicyMode:
        if risk == RiskLevel.SAFE:
            return "allow"
        if risk == RiskLevel.RISKY:
            return "confirm"
        return "block"

    def list_policy(self) -> dict:
        from backend.services.tool_registry import TOOL_REGISTRY

        tools = {}
        for name, tool in TOOL_REGISTRY.items():
            tools[name] = {
                "risk": tool.risk.value,
                "mode": self._policy.get(name) or self._default_mode(tool.risk),
                "description": tool.description,
            }
        return {"tools": tools, "overrides": dict(self._policy)}

    def set_policy(self, tool_name: str, mode: PolicyMode) -> None:
        self._policy[tool_name] = mode
        self._save_policy()

    def check(self, tool_name: str, args: dict) -> tuple[Decision, str | None, str | None]:
        tool = get_tool(tool_name)
        if tool is None:
            return "block", f"Unknown tool '{tool_name}'.", None

        mode = self._policy.get(tool_name) or self._default_mode(tool.risk)

        if mode == "allow":
            return "allow", None, None
        if mode == "block":
            return "block", f"I can't run '{tool_name}' automatically. It is blocked by Luna's permissions.", None

        confirm_id = str(uuid.uuid4())[:8]
        msg = tool.confirm_template
        for k, v in args.items():
            msg = msg.replace(f"{{{k}}}", str(v))
        if not msg:
            msg = f"Run {tool_name}?"
        _pending[confirm_id] = {"tool": tool_name, "args": args, "approved": None}
        return "confirm", msg, confirm_id

    def submit_answer(self, confirm_id: str, approved: bool) -> bool:
        if confirm_id not in _pending:
            return False
        _pending[confirm_id]["approved"] = approved
        return True

    def pop_answer(self, confirm_id: str) -> bool | None:
        entry = _pending.get(confirm_id)
        if entry is None or entry["approved"] is None:
            return None
        _pending.pop(confirm_id, None)
        return entry["approved"]

    def get_pending(self, confirm_id: str) -> dict | None:
        return _pending.get(confirm_id)


permission_manager = PermissionManager()
