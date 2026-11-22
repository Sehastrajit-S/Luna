"""Personal budget: categories with monthly limits, expenses and income.

Everything stays in Luna's own database. Amounts are stored as whole cents so
sums never drift; the API speaks dollars (floats rounded to cents).

Also reads a receipt photo (on-device OCR) into a draft expense — merchant,
total, date and a guessed category — that the user reviews before saving.
"""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from server.models.database import BudgetCategory, BudgetTransaction

KINDS = ("expense", "income")
MAX_CENTS = 100_000_000          # $1,000,000 per entry
TREND_MONTHS = 6
FIXED_CATEGORIES = {"housing", "bills"}     # paid once a month; not extrapolated by pace

# Seeded the first time the budget is opened. Limits start unset (0) — the
# user's budget is theirs to set, not ours to guess.
DEFAULT_CATEGORIES = [
    ("Groceries", "🛒"), ("Dining", "🍽️"), ("Transport", "🚗"), ("Housing", "🏠"),
    ("Bills", "💡"), ("Shopping", "🛍️"), ("Health", "💊"), ("Entertainment", "🎬"),
    ("Other", "📦"),
]


class BudgetError(Exception):
    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind
        self.message = message


# ── helpers ────────────────────────────────────────────────────────────────

def to_cents(amount: float) -> int:
    cents = int(round(float(amount) * 100))
    if cents <= 0:
        raise BudgetError("bad_request", "Amount must be more than zero.")
    if cents > MAX_CENTS:
        raise BudgetError("bad_request", "That amount is too large.")
    return cents


def dollars(cents: int) -> float:
    return round((cents or 0) / 100, 2)


def parse_month(month: str | None) -> str:
    if not month:
        return date.today().strftime("%Y-%m")
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
        raise BudgetError("bad_request", "Month must look like 2026-11.")
    return month


def parse_day(value: str | None) -> str:
    if not value:
        return date.today().isoformat()
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as e:
        raise BudgetError("bad_request", "Date must look like 2026-11-17.") from e


def _shift(month: str, delta: int) -> str:
    y, m = map(int, month.split("-"))
    m += delta
    y += (m - 1) // 12
    m = (m - 1) % 12 + 1
    return f"{y:04d}-{m:02d}"


def _days_in(month: str) -> int:
    y, m = map(int, month.split("-"))
    nxt = date(y + (m == 12), m % 12 + 1, 1)
    return (nxt - date(y, m, 1)).days


def ensure_categories(db: Session) -> None:
    if db.query(BudgetCategory.id).first():
        return
    for i, (name, icon) in enumerate(DEFAULT_CATEGORIES):
        db.add(BudgetCategory(name=name, icon=icon, limit_cents=0, sort=i))
    db.commit()


def category_dict(c: BudgetCategory) -> dict:
    return {"id": c.id, "name": c.name, "icon": c.icon, "limit": dollars(c.limit_cents)}


def transaction_dict(t: BudgetTransaction) -> dict:
    return {
        "id": t.id, "kind": t.kind, "amount": dollars(t.amount_cents),
        "description": t.description, "category_id": t.category_id,
        "date": t.date_str, "source": t.source,
    }


def _category(db: Session, category_id: int | None) -> int | None:
    if category_id is None:
        return None
    if not db.get(BudgetCategory, category_id):
        raise BudgetError("not_found", "That category doesn't exist any more.")
    return category_id


# ── summary ────────────────────────────────────────────────────────────────

def summary(db: Session, month: str | None = None, today: date | None = None) -> dict:
    """Everything the budget page shows for one month."""
    ensure_categories(db)
    month = parse_month(month)
    today = today or date.today()

    cats = db.query(BudgetCategory).order_by(BudgetCategory.sort, BudgetCategory.id).all()
    txns = (db.query(BudgetTransaction)
            .filter(BudgetTransaction.date_str.like(f"{month}-%"))
            .order_by(BudgetTransaction.date_str.desc(), BudgetTransaction.id.desc())
            .all())

    spent_by: dict[int | None, int] = {}
    spent = income = 0
    for t in txns:
        if t.kind == "income":
            income += t.amount_cents
        else:
            spent += t.amount_cents
            spent_by[t.category_id] = spent_by.get(t.category_id, 0) + t.amount_cents

    categories = [
        {**category_dict(c), "spent": dollars(spent_by.get(c.id, 0))}
        for c in cats
    ]
    if spent_by.get(None):
        categories.append({"id": None, "name": "Uncategorized", "icon": "•", "limit": 0,
                           "spent": dollars(spent_by[None])})
    budget_cents = sum(c.limit_cents for c in cats)

    # Pace: how far through the month we are. Fixed costs (rent, bills) are
    # paid once, so only everyday spending is averaged and extrapolated.
    days = _days_in(month)
    this_month = today.strftime("%Y-%m")
    elapsed = today.day if month == this_month else (days if month < this_month else 0)
    fixed = sum(spent_by.get(c.id, 0) for c in cats if c.name.lower() in FIXED_CATEGORIES)
    everyday = spent - fixed
    projected = fixed + round(everyday / elapsed * days) if elapsed and month == this_month else spent

    # Trend: spent and income for the last few months, oldest first.
    first = _shift(month, -(TREND_MONTHS - 1))
    rows = (db.query(func.substr(BudgetTransaction.date_str, 1, 7), BudgetTransaction.kind,
                     func.sum(BudgetTransaction.amount_cents))
            .filter(BudgetTransaction.date_str >= f"{first}-01",
                    BudgetTransaction.date_str <= f"{month}-31")
            .group_by(func.substr(BudgetTransaction.date_str, 1, 7), BudgetTransaction.kind)
            .all())
    totals = {(m, k): v for m, k, v in rows}
    trend = [
        {"month": m, "spent": dollars(totals.get((m, "expense"), 0)),
         "income": dollars(totals.get((m, "income"), 0))}
        for m in (_shift(first, i) for i in range(TREND_MONTHS))
    ]

    return {
        "month": month,
        "spent": dollars(spent),
        "income": dollars(income),
        "budget": dollars(budget_cents),
        "left": dollars(budget_cents - spent) if budget_cents else None,
        "saved": dollars(income - spent),
        "daily_average": dollars(round(everyday / elapsed)) if elapsed else 0,
        "projected": dollars(projected),
        "days_in_month": days,
        "days_elapsed": elapsed,
        "categories": categories,
        "transactions": [transaction_dict(t) for t in txns],
        "trend": trend,
    }


# ── transactions ───────────────────────────────────────────────────────────

def add_transaction(db: Session, *, amount: float, kind: str = "expense", description: str = "",
                    category_id: int | None = None, day: str | None = None,
                    source: str = "manual") -> dict:
    if kind not in KINDS:
        raise BudgetError("bad_request", "Kind must be expense or income.")
    t = BudgetTransaction(
        kind=kind, amount_cents=to_cents(amount), description=description.strip()[:200],
        category_id=None if kind == "income" else _category(db, category_id),
        date_str=parse_day(day), source=source if source in ("manual", "receipt") else "manual",
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return transaction_dict(t)


def update_transaction(db: Session, txn_id: int, changes: dict) -> dict:
    t = db.get(BudgetTransaction, txn_id)
    if not t:
        raise BudgetError("not_found", "That entry doesn't exist any more.")
    if "kind" in changes:
        if changes["kind"] not in KINDS:
            raise BudgetError("bad_request", "Kind must be expense or income.")
        t.kind = changes["kind"]
    if "amount" in changes:
        t.amount_cents = to_cents(changes["amount"])
    if "description" in changes:
        t.description = (changes["description"] or "").strip()[:200]
    if "category_id" in changes:
        t.category_id = _category(db, changes["category_id"])
    if "date" in changes:
        t.date_str = parse_day(changes["date"])
    if t.kind == "income":
        t.category_id = None
    db.commit()
    db.refresh(t)
    return transaction_dict(t)


def delete_transaction(db: Session, txn_id: int) -> None:
    t = db.get(BudgetTransaction, txn_id)
    if not t:
        raise BudgetError("not_found", "That entry doesn't exist any more.")
    db.delete(t)
    db.commit()


# ── categories ─────────────────────────────────────────────────────────────

def _clean_name(db: Session, name: str, skip_id: int | None = None) -> str:
    name = (name or "").strip()[:40]
    if not name:
        raise BudgetError("bad_request", "Give the category a name.")
    clash = db.query(BudgetCategory).filter(func.lower(BudgetCategory.name) == name.lower()).first()
    if clash and clash.id != skip_id:
        raise BudgetError("conflict", f"There's already a {clash.name} category.")
    return name


def _limit_cents(limit: float | None) -> int:
    cents = int(round(float(limit or 0) * 100))
    if cents < 0 or cents > MAX_CENTS:
        raise BudgetError("bad_request", "Limit must be between 0 and 1,000,000.")
    return cents


def add_category(db: Session, *, name: str, icon: str = "", limit: float = 0) -> dict:
    ensure_categories(db)
    last = db.query(func.max(BudgetCategory.sort)).scalar() or 0
    c = BudgetCategory(name=_clean_name(db, name), icon=(icon or "").strip()[:8],
                       limit_cents=_limit_cents(limit), sort=last + 1)
    db.add(c)
    db.commit()
    db.refresh(c)
    return category_dict(c)


def update_category(db: Session, cat_id: int, changes: dict) -> dict:
    c = db.get(BudgetCategory, cat_id)
    if not c:
        raise BudgetError("not_found", "That category doesn't exist any more.")
    if "name" in changes:
        c.name = _clean_name(db, changes["name"], skip_id=c.id)
    if "icon" in changes:
        c.icon = (changes["icon"] or "").strip()[:8]
    if "limit" in changes:
        c.limit_cents = _limit_cents(changes["limit"])
    db.commit()
    db.refresh(c)
    return category_dict(c)


def delete_category(db: Session, cat_id: int) -> None:
    """Delete a category; its expenses stay, as Uncategorized."""
    c = db.get(BudgetCategory, cat_id)
    if not c:
        raise BudgetError("not_found", "That category doesn't exist any more.")
    db.query(BudgetTransaction).filter(BudgetTransaction.category_id == cat_id) \
        .update({BudgetTransaction.category_id: None})
    db.delete(c)
    db.commit()


# ── export ─────────────────────────────────────────────────────────────────

def export_csv(db: Session, month: str | None = None) -> str:
    month = parse_month(month)
    names = {c.id: c.name for c in db.query(BudgetCategory).all()}
    txns = (db.query(BudgetTransaction)
            .filter(BudgetTransaction.date_str.like(f"{month}-%"))
            .order_by(BudgetTransaction.date_str, BudgetTransaction.id).all())
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Date", "Type", "Category", "Description", "Amount"])
    for t in txns:
        w.writerow([t.date_str, t.kind, names.get(t.category_id, "") if t.kind == "expense" else "",
                    _csv_safe(t.description), f"{dollars(t.amount_cents):.2f}"])
    return out.getvalue()


def _csv_safe(text: str) -> str:
    # Spreadsheet apps run cells starting with these as formulas.
    return "'" + text if text[:1] in ("=", "+", "-", "@") else text


# ── receipts ───────────────────────────────────────────────────────────────

_AMOUNT = r"\$?\s*(\d{1,6}(?:,\d{3})*[.,]\d{2})(?!\d)"
_TOTAL_LINE = re.compile(
    r"(?i)\b(grand\s*total|total\s*due|amount\s*due|balance\s*due|total\s*amount|total)\b(?!\s*(savings|saved|items?|tax|discount))")
_NOT_TOTAL = re.compile(r"(?i)sub\s*-?\s*total|savings|you\s*saved|tax\b|tip\b|change\b|cash\b|tender")
_MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}

# Merchant keyword → category name (matched against the default categories).
_MERCHANT_CATEGORY = [
    (("walmart", "costco", "safeway", "kroger", "aldi", "trader joe", "whole foods", "sam's club",
      "publix", "h-e-b", "heb", "wegmans", "sprouts", "albertsons", "grocery", "market", "foods"), "Groceries"),
    (("starbucks", "mcdonald", "chipotle", "subway", "restaurant", "cafe", "coffee", "pizza",
      "grill", "kitchen", "burger", "taco", "diner", "bar ", "bistro", "doordash", "uber eats"), "Dining"),
    (("shell", "chevron", "exxon", "mobil", "bp ", "valero", "arco", "fuel", "gas", "uber", "lyft",
      "parking", "transit"), "Transport"),
    (("cvs", "walgreens", "rite aid", "pharmacy", "clinic", "dental"), "Health"),
    (("target", "amazon", "best buy", "home depot", "lowe's", "ikea", "macy"), "Shopping"),
    (("cinema", "theatre", "theater", "amc", "netflix", "spotify", "steam"), "Entertainment"),
    (("electric", "energy", "water", "internet", "comcast", "verizon", "at&t", "t-mobile"), "Bills"),
]
_CHAINS = [
    ("walmart", "Walmart"), ("costco", "Costco"), ("safeway", "Safeway"), ("kroger", "Kroger"),
    ("aldi", "Aldi"), ("trader joe", "Trader Joe's"), ("whole foods", "Whole Foods"),
    ("sam's club", "Sam's Club"), ("publix", "Publix"), ("wegmans", "Wegmans"), ("target", "Target"),
    ("starbucks", "Starbucks"), ("mcdonald", "McDonald's"), ("chipotle", "Chipotle"),
    ("cvs", "CVS"), ("walgreens", "Walgreens"), ("home depot", "The Home Depot"),
    ("best buy", "Best Buy"), ("ikea", "IKEA"), ("shell", "Shell"), ("chevron", "Chevron"),
]
_SKIP_MERCHANT = re.compile(r"(?i)receipt|welcome|thank|store\s*#|^\W*$|tel|phone|www\.|http")


@dataclass
class ReceiptDraft:
    amount: float | None
    merchant: str
    date: str | None
    category: str | None
    text: str

    def to_dict(self) -> dict:
        return {"amount": self.amount, "merchant": self.merchant, "date": self.date,
                "category": self.category, "text": self.text}


def _money(s: str) -> float | None:
    s = s.replace(" ", "")
    # 1,234.56 → 1234.56; 12,34 (comma decimals) → 12.34
    if re.fullmatch(r"\d{1,3}(,\d{3})+\.\d{2}", s):
        s = s.replace(",", "")
    elif re.fullmatch(r"\d+,\d{2}", s):
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _find_total(lines: list[str]) -> float | None:
    # The last "total" line that isn't a subtotal/tax/savings line; the amount
    # can sit on the same line or the next one.
    for i in range(len(lines) - 1, -1, -1):
        line = lines[i]
        if not _TOTAL_LINE.search(line) or _NOT_TOTAL.search(line):
            continue
        for candidate in (line, lines[i + 1] if i + 1 < len(lines) else ""):
            amounts = [a for a in (_money(m) for m in re.findall(_AMOUNT, candidate)) if a]
            if amounts:
                return amounts[-1]
    # No total line: the largest amount on the receipt.
    amounts = [a for line in lines for a in (_money(m) for m in re.findall(_AMOUNT, line)) if a]
    return max(amounts) if amounts else None


def _find_date(text: str, today: date) -> str | None:
    def ok(y: int, m: int, d: int) -> str | None:
        if y < 100:
            y += 2000
        try:
            found = date(y, m, d)
        except ValueError:
            return None
        return found.isoformat() if found <= today and found.year >= today.year - 5 else None

    for y, m, d in re.findall(r"\b(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})\b", text):
        if (v := ok(int(y), int(m), int(d))):
            return v
    for m, d, y in re.findall(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4}|\d{2})\b", text):
        if (v := ok(int(y), int(m), int(d))):
            return v
    for mon, d, y in re.findall(r"(?i)\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})\b", text):
        if (v := ok(int(y), _MONTHS[mon.lower()], int(d))):
            return v
    return None


def _find_merchant(lines: list[str]) -> str:
    # Known chains by name first: the receipt header is often a logo OCR can't read.
    lowered = " ".join(lines).lower()
    squashed = re.sub(r"[^a-z0-9]", "", lowered)          # OCR often drops spaces: "TRADERJOE'S"
    for key, name in _CHAINS:
        key_squashed = re.sub(r"[^a-z0-9]", "", key)
        if re.search(rf"\b{re.escape(key)}", lowered) or (len(key_squashed) >= 7 and key_squashed in squashed):
            return name
    for line in lines[:6]:
        letters = sum(ch.isalpha() for ch in line)
        if letters >= 3 and letters >= len(line) * 0.5 and not _SKIP_MERCHANT.search(line):
            return line.strip()[:60]
    return ""


def _guess_category(merchant: str, text: str) -> str | None:
    hay = f"{merchant} {text[:400]}".lower()
    for keywords, category in _MERCHANT_CATEGORY:
        if any(k in hay for k in keywords):
            return category
    return None


def parse_receipt_text(text: str, today: date | None = None) -> ReceiptDraft:
    today = today or date.today()
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    merchant = _find_merchant(lines)
    return ReceiptDraft(
        amount=_find_total(lines),
        merchant=merchant,
        date=_find_date(text, today),
        category=_guess_category(merchant, text),
        text=text[:4000],
    )


def read_receipt(image_bytes: bytes) -> ReceiptDraft:
    """OCR a receipt photo into a draft expense. Raises BudgetError."""
    from server.services.files.ocr import OcrUnavailable, ocr_image

    try:
        import cv2
        import numpy as np

        img = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    except Exception:
        img = None
    if img is None:
        raise BudgetError("bad_image", "That file isn't a photo Luna can read.")
    # Big phone photos: shrink so OCR stays quick; receipts stay legible at 2000 px.
    h, w = img.shape[:2]
    if max(h, w) > 2000:
        scale = 2000 / max(h, w)
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    try:
        result = ocr_image(img[:, :, ::-1].copy())     # BGR → RGB
    except OcrUnavailable as e:
        raise BudgetError("not_configured", str(e)) from e
    if not result.text.strip():
        raise BudgetError("no_text", "Couldn't read any text. Try a flatter, brighter photo of the receipt.")
    return parse_receipt_text(result.text)


def month_label(month: str) -> str:
    return datetime.strptime(month, "%Y-%m").strftime("%B %Y")
