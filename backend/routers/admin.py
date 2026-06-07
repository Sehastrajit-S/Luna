"""
Admin API — production user and JWT token management.

Authentication
──────────────
All admin endpoints require a valid admin-role JWT in the Authorization header:
    Authorization: Bearer <admin-jwt>

To bootstrap the first admin token, use the /api/admin/bootstrap endpoint with
the admin_bootstrap_secret set in .env. This one-time secret is NEVER used as a
bearer token for other endpoints — it only generates the initial admin JWT.

After bootstrapping, use the returned admin JWT for all further admin calls.

Usage
─────
Bootstrap admin (first time only):
  POST /api/admin/bootstrap
  Body: { "bootstrap_secret": "<admin_bootstrap_secret from .env>" }
  Returns: { "token": "<admin-jwt>", "user_id": "...", "username": "admin" }

Create a user:
  POST /api/admin/users
  Body: { "username": "alice", "role": "user" }
  Returns: { "user_id": "...", "token": "..." }

List users:
  GET /api/admin/users

Revoke a user:
  DELETE /api/admin/users/{user_id}

Rotate a user token:
  POST /api/admin/users/{user_id}/rotate-token

System info:
  GET /api/admin/info
"""
import secrets
import time
import uuid
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from backend.config import settings
from backend.models.database import get_db
import backend.services.db_manager as db_mgr

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])

# Simple JSON flat-file store for users (no extra DB table required)
_USERS_FILE = Path("data/users.json")


# ── JWT helpers ───────────────────────────────────────────────────────────────

def _sign_jwt(user_id: str, username: str, role: str) -> str:
    """Create a HS256 JWT.  Falls back to opaque token if PyJWT is not installed."""
    try:
        import jwt  # PyJWT
        payload = {
            "sub": user_id,
            "username": username,
            "role": role,
            "iat": int(time.time()),
            "exp": int(time.time()) + settings.jwt_expiry_hours * 3600,
        }
        return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    except ImportError:
        # No PyJWT — fall back to an opaque random token stored in the user record
        return secrets.token_urlsafe(48)


def verify_jwt(token: str) -> dict | None:
    """Return decoded payload or None if invalid/expired."""
    try:
        import jwt
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except (ImportError, Exception) as e:
        logger.debug("JWT verification failed: %s", e)
        return None


# ── flat-file user store ──────────────────────────────────────────────────────

def _load_users() -> dict:
    import json
    if _USERS_FILE.exists():
        try:
            return json.loads(_USERS_FILE.read_text())
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load users file: %s", e)
    return {}


def _save_users(users: dict):
    import json
    _USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _USERS_FILE.write_text(json.dumps(users, indent=2))


# ── auth guard ────────────────────────────────────────────────────────────────

def _require_admin(request: Request):
    """
    Verify the caller has a valid admin-role JWT.

    SECURITY: The jwt_secret is NEVER accepted as a bearer token directly.
    Admin access requires a properly signed JWT with role="admin".
    """
    if not settings.jwt_secret:
        raise HTTPException(403, "Admin API requires jwt_secret to be set in .env")

    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Missing Authorization: Bearer <token> header")

    token = auth[7:]
    payload = verify_jwt(token)
    if payload is None:
        raise HTTPException(401, "Invalid or expired token")
    if payload.get("role") != "admin":
        raise HTTPException(403, "Admin role required")


# ── bootstrap endpoint ────────────────────────────────────────────────────────

@router.post("/bootstrap")
async def bootstrap_admin(request: Request):
    """
    One-time admin token generation using the bootstrap secret from .env.

    The bootstrap secret (admin_bootstrap_secret) is a separate value from
    jwt_secret, and is only used here to create the initial admin JWT.
    It should be rotated/removed from .env after first use in production.
    """
    if not settings.jwt_secret:
        raise HTTPException(503, "jwt_secret must be set in .env")
    if not settings.admin_bootstrap_secret:
        raise HTTPException(503, "admin_bootstrap_secret must be set in .env for bootstrapping")

    body = await request.json()
    provided_secret = str(body.get("bootstrap_secret", "")).strip()

    if not provided_secret:
        raise HTTPException(400, "bootstrap_secret is required in request body")

    # Constant-time comparison to prevent timing attacks
    if not secrets.compare_digest(provided_secret, settings.admin_bootstrap_secret):
        logger.warning("Failed admin bootstrap attempt from %s", request.client.host if request.client else "unknown")
        raise HTTPException(401, "Invalid bootstrap secret")

    # Create or find the admin user
    users = _load_users()
    admin_user = None
    for u in users.values():
        if u.get("username") == "admin" and u.get("role") == "admin":
            admin_user = u
            break

    if admin_user is None:
        user_id = str(uuid.uuid4())
        token = _sign_jwt(user_id, "admin", "admin")
        users[user_id] = {
            "user_id": user_id,
            "username": "admin",
            "role": "admin",
            "token": token,
            "created_at": datetime.utcnow().isoformat(),
            "active": True,
        }
        _save_users(users)
        logger.info("Admin user bootstrapped: %s", user_id)
        return {"user_id": user_id, "username": "admin", "role": "admin", "token": token}
    else:
        # Rotate existing admin token
        token = _sign_jwt(admin_user["user_id"], "admin", "admin")
        admin_user["token"] = token
        _save_users(users)
        logger.info("Admin token rotated via bootstrap for: %s", admin_user["user_id"])
        return {"user_id": admin_user["user_id"], "username": "admin", "role": "admin", "token": token}


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.get("/info")
def admin_info(request: Request):
    _require_admin(request)
    users = _load_users()
    return {
        "provider": settings.llm_provider,
        "model": _current_model(),
        "jwt_enabled": bool(settings.jwt_secret),
        "rate_limit_enabled": settings.rate_limit_enabled,
        "rate_limit_per_minute": settings.rate_limit_per_minute,
        "user_count": len(users),
        "channels": {
            "telegram": bool(settings.telegram_bot_token),
            "discord": bool(settings.discord_bot_token),
            "slack": bool(settings.slack_bot_token),
        },
    }


@router.get("/users")
def list_users(request: Request):
    _require_admin(request)
    users = _load_users()
    # Strip tokens from list response
    return [
        {k: v for k, v in u.items() if k != "token"}
        for u in users.values()
    ]


@router.post("/users", status_code=201)
def create_user(request: Request, body: dict):
    _require_admin(request)
    if not settings.jwt_secret:
        raise HTTPException(503, "jwt_secret must be set in .env to create users")

    username = str(body.get("username", "")).strip()
    role: Literal["admin", "user"] = body.get("role", "user")
    if not username:
        raise HTTPException(400, "username is required")
    if role not in ("admin", "user"):
        raise HTTPException(400, "role must be 'admin' or 'user'")

    users = _load_users()
    # Check uniqueness
    if any(u["username"] == username for u in users.values()):
        raise HTTPException(409, f"User '{username}' already exists")

    user_id = str(uuid.uuid4())
    token = _sign_jwt(user_id, username, role)
    users[user_id] = {
        "user_id": user_id,
        "username": username,
        "role": role,
        "token": token,
        "created_at": datetime.utcnow().isoformat(),
        "active": True,
    }
    _save_users(users)
    return {"user_id": user_id, "username": username, "role": role, "token": token}


@router.delete("/users/{user_id}")
def delete_user(user_id: str, request: Request):
    _require_admin(request)
    users = _load_users()
    if user_id not in users:
        raise HTTPException(404, "User not found")
    users.pop(user_id)
    _save_users(users)
    return {"ok": True, "user_id": user_id}


@router.post("/users/{user_id}/rotate-token")
def rotate_token(user_id: str, request: Request):
    _require_admin(request)
    if not settings.jwt_secret:
        raise HTTPException(503, "jwt_secret must be set in .env")
    users = _load_users()
    if user_id not in users:
        raise HTTPException(404, "User not found")
    u = users[user_id]
    new_token = _sign_jwt(user_id, u["username"], u["role"])
    u["token"] = new_token
    _save_users(users)
    return {"user_id": user_id, "token": new_token}


@router.get("/llm/providers")
def list_providers(request: Request):
    """Return all configured LLM providers and which is active."""
    _require_admin(request)
    return {
        "active": settings.llm_provider,
        "providers": {
            "ollama": {
                "configured": True,
                "model": settings.ollama_model,
                "base_url": settings.ollama_base_url,
            },
            "openai-compatible": {
                "configured": bool(settings.openai_api_key or settings.openai_base_url),
                "model": settings.openai_model,
                "base_url": settings.openai_base_url,
            },
            "nvidia-nim": {
                "configured": bool(settings.nvidia_nim_api_key and settings.nvidia_nim_base_url),
                "model": settings.nvidia_nim_model,
                "base_url": settings.nvidia_nim_base_url,
            },
            "anthropic": {
                "configured": bool(settings.anthropic_api_key),
                "model": settings.anthropic_model,
            },
            "google": {
                "configured": bool(settings.google_api_key),
                "model": settings.google_model,
            },
            "groq": {
                "configured": bool(settings.groq_api_key),
                "model": settings.groq_model,
            },
            "cohere": {
                "configured": bool(settings.cohere_api_key),
                "model": settings.cohere_model,
            },
            "mistral": {
                "configured": bool(settings.mistral_api_key),
                "model": settings.mistral_model,
            },
        },
    }


def _current_model() -> str:
    from backend.services.llm import ollama as llm
    return llm.model


# ── Database management ───────────────────────────────────────────────────────

@router.get("/database/status")
def database_status(request: Request, db: Session = Depends(get_db)):
    """Database health, connection pool stats, and per-table row counts."""
    _require_admin(request)
    return {
        **db_mgr.db_health(),
        "tables": db_mgr.table_stats(db),
        "migrations": db_mgr.migration_status(),
    }


@router.post("/database/migrate")
def run_migrations(request: Request):
    """Run `alembic upgrade head` — applies all pending schema migrations."""
    _require_admin(request)
    result = db_mgr.run_migrations()
    if not result.get("ok"):
        raise HTTPException(status_code=500, detail=result)
    return result


@router.get("/database/tables")
def table_stats(request: Request, db: Session = Depends(get_db)):
    """Row counts for all Luna tables."""
    _require_admin(request)
    return {"tables": db_mgr.table_stats(db)}
