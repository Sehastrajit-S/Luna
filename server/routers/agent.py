from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse, StreamingResponse

import json

from server.services.agent_tasks import create_agent_task, list_agent_tasks, update_agent_task
from server.services.agents import (
    AgentRole,
    ROLE_DEFINITIONS,
    is_crew_request,
    run_crew,
)
from server.services.audit_log import list_audit, record_audit
from server.services.browser_automation import browser_open, browser_read, playwright_status
from server.services.permission_manager import permission_manager
from server.services.skill_manager import list_skills
from server.services.task_planner import generate_plan
from server.services.enterprise_workflow import run_enterprise_bugfix_workflow
from server.services.workspace import (
    list_workspace,
    read_workspace_file,
    read_workspace_file_base64,
    write_workspace_file,
    write_workspace_file_base64,
)
from server.processes.registry import list_processes

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.get("/skills")
def skills():
    return list_skills()


@router.get("/processes")
def processes():
    return list_processes()


@router.get("/audit")
def audit(limit: int = 100):
    return list_audit(limit)


@router.get("/permissions")
def permissions():
    return permission_manager.list_policy()


@router.post("/permissions/{tool_name}")
def set_permission(tool_name: str, payload: dict = Body(default={})):
    mode = payload.get("mode")
    if mode not in ("allow", "confirm", "block"):
        return JSONResponse({"detail": "mode must be allow, confirm, or block"}, status_code=400)
    permission_manager.set_policy(tool_name, mode)
    return permission_manager.list_policy()


@router.get("/workspace")
def workspace_list(path: str = ""):
    return list_workspace(path)


@router.get("/workspace/read")
def workspace_read(path: str):
    return {"path": path, "content": read_workspace_file(path)}


@router.get("/workspace/read-base64")
def workspace_read_base64(path: str):
    return read_workspace_file_base64(path)


@router.post("/workspace/write")
def workspace_write(payload: dict = Body(default={})):
    result = write_workspace_file(payload.get("path", ""), payload.get("content", ""))
    record_audit("workspace_write", args=result, status="ok")
    return result


@router.post("/workspace/write-base64")
def workspace_write_base64(payload: dict = Body(default={})):
    result = write_workspace_file_base64(payload.get("path", ""), payload.get("content_base64", ""))
    record_audit("workspace_write_base64", args=result, status="ok")
    return result


@router.get("/browser/status")
async def browser_status():
    return await playwright_status()


@router.post("/browser/open")
def open_browser(payload: dict = Body(default={})):
    result = browser_open(payload.get("url", ""))
    record_audit("browser_open", args=result, status="ok")
    return result


@router.post("/browser/read")
async def read_browser(payload: dict = Body(default={})):
    result = await browser_read(payload.get("url", ""))
    record_audit("browser_read", args={"url": payload.get("url", "")}, result=str(result)[:500], status="ok")
    return result


@router.get("/tasks")
def tasks(limit: int = 50):
    return list_agent_tasks(limit)


@router.post("/tasks")
async def create_task(payload: dict = Body(default={})):
    description = payload.get("description", "").strip()
    if not description:
        return JSONResponse({"detail": "description is required"}, status_code=400)
    steps = payload.get("steps")
    if steps is None:
        steps = await generate_plan(description)
    task = create_agent_task(description, steps)
    record_audit("agent_task_created", args={"description": description, "steps": steps}, result=task["id"], status="ok")
    return task


@router.patch("/tasks/{task_id}")
def patch_task(task_id: str, payload: dict = Body(default={})):
    task = update_agent_task(task_id, **payload)
    if not task:
        return JSONResponse({"detail": "task not found"}, status_code=404)
    return task


@router.post("/enterprise/bugfix")
async def enterprise_bugfix(payload: dict = Body(default={})):
    """
    Run the enterprise bugfix workflow:
    Jira/GitHub/Slack context -> coding agent -> tests -> commit/push -> draft PR.
    """
    result = await run_enterprise_bugfix_workflow(payload)
    status_code = 200 if result.ok else 400
    return JSONResponse(result.as_dict(), status_code=status_code)


# ── Crew Mode (multi-agent orchestration) ────────────────────────────────────


@router.get("/crew/roles")
def crew_roles():
    """Return the catalog of available agent roles."""
    return {"roles": [d.to_dict() for d in ROLE_DEFINITIONS.values()]}


@router.post("/crew/preview")
def crew_preview(payload: dict = Body(default={})):
    """Tell the user whether a request would trigger Crew Mode."""
    message = str(payload.get("message", "")).strip()
    if not message:
        return JSONResponse({"detail": "message is required"}, status_code=400)
    return {
        "message": message,
        "would_run_crew": is_crew_request(message),
    }


@router.post("/crew/run")
async def crew_run(payload: dict = Body(default={})):
    """
    Run a multi-agent crew against a task and stream the events as SSE.

    Body:
        task            (str, required)  — the user's high-level goal
        enable_critic   (bool, optional) — default True
        max_revisions   (int, optional)  — default 1
    """
    task = str(payload.get("task", "")).strip()
    if not task:
        return JSONResponse({"detail": "task is required"}, status_code=400)
    enable_critic = bool(payload.get("enable_critic", True))
    max_revisions = int(payload.get("max_revisions", 1))

    record_audit("crew_run", args={"task": task[:200]}, status="started")

    async def stream():
        try:
            async for event in run_crew(
                task,
                enable_critic=enable_critic,
                max_revisions=max_revisions,
            ):
                yield f"data: {json.dumps(event.to_dict())}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
