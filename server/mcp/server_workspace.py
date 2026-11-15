"""Luna MCP server — workspace file tools.

Exposes: workspace_list, workspace_read, workspace_write
Resources: workspace://{path}

Run:
    python -m backend.mcp.server_workspace
"""
import json
from mcp.server.fastmcp import FastMCP
from backend.services.workspace import (
    list_workspace as _list,
    read_workspace_file as _read,
    write_workspace_file as _write,
)

mcp = FastMCP("luna-workspace")


@mcp.resource("workspace://{path}")
def workspace_resource(path: str) -> str:
    """Read a file from Luna's sandboxed workspace as an MCP resource."""
    try:
        return _read(path)
    except FileNotFoundError:
        return f"File not found: {path}"


@mcp.tool()
def workspace_list(path: str = "") -> str:
    """List files and directories inside Luna's workspace sandbox."""
    items = _list(path)
    if not items:
        return "Workspace is empty." if not path else f"No files at '{path}'."
    return json.dumps(items, indent=2)


@mcp.tool()
def workspace_read(path: str) -> str:
    """Read a text file from Luna's workspace sandbox."""
    try:
        return _read(path)
    except FileNotFoundError:
        return f"File not found: {path}"
    except Exception as e:
        return f"Error reading {path}: {e}"


@mcp.tool()
def workspace_write(path: str, content: str) -> str:
    """Write or overwrite a text file in Luna's workspace sandbox.

    The path is relative to Luna's workspace root. Parent directories
    are created automatically. Paths that escape the workspace are rejected.
    """
    try:
        _write(path, content)
        return f"Written: {path}"
    except ValueError as e:
        return f"Rejected: {e}"
    except Exception as e:
        return f"Error writing {path}: {e}"


if __name__ == "__main__":
    mcp.run()
