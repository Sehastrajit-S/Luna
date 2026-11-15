"""Microsoft 365 integration."""
from __future__ import annotations

from typing import Any

from backend.config import settings
from backend.services.workspace_integrations.base import (
    MICROSOFT_GRAPH_BASE,
    WorkspaceIntegrationError,
    WorkspaceResponse,
    _clean_path,
    _request,
)


async def microsoft_workspace(
    service: str,
    action: str,
    args: dict[str, Any] | None = None,
    token: str = "",
) -> WorkspaceResponse:
    args = args or {}
    service = service.lower().strip()
    action = action.lower().strip()

    if action == "raw_request":
        path = _clean_path(str(args.get("path", "")))
        data = await _request(
            str(args.get("method", "GET")),
            f"{MICROSOFT_GRAPH_BASE}{path}",
            "microsoft",
            token,
            params=args.get("params"),
            json_body=args.get("body"),
        )
        return WorkspaceResponse("microsoft", service or "graph", action, data)

    if service == "profile":
        if action == "me":
            data = await _request("GET", f"{MICROSOFT_GRAPH_BASE}/me", "microsoft", token)
        else:
            raise WorkspaceIntegrationError(f"unsupported Microsoft profile action: {action}")
    elif service == "mail":
        if action == "search_messages":
            params: dict[str, Any] = {"$top": int(args.get("limit", 10))}
            if args.get("query"):
                params["$search"] = f'"{args["query"]}"'
            data = await _request("GET", f"{MICROSOFT_GRAPH_BASE}/me/messages", "microsoft", token, params)
        elif action == "send_message":
            payload = {
                "message": {
                    "subject": args.get("subject", ""),
                    "body": {"contentType": args.get("content_type", "Text"), "content": args.get("body", "")},
                    "toRecipients": [{"emailAddress": {"address": email}} for email in args.get("to", [])],
                },
                "saveToSentItems": bool(args.get("save_to_sent_items", True)),
            }
            data = await _request("POST", f"{MICROSOFT_GRAPH_BASE}/me/sendMail", "microsoft", token, json_body=payload)
        else:
            raise WorkspaceIntegrationError(f"unsupported Microsoft mail action: {action}")
    elif service == "calendar":
        if action == "list_events":
            data = await _request("GET", f"{MICROSOFT_GRAPH_BASE}/me/calendar/events", "microsoft", token, {"$top": int(args.get("limit", 10))})
        elif action == "create_event":
            payload = {
                "subject": args["title"],
                "body": {"contentType": "Text", "content": args.get("description", "")},
                "start": {"dateTime": args["start"], "timeZone": args.get("time_zone", settings.weather_timezone)},
                "end": {"dateTime": args["end"], "timeZone": args.get("time_zone", settings.weather_timezone)},
            }
            if args.get("attendees"):
                payload["attendees"] = [
                    {"emailAddress": {"address": email}, "type": "required"} for email in args["attendees"]
                ]
            data = await _request("POST", f"{MICROSOFT_GRAPH_BASE}/me/calendar/events", "microsoft", token, json_body=payload)
        else:
            raise WorkspaceIntegrationError(f"unsupported Microsoft calendar action: {action}")
    elif service == "drive":
        if action == "list_children":
            item = args.get("item_id", "root")
            data = await _request("GET", f"{MICROSOFT_GRAPH_BASE}/me/drive/items/{item}/children", "microsoft", token, {"$top": int(args.get("limit", 20))})
        elif action == "search_files":
            data = await _request("GET", f"{MICROSOFT_GRAPH_BASE}/me/drive/root/search(q='{args.get('query', '')}')", "microsoft", token)
        elif action == "create_folder":
            parent = args.get("parent_id", "root")
            payload = {"name": args["name"], "folder": {}, "@microsoft.graph.conflictBehavior": args.get("conflict_behavior", "rename")}
            data = await _request("POST", f"{MICROSOFT_GRAPH_BASE}/me/drive/items/{parent}/children", "microsoft", token, json_body=payload)
        else:
            raise WorkspaceIntegrationError(f"unsupported Microsoft Drive action: {action}")
    elif service == "todo":
        if action == "list_tasks":
            list_id = args.get("list_id")
            if list_id:
                data = await _request("GET", f"{MICROSOFT_GRAPH_BASE}/me/todo/lists/{list_id}/tasks", "microsoft", token)
            else:
                data = await _request("GET", f"{MICROSOFT_GRAPH_BASE}/me/todo/lists", "microsoft", token)
        elif action == "create_task":
            list_id = args["list_id"]
            payload = {"title": args["title"], "body": {"content": args.get("body", ""), "contentType": "text"}}
            if args.get("due"):
                payload["dueDateTime"] = {"dateTime": args["due"], "timeZone": args.get("time_zone", settings.weather_timezone)}
            data = await _request("POST", f"{MICROSOFT_GRAPH_BASE}/me/todo/lists/{list_id}/tasks", "microsoft", token, json_body=payload)
        else:
            raise WorkspaceIntegrationError(f"unsupported Microsoft To Do action: {action}")
    elif service == "excel":
        item_id = args["item_id"]
        workbook_path = f"{MICROSOFT_GRAPH_BASE}/me/drive/items/{item_id}/workbook"
        if action == "get_range":
            data = await _request("GET", f"{workbook_path}/worksheets/{args['worksheet_id_or_name']}/range(address='{args['range']}')", "microsoft", token)
        elif action == "update_range":
            data = await _request(
                "PATCH",
                f"{workbook_path}/worksheets/{args['worksheet_id_or_name']}/range(address='{args['range']}')",
                "microsoft",
                token,
                json_body={"values": args.get("values", [])},
            )
        else:
            raise WorkspaceIntegrationError(f"unsupported Microsoft Excel action: {action}")
    elif service == "teams":
        if action == "list_joined_teams":
            data = await _request("GET", f"{MICROSOFT_GRAPH_BASE}/me/joinedTeams", "microsoft", token)
        elif action == "list_channels":
            data = await _request("GET", f"{MICROSOFT_GRAPH_BASE}/teams/{args['team_id']}/channels", "microsoft", token)
        else:
            raise WorkspaceIntegrationError(f"unsupported Microsoft Teams action: {action}")
    else:
        raise WorkspaceIntegrationError(f"unsupported Microsoft 365 service: {service}")

    return WorkspaceResponse("microsoft", service, action, data)
