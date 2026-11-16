# Backward-compat shim — all logic lives in server.services.coding
from server.services.coding import *  # noqa: F401, F403
from server.services.coding import (
    WORKSPACE_ROOT,
    execute_coding_tool,
    stream_coding_agent,
    tool_delete_file,
    tool_edit_file,
    tool_list_files,
    tool_read_file,
    tool_rename_file,
    tool_write_file,
    build_workspace_index,
)
