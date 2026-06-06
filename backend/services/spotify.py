"""
Spotify integration — search, playback control, current track polling.
Credentials are read from data/integrations/.env.
"""
import re
from pathlib import Path

CREDS_FILE   = Path("data/integrations/.env")
TOKEN_CACHE  = Path("data/spotify_token.json")
REDIRECT_URI = "http://127.0.0.1:8899/api/spotify/callback"
SCOPES       = (
    "user-read-playback-state "
    "user-modify-playback-state "
    "user-read-currently-playing"
)


_NON_ORIGINAL = re.compile(
    r'\b(remix|cover|karaoke|tribute|mashup|medley|acoustic|live|version|edit|'
    r'instrumental|lofi|lo-fi|slowed|sped up|nightcore|flip)\b'
    r'|\bx\b',   # "Song x Other Song" mashups
    re.IGNORECASE,
)


def _pick_original(items: list[dict]) -> dict:
    """
    Prefer the original recording over covers/remixes/mashups.
    Score = popularity − penalty for non-original keywords in the title.
    """
    def score(t: dict) -> float:
        title = t.get("name", "")
        pop   = t.get("popularity", 0)
        # Heavy penalty for each non-original marker in the title
        penalty = len(_NON_ORIGINAL.findall(title)) * 30
        return pop - penalty

    return max(items, key=score)


_DEFAULT_CLIENT_ID     = "43e39c11e46449359f5090ca9fc1e7ee"
_DEFAULT_CLIENT_SECRET = "884d7cfd25bb461ebeae3a26f0a475c7"


def _load_creds() -> dict[str, str]:
    from backend.config import settings
    creds: dict[str, str] = {}
    # Primary: main .env via Settings
    if settings.spotify_client_id:
        creds["spotify_client_id"] = settings.spotify_client_id
    if settings.spotify_client_secret:
        creds["spotify_client_secret"] = settings.spotify_client_secret
    # Secondary: data/integrations/.env (legacy path)
    if not creds.get("spotify_client_id") and CREDS_FILE.exists():
        for line in CREDS_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                creds[k.strip()] = v.strip()
    # Fallback: built-in credentials (users just click Connect)
    if not creds.get("spotify_client_id"):
        creds["spotify_client_id"] = _DEFAULT_CLIENT_ID
    if not creds.get("spotify_client_secret"):
        creds["spotify_client_secret"] = _DEFAULT_CLIENT_SECRET
    return creds


class SpotifyService:
    def __init__(self):
        creds = _load_creds()
        self._client_id     = creds.get("spotify_client_id", "")
        self._client_secret = creds.get("spotify_client_secret", "")
        self._oauth         = None
        self._ready         = bool(self._client_id and self._client_secret)
        if self._ready:
            self._init_oauth()

    def _init_oauth(self):
        from spotipy.oauth2 import SpotifyOAuth
        self._oauth = SpotifyOAuth(
            client_id=self._client_id,
            client_secret=self._client_secret,
            redirect_uri=REDIRECT_URI,
            scope=SCOPES,
            cache_path=str(TOKEN_CACHE),
            open_browser=False,
        )

    # ── auth ──────────────────────────────────────────────────────────────────

    def get_auth_url(self) -> str:
        if not self._ready:
            return ""
        return self._oauth.get_authorize_url()

    def handle_callback(self, code: str):
        if self._oauth:
            self._oauth.get_access_token(code, as_dict=False)

    def _get_token(self) -> str | None:
        if not self._ready or not self._oauth:
            return None
        try:
            info = self._oauth.get_cached_token()
            if not info:
                return None
            if self._oauth.is_token_expired(info):
                info = self._oauth.refresh_access_token(info["refresh_token"])
            return info["access_token"]
        except Exception:
            return None

    def _client(self):
        import spotipy
        token = self._get_token()
        if not token:
            return None
        return spotipy.Spotify(auth=token, retries=1, status_retries=1)

    @property
    def is_connected(self) -> bool:
        return self._get_token() is not None

    @property
    def needs_auth(self) -> bool:
        """Credentials are configured but OAuth has not been completed yet."""
        return self._ready and not self.is_connected

    # ── playback ──────────────────────────────────────────────────────────────

    def get_current(self) -> dict | None:
        sp = self._client()
        if not sp:
            return None
        try:
            pb = sp.current_playback()
            if not pb or not pb.get("item"):
                return None
            item = pb["item"]
            images = item["album"]["images"]
            return {
                "title":       item["name"],
                "artist":      ", ".join(a["name"] for a in item["artists"]),
                "album":       item["album"]["name"],
                "cover":       images[0]["url"] if images else None,
                "progress_ms": pb["progress_ms"],
                "duration_ms": item["duration_ms"],
                "is_playing":  pb["is_playing"],
            }
        except Exception:
            return None

    def _get_device_id(self, sp) -> str | None:
        """Return a usable device ID, preferring desktop/computer devices."""
        try:
            devices = sp.devices().get("devices", [])
            if not devices:
                return None
            # Prefer computer / desktop type
            for d in devices:
                if d.get("type", "").lower() in ("computer", "desktop"):
                    return d["id"]
            return devices[0]["id"]
        except Exception:
            return None

    def _wake_device(self, sp, device_id: str | None) -> bool:
        """Transfer playback to device to wake it, return True if succeeded."""
        if not device_id:
            return False
        try:
            sp.transfer_playback(device_id=device_id, force_play=False)
            import time; time.sleep(1.2)
            return True
        except Exception:
            return False

    def play(self, query: str | None = None) -> bool:
        sp = self._client()
        if not sp:
            return False
        try:
            devices = sp.devices().get("devices", [])
            if not devices:
                print("[spotify] No devices found — Spotify may not be open")
                return False

            device_id = self._get_device_id(sp)
            uris = None
            if query:
                results = sp.search(q=query, type="track", limit=10)
                items = results["tracks"]["items"]
                if not items:
                    return False
                uris = [_pick_original(items)["uri"]]

            try:
                sp.start_playback(device_id=device_id, uris=uris)
            except Exception as first_err:
                no_device = "NO_ACTIVE_DEVICE" in str(first_err) or "404" in str(first_err)
                if no_device and device_id:
                    # Wake the device then retry
                    self._wake_device(sp, device_id)
                    try:
                        sp.start_playback(device_id=device_id, uris=uris)
                    except Exception:
                        sp.start_playback(uris=uris)
                else:
                    sp.start_playback(uris=uris)
            return True
        except Exception as e:
            print(f"[spotify] Play error: {e}")
            return False

    def queue(self, query: str) -> bool:
        sp = self._client()
        if not sp or not query:
            return False
        try:
            devices = sp.devices().get("devices", [])
            if not devices:
                print("[spotify] No devices found — Spotify may not be open")
                return False
            device_id = self._get_device_id(sp)
            results = sp.search(q=query, type="track", limit=10)
            items = results["tracks"]["items"]
            if not items:
                return False
            best = _pick_original(items)
            try:
                sp.add_to_queue(best["uri"], device_id=device_id)
            except Exception as first_err:
                no_device = "NO_ACTIVE_DEVICE" in str(first_err) or "404" in str(first_err)
                if no_device and device_id:
                    self._wake_device(sp, device_id)
                    sp.add_to_queue(best["uri"], device_id=device_id)
                else:
                    sp.add_to_queue(best["uri"])
            return True
        except Exception as e:
            print(f"[spotify] Queue error: {e}")
            return False

    def pause(self) -> bool:
        sp = self._client()
        if not sp:
            return False
        try:
            sp.pause_playback()
            return True
        except Exception:
            return False

    def next_track(self) -> bool:
        sp = self._client()
        if not sp:
            return False
        try:
            sp.next_track()
            return True
        except Exception:
            return False

    def prev_track(self) -> bool:
        sp = self._client()
        if not sp:
            return False
        try:
            sp.previous_track()
            return True
        except Exception:
            return False


spotify_service = SpotifyService()
