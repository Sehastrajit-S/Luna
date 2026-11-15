import json
import re
from fastapi import APIRouter, Request
from backend.models.schemas import AppLaunchRequest, StatusResponse
from backend.services.app_launcher import launch_app, close_app, list_app_profiles, list_known_apps
from backend.services.media_context import get_watching_context
from backend.services.scheduler import proactive_queue
from backend.services import system_controls as sc
from backend.config import reload_settings

router = APIRouter(prefix="/api/system", tags=["system"])


@router.post("/config/reload")
def config_reload():
    """Re-read the .env file and apply new values without restarting the backend."""
    reload_settings()
    return {"ok": True}


@router.post("/launch", response_model=StatusResponse)
def launch_application(req: AppLaunchRequest):
    success, message = launch_app(req.name)
    return StatusResponse(status="ok" if success else "error", message=message)


@router.post("/close", response_model=StatusResponse)
def close_application(req: AppLaunchRequest):
    success, message = close_app(req.name)
    return StatusResponse(status="ok" if success else "error", message=message)


@router.get("/apps")
def get_apps():
    return {"apps": list_known_apps()}


@router.get("/apps/profiles")
def get_app_profiles():
    return list_app_profiles()


@router.get("/github/repos")
async def github_repositories():
    """List repositories for the Capabilities panel."""
    from backend.services import github
    try:
        return {"repos": await github.list_repos()}
    except Exception as exc:
        return {"repos": [], "error": str(exc)}


@router.get("/dev-dashboard")
async def dev_dashboard(refresh: bool = False):
    """Local checkout status + GitHub repo pulse for the dashboard (cached ~3 min)."""
    from backend.services.dev_dashboard import dashboard
    return await dashboard(force=refresh)


@router.get("/github/activity")
async def github_activity():
    """Return contribution, PR, and comment-review data for the home widget."""
    from backend.services import github
    try:
        repo = github.default_repo()
        prs = await github.list_prs(repo, state="open", limit=10)
        commits = await github.list_commits(repo, per_page=30)
        comments = []
        for pr in prs[:5]:
            comments.extend(await github.list_pr_comments(repo, pr["number"], limit=5))
        return {"repo": repo, "contributions": commits, "prs": prs, "comments": comments[:12]}
    except Exception as exc:
        return {"contributions": [], "prs": [], "comments": [], "error": str(exc)}


@router.get("/watching")
def get_current_watching():
    ctx = get_watching_context()
    return {
        "title": ctx.title,
        "cleaned_title": ctx.cleaned_title,
        "source": ctx.source,
        "confidence": ctx.confidence,
    }


@router.get("/proactive")
def get_proactive_messages():
    msgs = list(proactive_queue)
    proactive_queue.clear()
    return {"messages": msgs}


@router.get("/audio-devices")
def get_audio_devices():
    from backend.services.audio_switcher import list_output_devices, get_default_device_id
    try:
        devices = list_output_devices()
        current = get_default_device_id()
        return {"devices": devices, "current": current}
    except Exception as e:
        return {"devices": [], "current": None, "error": str(e)}


@router.post("/audio-device")
async def set_audio_device(request: Request):
    from backend.services.audio_switcher import set_default_device
    body = await request.json()
    device_id = body.get("device_id", "")
    if not device_id:
        return {"ok": False, "error": "missing device_id"}
    ok = set_default_device(device_id)
    return {"ok": ok}


@router.get("/audio-input-devices")
def get_audio_input_devices():
    try:
        import sounddevice as sd
        devs = sd.query_devices()
        inputs = [
            {"id": str(i), "name": d["name"]}
            for i, d in enumerate(devs)
            if d["max_input_channels"] > 0
        ]
        try:
            default = sd.query_devices(kind="input")
            current = str(next(
                (str(i) for i, d in enumerate(devs) if d["name"] == default["name"]), ""
            ))
        except Exception:
            current = ""
        return {"devices": inputs, "current": current}
    except Exception as e:
        return {"devices": [], "current": None, "error": str(e)}


@router.post("/audio-input-device")
async def set_audio_input_device(request: Request):
    try:
        import sounddevice as sd
        body = await request.json()
        idx = int(body.get("device_id", -1))
        if idx < 0:
            return {"ok": False, "error": "invalid device_id"}
        devs = sd.query_devices()
        if idx >= len(devs):
            return {"ok": False, "error": "device not found"}
        sd.default.device = (idx, sd.default.device[1] if isinstance(sd.default.device, (list, tuple)) else sd.default.device)
        return {"ok": True, "name": devs[idx]["name"]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


_SCENE_SYSTEM = (
    "You are a 3D scene designer. Output ONLY valid JSON — no markdown, no explanation, no code fences."
)

_SCENE_PROMPT = """\
Generate a holographic 3D scene spec for: "{topic}"

Build the {topic} from geometric primitives. Each shape represents one key component.
The scene will render as a holographic wireframe — no colors needed.

Output this exact JSON schema:
{{
  "shapes": [
    {{
      "type": "cylinder" | "sphere" | "box" | "torus" | "cone",
      "pos": [x, y, z],
      "label": "Component Name",
      // cylinder: "r": radius(float), "h": height(float), "rot": [rx,ry,rz](degrees, optional)
      // sphere:   "r": radius(float)
      // box:      "w": width(float), "h": height(float), "d": depth(float)
      // torus:    "r": major_radius(float), "tube": tube_radius(float), "rot": [rx,ry,rz](optional)
      // cone:     "r": base_radius(float), "h": height(float)
    }}
  ],
  "animate": "turntable"
}}

Rules:
- 6-12 shapes that together clearly represent {topic}
- pos values MUST be in range -3 to 3 on every axis
- Spatially accurate: parts in correct relative positions
- Labels are the real component names (barrel, cylinder, piston, nucleus, etc.)
- Realistic proportions

Output ONLY the JSON object:"""


@router.get("/scene")
async def generate_scene(topic: str = ""):
    """Generate a holographic 3D scene spec for a given topic using the LLM."""
    if not topic.strip():
        return {"error": "topic required"}
    from backend.services.llm import ollama
    prompt = _SCENE_PROMPT.format(topic=topic)
    try:
        raw = await ollama.complete(prompt, system=_SCENE_SYSTEM, temperature=0.3)
    except Exception as e:
        return {"error": str(e)}

    # Extract JSON even if model added surrounding text
    m = re.search(r'\{[\s\S]*\}', raw)
    if not m:
        return {"error": "LLM did not return JSON", "raw": raw[:300]}
    try:
        spec = json.loads(m.group())
        # Basic validation
        if not isinstance(spec.get("shapes"), list):
            raise ValueError("missing shapes")
        return spec
    except Exception as e:
        return {"error": f"JSON parse failed: {e}", "raw": raw[:300]}


@router.get("/volume")
def get_volume():
    ok, val = sc.get_volume()
    return {"ok": ok, "volume": val if ok else None, "error": None if ok else val}

@router.post("/volume")
async def set_volume(request: Request):
    body = await request.json()
    level = body.get("level", 50)
    ok, msg = sc.set_volume(int(level))
    return {"ok": ok, "message": msg}

@router.post("/volume/mute")
def mute_audio():
    ok, msg = sc.mute_audio()
    return {"ok": ok, "message": msg}

@router.post("/volume/unmute")
def unmute_audio():
    ok, msg = sc.unmute_audio()
    return {"ok": ok, "message": msg}

@router.get("/brightness")
def get_brightness():
    ok, val = sc.get_brightness()
    return {"ok": ok, "brightness": val if ok else None, "error": None if ok else val}

@router.post("/brightness")
async def set_brightness(request: Request):
    body = await request.json()
    level = body.get("level", 50)
    ok, msg = sc.set_brightness(int(level))
    return {"ok": ok, "message": msg}

@router.post("/lock")
def lock_screen():
    ok, msg = sc.lock_screen()
    return {"ok": ok, "message": msg}

@router.post("/display/off")
def display_off():
    ok, msg = sc.turn_off_display()
    return {"ok": ok, "message": msg}

@router.post("/sleep")
def sleep():
    ok, msg = sc.sleep_system()
    return {"ok": ok, "message": msg}

@router.get("/clipboard")
def get_clipboard():
    ok, text = sc.get_clipboard()
    return {"ok": ok, "text": text if ok else None, "error": None if ok else text}

@router.post("/clipboard")
async def set_clipboard_route(request: Request):
    body = await request.json()
    text = body.get("text", "")
    ok, msg = sc.set_clipboard(text)
    return {"ok": ok, "message": msg}

@router.get("/info")
def system_info():
    return sc.get_system_info()

@router.get("/health")
async def health():
    from backend.services.llm import ollama
    available = await ollama.is_available()
    return {
        "status": "ok",
        "llm": available,
        "llm_provider": ollama.provider,
        "ollama": available,
        "model": ollama.model,
    }


@router.get("/llm-selection")
async def llm_selection():
    """Which model the priority-based selector picked, and every candidate it saw."""
    from backend.services.llm import selector
    return selector.status()
