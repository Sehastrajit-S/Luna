"""Read a website in the user's own (logged-in) browser by looking at it: screenshot,
OCR, scroll, repeat. For things a web search can't answer: "find 10 internship
posts on LinkedIn from the last 20 minutes", "what's on my YouTube home page".

Nothing is clicked or typed into the page: it only opens a URL, presses Page
Down, and reads. LinkedIn posts are parsed into cards (author, headline, age,
text) so "posted within 20 minutes" is filtered exactly from LinkedIn's own
"15m" labels rather than guessed by the model. Other sites return the text seen.
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Callable, Optional
from urllib.parse import quote_plus

logger = logging.getLogger("luna.site_reader")

MAX_SCROLLS = 14
_AGE = re.compile(r"^(?P<n>\d{1,3})\s?(?P<unit>m|min|mins|h|hr|hrs|d|w|wk|mo|yr|y)\b|^(?P<now>now|just now)\b",
                  re.IGNORECASE)
_UNIT_MINUTES = {"m": 1, "min": 1, "mins": 1, "h": 60, "hr": 60, "hrs": 60, "d": 1440, "w": 10080, "wk": 10080,
                 "mo": 43200, "yr": 525600, "y": 525600}
_ACTIONS = {"like", "comment", "repost", "send", "share"}
_NOISE = {"more", "follow", "+ follow", "...", "…", "following", "promoted", "see more", "see translation"}


@dataclass
class Post:
    author: str
    headline: str
    age: str            # as LinkedIn shows it: "now", "15m", "2h"
    minutes_ago: int
    text: str

    def key(self) -> str:
        # The same post read on two screens can show more or less of its text; author + headline is stable.
        return re.sub(r"\W", "", (self.author + "|" + self.headline).lower())


@dataclass
class ReadResult:
    site: str
    url: str
    posts: list[Post] = field(default_factory=list)
    text: str = ""
    screens: int = 0
    screenshot: Optional[str] = None
    stopped_because: str = ""
    error: str = ""
    loaded_more: int = 0   # times "Load more" was clicked

    def as_tool_result(self, limit: int | None = None, max_age: int | None = None) -> dict:
        data = {"site": self.site, "url": self.url, "screens_read": self.screens, "stopped_because": self.stopped_because,
                "screenshot": self.screenshot}
        if self.error:
            data["error"] = self.error
        if self.posts:
            data["posts"] = [asdict(p) for p in self.posts]
            data["note"] = ("Ages come from LinkedIn's own labels ('15m' = 15 minutes ago). "
                            + (f"Only posts at most {max_age} minutes old are listed. " if max_age is not None else "")
                            + (f"Found {len(self.posts)} of the {limit} asked for." if limit else ""))
        elif self.text:
            data["text"] = self.text
        return data


# ── LinkedIn ─────────────────────────────────────────────────────────────────

def linkedin_posts_url(query: str, max_age_minutes: int | None = None) -> str:
    url = f"https://www.linkedin.com/search/results/content/?keywords={quote_plus(query)}&sortBy=%22date_posted%22"
    if max_age_minutes is not None and max_age_minutes <= 1440:
        url += "&datePosted=%22past-24h%22"
    elif max_age_minutes is not None and max_age_minutes <= 10080:
        url += "&datePosted=%22past-week%22"
    return url


def age_minutes(text: str) -> Optional[int]:
    t = (text or "").strip().lower().replace("•", " ").strip()
    m = _AGE.match(t)
    if not m:
        return None
    if m.group("now"):
        return 0
    return int(m.group("n")) * _UNIT_MINUTES[m.group("unit").lower()]


def _rows(boxes) -> list[list]:
    """OCR boxes grouped into visual rows, top to bottom."""
    rows: list[list] = []
    for b in sorted(boxes, key=lambda b: (b.top, b.left)):
        mid = (b.top + b.bottom) / 2
        if rows and abs(mid - rows[-1][0]) < max(8, (b.bottom - b.top) * 0.6):
            rows[-1][1].append(b)
        else:
            rows.append([mid, [b]])
    return [sorted(r[1], key=lambda b: b.left) for r in rows]


def _is_action_row(row) -> bool:
    words = {re.sub(r"[^a-z]", "", b.text.lower()) for b in row}
    return len(words & _ACTIONS) >= 2


def parse_linkedin_posts(boxes, width: int) -> list[Post]:
    """Posts whose header (author, age) is on this screen. Each post's text runs from its age line to its
    action row, the next post's header, or the bottom of the screen — image posts are often taller than
    the screen, so the action row can't be required."""
    lines: list[str] = []
    for row in _rows(b for b in boxes if b.top > 140):   # below LinkedIn's top bar
        joined = " ".join(b.text for b in row).strip()
        low = joined.lower()
        if "filters" in low or ("posted" in low and "content" in low):
            lines = []   # the filter chips ("Posts · Latest · Date posted · All filters"): posts start below
            continue
        squashed = re.sub(r"[^a-z]", "", low)
        if any(s in squashed for s in ("resultshelpful", "feedbackhelpsus", "loadmore", "linkedincorporation")):
            lines.append("\x00ACTIONS")   # LinkedIn's own widgets end the post above, and aren't posts
            continue
        lines.append("\x00ACTIONS" if _is_action_row(row) else joined)
    ages = [i for i, line in enumerate(lines) if age_minutes(line) is not None and i > 0]
    posts: list[Post] = []
    for n, i in enumerate(ages):
        # Header: up to two lines above the age line (author, then headline), after the previous post's end.
        start = max(ages[n - 1] + 1 if n else 0, i - 2)
        prev_actions = max((k for k in range(start, i) if lines[k] == "\x00ACTIONS"), default=None)
        if prev_actions is not None:
            start = prev_actions + 1
        header = [l for l in lines[start:i] if l != "\x00ACTIONS"]
        end = ages[n + 1] - 2 if n + 1 < len(ages) else len(lines)
        body = []
        for line in lines[i + 1:end]:
            if line == "\x00ACTIONS":
                break
            body.append(line)
        post = _card_to_post(header, lines[i], body)
        if post:
            posts.append(post)
    return posts


def _card_to_post(header_lines, age_line, body_lines) -> Optional[Post]:
    header = [l for l in header_lines if l.lower() not in _NOISE]
    if not header:
        return None
    author = re.split(r"\s*[•·]\s*", header[0])[0]
    author = re.sub(r"\s*(?:[+十]\s*)?Follow(?:ing)?\b.*$", "", author).strip(" +十")
    author = re.sub(r"\s+in$", "", author)   # LinkedIn's premium "in" badge after the name
    headline = header[1] if len(header) > 1 else ""
    age = re.split(r"\s*[•·]\s*|\s", age_line.strip())[0]
    body: list[str] = []
    for line in body_lines:
        clean = re.sub(r"\s*…?\s*more$", "", line).strip()
        if clean and clean.lower() not in _NOISE:
            body.append(clean)
    text = " ".join(body)
    if not author:
        return None
    return Post(author=author, headline=headline, age=age, minutes_ago=age_minutes(age_line) or 0, text=text[:500])


_READ_SITES = {"linkedin": "linkedin", "linked in": "linkedin", "youtube": "youtube", "you tube": "youtube",
               "reddit": "reddit", "github": "github", "twitter": "x", "x.com": "x"}
_READ_VERB = re.compile(r"\b(?:find|show|get|list|read|look\s+for|look\s+up|search\s+for|search|pull\s+up|give\s+me|check)\b",
                        re.IGNORECASE)
_SITE_MENTION = re.compile(r"\b(?:on|in|from|at|through)?\s*(?:the\s+|my\s+)?(linked\s*in|you\s*tube|reddit|github|twitter|x\.com)\b",
                           re.IGNORECASE)
_COUNT = re.compile(r"\b(?P<n>\d{1,2})\s+(?:\w+\s+){0,2}?(?:posts?|jobs?|results?|videos?|items?|listings?|openings?)\b",
                    re.IGNORECASE)
_WITHIN = re.compile(r"\b(?:posted\s+)?(?:within|in\s+the\s+(?:last|past)|from\s+the\s+(?:last|past)|over\s+the\s+(?:last|past)|"
                     r"in\s+(?:the\s+)?last|past|last|under|less\s+than)\s+(?P<n>\d{1,4}|an?|one)\s*"
                     r"(?P<unit>minutes?|mins?|m|hours?|hrs?|h|days?|d)\b(?:\s+ago)?", re.IGNORECASE)
_TODAY = re.compile(r"\b(?:posted\s+)?today\b", re.IGNORECASE)
_FILLER = re.compile(r"\b(?:posts?|jobs?|results?|videos?|items?|listings?|openings?|posted|with|about|for|on|in|of|"
                     r"the|my|me|some|any|latest|recent|new|newest|that|which|are|is|as|follows?|please|can|you|could|"
                     r"mention(?:ing)?|related|to|containing|having|ago|open|opening|go|and|there|it)\b", re.IGNORECASE)


def parse_read_request(message: str) -> Optional[dict]:
    """'find 10 posts with internship posted within 20 mins on linkedin' →
    {"site": "linkedin", "query": "internship", "limit": 10, "max_age_minutes": 20}. None if it isn't one."""
    text = " ".join((message or "").split())
    site_m = _SITE_MENTION.search(text)
    if not site_m or not _READ_VERB.search(text):
        return None
    site = _READ_SITES.get(re.sub(r"\s+", " ", site_m.group(1).lower()).replace("linkedin", "linkedin"), None) \
        or _READ_SITES.get(site_m.group(1).lower().replace(" ", ""), None)
    if site is None:
        return None
    if re.search(r"\b(?:open|go\s+to)\b", text, re.IGNORECASE) and not _COUNT.search(text) and not _WITHIN.search(text):
        return None   # "open linkedin and search …" is the open/search path
    rest = text[:site_m.start()] + " " + text[site_m.end():]
    limit = None
    m = _COUNT.search(rest)
    if m:
        limit = int(m.group("n"))
        rest = rest[:m.start()] + " " + rest[m.end():]
    max_age = None
    m = _WITHIN.search(rest)
    if m:
        n = m.group("n").lower()
        n = 1 if n in ("a", "an", "one") else int(n)
        unit = m.group("unit").lower()
        max_age = n * (60 if unit.startswith("h") else 1440 if unit.startswith("d") else 1)
        rest = rest[:m.start()] + " " + rest[m.end():]
    elif _TODAY.search(rest):
        max_age = 1440
        rest = _TODAY.sub(" ", rest)
    rest = _READ_VERB.sub(" ", rest)
    rest = re.sub(r"[^\w\s#+.-]", " ", rest)
    query = " ".join(_FILLER.sub(" ", rest).split()).strip(" .-")
    if not query or (limit is None and max_age is None and not re.search(r"\bposts?\b", text, re.IGNORECASE)):
        return None
    return {"site": site, "query": query, "limit": limit or 10, "max_age_minutes": max_age}


def describe_read(result: "ReadResult", ask: dict) -> str:
    """The reply, built only from what was read."""
    site = {"linkedin": "LinkedIn", "youtube": "YouTube", "github": "GitHub", "x": "X"}.get(ask["site"], ask["site"].title())
    if result.error:
        return result.error
    if not result.posts:
        within = f" from the last {_ago(ask['max_age_minutes'])}" if ask.get("max_age_minutes") is not None else ""
        if result.text:
            return f"Here's what's on {site} for “{ask['query']}”:\n\n{result.text[:3000]}"
        return (f"I didn't find any {site} posts about “{ask['query']}”{within} "
                f"(read {result.screens} screens; {result.stopped_because}).")
    within = f" from the last {_ago(ask['max_age_minutes'])}" if ask.get("max_age_minutes") is not None else ""
    found = len(result.posts)
    short = f" — that's all {site} had{within}" if found < ask["limit"] else ""
    lines = [f"Found {found} {site} post{'s' if found != 1 else ''} about “{ask['query']}”{within}{short}:"]
    for i, p in enumerate(result.posts, 1):
        when = "just now" if p.minutes_ago == 0 else f"{_ago(p.minutes_ago)} ago"
        head = f" — {p.headline}" if p.headline else ""
        snippet = (p.text[:180] + "…") if len(p.text) > 180 else p.text
        lines.append(f"{i}. **{p.author}**{head} · {when}\n   {snippet}")
    lines.append(f"\n(Ages from LinkedIn's labels; read {result.screens} screens in your browser.)")
    return "\n".join(lines)


def _ago(minutes: int) -> str:
    if minutes < 60:
        return f"{minutes} min"
    if minutes < 1440:
        h = minutes // 60
        return f"{h} hour{'s' if h != 1 else ''}"
    d = minutes // 1440
    return f"{d} day{'s' if d != 1 else ''}"


def plan_read(args: dict) -> dict:
    """read_site arguments from the tool call: which URL, posts mode, limits."""
    from server.services import browser_open as B

    site = str(args.get("site") or "").strip()
    query = " ".join(str(args.get("query") or "").split())
    try:
        limit = max(1, min(int(args.get("limit") or 10), 30))
    except (TypeError, ValueError):
        limit = 10
    try:
        max_age = int(args["max_age_minutes"]) if args.get("max_age_minutes") not in (None, "") else None
    except (TypeError, ValueError):
        max_age = None
    key = B.resolve_site(site) if site else None
    if key == "linkedin" and query:
        url, posts, hint = linkedin_posts_url(query, max_age), True, "linkedin"
    elif key and query and key in B.SEARCH_URLS and B.SEARCH_URLS[key] != "MAIL":
        url, posts, hint = B.SEARCH_URLS[key].format(q=quote_plus(query)), False, B.SITES[key][1].strip()
    elif key:
        url, posts, hint = B.SITES[key][0], False, B.SITES[key][1].strip()
    elif re.match(r"^(?:https?://)?(?:[\w-]+\.)+[a-z]{2,}", site, re.IGNORECASE):
        url = site if site.lower().startswith("http") else f"https://{site}"
        posts, hint = False, re.sub(r"^(?:https?://)?(?:www\.)?", "", site.lower()).split(".")[0]
    else:
        return {"error": f"I don't know the site '{site}'. Give its name (linkedin, youtube…) or a URL."}
    # Enough scrolling to see `limit` posts (about 2 complete posts per screen).
    scrolls = min(MAX_SCROLLS, max(3, limit + 2))   # about one complete post per screen with images
    browser = B.BROWSERS.get(str(args.get("browser") or "").lower(), "") or "chrome"
    return {"limit": limit, "max_age": max_age,
            "read": {"url": url, "site": site, "title_hint": hint, "profile": str(args.get("profile") or ""),
                     "browser": browser, "linkedin_posts": posts, "limit": limit, "max_age_minutes": max_age,
                     "scrolls": scrolls}}


def _same_post(posts, post: Post) -> Optional[Post]:
    """The same post read again with a different headline/OCR: same author, and the texts agree
    (or one screen showed none of the text)."""
    def start(text):
        return re.sub(r"\W", "", text.lower())[:30]
    for known in posts:
        if re.sub(r"\W", "", known.author.lower()) != re.sub(r"\W", "", post.author.lower()):
            continue
        a, b = start(known.text), start(post.text)
        if not a or not b or a.startswith(b[:15]) or b.startswith(a[:15]):
            return known
    return None


# The only things read_site ever clicks: buttons that load more of the same results.
LOAD_MORE_LABELS = ("load more", "show more results", "see more results", "show more posts", "more results")


def find_load_more(boxes) -> Optional[tuple[int, int]]:
    for b in boxes:
        label = " ".join(b.text.lower().split())
        if label in LOAD_MORE_LABELS:
            return int((b.left + b.right) / 2), int((b.top + b.bottom) / 2)
    return None


def _same_picture(a, b) -> bool:
    try:
        from PIL import ImageChops
        small_a, small_b = a.convert("L").resize((96, 96)), b.convert("L").resize((96, 96))
        diff = ImageChops.difference(small_a, small_b)
        return sum(diff.getdata()) / (96 * 96) < 1.5
    except Exception:
        return False


# ── Reading loop ─────────────────────────────────────────────────────────────

def read_site(url: str, site: str, *, title_hint: str, profile: str = "", browser: str = "chrome",
              linkedin_posts: bool = False, limit: int = 10, max_age_minutes: int | None = None,
              scrolls: int = 6, sleep: Callable[[float], None] = time.sleep,
              opener=None, find_window=None, capture=None, keys=None, ocr=None) -> ReadResult:
    from server.services import browser_open as B
    from server.services import desktop_input as K_default
    from server.services import verification as V

    K = keys or K_default
    result = ReadResult(site=site, url=url)
    request = B.WebRequest(url=url, site=site, title_hint=title_hint, browser=browser, profile=profile)
    opened = (opener or B.open_website)(request)
    if opened.get("error"):
        result.error = opened["error"]
        return result
    sleep(4.0)   # let the page load and render
    win = (find_window or (lambda: V.window_titled(title_hint, {"chrome.exe", "msedge.exe", "brave.exe", "firefox.exe"})))()
    if not win:
        result.error = "The page opened, but I couldn't find its browser window to read."
        return result
    hwnd = win["hwnd"]
    capture = capture or (lambda: V.capture_window(hwnd))
    if ocr is None:
        from server.services.files.ocr import ocr_boxes as ocr
    previous = K.foreground()
    seen: dict[str, Post] = {}
    text_lines: list[str] = []
    image = None
    try:
        for screen_no in range(max(1, min(scrolls, MAX_SCROLLS)) + 1):
            image = capture()
            if image is None:
                result.error = "Couldn't capture the browser window (is it minimised?)."
                break
            result.screens += 1
            boxes = ocr(image)
            if linkedin_posts:
                fresh = 0
                oldest = 0
                for post in parse_linkedin_posts(boxes, image.size[0]):
                    oldest = max(oldest, post.minutes_ago)
                    known = seen.get(post.key()) or _same_post(seen.values(), post)
                    if known is None:
                        seen[post.key()] = post
                        fresh += 1
                    elif len(post.text) > len(known.text):
                        known.text = post.text   # more of it was visible this time
                wanted = [p for p in seen.values() if max_age_minutes is None or p.minutes_ago <= max_age_minutes]
                if len(wanted) >= limit:
                    result.stopped_because = f"found {limit} posts"
                    break
                if max_age_minutes is not None and oldest > max_age_minutes:
                    result.stopped_because = f"reached posts older than {max_age_minutes} minutes (sorted newest first)"
                    break
            else:
                for row in _rows(boxes):
                    line = " ".join(b.text for b in row).strip()
                    if line and line not in text_lines[-80:]:
                        text_lines.append(line)
            if screen_no == min(scrolls, MAX_SCROLLS):
                result.stopped_because = f"read {result.screens} screens"
                break
            if not K.focus_window(hwnd):
                result.stopped_because = "couldn't keep the browser in front to scroll"
                break
            K.scroll(hwnd, 5)   # less than a screen, so consecutive screens overlap
            sleep(1.6)
            # Check the page really moved; the same picture twice means the end, or scrolling is blocked.
            after = capture()
            if after is not None and _same_picture(image, after):
                more = find_load_more(boxes)
                if more is not None:
                    result.loaded_more += 1
                    K.click(hwnd, *more)   # "Load more": the only click read_site makes
                    sleep(2.5)
                    K.scroll(hwnd, 5)
                    sleep(1.6)
                    after = capture()
                if after is None or _same_picture(image, after):
                    result.stopped_because = "the page stopped scrolling (end of results, or scrolling is blocked)"
                    break
    finally:
        if previous and previous != hwnd:
            try:
                K.focus_window(previous, timeout=0.6)
            except Exception:
                pass
    if image is not None:
        try:
            result.screenshot = V.save_screenshot(image, f"read-{title_hint}")
        except Exception:
            pass
    posts = sorted(seen.values(), key=lambda p: p.minutes_ago)
    if max_age_minutes is not None:
        posts = [p for p in posts if p.minutes_ago <= max_age_minutes]
    result.posts = posts[:limit] if linkedin_posts else []
    result.text = "\n".join(text_lines)[:8000]
    return result
