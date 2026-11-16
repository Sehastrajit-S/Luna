from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from server.config import settings
from server.models.database import init_db, Base, engine
from server.services.activity_tracker import Activity
from server.services.scheduler import luna_scheduler
from server.routers import chat, memory, calendar, system, voice as voice_router, spotify as spotify_router, state as state_router, train as train_router, sleep as sleep_router, luna as luna_router, agent as agent_router, channels as channels_router, admin as admin_router, workspace_integrations as workspace_integrations_router
from server.routers.proactive import router as proactive_router
from server.routers.coding import router as coding_router
from server.routers.observe import router as observe_router
from server.routers.health_integrations import router as health_router
from server.routers.skills import router as skills_router
from server.routers.files import router as files_router
from server.routers.settings import router as settings_router
from server.middleware.rate_limit import RateLimitMiddleware
from server.middleware.logging_middleware import RequestIDMiddleware
from server.core.logging import configure_logging
from server.core.access import RemoteAccessMiddleware
from server.processes.registry import start_lifecycle_processes, stop_lifecycle_processes
from server.services.telemetry import tracer
from server.models.database import SessionLocal

# Configure structured logging before anything else logs
configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Init DB (creates all tables including Activity)
    Base.metadata.create_all(bind=engine)
    init_db()
    # Local access token for settings writes (read by the desktop app's main process).
    from server.services.settings_store import local_api_token
    local_api_token()
    tracer.init(SessionLocal)
    # Test/eval instances run without reminders, check-ins and other jobs that
    # would notify the real user.
    jobs = settings.background_jobs_enabled
    if jobs:
        luna_scheduler.start()
        start_lifecycle_processes()
    selector_task = None
    if settings.llm_auto_select:
        import asyncio
        from server.services.llm import selector
        await selector.select_now()
        selector_task = asyncio.create_task(selector.run_forever())
    yield
    if selector_task is not None:
        selector_task.cancel()
    await tracer.flush()
    if jobs:
        luna_scheduler.stop()
        stop_lifecycle_processes()


app = FastAPI(
    title="L.U.N.A.",
    description="Large Unified Nexus Mind AI",
    version="1.0.0",
    lifespan=lifespan,
)

# Middleware order matters: outermost (first added) wraps everything.
# RequestID → RateLimit → CORS → route handler
app.add_middleware(RequestIDMiddleware)
app.add_middleware(RateLimitMiddleware)
# Remote requests (via Tailscale or another proxy) need the access token.
# Added before CORS so CORS wraps it and 401s still carry CORS headers.
app.add_middleware(RemoteAccessMiddleware, require_token_on_lan=settings.require_token_on_lan)

# ── CORS ──────────────────────────────────────────────────────────────────────
# allow_origins=["*"] + allow_credentials=True is invalid per the CORS spec
# and creates CSRF exposure when JWT auth is active.  Use an explicit origin list.
_DEFAULT_ORIGINS = [
    # Electron loads the desktop renderer from file://, which browsers expose
    # to the API as the opaque `null` origin.
    "null",
    "http://localhost:5173",
    "http://localhost:8899",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8899",
    # Mobile app WebViews (Capacitor on Android and iOS).
    "https://localhost",
    "capacitor://localhost",
]
_configured_origins = (
    [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    if settings.cors_origins
    else _DEFAULT_ORIGINS
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_configured_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Voice-Emotion",
        "X-Volume",
        "X-Speech-Speed",
        "X-Speech-Duration",
        "X-Luna-Token",
    ],
)


# Routers
app.include_router(chat.router)
app.include_router(memory.router)
app.include_router(calendar.router)
app.include_router(system.router)
app.include_router(voice_router.router)
app.include_router(spotify_router.router)
app.include_router(state_router.router)
app.include_router(train_router.router)
app.include_router(sleep_router.router)
app.include_router(luna_router.router)
app.include_router(agent_router.router)
app.include_router(channels_router.router)
app.include_router(admin_router.router)
app.include_router(workspace_integrations_router.router)
app.include_router(observe_router)
app.include_router(health_router)
app.include_router(coding_router)
app.include_router(proactive_router)
app.include_router(skills_router)
app.include_router(files_router)
app.include_router(settings_router)

# Serve Office Add-in static files at /addin/office/
office_addin_dir = Path(__file__).parent.parent / "interfaces" / "office"
if office_addin_dir.exists():
    app.mount("/addin/office", StaticFiles(directory=str(office_addin_dir)), name="office-addin")

# Serve the browser UI: the desktop app's renderer, so web and desktop are one UI.
# The renderer links its images as ../../resources/…, which resolves to /resources/.
web_ui_dir = Path(settings.web_ui_dir)
frontend_dist = Path(settings.frontend_dist)
if (web_ui_dir / "index.html").exists():
    web_ui_resources = Path(settings.web_ui_resources)
    if web_ui_resources.exists():
        app.mount("/resources", StaticFiles(directory=str(web_ui_resources)), name="web-ui-resources")
    app.mount("/", StaticFiles(directory=str(web_ui_dir), html=True), name="web-ui")
# Fallback: React frontend (production build)
elif frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        index = frontend_dist / "index.html"
        if index.exists():
            return FileResponse(str(index))
        return {"detail": "Frontend not built. Run: cd frontend && npm run build"}
