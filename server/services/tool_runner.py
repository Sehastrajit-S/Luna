# Backward-compat shim — all logic lives in backend.services.tool_runner package
from backend.services.tool_runner import *  # noqa: F401, F403
from backend.services.tool_runner import (
    parse_tool_call_json,
    strip_tool_call_json,
    execute_tool_call,
    verify_tool_result,
)
