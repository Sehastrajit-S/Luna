"""Barcodes → products, for "scan a product and compare prices".

decode_image(): reads a UPC/EAN barcode from a photo or camera frame with
OpenCV's barcode detector (OpenCV is already installed for OCR).

lookup(): turns the number into a product using free databases, no key needed:
Open Food Facts (groceries) and its Beauty / Products siblings first, then
UPCitemdb's free tier (general merchandise, about 100 lookups a day per IP).
Results are cached in memory so rescanning the same item costs nothing.
"""
from __future__ import annotations

import asyncio
import re
from collections import OrderedDict
from dataclasses import asdict, dataclass

import httpx

from server.services.audit_log import record_audit

TIMEOUT = 6.0
MAX_IMAGE_BYTES = 12 * 1024 * 1024
_HEADERS = {"User-Agent": "Luna/1.0 (self-hosted assistant; barcode lookup)", "Accept": "application/json"}
_OPEN_FACTS = (
    ("Open Food Facts", "https://world.openfoodfacts.org"),
    ("Open Beauty Facts", "https://world.openbeautyfacts.org"),
    ("Open Products Facts", "https://world.openproductsfacts.org"),
)
_UPCITEMDB = "https://api.upcitemdb.com/prod/trial/lookup"
_CACHE: OrderedDict[str, "Product"] = OrderedDict()
_CACHE_SIZE = 256


class BarcodeError(Exception):
    """kind: bad_image | no_barcode | invalid_code | not_found | rate_limited | upstream_error"""

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind
        self.message = message


@dataclass
class Product:
    code: str
    name: str            # what to search store prices for: brand + product + size
    title: str           # the product's own name
    brand: str
    size: str
    image: str
    source: str

    def to_dict(self) -> dict:
        return asdict(self)


# ── Codes ────────────────────────────────────────────────────────────────────

def check_digit_ok(code: str) -> bool:
    """GTIN mod-10 check (EAN-8, UPC-A, EAN-13, GTIN-14)."""
    digits = [int(c) for c in code]
    body, check = digits[:-1], digits[-1]
    total = sum(d * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(body)))
    return (10 - total % 10) % 10 == check


def normalize_code(raw: str) -> str:
    code = re.sub(r"[\s-]", "", str(raw or ""))
    if not re.fullmatch(r"\d{8}|\d{12,14}", code) or not check_digit_ok(code):
        raise BarcodeError("invalid_code", "That isn't a valid product barcode (UPC or EAN). Check the number and try again.")
    return code


# ── Decoding ─────────────────────────────────────────────────────────────────

def decode_image(data: bytes) -> str:
    """The first valid UPC/EAN in the image. Tries the photo as taken, then
    rotated, since phone photos of a box are often sideways."""
    import cv2
    import numpy as np

    if not data:
        raise BarcodeError("bad_image", "The photo was empty. Try again.")
    if len(data) > MAX_IMAGE_BYTES:
        raise BarcodeError("bad_image", "That photo is too large. Try a smaller one.")
    image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise BarcodeError("bad_image", "Couldn't read that image. Use a JPEG or PNG photo.")
    detector = cv2.barcode.BarcodeDetector()
    code = _decode_once(cv2, detector, _fit(cv2, image, 1600))
    if code:
        return code
    # OpenCV only finds a barcode that fills a fair share of the image. In a
    # 12 MP phone photo taken at arm's length it's small, so look again in
    # overlapping tiles, centre first (live camera frames are too small to need it).
    if max(image.shape[:2]) >= 2000:
        for fraction in (0.5, 0.4):
            for tile in _tiles(image, fraction):
                code = _decode_once(cv2, detector, _fit(cv2, tile, 1600))
                if code:
                    return code
    raise BarcodeError("no_barcode", "No barcode found. Fill the frame with the barcode, keep it sharp and well lit, and try again.")


def _fit(cv2, image, limit: int):
    height, width = image.shape[:2]
    scale = limit / max(height, width)
    if scale >= 1:
        return image
    return cv2.resize(image, (int(width * scale), int(height * scale)), interpolation=cv2.INTER_AREA)


def _tiles(image, fraction: float):
    """A 3x3 grid of overlapping crops, each `fraction` of the image, centre first."""
    height, width = image.shape[:2]
    th, tw = int(height * fraction), int(width * fraction)
    ys = [(height - th) // 2, 0, height - th]
    xs = [(width - tw) // 2, 0, width - tw]
    return [image[y:y + th, x:x + tw] for y in ys for x in xs]


def _decode_once(cv2, detector, image) -> str | None:
    # OpenCV's detector misses razor-sharp bars (screenshots, scanned labels)
    # but reads them after a slight blur; phone photos are usually soft already.
    soft = cv2.GaussianBlur(image, (3, 3), 0.8)
    for candidate in (image, soft, cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE), cv2.rotate(soft, cv2.ROTATE_90_CLOCKWISE)):
        ok, texts, _types, _points = detector.detectAndDecodeWithType(candidate)
        if not ok:
            continue
        for text in texts:
            try:
                return normalize_code(text)
            except BarcodeError:
                continue
    return None


async def decode_image_async(data: bytes) -> str:
    return await asyncio.to_thread(decode_image, data)


def decode_qr(data: bytes) -> str | None:
    """The text in a QR code in the photo (often a link), or None. Tries the photo as taken, then
    larger/sharper/tiled versions, since a QR on paper is often small or tilted in a phone photo."""
    import cv2
    import numpy as np

    if not data or len(data) > MAX_IMAGE_BYTES:
        return None
    image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        return None
    detector = cv2.QRCodeDetector()
    candidates = [_fit(cv2, image, 1600), image]
    if max(image.shape[:2]) < 900:
        candidates.append(cv2.resize(image, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC))
    candidates.append(cv2.threshold(_fit(cv2, image, 1600), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1])
    if max(image.shape[:2]) >= 1400:
        candidates += [_fit(cv2, tile, 1600) for tile in _tiles(image, 0.5)]
    for candidate in candidates:
        try:
            text, points, _ = detector.detectAndDecode(candidate)
        except cv2.error:
            continue
        if text:
            return text.strip()
    return None


# ── Lookup ───────────────────────────────────────────────────────────────────

def search_name(brand: str, title: str, size: str) -> str:
    """"Coca-Cola" + "Coca-Cola Classic" + "12 fl oz" → "Coca-Cola Classic 12 fl oz"."""
    parts = []
    first_brand = (brand or "").split(",")[0].strip()
    if first_brand and first_brand.lower() not in (title or "").lower():
        parts.append(first_brand)
    if title:
        parts.append(title.strip())
    if size and size.lower() not in (title or "").lower():
        parts.append(size.strip())
    return " ".join(" ".join(parts).split())[:160]


async def _open_facts(client: httpx.AsyncClient, source: str, base: str, code: str) -> Product | None:
    response = await client.get(f"{base}/api/v2/product/{code}.json",
                                params={"fields": "product_name,product_name_en,brands,quantity,image_front_small_url"})
    if response.status_code == 404:
        return None
    if response.status_code == 429:
        raise BarcodeError("rate_limited", f"{source} is busy. Try again in a minute.")
    response.raise_for_status()
    data = response.json()
    product = data.get("product") or {}
    title = (product.get("product_name_en") or product.get("product_name") or "").strip()
    if data.get("status") != 1 or not title:
        return None
    brand = (product.get("brands") or "").strip()
    size = (product.get("quantity") or "").strip()
    image = product.get("image_front_small_url") or ""
    return Product(code, search_name(brand, title, size), title, brand.split(",")[0].strip(), size,
                   image if image.startswith("https://") else "", source)


async def _upcitemdb(client: httpx.AsyncClient, code: str) -> Product | None:
    response = await client.get(_UPCITEMDB, params={"upc": code})
    if response.status_code == 429:
        raise BarcodeError("rate_limited", "The free product lookup has hit its daily limit. Type the product name instead.")
    if response.status_code == 400:
        return None
    response.raise_for_status()
    items = response.json().get("items") or []
    if not items:
        return None
    item = items[0]
    title = (item.get("title") or "").strip()
    if not title:
        return None
    brand = (item.get("brand") or "").strip()
    size = (item.get("size") or "").strip()
    image = next((url for url in item.get("images") or [] if str(url).startswith("https://")), "")
    return Product(code, search_name(brand, title, size), title, brand, size, image, "UPCitemdb")


async def lookup(raw_code: str, *, client: httpx.AsyncClient | None = None) -> Product:
    code = normalize_code(raw_code)
    if code in _CACHE:
        _CACHE.move_to_end(code)
        return _CACHE[code]

    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=TIMEOUT, headers=_HEADERS, follow_redirects=True)
    product: Product | None = None
    status = "ok"
    errors: list[BarcodeError] = []
    answered = 0                         # sources that replied, found or not
    try:
        # Groceries are most scans: ask the three Open … Facts databases at once.
        results = await asyncio.gather(*(_open_facts(client, name, base, code) for name, base in _OPEN_FACTS),
                                       return_exceptions=True)
        for result in results:
            if isinstance(result, Product):
                product = result
                break
            if isinstance(result, BarcodeError):
                errors.append(result)
            elif isinstance(result, Exception):
                errors.append(BarcodeError("upstream_error", "The product lookup didn't respond. Try again in a minute."))
            else:
                answered += 1
        if product is None:
            try:
                product = await _upcitemdb(client, code)
                answered += 1
            except BarcodeError as e:
                errors.append(e)
            except (httpx.HTTPError, ValueError):
                errors.append(BarcodeError("upstream_error", "The product lookup didn't respond. Try again in a minute."))
    finally:
        if owns_client:
            await client.aclose()
        if product is None:
            status = "not_found" if answered else (errors[0].kind if errors else "upstream_error")
        record_audit(
            "external_read", tool="barcode_lookup", risk="safe", status=status,
            args={"provider": product.source if product else "open_facts+upcitemdb", "code": code},
            result=product.name if product else status,
        )

    if product is None:
        if not answered and errors:      # nobody could say: report why, not "not found"
            raise next((e for e in errors if e.kind == "rate_limited"), errors[0])
        raise BarcodeError("not_found", "This barcode isn't in the free product databases. Type the product name to compare prices.")
    _CACHE[code] = product
    if len(_CACHE) > _CACHE_SIZE:
        _CACHE.popitem(last=False)
    return product


_BARE_CODE_RE = re.compile(r"^\s*(?:upc|ean|barcode)?[:#\s]*([\d\s-]{8,18})\s*$", re.IGNORECASE)


async def product_for_query(text: str) -> tuple[str, Product | None]:
    """What to compare prices for: the text itself, or, when the text is just a
    barcode number, that product's name (plus the product, for display)."""
    match = _BARE_CODE_RE.match(text or "")
    if not match:
        return text, None
    product = await lookup(match.group(1))
    return product.name, product


def recent_image(name: str) -> str:
    """The photo of a product scanned recently under this name (the scanner
    sends the name to chat, possibly edited), or ""."""
    wanted = " ".join((name or "").lower().split())
    for product in reversed(_CACHE.values()):
        if product.image and product.name.lower() == wanted:
            return product.image
    return ""
