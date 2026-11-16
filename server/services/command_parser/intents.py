"""Direct intent parsers for app launch, map, and Spotify requests."""
import re


_LAUNCH_TRAILING_FILLERS = re.compile(r"\s+(?:for me|please|now|then|right now|already)$")


def parse_user_launch_request(message: str) -> str | None:
    text = " ".join(message.lower().strip().split())
    patterns = [
        r"^(?:please\s+)?(?:open|launch|start|run)\s+(.+)$",
        r"^(?:can|could|would)\s+you\s+(?:please\s+)?(?:open|launch|start|run)\s+(.+)$",
        r"^(?:i\s+want\s+you\s+to|i\s+need\s+you\s+to)\s+(?:open|launch|start|run)\s+(.+)$",
    ]
    for pattern in patterns:
        match = re.match(pattern, text)
        if not match:
            continue
        app_name = match.group(1).strip(" .?!")
        while True:
            stripped = _LAUNCH_TRAILING_FILLERS.sub("", app_name).strip()
            if stripped == app_name:
                break
            app_name = stripped
        if app_name and len(app_name) <= 80:
            return app_name
    return None


def parse_user_map_request(message: str) -> dict | None:
    text = " ".join(message.lower().strip().split()).strip(" .?!")
    text = re.sub(r"^(?:hey luna|luna)[, ]+", "", text).strip()

    close_patterns = [
        r"^(?:please\s+)?(?:close|hide|dismiss|exit)\s+(?:the\s+)?map$",
        r"^(?:can|could|would)\s+you\s+(?:please\s+)?(?:close|hide|dismiss|exit)\s+(?:the\s+)?map$",
    ]
    if any(re.match(p, text) for p in close_patterns):
        return {"action": "close"}

    open_patterns = [
        r"^(?:please\s+)?(?:bring up|pull up|open|show|display|launch)\s+(?:the\s+)?map$",
        r"^(?:please\s+)?(?:bring up|pull up|open|show|display|launch)\s+(?:the\s+)?(?:usa|us|america|united states)\s+map$",
        r"^(?:can|could|would)\s+you\s+(?:please\s+)?(?:bring up|pull up|open|show|display|launch)\s+(?:the\s+)?map$",
        r"^(?:show|display)\s+my\s+location$",
        r"^(?:where am i|where am i right now)$",
        r"^my location$",
    ]
    if any(re.match(p, text) for p in open_patterns):
        return {"action": "open"}

    text = re.sub(r"^(?:now\s+)?(?:can|could|would)\s+you\s+(?:please\s+)?", "", text).strip()
    route_patterns = [
        r"^(?:get\s+)?directions?\s+to\s+(.+)$",
        r"^(?:navigate|navigation)\s+to\s+(.+)$",
        r"^(?:how\s+do\s+i\s+(?:get|reach)\s+to\s+|how\s+to\s+(?:get|reach)\s+to\s+)(.+)$",
        r"^(?:route|routing)\s+to\s+(.+)$",
        r"^(?:take\s+me\s+to|go\s+to)\s+(.+)\s+on\s+(?:the\s+)?map$",
        r"^(?:show\s+(?:me\s+)?(?:the\s+)?(?:way|route)\s+to)\s+(.+)$",
        r"^how\s+(?:do\s+i\s+|to\s+)?(?:get|reach|go)\s+there(?:\s+from\s+here)?$",
        r"^how\s+(?:do\s+i\s+|to\s+)?(?:get|reach)\s+(?:to\s+)?(?:it|that|there)$",
    ]
    for p in route_patterns:
        m = re.match(p, text)
        if m:
            query = m.group(1).strip(" .?!")
            if query and len(query) <= 120:
                return {"action": "route", "query": query}

    text = re.sub(r"^(?:now\s+)?(?:can|could|would)\s+you\s+(?:please\s+)?", "", text).strip()
    where_is_patterns = [
        r"^where\s+is\s+(.+)$",
        r"^where(?:'s|\s+is)\s+(?:the\s+)?(.+)$",
    ]
    for p in where_is_patterns:
        m = re.match(p, text)
        if m:
            query = m.group(1).strip(" .?!")
            if query and len(query) <= 120:
                return {"action": "route", "query": query}

    search_patterns = [
        r"^(?:search|find|look\s+up|show\s+me)\s+(.+?)\s+on\s+(?:the\s+)?map$",
        r"^(?:search|find|look\s+up)\s+(.+?)\s+(?:near\s+(?:me|here)|nearby)$",
        r"^(?:where\s+is\s+the\s+nearest?)\s+(.+)$",
        r"^(?:find\s+(?:a|the|some|me\s+a|me\s+the|me\s+some|me\s+)\s*)(.+?)\s+(?:near\s+(?:me|here)|nearby|close\s+by)$",
        r"^(?:any\s+)(.+?)\s+(?:near\s+(?:me|here)|nearby)$",
        r"^(?:show\s+me\s+)(.+?)\s+(?:near\s+(?:me|here)|nearby|close\s+by)$",
        r"^(?:map\s+search\s+(?:for\s+)?)(.+)$",
        r"^(.+?)\s+(?:near\s+(?:me|here)|nearby)$",
    ]
    for p in search_patterns:
        m = re.match(p, text)
        if m:
            query = m.group(1).strip(" .?!")
            if query and len(query) <= 120:
                return {"action": "search", "query": query}
    return None


def parse_user_spotify_request(message: str, current_track: dict | None = None) -> dict | None:
    text = " ".join(message.lower().strip().split()).strip(" .?!")
    if not text:
        return None
    text = re.sub(r"^(?:hey luna|luna)[, ]+", "", text).strip()
    text = re.sub(r"\b(?:on spotify|from spotify)\b", "", text).strip()
    text = re.sub(r"\s+", " ", text)

    if text in {
        "pause", "pause music", "pause song", "pause track",
        "pause the music", "pause the song", "pause spotify",
        "stop music", "stop the music", "stop spotify",
    }:
        return {"action": "pause"}

    if text in {
        "next", "next song", "next track", "skip", "skip song", "skip track",
        "skip this", "skip this song", "skip this track",
    }:
        return {"action": "next"}

    if text in {
        "previous", "prev", "last song", "previous song", "previous track",
        "go back", "back one", "go to previous song", "go to the previous song",
    }:
        return {"action": "prev"}

    if text in {
        "resume", "resume music", "resume the music", "resume spotify",
        "resume song", "resume the song", "resume track", "resume the track",
        "resume playback", "resume it", "unpause", "unpause music",
        "unpause the music", "unpause song", "unpause the song",
        "play", "play music", "play the music", "play spotify",
        "play some music", "start music", "start the music",
        "continue", "continue music", "continue the music",
        "continue song", "continue the song", "keep playing",
    }:
        return {"action": "play", "query": None}

    if text in {"replay", "play it again", "play that again", "run it back", "restart this song"}:
        if current_track:
            return {"action": "play", "query": f"{current_track['title']} {current_track['artist']}"}
        return {"action": "play", "query": None}

    queue_patterns = [
        r"^(?:please\s+)?(?:queue up|queue)\s+(.+)$",
        r"^(?:please\s+)?(?:add)\s+(.+?)\s+(?:to|into|in)\s+(?:the\s+)?queue$",
        r"^(?:please\s+)?(?:add)\s+(.+?)\s+(?:next|up next)$",
        r"^(?:can|could|would)\s+you\s+(?:please\s+)?(?:queue up|queue)\s+(.+)$",
        r"^(?:can|could|would)\s+you\s+(?:please\s+)?(?:add)\s+(.+?)\s+(?:to|into|in)\s+(?:the\s+)?queue$",
        r"^(?:can|could|would)\s+you\s+(?:please\s+)?(?:add)\s+(.+?)\s+(?:next|up next)$",
    ]
    for pattern in queue_patterns:
        match = re.match(pattern, text)
        if not match:
            continue
        query = match.group(1).strip(" .?!")
        query = re.sub(r"^(?:the song|song|track|music)\s+", "", query).strip()
        query = re.sub(r"\s+(?:for me|please|right now|now)$", "", query).strip()
        if query and len(query) <= 120:
            return {"action": "queue", "query": query}

    lead_in = (
        r"(?:please\s+)?"
        r"(?:(?:can|could|would)\s+you\s+(?:please\s+)?|"
        r"(?:i\s+want\s+you\s+to|i\s+need\s+you\s+to|i\s+wanna|i\s+want\s+to)\s+)?"
    )
    play_verbs = (
        r"let'?s listen to|i want to hear|i wanna hear|start playing|"
        r"play me|put on|put some|throw on|turn on|listen to|"
        r"play|put|start"
    )
    patterns = [
        rf"^{lead_in}(?:{play_verbs})\s+(.+)$",
        r"^i(?:'| a)?m in the mood for\s+(.+)$",
        r"^some\s+(.+)$",
    ]
    for pattern in patterns:
        match = re.match(pattern, text)
        if not match:
            continue
        query = match.group(1).strip(" .?!")
        query = re.sub(r"^(?:the song|song|track|music)\s+", "", query).strip()
        query = re.sub(r"\s+(?:for me|please|right now|now)$", "", query).strip()
        if query in {"music", "some music", "spotify", "a song", "song", "track"}:
            query = ""
        if len(query) <= 120:
            return {"action": "play", "query": query or None}
    return None
