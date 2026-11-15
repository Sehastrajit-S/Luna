from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from backend.services.spotify import spotify_service

router = APIRouter(prefix="/api/spotify", tags=["spotify"])


class PlayRequest(BaseModel):
    query: str | None = None


@router.get("/status")
def get_status():
    return {
        "connected": spotify_service.is_connected,
        "current":   spotify_service.get_current(),
    }


@router.get("/auth-url")
def get_auth_url():
    return {"url": spotify_service.get_auth_url()}


@router.get("/callback")
def oauth_callback(code: str):
    spotify_service.handle_callback(code)
    return HTMLResponse("""
<!doctype html>
<html>
<head><style>
  body { background:#09090f; color:#a78bfa; font-family:monospace;
         display:flex; align-items:center; justify-content:center; height:100vh; margin:0; }
</style></head>
<body>
  <p>Spotify connected. You can close this tab.</p>
  <script>setTimeout(() => window.close(), 1500)</script>
</body>
</html>
""")


@router.post("/play")
def play(req: PlayRequest):
    ok = spotify_service.play(req.query)
    return {"ok": ok, "current": spotify_service.get_current()}


@router.post("/pause")
def pause():
    ok = spotify_service.pause()
    return {"ok": ok}


@router.post("/next")
def next_track():
    ok = spotify_service.next_track()
    return {"ok": ok, "current": spotify_service.get_current()}


@router.post("/prev")
def prev_track():
    ok = spotify_service.prev_track()
    return {"ok": ok, "current": spotify_service.get_current()}
