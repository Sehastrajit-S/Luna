"""Budget app: categories, expenses/income, monthly summary, CSV export, receipts."""
from __future__ import annotations

import io
import unittest
from datetime import date
from pathlib import Path

from tests.tools import _bootstrap  # noqa: F401

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from server.models.database import Base, get_db
from server.routers import budget as budget_router
from server.services import budget


class BudgetTestCase(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine)

        app = FastAPI()
        app.include_router(budget_router.router)

        def db():
            session = self.Session()
            try:
                yield session
            finally:
                session.close()

        app.dependency_overrides[get_db] = db
        self.client = TestClient(app)

    def cat_id(self, name: str) -> int:
        cats = self.client.get("/api/budget/summary?month=2026-11").json()["categories"]
        return next(c["id"] for c in cats if c["name"] == name)

    def add(self, amount, **kw):
        r = self.client.post("/api/budget/transactions", json={"amount": amount, **kw})
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()


class SummaryTests(BudgetTestCase):
    def test_first_open_seeds_categories_without_limits(self) -> None:
        s = self.client.get("/api/budget/summary?month=2026-11").json()
        names = [c["name"] for c in s["categories"]]
        self.assertEqual(names[:3], ["Groceries", "Dining", "Transport"])
        self.assertTrue(all(c["limit"] == 0 for c in s["categories"]), "limits are the user's to set")
        self.assertEqual((s["spent"], s["income"], s["budget"], s["left"]), (0, 0, 0, None))
        self.assertEqual(len(s["trend"]), 6)
        self.assertEqual(s["trend"][-1]["month"], "2026-11")
        self.assertEqual(s["trend"][0]["month"], "2026-06")

    def test_totals_limits_and_month_isolation(self) -> None:
        groceries, dining = self.cat_id("Groceries"), self.cat_id("Dining")
        self.client.patch(f"/api/budget/categories/{groceries}", json={"limit": 300})
        self.client.patch(f"/api/budget/categories/{dining}", json={"limit": 50})
        self.add(120.10, category_id=groceries, description="Costco", date="2026-11-03")
        self.add(0.2, category_id=groceries, date="2026-11-04")          # cents add up exactly
        self.add(64.5, category_id=dining, description="Dinner", date="2026-11-05")
        self.add(2500, kind="income", description="Paycheck", date="2026-11-01", category_id=dining)
        self.add(99, category_id=groceries, date="2026-10-30")           # last month

        s = self.client.get("/api/budget/summary?month=2026-11").json()
        self.assertEqual(s["spent"], 184.8)
        self.assertEqual(s["income"], 2500)
        self.assertEqual(s["budget"], 350)
        self.assertEqual(s["left"], 165.2)
        self.assertEqual(s["saved"], 2315.2)
        by = {c["name"]: c for c in s["categories"]}
        self.assertEqual(by["Groceries"]["spent"], 120.3)
        self.assertEqual(by["Dining"]["spent"], 64.5, "income never counts against a category")
        self.assertEqual([t["date"] for t in s["transactions"]], ["2026-11-05", "2026-11-04", "2026-11-03", "2026-11-01"])
        income = next(t for t in s["transactions"] if t["kind"] == "income")
        self.assertIsNone(income["category_id"])
        self.assertEqual(s["trend"][-2], {"month": "2026-10", "spent": 99.0, "income": 0})

    def test_pace_for_the_current_month(self) -> None:
        s = self.Session()
        budget.add_transaction(s, amount=100, day="2026-11-02")
        budget.add_transaction(s, amount=50, day="2026-11-09")
        out = budget.summary(s, "2026-11", today=date(2026, 11, 10))
        self.assertEqual(out["days_elapsed"], 10)
        self.assertEqual(out["daily_average"], 15)
        self.assertEqual(out["projected"], 450)                     # 150 / 10 days × 30
        past = budget.summary(s, "2026-11", today=date(2026, 12, 5))
        self.assertEqual((past["days_elapsed"], past["projected"]), (30, 150))
        # Rent on the 1st is a fixed cost: it isn't averaged or extrapolated.
        housing = next(c["id"] for c in out["categories"] if c["name"] == "Housing")
        budget.add_transaction(s, amount=1500, day="2026-11-01", category_id=housing)
        out = budget.summary(s, "2026-11", today=date(2026, 11, 10))
        self.assertEqual((out["daily_average"], out["projected"]), (15, 1950))
        s.close()

    def test_bad_month(self) -> None:
        r = self.client.get("/api/budget/summary?month=2026-13")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["detail"]["kind"], "bad_request")


class TransactionTests(BudgetTestCase):
    def test_edit_and_delete(self) -> None:
        t = self.add(10, description="Coffee", date="2026-11-02")
        r = self.client.patch(f"/api/budget/transactions/{t['id']}", json={"amount": 12.75, "description": "Coffee x2"})
        self.assertEqual(r.json()["amount"], 12.75)
        self.assertEqual(r.json()["description"], "Coffee x2")
        self.assertEqual(self.client.delete(f"/api/budget/transactions/{t['id']}").status_code, 204)
        self.assertEqual(self.client.delete(f"/api/budget/transactions/{t['id']}").status_code, 404)

    def test_validation(self) -> None:
        self.assertEqual(self.client.post("/api/budget/transactions", json={"amount": 0}).status_code, 422)
        self.assertEqual(self.client.post("/api/budget/transactions", json={"amount": -5}).status_code, 422)
        r = self.client.post("/api/budget/transactions", json={"amount": 5, "date": "17/11/2026"})
        self.assertEqual((r.status_code, r.json()["detail"]["kind"]), (400, "bad_request"))
        r = self.client.post("/api/budget/transactions", json={"amount": 5, "category_id": 9999})
        self.assertEqual((r.status_code, r.json()["detail"]["kind"]), (404, "not_found"))
        r = self.client.post("/api/budget/transactions", json={"amount": 5_000_000})
        self.assertEqual(r.status_code, 400)


class CategoryTests(BudgetTestCase):
    def test_add_rename_and_duplicate(self) -> None:
        self.client.get("/api/budget/summary")
        r = self.client.post("/api/budget/categories", json={"name": "Pets", "icon": "🐶", "limit": 80})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["limit"], 80)
        r = self.client.post("/api/budget/categories", json={"name": "pets"})
        self.assertEqual((r.status_code, r.json()["detail"]["kind"]), (409, "conflict"))
        pets = self.cat_id("Pets")
        self.assertEqual(self.client.patch(f"/api/budget/categories/{pets}", json={"name": "Pets"}).status_code, 200,
                         "keeping its own name isn't a clash")

    def test_deleting_a_category_keeps_its_expenses(self) -> None:
        dining = self.cat_id("Dining")
        self.add(30, category_id=dining, date="2026-11-03")
        self.assertEqual(self.client.delete(f"/api/budget/categories/{dining}").status_code, 204)
        s = self.client.get("/api/budget/summary?month=2026-11").json()
        self.assertEqual(s["spent"], 30)
        unc = next(c for c in s["categories"] if c["name"] == "Uncategorized")
        self.assertEqual((unc["id"], unc["spent"]), (None, 30))
        self.assertNotIn("Dining", [c["name"] for c in s["categories"]])


class ExportTests(BudgetTestCase):
    def test_csv_for_the_month(self) -> None:
        groceries = self.cat_id("Groceries")
        self.add(42.5, category_id=groceries, description="=HYPERLINK(\"x\")", date="2026-11-03")
        self.add(1000, kind="income", description="Salary", date="2026-11-01")
        self.add(5, date="2026-10-01")
        r = self.client.get("/api/budget/export.csv?month=2026-11")
        self.assertEqual(r.status_code, 200)
        self.assertIn('filename="luna-budget-2026-11.csv"', r.headers["content-disposition"])
        lines = r.text.strip().splitlines()
        self.assertEqual(lines[0], "Date,Type,Category,Description,Amount")
        self.assertEqual(lines[1], "2026-11-01,income,,Salary,1000.00")
        self.assertTrue(lines[2].startswith("2026-11-03,expense,Groceries,\"'=HYPERLINK"),
                        "formula-looking text is defused for spreadsheets")
        self.assertEqual(len(lines), 3)


RECEIPT = """WALMART
Save money. Live better.
ST# 1234 OP# 00 TE# 12
BANANAS            1.24
MILK 1GAL          3.48
SUBTOTAL          4.72
TAX 1   7.25 %     0.34
TOTAL             5.06
VISA TEND         5.06
CHANGE DUE        0.00
11/14/26  14:02:11
"""


class ReceiptParseTests(unittest.TestCase):
    def test_walmart_receipt(self) -> None:
        d = budget.parse_receipt_text(RECEIPT, today=date(2026, 11, 17))
        self.assertEqual(d.amount, 5.06)
        self.assertEqual(d.merchant, "Walmart")
        self.assertEqual(d.date, "2026-11-14")
        self.assertEqual(d.category, "Groceries")

    def test_amount_on_the_next_line_and_unknown_shop(self) -> None:
        text = "Blue Door Bistro\n12 Main St\nSubtotal 18.00\nTip 3.00\nTotal\n$21.00\nNov 2, 2026"
        d = budget.parse_receipt_text(text, today=date(2026, 11, 17))
        self.assertEqual((d.amount, d.merchant, d.date, d.category), (21.0, "Blue Door Bistro", "2026-11-02", "Dining"))

    def test_chain_name_with_spaces_lost_by_ocr(self) -> None:
        d = budget.parse_receipt_text("TRADERJOE'S\n123 Main St\nTOTAL 16.72", today=date(2026, 11, 17))
        self.assertEqual((d.merchant, d.category, d.amount), ("Trader Joe's", "Groceries", 16.72))

    def test_no_total_line_uses_largest_amount_and_ignores_future_dates(self) -> None:
        d = budget.parse_receipt_text("Corner Shop\nItem 2.50\nItem 1,204.99\n12/30/2027", today=date(2026, 11, 17))
        self.assertEqual(d.amount, 1204.99)
        self.assertIsNone(d.date)


def _font(size: int):
    from PIL import ImageFont
    for path in ("C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                 "/System/Library/Fonts/Supplemental/Arial.ttf"):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return None


class ReceiptRouteTests(BudgetTestCase):
    def test_photo_of_a_receipt(self) -> None:
        try:
            import rapidocr_onnxruntime  # noqa: F401
            from PIL import Image, ImageDraw
        except ImportError:
            self.skipTest("OCR not installed")
        font = _font(34)
        if font is None:
            self.skipTest("no TrueType font to draw a receipt")
        img = Image.new("RGB", (700, 640), "white")
        draw = ImageDraw.Draw(img)
        for i, line in enumerate(RECEIPT.strip().splitlines()):
            draw.text((40, 30 + i * 52), line, fill="black", font=font)
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=92)
        r = self.client.post("/api/budget/receipt", files={"image": ("r.jpg", buf.getvalue(), "image/jpeg")})
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["amount"], 5.06)
        self.assertEqual(body["merchant"], "Walmart")
        self.assertEqual(body["category"], "Groceries")

    def test_not_an_image(self) -> None:
        r = self.client.post("/api/budget/receipt", files={"image": ("r.jpg", b"not a photo", "image/jpeg")})
        self.assertEqual((r.status_code, r.json()["detail"]["kind"]), (400, "bad_image"))

    def test_blank_photo(self) -> None:
        try:
            import rapidocr_onnxruntime  # noqa: F401
            from PIL import Image
        except ImportError:
            self.skipTest("OCR not installed")
        buf = io.BytesIO()
        Image.new("RGB", (400, 600), "white").save(buf, "PNG")
        r = self.client.post("/api/budget/receipt", files={"image": ("r.png", buf.getvalue(), "image/png")})
        self.assertEqual((r.status_code, r.json()["detail"]["kind"]), (422, "no_text"))


if __name__ == "__main__":
    unittest.main()
