"""Open a website in a browser, in the right profile, without stopping at the profile picker.

"Open my Gmail in Chrome" used to launch plain chrome.exe, which stops at
Chrome's "Who's using Chrome?" picker when it has several profiles. This
opens the page directly: chrome.exe --profile-directory="<dir>" <url>.

Profile choice, in order: one named in the request ("in my Work profile",
"with acme"), the Browser profile setting (browser_profile), then the
profile Chrome used last. Profiles are read from Chrome's (or Edge's)
"Local State" file: names and account domains only.
"""
from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus

from server.config import settings

SYSTEM = platform.system()

SITES: dict[str, tuple[str, str]] = {
    # name: (url, word expected in the window title once it loads)
    "gmail": ("https://mail.google.com/", "gmail"),
    "mail": ("https://mail.google.com/", "gmail"),
    "email": ("https://mail.google.com/", "gmail"),
    "inbox": ("https://mail.google.com/", "gmail"),
    "google calendar": ("https://calendar.google.com/", "calendar"),
    "calendar": ("https://calendar.google.com/", "calendar"),
    "google drive": ("https://drive.google.com/", "drive"),
    "drive": ("https://drive.google.com/", "drive"),
    "google docs": ("https://docs.google.com/", "docs"),
    "google sheets": ("https://sheets.google.com/", "sheets"),
    "google maps": ("https://maps.google.com/", "maps"),
    "youtube": ("https://www.youtube.com/", "youtube"),
    "github": ("https://github.com/", "github"),
    "outlook": ("https://outlook.office.com/mail/", "outlook"),
    "linkedin": ("https://www.linkedin.com/", "linkedin"),
    "whatsapp web": ("https://web.whatsapp.com/", "whatsapp"),
    "chatgpt": ("https://chatgpt.com/", "chatgpt"),
    "claude": ("https://claude.ai/", "claude"),
    "netflix": ("https://www.netflix.com/", "netflix"),
    "amazon": ("https://www.amazon.com/", "amazon"),
    "reddit": ("https://www.reddit.com/", "reddit"),
    "twitter": ("https://x.com/", " x"),
    "x": ("https://x.com/", " x"),
    "instagram": ("https://www.instagram.com/", "instagram"),
    "notion": ("https://www.notion.so/", "notion"),
    "canvas": ("https://canvas.asu.edu/", "canvas"),
}
# Opened as websites even without "in chrome" (no desktop app is meant by these).
WEB_ONLY = {"gmail", "google calendar", "google drive", "google docs", "google sheets", "google maps",
            "youtube", "github", "linkedin", "whatsapp web", "chatgpt", "inbox", "reddit", "netflix", "amazon"}

BROWSERS = {
    "chrome": "chrome", "google chrome": "chrome",
    "edge": "edge", "microsoft edge": "edge",
    "firefox": "firefox", "brave": "brave",
    "browser": "", "my browser": "", "the browser": "",
}

_URL_RE = re.compile(r"^(?:https?://)?(?:[\w-]+\.)+[a-z]{2,}(?:/\S*)?$", re.IGNORECASE)
_OPEN_RE = re.compile(r"^(?:please\s+)?(?:(?:can|could|would)\s+you\s+(?:please\s+)?)?"
                      r"(?:open|launch|go\s+to|take\s+me\s+to|show\s+me|bring\s+up|pull\s+up)\s+(?P<rest>.+?)[\s.!?]*$",
                      re.IGNORECASE)
_PROFILE_RE = re.compile(r"\s+(?:with|using|in|on|from)\s+(?:my\s+|the\s+)?"
                         r"(?P<profile>(?:(?!\b(?:in|on|with|using|from|chrome|edge|browser)\b)[\w.@-]+\s*){1,3}?)\s*"
                         r"(?:chrome\s+|browser\s+)?profile$", re.IGNORECASE)
_FILLERS_RE = re.compile(r"\s+(?:please|for me|now|right now|real quick)$", re.IGNORECASE)
_BROWSER_RE = re.compile(r"\s+(?:in|on|with|using)\s+(?:my\s+|the\s+)?(?P<browser>google chrome|chrome|microsoft edge|edge|firefox|brave|browser)$",
                         re.IGNORECASE)


_MAIL_WORD = re.compile(r"\b(?:g-?mails?|e-?mails?|mails?|inbox)\b", re.IGNORECASE)
_MAIL_TIME = [
    (re.compile(r"\b(?:from\s+|since\s+|in\s+)?today\b", re.I), "newer_than:1d"),
    (re.compile(r"\b(?:from\s+|since\s+)?yesterday\b", re.I), "newer_than:2d"),
    (re.compile(r"\b(?:from\s+|in\s+|over\s+)?(?:the\s+)?(?:last|past|this)\s+week\b", re.I), "newer_than:7d"),
    (re.compile(r"\b(?:from\s+|in\s+|over\s+)?(?:the\s+)?(?:last|past|this)\s+month\b", re.I), "newer_than:31d"),
]
_MAIL_FLAGS = [
    (re.compile(r"\bunread\b", re.I), "is:unread"),
    (re.compile(r"\bstarred\b", re.I), "is:starred"),
    (re.compile(r"\bimportant\b", re.I), "is:important"),
    (re.compile(r"\b(?:with|having|that\s+have)\s+(?:an?\s+)?attachments?\b", re.I), "has:attachment"),
]
_STOP = r"(?=\s+(?:about|regarding|on|re|related\s+to|with|to|from|that|which|in|sent)\b|\s*$)"
_MAIL_FROM = re.compile(rf"\bfrom\s+(?P<who>[\w.@'+-]+(?:\s+[\w.@'+-]+)?){_STOP}", re.I)
_MAIL_TO = re.compile(rf"\b(?:sent\s+)?to\s+(?P<who>[\w.@'+-]+(?:\s+[\w.@'+-]+)?){_STOP}", re.I)
_MAIL_SUBJECT = re.compile(r"\bwith\s+(?:the\s+)?subject\s+(?:line\s+)?[\"“']?(?P<what>[^\"”']+?)[\"”']?$", re.I)
_MAIL_ABOUT = re.compile(r"\b(?:about|regarding|related\s+to|on\s+the\s+topic\s+of|re)\s+(?:the\s+|my\s+|our\s+|a\s+|an\s+)?(?P<what>.+?)$", re.I)


_MAIL_LEAD_WORDS = {"my", "the", "all", "new", "latest", "recent", "last", "unread", "starred", "important",
                    "an", "a", "any", "some", "those", "these", "that", "this", "today's", "todays"}


def gmail_search_query(text: str) -> str:
    """Gmail search operators for 'mails from priya about the invoice', 'unread emails from last week'…"""
    rest, parts = f" {text} ", []
    for pattern, op in _MAIL_TIME + _MAIL_FLAGS:
        if pattern.search(rest):
            parts.append(op)
            rest = pattern.sub(" ", rest)
    m = _MAIL_SUBJECT.search(rest.strip())
    if m:
        parts.append(f'subject:({m.group("what").strip()})')
        rest = rest.strip()[:m.start()]
    for pattern, op in ((_MAIL_FROM, "from"), (_MAIL_TO, "to")):
        m = pattern.search(rest)
        if m:
            who = re.sub(r"^(?:the|my|our)\s+", "", m.group("who").strip(), flags=re.I)
            parts.append(f"{op}:{who}" if " " not in who else f'{op}:"{who}"')
            rest = rest[:m.start()] + " " + rest[m.end():]
    m = _MAIL_ABOUT.search(rest.strip())
    if m:
        about = m.group("what").strip(" .?!")
        if about:
            parts.append(about)
    return " ".join(dict.fromkeys(parts))


def _mail_search_url(query: str) -> str:
    from urllib.parse import quote
    return f"https://mail.google.com/mail/u/0/#search/{quote(query, safe='')}"


@dataclass
class WebRequest:
    url: str
    site: str           # what the user called it
    title_hint: str     # word expected in the window title
    browser: str        # "chrome", "edge", "firefox", "brave", or "" for the default
    profile: str        # requested profile, "" for the default
    key: str = ""       # SITES key when it's a known site ("linkedin"), for "search … in it" later
    query: str = ""     # what was searched, for "search it on youtube" later


# Each site's own search page ("search OpenAI on LinkedIn" opens LinkedIn's results, not a web search).
SEARCH_URLS: dict[str, str] = {
    "linkedin": "https://www.linkedin.com/search/results/all/?keywords={q}",
    "youtube": "https://www.youtube.com/results?search_query={q}",
    "github": "https://github.com/search?q={q}",
    "amazon": "https://www.amazon.com/s?k={q}",
    "reddit": "https://www.reddit.com/search/?q={q}",
    "x": "https://x.com/search?q={q}", "twitter": "https://x.com/search?q={q}",
    "netflix": "https://www.netflix.com/search?q={q}",
    "google drive": "https://drive.google.com/drive/search?q={q}", "drive": "https://drive.google.com/drive/search?q={q}",
    "google maps": "https://www.google.com/maps/search/{q}", "maps": "https://www.google.com/maps/search/{q}",
    "gmail": "MAIL", "mail": "MAIL", "email": "MAIL", "inbox": "MAIL",
    # Not "google": "search X on google" keeps meaning Luna's own web search, answered in chat.
}
SITES.setdefault("maps", ("https://maps.google.com/", "maps"))
_SITE_SUFFIX = re.compile(r"\s+(?:account|website|site|page|tab|app)$", re.IGNORECASE)
_THIS_SITE = {"it", "there", "that", "this", "the page", "this page", "that page", "the site", "that site", "this site",
              "the website", "that website", "the same site", "the same page"}
_THIS_QUERY = {"it", "that", "this", "them", "the same", "the same thing"}


def resolve_site(name: str, *, fuzzy: bool = True) -> str | None:
    """A SITES key for what the user called the site: "LinkedIn", "the linked page" (speech typo), "you tube"."""
    text = _SITE_SUFFIX.sub("", re.sub(r"^(?:the|my|a)\s+", "", (name or "").strip().lower())).strip()
    if not text:
        return None
    if text in SITES:
        return text
    squashed = re.sub(r"[^a-z0-9]", "", text)
    for key in SITES:
        if re.sub(r"[^a-z0-9]", "", key) == squashed:
            return key
    if fuzzy and len(squashed) >= 4:
        from difflib import get_close_matches
        keys = {re.sub(r"[^a-z0-9]", "", k): k for k in SITES if len(k) >= 4}
        close = get_close_matches(squashed, list(keys), n=1, cutoff=0.75)
        if close:
            return keys[close[0]]
    return None


# conversation id → {"key", "query", "browser", "profile", "at"}: what "it" means in the next message
_RECENT: dict[int, dict] = {}
RECENT_TTL_S = 30 * 60


def remember_site(conversation_id, request: "WebRequest", profile_used: str | None = None) -> None:
    if conversation_id and request.key:
        import time
        previous = _RECENT.get(conversation_id, {})
        _RECENT[conversation_id] = {"key": request.key, "query": request.query or previous.get("query", ""),
                                    "browser": request.browser, "profile": request.profile or (profile_used or ""),
                                    "at": time.monotonic()}


def _recent(conversation_id) -> dict:
    import time
    entry = _RECENT.get(conversation_id or 0)
    if entry and time.monotonic() - entry["at"] <= RECENT_TTL_S:
        return entry
    return {}


_SEARCH_IN = re.compile(r"^(?:please\s+)?(?:(?:can|could)\s+you\s+)?(?:search|look\s+up|look\s+for|find)\s+(?:for\s+)?"
                        r"(?P<q>.+?)\s+(?:in|on|at|inside|within|through)\s+(?P<site>.+?)[\s.!?]*$", re.IGNORECASE)
_SEARCH_SITE_FOR = re.compile(r"^(?:please\s+)?(?:(?:can|could)\s+you\s+)?search\s+(?P<site>.+?)\s+for\s+(?P<q>.+?)[\s.!?]*$",
                              re.IGNORECASE)


def parse_site_search(message: str, conversation_id=None) -> Optional["WebRequest"]:
    """'search OpenAI on LinkedIn', 'search for open AI in it' (the site opened last), 'search it in the LinkedIn'
    (the thing searched last). None when no known site is meant — then it's a normal web search."""
    text = " ".join((message or "").split())
    m = _SEARCH_IN.match(text) or _SEARCH_SITE_FOR.match(text)
    if not m:
        return None
    query, site_text = m.group("q").strip(" \"'“”"), m.group("site").strip()
    recent = _recent(conversation_id)
    site_l = re.sub(r"^(?:the\s+)", "", site_text.lower()).strip()
    if site_text.lower() in _THIS_SITE or site_l in _THIS_SITE:
        key = recent.get("key")
    else:
        key = resolve_site(site_text, fuzzy=False)   # "google" must not become "google maps"
    if not key or key not in SEARCH_URLS:
        return None
    if query.lower() in _THIS_QUERY:
        query = recent.get("query", "")
        if not query:
            return None
    template = SEARCH_URLS[key]
    if template == "MAIL":
        url = _mail_search_url(query)
    else:
        url = template.format(q=quote_plus(query) if "maps/search" not in template else quote_plus(query))
    hint = SITES.get(key, ("", key))[1]
    same_site = recent.get("key") == key
    return WebRequest(url=url, site=f"{key.title() if key != 'x' else 'X'} search “{query}”", title_hint=hint,
                      browser=recent.get("browser", "") if same_site else "",
                      profile=recent.get("profile", "") if same_site else "", key=key, query=query)


def parse_web_open(message: str) -> Optional[WebRequest]:
    """'open my gmail in chrome', 'open youtube', 'go to github.com with my Work profile' → WebRequest."""
    match = _OPEN_RE.match(" ".join((message or "").split()))
    if not match:
        return None
    rest = match.group("rest").strip()
    while _FILLERS_RE.search(rest):
        rest = _FILLERS_RE.sub("", rest).strip()
    profile = browser = ""
    for _ in range(2):   # "in chrome with my work profile" or the other way round
        m = _PROFILE_RE.search(rest)
        if m:
            profile, rest = m.group("profile").strip(), rest[:m.start()].strip()
        m = _BROWSER_RE.search(rest)
        if m:
            browser, rest = BROWSERS.get(m.group("browser").lower(), ""), rest[:m.start()].strip()
            browser = browser or "default"
    site = re.sub(r"^(?:my|the|a|up)\s+", "", rest, flags=re.IGNORECASE).strip(" .")
    said_page = bool(re.search(r"\s+(?:website|site|page)$", site, flags=re.IGNORECASE))
    site = re.sub(r"\s+(?:account|website|site|page|tab)$", "", site, flags=re.IGNORECASE).strip()
    key = site.lower()
    explicit = bool(browser or profile)
    if said_page and key not in SITES:
        # "the linked page" (speech typo for LinkedIn): "page" says it's a website, so a near miss is safe.
        near = resolve_site(site)
        if near:
            site, key, explicit = near.title() if near != "x" else "X", near, True
    # Mail with a filter: "my mails from priya", "the email about the invoice", "unread emails".
    mail_word = _MAIL_WORD.search(key)
    if mail_word and key not in SITES:
        # Words before "mails" that aren't filters name the account: "my acme mails", "work emails".
        lead = [w for w in key[:mail_word.start()].split() if w not in _MAIL_LEAD_WORDS]
        if lead and not profile and len(lead) <= 2:
            profile = " ".join(lead)
        query = gmail_search_query(site)
        url, label = (_mail_search_url(query), f"Gmail search “{query}”") if query else ("https://mail.google.com/", "Gmail")
        return WebRequest(url=url, site=label, title_hint="gmail",
                          browser="" if browser == "default" else browser, profile=profile, key="gmail", query=query)
    if key not in SITES and not profile:
        # "my acme gmail": a profile hint in front of a known site.
        words = key.split()
        for cut in range(1, len(words)):
            head, tail = " ".join(words[:cut]), " ".join(words[cut:])
            if tail in SITES and len(head) <= 30:
                profile, site, key, explicit = head, " ".join(site.split()[cut:]), tail, True
                break
    if key in SITES and (explicit or key in WEB_ONLY):
        url, hint = SITES[key]
        return WebRequest(url=url, site=site, title_hint=hint, browser="" if browser == "default" else browser,
                          profile=profile, key=key)
    elif _URL_RE.match(site) and " " not in site:
        url = site if site.lower().startswith("http") else f"https://{site}"
        hint = re.sub(r"^(?:https?://)?(?:www\.)?", "", site.lower()).split(".")[0]
    elif explicit and site:
        url, hint = f"https://www.google.com/search?q={quote_plus(site)}", site.split()[0].lower()
    else:
        return None   # an app ("open spotify") — the app launcher handles it
    return WebRequest(url=url, site=site, title_hint=hint, browser="" if browser == "default" else browser,
                      profile=profile)


def request_for(site: str, browser: str = "", profile: str = "") -> Optional[WebRequest]:
    """A WebRequest from tool arguments (the model names the site, browser and profile separately)."""
    site = " ".join((site or "").split()).strip(" .")
    if not site:
        return None
    key = re.sub(r"^(?:my|the)\s+", "", site.lower())
    if re.match(r"^https?://\S+$", site, re.IGNORECASE):
        # A full link (from a QR code, say) opens as-is: IP addresses and ports included.
        url = site
        host = re.sub(r"^https?://(?:www\.)?", "", site.lower()).split("/")[0].split(":")[0]
        hint = host.split(".")[0] if not re.fullmatch(r"[\d.]+", host) else ""
    elif key in SITES:
        url, hint = SITES[key]
    elif _URL_RE.match(site) and " " not in site:
        url = site if site.lower().startswith("http") else f"https://{site}"
        hint = re.sub(r"^(?:https?://)?(?:www\.)?", "", site.lower()).split(".")[0]
    else:
        url, hint = f"https://www.google.com/search?q={quote_plus(site)}", key.split()[0]
    return WebRequest(url=url, site=site, title_hint=hint, browser=BROWSERS.get((browser or "").lower().strip(), browser or ""),
                      profile=(profile or "").strip())


# ── Profiles ─────────────────────────────────────────────────────────────────

@dataclass
class Profile:
    directory: str
    name: str
    account: str     # gaia name shown on the picker, if any
    email: str
    last_used: bool


def _user_data_dir(browser: str) -> Optional[Path]:
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    home = Path.home()
    candidates = {
        "chrome": [local / "Google/Chrome/User Data", home / "Library/Application Support/Google/Chrome",
                   home / ".config/google-chrome"],
        "edge": [local / "Microsoft/Edge/User Data", home / "Library/Application Support/Microsoft Edge",
                 home / ".config/microsoft-edge"],
        "brave": [local / "BraveSoftware/Brave-Browser/User Data",
                  home / "Library/Application Support/BraveSoftware/Brave-Browser", home / ".config/BraveSoftware/Brave-Browser"],
    }.get(browser, [])
    return next((p for p in candidates if (p / "Local State").exists()), None)


def list_profiles(browser: str = "chrome") -> list[Profile]:
    data_dir = _user_data_dir(browser)
    if not data_dir:
        return []
    try:
        state = json.loads((data_dir / "Local State").read_text(encoding="utf-8")).get("profile", {})
    except (OSError, ValueError):
        return []
    last = state.get("last_used", "Default")
    return [Profile(directory=d, name=str(i.get("name") or d), account=str(i.get("gaia_name") or ""),
                    email=str(i.get("user_name") or ""), last_used=d == last)
            for d, i in (state.get("info_cache") or {}).items()]


def _squash(text: str) -> str:
    return re.sub(r"[^a-z0-9@.]", "", (text or "").lower())


def profile_matches(profiles: list[Profile], wanted: str) -> list[Profile]:
    """Profiles a name, account name, email, email domain or folder refers to. An email or folder is exact."""
    w = _squash(wanted)
    if not w:
        return []
    exact_id = [p for p in profiles if w in {_squash(p.email), _squash(p.directory)}]
    if exact_id:
        return exact_id
    exact = [p for p in profiles if w in {_squash(p.name), _squash(p.account)}]
    return exact or [p for p in profiles if w in _squash(p.email).split("@")[-1] or w in _squash(p.name)
                     or (p.account and w in _squash(p.account))]


def describe_profile(p: Profile) -> str:
    """What tells same-named profiles apart: the account."""
    who = p.email or "no account signed in"
    extra = " · used last" if p.last_used else ""
    return f"{p.name} — {who}{extra}"


def pick_profile(profiles: list[Profile], requested: str = "") -> tuple[Optional[Profile], str]:
    """(profile, how it was chosen). how: asked | setting | last used | unknown | ambiguous | none.

    A name shared by several profiles (three called "Alexandra") is ambiguous: the caller asks
    which one, rather than guessing.
    """
    if not profiles:
        return None, "none"
    for wanted, how in ((requested, "asked"), (getattr(settings, "browser_profile", "") or "", "setting")):
        if not _squash(wanted):
            continue
        matches = profile_matches(profiles, wanted)
        if len(matches) == 1:
            return matches[0], how
        if len(matches) > 1:
            return None, "ambiguous"
        if how == "asked":
            return None, "unknown"
    last = next((p for p in profiles if p.last_used), profiles[0])
    return last, "last used"


# ── Opening ──────────────────────────────────────────────────────────────────

def _browser_exe(browser: str) -> Optional[str]:
    from server.services.app_launcher import find_app
    names = {"chrome": "chrome", "edge": "msedge", "firefox": "firefox", "brave": "brave"}
    ok, target = find_app(names.get(browser, browser))
    if ok and target and Path(target).exists():
        return target
    return shutil.which(names.get(browser, browser))


def open_website(request: WebRequest, launcher=None, verify: bool = True, sleep=None) -> dict:
    """Open the page; returns what was done and the evidence it worked."""
    launcher = launcher or subprocess.Popen
    browser = request.browser or "chrome"
    result = {"url": request.url, "site": request.site, "browser": browser, "profile": None, "chosen_by": "",
              "evidence": None, "error": ""}
    profiles = list_profiles(browser) if browser in ("chrome", "edge", "brave") else []
    profile, how = pick_profile(profiles, request.profile)
    if how == "ambiguous":
        wanted = request.profile or getattr(settings, "browser_profile", "")
        choices = profile_matches(profiles, wanted)
        result["choices"] = [{"profile": p.email or p.directory, "label": describe_profile(p)} for p in choices]
        options = "\n".join(f"{i}. {describe_profile(p)}" for i, p in enumerate(choices, 1))
        result["error"] = (f"You have {len(choices)} {browser.title()} profiles called '{wanted}'. Which one should I "
                           f"open {request.site} in?\n{options}\nReply with the number or the account.")
        result["question"] = True
        return result
    if request.profile and profile is None and profiles:
        options = "\n".join(f"- {describe_profile(p)}" for p in profiles)
        result["error"] = f"There's no {browser.title()} profile called '{request.profile}'. Your profiles:\n{options}"
        return result
    exe = _browser_exe(browser)
    if exe:
        command = [exe] + ([f"--profile-directory={profile.directory}"] if profile else []) + [request.url]
        launcher(command, close_fds=True)
    elif not request.browser and SYSTEM == "Windows":
        os.startfile(request.url)   # default browser
    else:
        result["error"] = f"{browser.title()} isn't installed on this computer."
        return result
    if profile:
        result["profile"] = profile.name + (f" ({profile.account})" if profile.account and profile.account != profile.name else "")
        result["profile_key"] = profile.email or profile.directory   # exact, for "search … in it" next
        result["chosen_by"] = how
    if verify and request.title_hint.strip():   # nothing to look for in the title (a bare IP link): skip
        from server.services.verification import verify_app_window
        kwargs = {"sleep": sleep} if sleep else {}
        result["evidence"] = verify_app_window(request.title_hint, "", timeout=10.0, **kwargs)
    return result


# ── Asking which profile ─────────────────────────────────────────────────────
# conversation id → (request waiting for a profile, its choices, when asked)
_PENDING: dict[int, tuple[WebRequest, list[dict], float]] = {}
PENDING_TTL_S = 15 * 60
_ORDINALS = {"first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3,
             "fourth": 4, "4th": 4, "fifth": 5, "5th": 5, "last": -1}
_CARDINALS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}   # only as the whole answer ("two")


def remember_question(conversation_id: Optional[int], request: WebRequest, result: dict) -> None:
    if conversation_id and result.get("choices"):
        import time
        _PENDING[conversation_id] = (request, result["choices"], time.monotonic())


def answer_pending(conversation_id: Optional[int], message: str) -> Optional[WebRequest]:
    """The waiting request with the profile the user just picked ("2", "the second one", an email, a button)."""
    import time
    pending = _PENDING.get(conversation_id or 0)
    if not pending or time.monotonic() - pending[2] > PENDING_TTL_S:
        _PENDING.pop(conversation_id or 0, None)
        return None
    request, choices, _ = pending
    text = " ".join((message or "").lower().replace("profile", " ").split()).strip(" .!?")
    if len(text) > 80:
        return None
    pick = None
    number = re.fullmatch(r"(?:use\s+|option\s+|number\s+|#)?(\d|one|two|three|four|five)", text)
    if number:
        n = int(number.group(1)) if number.group(1).isdigit() else _CARDINALS[number.group(1)]
        pick = choices[n - 1] if 1 <= n <= len(choices) else None
    for word, index in _ORDINALS.items():
        if pick is None and re.search(rf"\b{word}\b", text) and len(text.split()) <= 5:
            pick = choices[index - 1] if index > 0 and index <= len(choices) else (choices[-1] if index == -1 else None)
    if pick is None:
        squashed = _squash(text.replace("use ", "", 1))
        hits = [c for c in choices if squashed and (squashed == _squash(c["profile"]) or squashed in _squash(c["label"]))]
        pick = hits[0] if len(hits) == 1 else None
    if pick is None:
        return None
    _PENDING.pop(conversation_id, None)
    return WebRequest(url=request.url, site=request.site, title_hint=request.title_hint,
                      browser=request.browser, profile=pick["profile"], key=request.key, query=request.query)


def choice_buttons(result: dict) -> list[dict]:
    return [{"label": c["label"].split(" · ")[0].split(" — ")[-1], "message": f"Use profile {c['profile']}"}
            for c in result.get("choices", [])]


def describe(result: dict) -> str:
    """One reply line for the user, built only from what was checked."""
    if result["error"]:
        return result["error"]
    where = f" in {result['browser'].title()}"
    if result["profile"]:
        why = {"asked": "", "setting": " (your Browser profile setting)",
               "last used": " (the profile you used last; set another in Settings → Browser profile)"}.get(result["chosen_by"], "")
        where += f", profile {result['profile']}{why}"
    evidence = result["evidence"]
    if evidence is None:
        return f"Opened {result['site']}{where}."
    if evidence.verified:
        return f"Opened {result['site']}{where}. Checked: the window shows “{evidence.window['title']}”."
    return (f"Asked {result['browser'].title()} to open {result['site']}{where}, but I couldn't see it load within "
            "10 seconds. It may be waiting on a sign-in or still loading.")
