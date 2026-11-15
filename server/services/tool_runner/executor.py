"""Tool call execution dispatcher."""
from __future__ import annotations

import json
import os
from datetime import datetime
from sqlalchemy.orm import Session


async def execute_tool_call(tc: dict, db: Session, conversation_id: int) -> str:
    """Execute a structured tool call. Returns a short result string."""
    tool_name = tc.get("tool", "")
    args = tc.get("args", {})

    from backend.services.app_launcher import launch_app, close_app, list_known_apps
    from backend.services.spotify import spotify_service
    from backend.services.screen_perception import execute_screen_tool
    from backend.models.database import Task, CalendarEvent

    try:
        if tool_name == "launch_app":
            success, msg = launch_app(args.get("app", ""))
            return "opened successfully" if success else f"failed: {msg}"

        elif tool_name == "close_app":
            success, msg = close_app(args.get("app", ""))
            return "closed successfully" if success else f"failed: {msg}"

        elif tool_name == "list_apps":
            apps = list_known_apps()
            return json.dumps({"apps": apps[:200], "count": len(apps)})

        elif tool_name == "save_memory":
            # Read back from the database: the reply says what is stored, not what was meant.
            from backend.models.database import Fact
            from backend.services.memory_manager import MemoryManager
            fact = " ".join(str(args.get("fact", "")).split())
            if len(fact) < 4:
                return "Error: nothing to remember — give the fact as a sentence."
            fact_id = await MemoryManager(db).store_fact(
                fact, str(args.get("category") or "personal"), conversation_id=conversation_id,
                confidence=1.0, importance=0.8, source="explicit")
            stored = db.query(Fact).filter_by(id=fact_id, is_active=True).first()
            return f"Saved to memory: {stored.content}" if stored else "Error: the memory didn't save."

        elif tool_name == "forget_memory":
            from backend.services.memory_manager import MemoryManager
            about = str(args.get("about", "")).strip()
            forgotten = MemoryManager(db).forget(about)
            if not forgotten:
                return f"Nothing in memory matched “{about}”, so there was nothing to forget."
            return f"Forgot {len(forgotten)} memor{'y' if len(forgotten) == 1 else 'ies'}: " + "; ".join(forgotten)

        elif tool_name == "daily_news":
            from backend.services.dashboard.news import daily_news
            return await daily_news(str(args.get("topic") or ""), args.get("limit") or 8)

        elif tool_name == "calculate":
            from backend.services.calculator import calculate
            return calculate(str(args.get("expression", "")))

        elif tool_name == "spotify_play":
            ok = spotify_service.play(args.get("query") or None)
            if ok:
                return "playing"
            if spotify_service.needs_auth:
                auth_url = spotify_service.get_auth_url()
                if auth_url:
                    import webbrowser
                    webbrowser.open(auth_url)
                return "Spotify needs authorization. The auth page was opened in the browser. Tell the user to log in, allow access, then try again."
            if not spotify_service._ready:
                return "Spotify is not configured. Tell the user to add spotify_client_id and spotify_client_secret to .env."
            return "Spotify playback is not available. Tell the user to open Spotify on this computer or another active device, then try again."

        elif tool_name == "spotify_pause":
            ok = spotify_service.pause()
            return "paused" if ok else "couldn't pause"

        elif tool_name == "spotify_next":
            ok = spotify_service.next_track()
            return "skipped" if ok else "couldn't skip"

        elif tool_name == "spotify_prev":
            ok = spotify_service.prev_track()
            return "went back" if ok else "couldn't go back"

        elif tool_name == "spotify_queue":
            ok = spotify_service.queue(args.get("query", ""))
            return "queued" if ok else "couldn't queue"

        elif tool_name == "switch_audio":
            from backend.services.audio_switcher import list_output_devices, set_default_device
            wanted = (args.get("device_name") or "").lower().strip()
            _aliases = {
                "pc": "realtek", "computer": "realtek",
                "headphones": "realtek", "headphone": "realtek",
                "bathroom": "speaker 1", "sink": "speaker 1",
            }
            wanted = _aliases.get(wanted, wanted)
            devices = list_output_devices()
            def _score(dev_name: str) -> int:
                low = dev_name.lower()
                return sum(1 for w in wanted.split() if w in low)
            best = max(devices, key=lambda d: _score(d["name"]), default=None)
            if best and _score(best["name"]) > 0:
                ok = set_default_device(best["id"])
                return f"switched to {best['name']}" if ok else f"failed to switch to {best['name']}"
            return f"no device matching '{args.get('device_name')}' found"

        elif tool_name == "browse_url":
            url = args.get("url", "")
            if url.startswith("http"):
                os.startfile(url)
            return f"opened {url}"

        elif tool_name in ("create_task", "create_event"):
            # Same save path as [TASK:…]/[EVENT:…]: local time → UTC, same title
            # updates, and the confirmation is read back from the database.
            from backend.services.command_parser.commands import save_and_verify
            if tool_name == "create_task":
                cmd = {"type": "task", "title": str(args.get("title") or "task"),
                       "due": args.get("due"), "priority": args.get("priority")}
            else:
                cmd = {"type": "event", "title": str(args.get("title") or "event"),
                       "datetime": args.get("datetime"), "duration": args.get("duration", 60)}
            return save_and_verify(db, cmd)

        elif tool_name in ("take_screenshot", "get_active_window", "find_text_on_screen", "click_at", "type_text"):
            result = execute_screen_tool(tool_name, args)
            if "error" in result:
                return f"failed: {result['error']}"
            return json.dumps(result)[:200]

        elif tool_name == "web_search":
            from backend.services.web_tools import web_search
            return await web_search(args.get("query", ""))

        elif tool_name == "use_skill":
            # Generic: runs whichever skills/<id> is named (or best matches).
            from backend.services.skill_runtime import get_search_skill, pick_search_skill, run_search_skill, run_web_search
            request = str(args.get("request") or args.get("query") or "")
            skill = get_search_skill(str(args.get("skill", ""))) or pick_search_skill(request)
            run = await (run_search_skill(skill, request) if skill else run_web_search(request))
            return run.answer

        elif tool_name == "web_research":
            from backend.services.web_tools import web_research
            return await web_research(args.get("query", ""))

        elif tool_name == "dataset_search":
            from backend.services.web_tools import dataset_search
            return await dataset_search(args.get("query", ""))

        elif tool_name == "web_fetch":
            from backend.services.web_tools import web_fetch
            return await web_fetch(args.get("url", ""))

        elif tool_name == "web_download_file":
            from backend.services.web_tools import web_download_file
            result = await web_download_file(args.get("url", ""), args.get("path", ""))
            return json.dumps(result)[:4000]

        elif tool_name == "browser_open":
            from backend.services.audit_log import record_audit
            from backend.services.browser_automation import browser_open
            result = browser_open(args.get("url", ""))
            record_audit("tool_call", tool=tool_name, args=args, result=json.dumps(result)[:500], conversation_id=conversation_id)
            return f"opened {result.get('url')}"

        elif tool_name == "browser_read":
            from backend.services.audit_log import record_audit
            from backend.services.browser_automation import browser_read
            result = await browser_read(args.get("url", ""))
            record_audit("tool_call", tool=tool_name, args=args, result=json.dumps(result)[:500], conversation_id=conversation_id)
            return json.dumps(result)[:4000]

        elif tool_name == "workspace_read":
            from backend.services.audit_log import record_audit
            from backend.services.workspace import read_workspace_file
            content = read_workspace_file(args.get("path", ""))
            record_audit("tool_call", tool=tool_name, args=args, result=f"{len(content)} chars", conversation_id=conversation_id)
            return content[:4000]

        elif tool_name == "workspace_read_base64":
            from backend.services.audit_log import record_audit
            from backend.services.workspace import read_workspace_file_base64
            result = read_workspace_file_base64(args.get("path", ""))
            record_audit("tool_call", tool=tool_name, args=args, result=f"{result['size']} bytes", conversation_id=conversation_id)
            return json.dumps(result)[:4000]

        elif tool_name == "workspace_write":
            from backend.services.audit_log import record_audit
            from backend.services.workspace import write_workspace_file
            result = write_workspace_file(args.get("path", ""), args.get("content", ""))
            record_audit("tool_call", tool=tool_name, args=args, result=json.dumps(result), conversation_id=conversation_id)
            return f"workspace file written: {result['path']}"

        elif tool_name == "workspace_write_base64":
            from backend.services.audit_log import record_audit
            from backend.services.workspace import write_workspace_file_base64
            result = write_workspace_file_base64(args.get("path", ""), args.get("content_base64", ""))
            record_audit("tool_call", tool=tool_name, args={"path": args.get("path", "")}, result=json.dumps(result), conversation_id=conversation_id)
            return f"workspace binary file written: {result['path']}"

        elif tool_name == "search_conversation":
            from backend.services.session_state import search_conversation
            return search_conversation(db, conversation_id, str(args.get("query", "")))

        elif tool_name == "list_skills":
            from backend.services.skill_manager import list_skills
            return json.dumps(list_skills())[:4000]

        elif tool_name == "create_agent_task":
            from backend.services.agent_tasks import create_agent_task
            from backend.services.audit_log import record_audit
            task = create_agent_task(args.get("description", ""))
            record_audit("tool_call", tool=tool_name, args=args, result=task["id"], conversation_id=conversation_id)
            return f"agent task created: {task['id']}"

        elif tool_name in (
            "get_volume", "set_volume", "mute_audio", "unmute_audio",
            "get_brightness", "set_brightness", "lock_screen",
            "turn_off_display", "sleep_system", "get_clipboard",
            "set_clipboard", "get_system_info",
        ):
            from backend.services import system_controls
            dispatch = {
                "get_volume":       lambda: system_controls.get_volume(),
                "set_volume":       lambda: system_controls.set_volume(int(args.get("level", 50))),
                "mute_audio":       lambda: system_controls.mute_audio(),
                "unmute_audio":     lambda: system_controls.unmute_audio(),
                "get_brightness":   lambda: system_controls.get_brightness(),
                "set_brightness":   lambda: system_controls.set_brightness(int(args.get("level", 50))),
                "lock_screen":      lambda: system_controls.lock_screen(),
                "turn_off_display": lambda: system_controls.turn_off_display(),
                "sleep_system":     lambda: system_controls.sleep_system(),
                "get_clipboard":    lambda: system_controls.get_clipboard(),
                "set_clipboard":    lambda: system_controls.set_clipboard(args.get("text", "")),
                "get_system_info":  lambda: system_controls.get_system_info(),
            }
            result = dispatch[tool_name]()
            # Controls return (ok, value): report failures as errors, successes as the value.
            if isinstance(result, tuple) and len(result) == 2 and isinstance(result[0], bool):
                ok, value = result
                if not ok:
                    return f"Error: {value}"
                result = value if value is not None else "done"
            return json.dumps(result)[:4000] if isinstance(result, (dict, list)) else str(result)

        elif tool_name.startswith("github_"):
            from backend.services import github
            try:
                if tool_name == "github_list_repos":
                    return json.dumps(await github.list_repos())[:4000]
                if tool_name == "github_list_issues":
                    return json.dumps(await github.list_issues(args.get("repo", "")))[:4000]
                if tool_name == "github_create_issue":
                    return json.dumps(await github.create_issue(
                        args.get("repo", ""), args.get("title", ""), args.get("body", ""), args.get("labels"),
                    ))[:4000]
                if tool_name == "github_comment":
                    return json.dumps(await github.comment_on_issue(
                        args.get("repo", ""), int(args.get("number", 0)), args.get("body", ""),
                    ))[:4000]
                if tool_name == "github_list_prs":
                    return json.dumps(await github.list_prs(args.get("repo", "")))[:4000]
                if tool_name == "github_get_pr":
                    return json.dumps(await github.get_pr(args.get("repo", ""), int(args.get("number", 0))))[:4000]
                if tool_name == "github_summarize_user_pr":
                    return json.dumps(await github.summarize_user_pr_update(
                        args.get("repo", ""),
                        args.get("user", ""),
                        args.get("state", "all"),
                    ))[:8000]
                if tool_name == "github_create_pr":
                    return json.dumps(await github.create_pull_request(
                        args.get("repo", ""),
                        args.get("title", ""),
                        args.get("head", ""),
                        args.get("base", "main"),
                        args.get("body", ""),
                        bool(args.get("draft", True)),
                    ))[:4000]
            except Exception as exc:
                return f"GitHub error: {exc}"

        elif tool_name.startswith("slack_"):
            from backend.services import slack
            if tool_name == "slack_search_messages":
                return json.dumps(await slack.search_messages(
                    args.get("query", ""),
                    int(args.get("count", 10)),
                ))[:4000]
            if tool_name == "slack_channel_history":
                return json.dumps(await slack.channel_history(
                    args.get("channel_id", ""),
                    float(args.get("oldest", 0) or 0),
                    int(args.get("limit", 20)),
                ))[:4000]

        elif tool_name.startswith("jira_"):
            from backend.services import jira
            if tool_name == "jira_search_issues":
                return json.dumps(await jira.search_issues(
                    args.get("jql", ""),
                    int(args.get("max_results", 5)),
                ))[:4000]
            if tool_name == "jira_get_issue":
                return json.dumps(await jira.get_issue(args.get("issue_key", "")))[:4000]

        elif tool_name == "enterprise_bugfix_workflow":
            from backend.services.enterprise_workflow import run_enterprise_bugfix_workflow
            result = await run_enterprise_bugfix_workflow(args)
            return json.dumps(result.as_dict())[:8000]

        elif tool_name in (
            "code_read_file", "code_write_file", "code_list_files", "code_search", "code_run_shell",
            "code_edit_file", "code_delete_file", "code_rename_file", "code_web_search", "code_web_fetch",
        ):
            from backend.services.coding_agent import execute_coding_tool
            from backend.services.audit_log import record_audit
            result, needs_confirm = await execute_coding_tool(tool_name, args)
            if needs_confirm:
                record_audit("tool_call", tool=tool_name, args=args, result="confirmation_required", conversation_id=conversation_id)
                return "Needs user confirmation before running shell command."
            record_audit("tool_call", tool=tool_name, args=args, result=result[:200], conversation_id=conversation_id)
            return result[:4000]

        elif tool_name in ("google_workspace", "microsoft_workspace"):
            from backend.services.workspace_integrations import google_workspace, microsoft_workspace
            provider_call = google_workspace if tool_name == "google_workspace" else microsoft_workspace
            result = await provider_call(args.get("service", ""), args.get("action", ""), args.get("args", {}))
            return json.dumps(result.as_dict())[:4000]

        else:
            return f"unknown tool {tool_name}"

    except Exception as e:
        return f"error: {e}"
