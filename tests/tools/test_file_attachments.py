import asyncio
import io
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock


def _pdf_with_pages(pages: list[str]) -> bytes:
    """Minimal valid PDF with one text line per page (no PDF writer library needed)."""
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", None, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids = []
    for text in pages:
        stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
        objs.append(f"<< /Length {len(stream)} >>\nstream\n{stream.decode()}\nendstream")
        content_id = len(objs)
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                    f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>")
        kids.append(f"{len(objs)} 0 R")
    objs[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(kids)} >>"
    out, offsets = io.BytesIO(), []
    out.write(b"%PDF-1.4\n")
    for i, body in enumerate(objs, start=1):
        offsets.append(out.tell())
        out.write(f"{i} 0 obj\n{body}\nendobj\n".encode())
    xref = out.tell()
    out.write(f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode())
    for off in offsets:
        out.write(f"{off:010d} 00000 n \n".encode())
    out.write(f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
    return out.getvalue()


class ExtractionTests(unittest.TestCase):
    def test_pdf_pages_are_labelled(self) -> None:
        from server.services.files.extract import extract_file

        doc = extract_file(_pdf_with_pages(["Revenue grew 12 percent", "Churn fell to 3 percent"]), "report.pdf")
        self.assertEqual(doc.kind, "pdf")
        self.assertEqual(doc.page_count, 2)
        self.assertEqual([s.label for s in doc.sections], ["p. 1", "p. 2"])
        self.assertIn("Churn fell", doc.sections[1].text)
        self.assertEqual(doc.summary_line, "PDF · 2 pages")
        self.assertFalse(doc.warnings)

    def test_scanned_and_encrypted_pdfs_explain_themselves(self) -> None:
        from pypdf import PdfWriter
        from server.services.files.extract import UnsupportedFile, extract_file

        writer = PdfWriter()
        writer.add_blank_page(612, 792)
        blank = io.BytesIO(); writer.write(blank)
        doc = extract_file(blank.getvalue(), "blank.pdf")
        self.assertTrue(any("even with OCR" in w for w in doc.warnings))

        writer = PdfWriter()
        writer.add_blank_page(612, 792)
        writer.encrypt("secret")
        locked = io.BytesIO(); writer.write(locked)
        with self.assertRaisesRegex(UnsupportedFile, "password"):
            extract_file(locked.getvalue(), "locked.pdf")

        with self.assertRaisesRegex(UnsupportedFile, "damaged"):
            extract_file(b"%PDF-1.4 garbage", "broken.pdf")

    def test_docx_keeps_headings_and_tables(self) -> None:
        import docx
        from server.services.files.extract import extract_file

        d = docx.Document()
        d.add_heading("Quarterly Plan", level=1)
        d.add_paragraph("Ship the importer by May.")
        table = d.add_table(rows=2, cols=2)
        table.cell(0, 0).text, table.cell(0, 1).text = "Owner", "Task"
        table.cell(1, 0).text, table.cell(1, 1).text = "Ana", "Importer"
        buf = io.BytesIO(); d.save(buf)

        doc = extract_file(buf.getvalue(), "plan.docx")
        self.assertEqual(doc.kind, "docx")
        self.assertIn("# Quarterly Plan", doc.full_text)
        self.assertIn("| Ana | Importer |", doc.full_text)
        self.assertIn("Quarterly Plan", doc.overview)

    def test_pptx_slides_and_notes(self) -> None:
        from pptx import Presentation
        from server.services.files.extract import extract_file

        deck = Presentation()
        slide = deck.slides.add_slide(deck.slide_layouts[1])
        slide.shapes.title.text = "Roadmap"
        slide.placeholders[1].text = "Launch in Q3"
        slide.notes_slide.notes_text_frame.text = "Mention hiring"
        buf = io.BytesIO(); deck.save(buf)

        doc = extract_file(buf.getvalue(), "deck.pptx")
        self.assertEqual(doc.sections[0].label, "slide 1")
        self.assertIn("# Roadmap", doc.sections[0].text)
        self.assertIn("Speaker notes: Mention hiring", doc.sections[0].text)
        self.assertEqual(doc.summary_line, "PowerPoint · 1 slide")

    def test_xlsx_and_csv_get_a_data_profile(self) -> None:
        from openpyxl import Workbook
        from server.services.files.extract import extract_file

        wb = Workbook(); ws = wb.active; ws.title = "Sales"
        ws.append(["region", "revenue"])
        for region, revenue in [("East", 100), ("West", 250), ("East", 50)]:
            ws.append([region, revenue])
        buf = io.BytesIO(); wb.save(buf)
        xlsx = extract_file(buf.getvalue(), "sales.xlsx")
        self.assertEqual(xlsx.kind, "spreadsheet")
        self.assertIn("3 rows × 2 columns", xlsx.overview)
        self.assertIn("revenue: numeric, min 50, max 250", xlsx.overview)
        self.assertIn("East ×2", xlsx.overview)
        self.assertTrue(xlsx.sections[0].label.startswith("Sales, rows"))

        csv_doc = extract_file("name;score\nA;1\nB;3\n".encode("utf-8"), "scores.csv")
        self.assertIn("2 rows × 2 columns", csv_doc.overview)
        self.assertIn("score: numeric", csv_doc.overview)

    def test_text_code_html_and_notebooks(self) -> None:
        import json
        from server.services.files.extract import extract_file

        code = extract_file(("\n".join(f"line {i}" for i in range(400))).encode(), "big.py")
        self.assertEqual(code.sections[0].label, "lines 1–150")
        html = extract_file(b"<html><script>x()</script><h1>Title</h1><p>Body &amp; more</p></html>", "page.html")
        self.assertIn("Body & more", html.full_text)
        self.assertNotIn("x()", html.full_text)
        nb = json.dumps({"cells": [{"cell_type": "code", "source": ["print(1)"]}]}).encode()
        self.assertIn("```python\nprint(1)", extract_file(nb, "a.ipynb").full_text)
        latin = extract_file("café résumé".encode("latin-1"), "notes.txt")
        self.assertIn("caf", latin.full_text)

    def test_unsupported_types_have_clear_messages(self) -> None:
        from server.services.files.extract import UnsupportedFile, check_supported

        with self.assertRaisesRegex(UnsupportedFile, "save it as .docx"):
            check_supported("old.doc")
        with self.assertRaisesRegex(UnsupportedFile, "can't read .exe"):
            check_supported("setup.exe")


def _text_image(lines: list[str], size=(1400, 500)):
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 38)
    except OSError:
        font = ImageFont.load_default()
    for i, line in enumerate(lines):
        draw.text((50, 50 + i * 80), line, fill="black", font=font)
    return img


class OcrTests(unittest.TestCase):
    def test_scanned_pdf_is_read_with_ocr(self) -> None:
        from server.services.files.extract import extract_file

        page1 = _text_image(["Lease Agreement", "Monthly rent: $2,350 due on the 1st"])
        page2 = _text_image(["Security deposit: $4,700", "Term: 12 months"])
        buf = io.BytesIO()
        page1.save(buf, "PDF", save_all=True, append_images=[page2], resolution=150)

        doc = extract_file(buf.getvalue(), "lease-scan.pdf")
        self.assertEqual([s.label for s in doc.sections], ["p. 1", "p. 2"])
        self.assertIn("$2,350", doc.sections[0].text)
        self.assertIn("Security deposit", doc.sections[1].text)
        self.assertTrue(any("read with OCR" in w for w in doc.warnings))

    def test_mixed_pdf_only_ocrs_scanned_pages(self) -> None:
        from pypdf import PdfReader, PdfWriter
        from server.services.files.extract import extract_file

        scanned = io.BytesIO()
        _text_image(["Appendix B scanned signature page"]).save(scanned, "PDF")
        writer = PdfWriter()
        for page in PdfReader(io.BytesIO(_pdf_with_pages(["Typed page with a real text layer"]))).pages:
            writer.add_page(page)
        for page in PdfReader(scanned).pages:
            writer.add_page(page)
        out = io.BytesIO(); writer.write(out)

        with mock.patch("server.services.files.ocr.ocr_image", wraps=__import__(
                "server.services.files.ocr", fromlist=["ocr_image"]).ocr_image) as spy:
            doc = extract_file(out.getvalue(), "mixed.pdf")
        self.assertEqual(spy.call_count, 1)                   # only page 2 went through OCR
        self.assertIn("Typed page", doc.sections[0].text)
        self.assertIn("Appendix B", doc.sections[1].text)
        self.assertTrue(any("Page 2 was scanned" in w for w in doc.warnings))

    def test_image_gets_exact_ocr_text_plus_vision_description(self) -> None:
        from server.services.files import service

        img = _text_image(["TypeError: cannot read properties of undefined", "at render (App.jsx:42)"])
        buf = io.BytesIO(); img.save(buf, "PNG")

        async def fake_vision(model, png):
            self.assertEqual(model, "qwen2.5vl:7b")
            return "A screenshot of a JavaScript error in a browser console."

        with mock.patch.object(service, "_installed_models", new=mock.AsyncMock(return_value=["qwen2.5vl:7b", "moondream:latest"])), \
             mock.patch.object(service, "_vision_describe", side_effect=fake_vision):
            doc = asyncio.run(service._describe_image(buf.getvalue(), ".png"))
        labels = [s.label for s in doc.sections]
        self.assertEqual(labels, ["Description", "Text in the image (OCR)"])
        self.assertIn("App.jsx:42", doc.sections[1].text)
        self.assertIn("1400×500", doc.summary_line)
        self.assertFalse(doc.warnings)

    def test_vision_model_falls_back_to_best_installed(self) -> None:
        from server.services.files import service

        with mock.patch.object(service, "_installed_models", new=mock.AsyncMock(return_value=["llava:13b", "moondream:latest"])):
            self.assertEqual(asyncio.run(service.pick_vision_model()), "llava:13b")
        with mock.patch.object(service, "_installed_models", new=mock.AsyncMock(return_value=["qwen3:8b"])):
            self.assertIsNone(asyncio.run(service.pick_vision_model()))


class AttachmentServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        from sqlalchemy import create_engine, event
        from sqlalchemy.orm import sessionmaker
        from server.models.database import Base
        from server.services.files import service

        self.tmp = Path(tempfile.mkdtemp())
        self.patch_root = mock.patch.object(service, "UPLOAD_ROOT", self.tmp)
        self.patch_root.start()
        engine = create_engine("sqlite://")
        event.listen(engine, "connect", lambda conn, _r: conn.execute("PRAGMA foreign_keys=ON"))
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()

    def tearDown(self) -> None:
        self.patch_root.stop()
        self.db.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _conversation_with_message(self):
        from server.models.database import Conversation, Message
        conv = Conversation(message_count=1); self.db.add(conv); self.db.commit()
        msg = Message(conversation_id=conv.id, role="user", content="see attached"); self.db.add(msg); self.db.commit()
        return conv, msg

    def test_small_file_is_sent_in_full_and_stays_for_follow_ups(self) -> None:
        from server.services.files import build_attachment_context, link_to_message, save_upload

        conv, msg = self._conversation_with_message()
        att = asyncio.run(save_upload(self.db, "report.pdf", _pdf_with_pages(["Revenue grew 12 percent"])))
        self.assertEqual(att.status, "ready")
        linked = link_to_message(self.db, [att.id, "not-an-id"], conv.id, msg.id)
        self.assertEqual([a.id for a in linked], [att.id])

        block = asyncio.run(build_attachment_context(self.db, conv.id, "what grew?", current_ids=[att.id]))
        self.assertIn('name="report.pdf"', block)
        self.assertIn('coverage="full"', block)
        self.assertIn("[p. 1]", block)
        # A later turn with no new attachment still sees the file.
        later = asyncio.run(build_attachment_context(self.db, conv.id, "and the 12th follow-up?"))
        self.assertIn("Revenue grew 12 percent", later)

    def test_large_file_uses_relevant_excerpts_within_budget(self) -> None:
        from server.services.files import build_attachment_context, link_to_message, save_upload
        from server.services.files import retrieval
        from server.services.files.service import document_budget
        from server.services.llm.context_window import estimate_tokens

        conv, msg = self._conversation_with_message()
        pages = [f"Filler page {i} " + "lorem ipsum " * 400 for i in range(60)]
        pages[41] = "The warranty period is 36 months for all hardware. " + "details " * 200
        att = asyncio.run(save_upload(self.db, "manual.pdf", _pdf_with_pages(pages)))
        link_to_message(self.db, [att.id], conv.id, msg.id)

        async def no_embeddings(_texts):
            return None  # force the keyword ranker (no Ollama in tests)

        with mock.patch.object(retrieval, "_embed_batch", side_effect=no_embeddings):
            block = asyncio.run(build_attachment_context(self.db, conv.id, "how long is the warranty period?"))
        self.assertIn('coverage="excerpts relevant to the question"', block)
        self.assertIn("[p. 42]", block)
        self.assertIn("36 months", block)
        self.assertLessEqual(estimate_tokens(block), document_budget() + 400)

    def test_cannot_claim_another_conversations_file_and_sent_files_are_locked(self) -> None:
        from server.services.files import link_to_message, save_upload

        conv_a, msg_a = self._conversation_with_message()
        conv_b, msg_b = self._conversation_with_message()
        att = asyncio.run(save_upload(self.db, "a.txt", b"secret notes"))
        link_to_message(self.db, [att.id], conv_a.id, msg_a.id)
        self.assertEqual(link_to_message(self.db, [att.id], conv_b.id, msg_b.id), [])

    def test_deleting_a_chat_deletes_its_files(self) -> None:
        from server.models.database import Attachment
        from server.routers.chat import delete_conversation
        from server.services.files import link_to_message, save_upload

        conv, msg = self._conversation_with_message()
        att = asyncio.run(save_upload(self.db, "notes.md", b"# Notes\nremember the milk"))
        link_to_message(self.db, [att.id], conv.id, msg.id)
        folder = self.tmp / att.id
        self.assertTrue(folder.exists())

        delete_conversation(conv.id, db=self.db)
        self.assertFalse(folder.exists())
        self.assertEqual(self.db.query(Attachment).count(), 0)

    def test_unsent_uploads_are_swept_after_a_day(self) -> None:
        from datetime import datetime, timedelta, timezone
        from server.models.database import Attachment
        from server.services.files import link_to_message, save_upload
        from server.services.files.service import sweep_unsent_uploads

        conv, msg = self._conversation_with_message()
        old_unsent = asyncio.run(save_upload(self.db, "old.txt", b"forgotten"))
        new_unsent = asyncio.run(save_upload(self.db, "new.txt", b"still in composer"))
        old_sent = asyncio.run(save_upload(self.db, "sent.txt", b"part of history"))
        link_to_message(self.db, [old_sent.id], conv.id, msg.id)
        two_days_ago = datetime.now(timezone.utc) - timedelta(days=2)
        for row in (old_unsent, old_sent):
            row.created_at = two_days_ago
        self.db.commit()

        self.assertEqual(sweep_unsent_uploads(self.db), 1)
        remaining = {a.filename for a in self.db.query(Attachment).all()}
        self.assertEqual(remaining, {"new.txt", "sent.txt"})
        self.assertFalse((self.tmp / old_unsent.id).exists())

    def test_empty_upload_rejected(self) -> None:
        from server.services.files import UnsupportedFile, save_upload

        with self.assertRaisesRegex(UnsupportedFile, "empty"):
            asyncio.run(save_upload(self.db, "empty.txt", b""))


if __name__ == "__main__":
    unittest.main(verbosity=2)
