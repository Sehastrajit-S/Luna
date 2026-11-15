"""Google Workspace integration."""
from __future__ import annotations

import asyncio
from typing import Any

from backend.config import settings
from backend.services.workspace_integrations.base import (
    GOOGLE_BASES,
    WorkspaceIntegrationError,
    WorkspaceResponse,
    _clean_path,
    _gmail_raw_message,
    _request,
)


async def google_workspace(
    service: str,
    action: str,
    args: dict[str, Any] | None = None,
    token: str = "",
) -> WorkspaceResponse:
    args = args or {}
    service = service.lower().strip()
    action = action.lower().strip()
    if service not in GOOGLE_BASES:
        raise WorkspaceIntegrationError(f"unsupported Google Workspace service: {service}")
    base = GOOGLE_BASES[service]

    if action == "raw_request":
        path = _clean_path(str(args.get("path", "")))
        data = await _request(
            str(args.get("method", "GET")),
            f"{base}{path}",
            "google",
            token,
            params=args.get("params"),
            json_body=args.get("body"),
        )
        return WorkspaceResponse("google", service, action, data)

    if service == "gmail":
        user = args.get("user_id", "me")
        if action == "search_messages":
            q = args.get("q") or args.get("query", "")
            max_results = int(args.get("maxResults") or args.get("limit") or 10)
            list_data = await _request("GET", f"{base}/users/{user}/messages", "google", token, {
                "q": q,
                "maxResults": max_results,
            })
            messages = list_data.get("messages", [])
            if messages:
                async def _fetch_meta(msg_id: str) -> dict:
                    try:
                        md = await _request(
                            "GET", f"{base}/users/{user}/messages/{msg_id}", "google", token,
                            {"format": "metadata", "metadataHeaders": ["Subject", "From", "Date"]},
                        )
                        hdrs = {h["name"]: h["value"] for h in md.get("payload", {}).get("headers", [])}
                        return {
                            "id": msg_id,
                            "snippet": md.get("snippet", ""),
                            "subject": hdrs.get("Subject", "(no subject)"),
                            "from": hdrs.get("From", ""),
                            "date": hdrs.get("Date", ""),
                            "labels": md.get("labelIds", []),
                        }
                    except Exception:
                        return {"id": msg_id}
                enriched = await asyncio.gather(*[_fetch_meta(m["id"]) for m in messages[:5]])
                data = {**list_data, "messages": list(enriched)}
            else:
                data = list_data
        elif action == "get_message":
            data = await _request("GET", f"{base}/users/{user}/messages/{args['message_id']}", "google", token, {
                "format": args.get("format", "metadata"),
            })
        elif action == "send_message":
            raw = _gmail_raw_message(args["to"], args.get("subject", ""), args.get("body", ""), args.get("from", ""))
            data = await _request("POST", f"{base}/users/{user}/messages/send", "google", token, json_body={"raw": raw})
        else:
            raise WorkspaceIntegrationError(f"unsupported Gmail action: {action}")
    elif service == "calendar":
        calendar_id = args.get("calendar_id", "primary")
        if action == "list_events":
            data = await _request("GET", f"{base}/calendars/{calendar_id}/events", "google", token, {
                "timeMin": args.get("timeMin") or args.get("time_min"),
                "timeMax": args.get("timeMax") or args.get("time_max"),
                "maxResults": int(args.get("maxResults") or args.get("limit") or 10),
                "singleEvents": True,
                "orderBy": "startTime",
            })
        elif action == "create_event":
            event = {
                "summary": args["title"],
                "description": args.get("description", ""),
                "start": {"dateTime": args["start"], "timeZone": args.get("time_zone", settings.weather_timezone)},
                "end": {"dateTime": args["end"], "timeZone": args.get("time_zone", settings.weather_timezone)},
            }
            if args.get("attendees"):
                event["attendees"] = [{"email": email} for email in args["attendees"]]
            data = await _request("POST", f"{base}/calendars/{calendar_id}/events", "google", token, json_body=event)
        else:
            raise WorkspaceIntegrationError(f"unsupported Google Calendar action: {action}")
    elif service == "drive":
        if action == "search_files":
            data = await _request("GET", f"{base}/files", "google", token, {
                "q": args.get("q") or args.get("query", "trashed=false"),
                "pageSize": int(args.get("pageSize") or args.get("maxResults") or args.get("limit") or 10),
                "fields": "files(id,name,mimeType,webViewLink,modifiedTime,size)",
            })
        elif action == "get_file":
            data = await _request("GET", f"{base}/files/{args['file_id']}", "google", token, {
                "fields": args.get("fields", "id,name,mimeType,webViewLink,modifiedTime,size,owners"),
            })
        elif action == "create_folder":
            payload = {"name": args["name"], "mimeType": "application/vnd.google-apps.folder"}
            if args.get("parent_id"):
                payload["parents"] = [args["parent_id"]]
            data = await _request("POST", f"{base}/files", "google", token, json_body=payload)
        else:
            raise WorkspaceIntegrationError(f"unsupported Google Drive action: {action}")
    elif service == "docs":
        if action == "create_document":
            data = await _request("POST", f"{base}/documents", "google", token, json_body={"title": args["title"]})
        elif action == "get_document":
            data = await _request("GET", f"{base}/documents/{args['document_id']}", "google", token)
        else:
            raise WorkspaceIntegrationError(f"unsupported Google Docs action: {action}")
    elif service == "sheets":
        if action == "get_values":
            data = await _request("GET", f"{base}/spreadsheets/{args['spreadsheet_id']}/values/{args['range']}", "google", token)
        elif action == "update_values":
            data = await _request(
                "PUT",
                f"{base}/spreadsheets/{args['spreadsheet_id']}/values/{args['range']}",
                "google",
                token,
                params={"valueInputOption": args.get("value_input_option", "USER_ENTERED")},
                json_body={"values": args.get("values", [])},
            )
        elif action == "create_spreadsheet":
            data = await _request("POST", f"{base}/spreadsheets", "google", token, json_body={"properties": {"title": args["title"]}})
        else:
            raise WorkspaceIntegrationError(f"unsupported Google Sheets action: {action}")
    elif service == "slides":
        if action == "create_presentation":
            data = await _request("POST", f"{base}/presentations", "google", token, json_body={"title": args["title"]})
        elif action == "get_presentation":
            data = await _request("GET", f"{base}/presentations/{args['presentation_id']}", "google", token)
        else:
            raise WorkspaceIntegrationError(f"unsupported Google Slides action: {action}")
    elif service == "tasks":
        tasklist = args.get("tasklist", "@default")
        if action == "list_tasks":
            data = await _request("GET", f"{base}/lists/{tasklist}/tasks", "google", token, {"maxResults": int(args.get("maxResults") or args.get("limit") or 20)})
        elif action == "create_task":
            data = await _request("POST", f"{base}/lists/{tasklist}/tasks", "google", token, json_body={
                "title": args["title"],
                "notes": args.get("notes", ""),
                "due": args.get("due"),
            })
        else:
            raise WorkspaceIntegrationError(f"unsupported Google Tasks action: {action}")
    elif service == "people":
        if action == "search_contacts":
            data = await _request("GET", f"{base}/people:searchContacts", "google", token, {
                "query": args.get("query", ""),
                "readMask": args.get("read_mask", "names,emailAddresses,phoneNumbers"),
                "pageSize": int(args.get("limit", 10)),
            })
        else:
            raise WorkspaceIntegrationError(f"unsupported Google People action: {action}")
    else:
        raise WorkspaceIntegrationError(f"unsupported Google Workspace action: {service}.{action}")

    return WorkspaceResponse("google", service, action, data)
