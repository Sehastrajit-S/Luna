"""Barcode scan → product → price comparison (server/services/shopping/barcode.py)."""
import asyncio
import io
import unittest
from unittest import mock

import httpx

from tests.tools import _bootstrap  # noqa: F401

_L = ["0001101", "0011001", "0010011", "0111101", "0100011", "0110001", "0101111", "0111011", "0110111", "0001011"]
_R = ["".join("1" if b == "0" else "0" for b in code) for code in _L]
_G = [code[::-1] for code in _R]
_PARITY = ["LLLLLL", "LLGLGG", "LLGGLG", "LLGGGL", "LGLLGG", "LGGLLG", "LGGGLL", "LGLGLG", "LGLGGL", "LGGLGL"]


def ean13_png(code: str, *, module: int = 4, rotate: int = 0, blur: bool = False) -> bytes:
    """A printed-label-like EAN-13: white quiet zone, black bars."""
    from PIL import Image, ImageDraw, ImageFilter

    digits = [int(c) for c in code]
    left = "".join((_L if p == "L" else _G)[d] for p, d in zip(_PARITY[digits[0]], digits[1:7]))
    right = "".join(_R[d] for d in digits[7:])
    bits = "101" + left + "01010" + right + "101"
    quiet = 14 * module
    width, height = len(bits) * module + 2 * quiet, 70 * module
    image = Image.new("L", (width, height), 255)
    draw = ImageDraw.Draw(image)
    for i, bit in enumerate(bits):
        if bit == "1":
            x = quiet + i * module
            draw.rectangle([x, 10 * module, x + module - 1, height - 10 * module], fill=0)
    if rotate:
        image = image.rotate(rotate, expand=True, fillcolor=255)
    if blur:
        image = image.filter(ImageFilter.GaussianBlur(0.8))
    canvas = Image.new("L", (image.width + 200, image.height + 160), 235)   # the box around the label
    canvas.paste(image, (100, 80))
    out = io.BytesIO()
    canvas.save(out, format="PNG")
    return out.getvalue()


class CodeTests(unittest.TestCase):
    def test_check_digits(self) -> None:
        from server.services.shopping.barcode import normalize_code
        self.assertEqual(normalize_code("4006381333931"), "4006381333931")     # EAN-13
        self.assertEqual(normalize_code("0 49000 02891 1"), "049000028911")     # UPC-A with spaces
        self.assertEqual(normalize_code("96385074"), "96385074")                # EAN-8

    def test_rejects_bad_codes(self) -> None:
        from server.services.shopping.barcode import BarcodeError, normalize_code
        for bad in ("4006381333932", "12345", "abc", "", "04900002891"):
            with self.assertRaises(BarcodeError) as ctx:
                normalize_code(bad)
            self.assertEqual(ctx.exception.kind, "invalid_code")


class DecodeTests(unittest.TestCase):
    def test_reads_an_ean13_label(self) -> None:
        from server.services.shopping.barcode import decode_image
        self.assertEqual(decode_image(ean13_png("4006381333931")), "4006381333931")

    def test_reads_a_sideways_slightly_soft_photo(self) -> None:
        from server.services.shopping.barcode import decode_image
        self.assertEqual(decode_image(ean13_png("5901234123457", rotate=90, blur=True)), "5901234123457")

    def test_small_barcode_in_a_12mp_iphone_photo(self) -> None:
        """Arm's-length shot: the barcode is a small part of a 4032x3024 JPEG
        with an EXIF rotation tag, the way an iPhone uploads it."""
        from PIL import Image

        from server.services.shopping.barcode import decode_image
        for module, position in ((2, (1700, 1300)), (3, (3200, 2300)), (2, (200, 200))):
            with self.subTest(module=module, position=position):
                label = Image.open(io.BytesIO(ean13_png("0049000028911", module=module, blur=True)))
                photo = Image.new("L", (4032, 3024), 150)
                photo.paste(label, position)
                exif = Image.Exif()
                exif[0x0112] = 6                      # "rotate 90°": a portrait iPhone photo
                out = io.BytesIO()
                photo.convert("RGB").save(out, "JPEG", quality=88, exif=exif)
                self.assertEqual(decode_image(out.getvalue()), "049000028911")   # read as UPC-A

    def test_no_barcode_and_bad_image(self) -> None:
        from PIL import Image

        from server.services.shopping.barcode import BarcodeError, decode_image
        blank = io.BytesIO()
        Image.new("L", (400, 300), 200).save(blank, format="PNG")
        with self.assertRaises(BarcodeError) as ctx:
            decode_image(blank.getvalue())
        self.assertEqual(ctx.exception.kind, "no_barcode")
        with self.assertRaises(BarcodeError) as ctx:
            decode_image(b"not an image")
        self.assertEqual(ctx.exception.kind, "bad_image")


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


class LookupTests(unittest.TestCase):
    def setUp(self) -> None:
        from server.services.shopping import barcode
        barcode._CACHE.clear()
        patcher = mock.patch("server.services.shopping.barcode.record_audit")
        self.audit = patcher.start()
        self.addCleanup(patcher.stop)

    def test_grocery_from_open_food_facts(self) -> None:
        from server.services.shopping.barcode import lookup

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.host == "world.openfoodfacts.org":
                return httpx.Response(200, json={"status": 1, "product": {
                    "product_name": "Coca-Cola Classic", "brands": "Coca-Cola, The Coca-Cola Company",
                    "quantity": "12 fl oz", "image_front_small_url": "https://images.openfoodfacts.org/x.jpg"}})
            return httpx.Response(404, json={"status": 0})

        product = asyncio.run(lookup("049000028911", client=_client(handler)))
        self.assertEqual(product.name, "Coca-Cola Classic 12 fl oz")     # brand not repeated
        self.assertEqual(product.brand, "Coca-Cola")
        self.assertEqual(product.source, "Open Food Facts")
        self.assertEqual(self.audit.call_args.kwargs["status"], "ok")

    def test_general_merchandise_falls_back_to_upcitemdb(self) -> None:
        from server.services.shopping.barcode import lookup

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.host == "api.upcitemdb.com":
                return httpx.Response(200, json={"code": "OK", "items": [{
                    "title": "Duracell Coppertop AA Batteries 20 Count", "brand": "Duracell",
                    "images": ["http://insecure.example/a.jpg", "https://img.example/a.jpg"]}]})
            return httpx.Response(200, json={"status": 0})

        product = asyncio.run(lookup("041333424019", client=_client(handler)))
        self.assertEqual(product.name, "Duracell Coppertop AA Batteries 20 Count")
        self.assertEqual(product.image, "https://img.example/a.jpg")        # https only
        self.assertEqual(product.source, "UPCitemdb")

    def test_not_found_rate_limited_and_down_are_distinct(self) -> None:
        from server.services.shopping.barcode import BarcodeError, lookup

        cases = {
            "not_found": lambda r: httpx.Response(200, json={"status": 0, "items": []}),
            "rate_limited": lambda r: httpx.Response(429),
            "upstream_error": lambda r: httpx.Response(503),
        }
        for kind, handler in cases.items():
            with self.subTest(kind=kind), self.assertRaises(BarcodeError) as ctx:
                asyncio.run(lookup("4006381333931", client=_client(handler)))
            self.assertEqual(ctx.exception.kind, kind)

    def test_cached_after_first_lookup(self) -> None:
        from server.services.shopping.barcode import lookup
        calls = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request.url.host)
            return httpx.Response(200, json={"status": 1, "product": {"product_name": "Oat Milk", "brands": "Oatly"}})

        asyncio.run(lookup("4006381333931", client=_client(handler)))
        before = len(calls)
        product = asyncio.run(lookup("4006381333931", client=_client(handler)))
        self.assertEqual(len(calls), before)
        self.assertEqual(product.name, "Oatly Oat Milk")


class QueryTests(unittest.TestCase):
    def test_bare_code_becomes_product_name(self) -> None:
        from server.services.shopping import barcode
        found = barcode.Product("049000028911", "Coca-Cola Classic 12 fl oz", "Coca-Cola Classic",
                                "Coca-Cola", "12 fl oz", "", "Open Food Facts")
        with mock.patch.object(barcode, "lookup", mock.AsyncMock(return_value=found)) as looked_up:
            self.assertEqual(asyncio.run(barcode.product_for_query("UPC 0 49000 02891 1")),
                             ("Coca-Cola Classic 12 fl oz", found))
            self.assertEqual(asyncio.run(barcode.product_for_query("Tide Pods 81 count")), ("Tide Pods 81 count", None))
        looked_up.assert_awaited_once()


class RouteTests(unittest.TestCase):
    def test_decode_route_and_error_shape(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from server.routers.shopping import router
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        ok = client.post("/api/shopping/barcode/decode", files={"image": ("a.png", ean13_png("4006381333931"), "image/png")})
        self.assertEqual(ok.json(), {"code": "4006381333931"})
        bad = client.get("/api/shopping/barcode/123")
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(bad.json()["detail"]["kind"], "invalid_code")


if __name__ == "__main__":
    unittest.main(verbosity=2)
