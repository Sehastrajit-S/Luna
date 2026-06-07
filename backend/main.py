from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.config import settings
from backend.models.database import init_db, Base, engine
from backend.services.activity_tracker import Activity
from backend.services.scheduler import luna_scheduler
from backend.routers import chat, memory, calendar, system, voice as voice_router, spotify as spotify_router, state as state_router, train as train_router, sleep as sleep_router, vision as vision_router, luna as luna_router, agent as agent_router, channels as channels_router, admin as admin_router, workspace_integrations as workspace_integrations_router
from backend.routers.proactive import router as proactive_router
from backend.routers.coding import router as coding_router
from backend.routers.observe import router as observe_router
from backend.routers.health_integrations import router as health_router
from backend.routers.skills import router as skills_router
from backend.middleware.rate_limit import RateLimitMiddleware
from backend.middleware.logging_middleware import RequestIDMiddleware, configure_logging
from backend.processes.registry import start_lifecycle_processes, stop_lifecycle_processes
from backend.services.telemetry import tracer
from backend.models.database import SessionLocal

# Configure structured logging before anything else logs
configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Init DB (creates all tables including Activity)
    Base.metadata.create_all(bind=engine)
    init_db()
    tracer.init(SessionLocal)
    luna_scheduler.start()
    start_lifecycle_processes()
    yield
    await tracer.flush()
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

# ── CORS ──────────────────────────────────────────────────────────────────────
# allow_origins=["*"] + allow_credentials=True is invalid per the CORS spec
# and creates CSRF exposure when JWT auth is active.  Use an explicit origin list.
_DEFAULT_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:8899",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8899",
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
app.include_router(vision_router.router)
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

# Serve Office Add-in static files at /addin/office/
office_addin_dir = Path(__file__).parent.parent / "office-addin"
if office_addin_dir.exists():
    app.mount("/addin/office", StaticFiles(directory=str(office_addin_dir)), name="office-addin")

# Serve React frontend (production build)
frontend_dist = Path(settings.frontend_dist)
if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        index = frontend_dist / "index.html"
        if index.exists():
            return FileResponse(str(index))
        return {"detail": "Frontend not built. Run: cd frontend && npm run build"}
