"""Fill a web form open in the user's Chrome, by field label, and check every value.

Fields are found through Windows UI Automation, which exposes each form field in
Chrome with its label ("First name", "Email address"), so filling doesn't depend
on screen positions. Each field is focused and typed into (real key presses, so
sites see normal input), then read back to verify.

The form is never submitted here. The reply lists what was filled and what was
left empty; submitting is a separate, confirmed step (submit_form).

Values come from one of two places:
- the user's own details (settings + Luna's memory) — "scan this QR and fill the form";
- details read off a scanned page — "scan this and fill the form with it".
Fields with no known value are left empty and named, never guessed.
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

logger = logging.getLogger("luna.form_filler")

BROWSER_PROCESSES = {"chrome.exe", "msedge.exe", "brave.exe"}
_SKIP_FIELDS = re.compile(r"address and search bar|search|captcha|password|card number|cvv|cvc|security code|"
                          r"one[- ]time|otp|verification code", re.IGNORECASE)


class FormError(Exception):
    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind, self.message = kind, message


@dataclass
class Field:
    label: str
    kind: str            # "text" | "select"
    element: object = None
    value: str = ""      # what's in it now


@dataclass
class FillResult:
    title: str
    filled: list[tuple[str, str]] = field(default_factory=list)      # (label, value) verified
    empty: list[str] = field(default_factory=list)                   # no known value
    skipped: list[str] = field(default_factory=list)                 # sensitive / already filled
    failed: list[tuple[str, str]] = field(default_factory=list)      # (label, why)
    screenshot: Optional[str] = None


# ── The user's details ───────────────────────────────────────────────────────

# Canonical detail keys and the words a form label uses for them.
DETAIL_LABELS: list[tuple[str, re.Pattern]] = [
    ("email", re.compile(r"e-?mail", re.I)),
    ("phone", re.compile(r"phone|mobile|cell|contact number|whatsapp", re.I)),
    ("first_name", re.compile(r"first\s*name|given\s*name|forename", re.I)),
    ("last_name", re.compile(r"last\s*name|surname|family\s*name", re.I)),
    ("full_name", re.compile(r"^(?:your\s+)?(?:full\s+)?name\b|name\s*\(full\)|applicant name|student name", re.I)),
    ("date_of_birth", re.compile(r"birth|dob|d\.o\.b", re.I)),
    ("street_address", re.compile(r"street|address\s*(?:line)?\s*1?$|^address|residential", re.I)),
    ("city", re.compile(r"\bcity\b|\btown\b", re.I)),
    ("state", re.compile(r"\bstate\b|province|region|county", re.I)),
    ("postal_code", re.compile(r"zip|postal|post\s*code|pin\s*code", re.I)),
    ("country", re.compile(r"country|nationality", re.I)),
    ("university", re.compile(r"university|college|school|institution", re.I)),
    ("degree", re.compile(r"degree|major|course|program(?:me)?\b|field of study", re.I)),
    ("graduation", re.compile(r"graduat", re.I)),
    ("company", re.compile(r"company|organi[sz]ation|employer", re.I)),
    ("job_title", re.compile(r"job title|position|role|designation|occupation", re.I)),
    ("linkedin", re.compile(r"linked\s*in", re.I)),
    ("github", re.compile(r"github", re.I)),
    ("website", re.compile(r"website|portfolio|url", re.I)),
]


def detail_key(label: str) -> Optional[str]:
    for key, pattern in DETAIL_LABELS:
        if pattern.search(label or ""):
            return key
    return None


def complete_details(details: dict) -> dict:
    """Fill in derivable keys (first/last from full name and back)."""
    d = {k: str(v).strip() for k, v in details.items() if v and str(v).strip()}
    if d.get("full_name") and not d.get("first_name"):
        parts = d["full_name"].split()
        if len(parts) >= 2:
            d.setdefault("first_name", parts[0])
            d.setdefault("last_name", " ".join(parts[1:]))
    if d.get("first_name") and d.get("last_name") and not d.get("full_name"):
        d["full_name"] = f"{d['first_name']} {d['last_name']}"
    return d


async def my_details(db=None, browser_email: str = "") -> dict:
    """The user's own details from settings and memory. Only what's actually known."""
    from server.config import settings

    details: dict = {}
    if getattr(settings, "user_name", ""):
        details["full_name"] = settings.user_name
    if getattr(settings, "weather_city", ""):
        details["city"] = settings.weather_city.split(",")[0].strip()
    if browser_email:
        details["email"] = browser_email
    facts: list[str] = []
    if db is not None:
        try:
            from server.models.database import Fact
            rows = (db.query(Fact).filter(Fact.is_active.is_(True), Fact.is_private.isnot(True),
                                          Fact.category.in_(["personal", "relationship", "goal", "preference"]))
                    .order_by(Fact.importance.desc()).limit(60).all())
            facts = [r.content for r in rows]
        except Exception as e:
            logger.info("Couldn't read memory for form details: %s", e)
    if facts:
        details.update({k: v for k, v in (await _details_from_text("\n".join(facts), about_user=True)).items()
                        if v and k not in details})
    return complete_details(details)


async def details_from_scan(text: str) -> dict:
    """Details printed on a scanned page (ID card, CV, business card, letter)."""
    return complete_details(await _details_from_text(text, about_user=False))


async def _details_from_text(text: str, about_user: bool) -> dict:
    import json

    from server.services.llm import ollama
    keys = [k for k, _ in DETAIL_LABELS]
    who = "the user (facts Luna remembers about them)" if about_user else "the person on this scanned page"
    prompt = (
        f"Extract details about {who} from the text below.\n"
        f"Return only JSON with any of these keys: {', '.join(keys)}.\n"
        "Copy values exactly as written. Leave a key out if the text doesn't state it. Never guess.\n"
        "Facts about other people (family, friends) are not the user's details.\n\n"
        f"Text:\n{text[:6000]}"
    )
    try:
        raw = await ollama.complete(prompt, system="You extract fields into JSON. Output JSON only.")
        match = re.search(r"\{[\s\S]*\}", raw or "")
        data = json.loads(match.group(0)) if match else {}
    except Exception as e:
        logger.info("Detail extraction failed: %s", e)
        return {}
    clean = {}
    for k, v in (data or {}).items():
        if k in keys and isinstance(v, (str, int, float)) and str(v).strip() and len(str(v)) < 200:
            value = str(v).strip()
            # Grounding: the value (or most of its words) must appear in the source text.
            words = [w for w in re.findall(r"\w+", value.lower()) if len(w) > 1]
            source = text.lower()
            if words and sum(w in source for w in words) >= max(1, len(words) * 0.6):
                clean[k] = value
    return clean


# ── UI Automation ────────────────────────────────────────────────────────────

class _UIA:
    _instance = None

    def __init__(self):
        import comtypes.client
        comtypes.client.GetModule("UIAutomationCore.dll")
        from comtypes.gen import UIAutomationClient as UIA
        self.UIA = UIA
        self.uia = comtypes.client.CreateObject(UIA.CUIAutomation, interface=UIA.IUIAutomation)

    @classmethod
    def get(cls) -> "_UIA":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def fields(self, hwnd: int) -> list[Field]:
        UIA = self.UIA
        root = self.uia.ElementFromHandle(hwnd)
        cond = self.uia.CreateOrCondition(
            self.uia.CreatePropertyCondition(UIA.UIA_ControlTypePropertyId, UIA.UIA_EditControlTypeId),
            self.uia.CreatePropertyCondition(UIA.UIA_ControlTypePropertyId, UIA.UIA_ComboBoxControlTypeId))
        found = None
        for _ in range(6):   # Chrome turns on page accessibility after the first query
            found = root.FindAll(UIA.TreeScope_Descendants, cond)
            if found.Length > 1:
                break
            time.sleep(0.8)
        fields = []
        for i in range(found.Length if found else 0):
            el = found.GetElement(i)
            label = (el.CurrentName or el.CurrentHelpText or "").strip()
            if not label or _SKIP_FIELDS.search(label) or el.CurrentIsOffscreen and label.lower().startswith("address"):
                continue
            kind = "select" if el.CurrentControlType == UIA.UIA_ComboBoxControlTypeId else "text"
            fields.append(Field(label=label, kind=kind, element=el, value=self.value(el)))
        return fields

    def value(self, el) -> str:
        try:
            pattern = el.GetCurrentPattern(self.UIA.UIA_ValuePatternId)
            if pattern:
                return pattern.QueryInterface(self.UIA.IUIAutomationValuePattern).CurrentValue or ""
        except Exception:
            pass
        return ""

    def focus(self, el) -> None:
        el.SetFocus()

    def select_option(self, el, wanted: str) -> bool:
        """Pick the dropdown option whose text matches `wanted`."""
        UIA = self.UIA
        try:
            expand = el.GetCurrentPattern(UIA.UIA_ExpandCollapsePatternId).QueryInterface(UIA.IUIAutomationExpandCollapsePattern)
            expand.Expand()
            time.sleep(0.3)
        except Exception:
            expand = None
        items = el.FindAll(UIA.TreeScope_Descendants,
                           self.uia.CreatePropertyCondition(UIA.UIA_ControlTypePropertyId, UIA.UIA_ListItemControlTypeId))
        target = None
        for i in range(items.Length):
            item = items.GetElement(i)
            name = (item.CurrentName or "").strip()
            if name.lower() == wanted.lower() or (len(wanted) > 3 and wanted.lower() in name.lower()):
                target = item
                break
        ok = False
        if target is not None:
            try:
                target.GetCurrentPattern(UIA.UIA_SelectionItemPatternId).QueryInterface(
                    UIA.IUIAutomationSelectionItemPattern).Select()
                ok = True
            except Exception:
                ok = False
        if expand is not None:
            try:
                expand.Collapse()
            except Exception:
                pass
        return ok

    def submit_button(self, hwnd: int):
        UIA = self.UIA
        root = self.uia.ElementFromHandle(hwnd)
        buttons = root.FindAll(UIA.TreeScope_Descendants,
                               self.uia.CreatePropertyCondition(UIA.UIA_ControlTypePropertyId, UIA.UIA_ButtonControlTypeId))
        best = None
        for i in range(buttons.Length):
            b = buttons.GetElement(i)
            name = (b.CurrentName or "").strip().lower()
            if re.search(r"\b(submit|send|apply|register|sign up|done|finish)\b", name) and not b.CurrentIsOffscreen:
                best = b
                if "submit" in name:
                    break
        return best

    def press(self, el) -> None:
        el.GetCurrentPattern(self.UIA.UIA_InvokePatternId).QueryInterface(self.UIA.IUIAutomationInvokePattern).Invoke()


# ── Filling ──────────────────────────────────────────────────────────────────

def find_form_window(title_hint: str = "") -> Optional[dict]:
    """The browser window with the form: one whose title contains the hint, else the front-most browser."""
    from server.services import verification as V
    from server.services.app_launcher import list_open_apps

    if title_hint:
        win = V.window_titled(title_hint, BROWSER_PROCESSES)
        if win:
            return win
    for app in list_open_apps():   # front-most first
        if (app.get("process") or "").lower() in BROWSER_PROCESSES and app.get("windows"):
            return V.window_titled(app["windows"][0][:60], BROWSER_PROCESSES)
    return None


def plan_values(fields: list[Field], details: dict) -> list[tuple[Field, Optional[str]]]:
    """Each field with the value it should get, or None when the details don't cover it."""
    plan = []
    for f in fields:
        key = detail_key(f.label)
        plan.append((f, details.get(key) if key else None))
    return plan


def fill_form(details: dict, *, window: Optional[dict] = None, title_hint: str = "", uia=None, keys=None,
              sleep: Callable[[float], None] = time.sleep, overwrite: bool = False) -> FillResult:
    from server.services import desktop_input as K_default
    from server.services import verification as V

    K = keys or K_default
    win = window or find_form_window(title_hint)
    if not win:
        raise FormError("no_form", "I can't find a browser window with a form. Open the form in Chrome first.")
    uia = uia or _UIA.get()
    fields = uia.fields(win["hwnd"])
    if not fields:
        raise FormError("no_fields", f"I don't see any form fields in “{win['title']}”.")
    result = FillResult(title=win["title"].replace(" - Google Chrome", ""))
    previous = K.foreground()
    try:
        if not K.focus_window(win["hwnd"]):
            raise FormError("focus", "Couldn't bring the browser to the front, so I didn't type anything.")
        for f, value in plan_values(fields, details):
            if value is None:
                if not f.value or _placeholder(f.value):
                    result.empty.append(f.label)
                continue
            if f.value and not overwrite and not _placeholder(f.value):
                result.skipped.append(f"{f.label} (already filled)")
                continue
            try:
                if f.kind == "select":
                    ok = uia.select_option(f.element, value)
                    now = uia.value(f.element)
                    if ok or (now and value.lower() in now.lower()):
                        result.filled.append((f.label, value))
                    else:
                        result.failed.append((f.label, f"no option matching “{value}”"))
                    continue
                uia.focus(f.element)
                sleep(0.15)
                K.press(win["hwnd"], "ctrl", "A")
                K.type_text(win["hwnd"], value)
                sleep(0.2)
                now = uia.value(f.element)
                if _same(now, value):
                    result.filled.append((f.label, value))
                else:
                    result.failed.append((f.label, f"it shows “{now[:40]}” after typing"))
            except Exception as e:
                result.failed.append((f.label, str(e)[:80]))
        try:
            image = V.capture_window(win["hwnd"])
            if image is not None:
                result.screenshot = V.save_screenshot(image, "form-filled")
        except Exception:
            pass
    finally:
        if previous and previous != win["hwnd"]:
            try:
                K.focus_window(previous, timeout=0.6)
            except Exception:
                pass
    return result


def _placeholder(value: str) -> bool:
    """A dropdown's "Choose…" / "Select…" isn't a real value."""
    return bool(re.fullmatch(r"\s*(?:-+|choose|select|please select|pick one|none|--\s*select\s*--)\b.*", value or "",
                             re.IGNORECASE)) or (value or "").strip() in ("", "…", "...")


def _same(shown: str, wanted: str) -> bool:
    a = re.sub(r"\s+", " ", (shown or "").strip().lower())
    b = re.sub(r"\s+", " ", (wanted or "").strip().lower())
    return a == b or (b and b in a) or re.sub(r"\D", "", a) == re.sub(r"\D", "", b) != ""


def submit_form(title_hint: str = "", *, uia=None, sleep: Callable[[float], None] = time.sleep) -> str:
    """Press the form's submit button (only after the user said yes) and report what the page shows next."""
    from server.services import verification as V

    win = find_form_window(title_hint)
    if not win:
        raise FormError("no_form", "I can't find the form's browser window any more.")
    uia = uia or _UIA.get()
    button = uia.submit_button(win["hwnd"])
    if button is None:
        raise FormError("no_submit", "I can't find a Submit button on that page.")
    label = button.CurrentName
    uia.press(button)
    sleep(2.5)
    image = V.capture_window(win["hwnd"])
    seen = V.read_screen_text(image, last_lines=12) if image is not None else ""
    shot = V.save_screenshot(image, "form-submitted") if image is not None else None
    confirmed = bool(re.search(r"response (?:has been )?recorded|thank you|thanks|submitted|received|success",
                               seen, re.IGNORECASE))
    status = "The page confirms it was received." if confirmed else "I can't see a confirmation on the page yet — please check it."
    return f"Pressed “{label}”. {status}" + (f" Screenshot: {shot}" if shot else "")


def describe(result: FillResult) -> str:
    lines = [f"Filled {len(result.filled)} field{'s' if len(result.filled) != 1 else ''} in “{result.title}” "
             "(each checked after typing):"]
    lines += [f"- {label}: {value}" for label, value in result.filled]
    if result.empty:
        lines.append(f"Left empty — I don't know these: {', '.join(result.empty)}.")
    if result.skipped:
        lines.append(f"Didn't touch: {', '.join(result.skipped)}.")
    if result.failed:
        lines.append("Couldn't fill: " + "; ".join(f"{label} ({why})" for label, why in result.failed) + ".")
    lines.append("I haven't submitted it. Check it, then say “submit it” and I'll press Submit.")
    return "\n".join(lines)
