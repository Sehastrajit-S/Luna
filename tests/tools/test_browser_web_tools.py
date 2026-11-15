from __future__ import annotations

import unittest
from contextlib import redirect_stdout
from io import StringIO

from tests.tools import _bootstrap  # noqa: F401


class BrowserWebToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_browser_read_rejects_non_http(self) -> None:
        from server.services.browser_automation import browser_read

        with self.assertRaises(ValueError):
            await browser_read("file:///etc/passwd")

    async def test_web_fetch_rejects_empty_url_safely(self) -> None:
        from server.services.web_tools import web_fetch

        with redirect_stdout(StringIO()):
            result = await web_fetch("")
        self.assertIsInstance(result, str)
        self.assertTrue(result)

    async def test_reference_url_extraction_for_research(self) -> None:
        from server.services.web_tools import _extract_reference_urls

        result = "URL: https://example.com/a\nURL: https://example.com/b\nURL: https://example.com/a"
        self.assertEqual(
            _extract_reference_urls(result, limit=3),
            ["https://example.com/a", "https://example.com/b"],
        )

    def test_web_answer_reference_safeguard(self) -> None:
        from server.services.response_formatter import ensure_references as _ensure_references

        tool_result = "References:\n[1] Example - https://example.com/"
        answer = _ensure_references("Short answer.", tool_result)
        self.assertIn("\n\nReferences:", answer)
        self.assertIn("https://example.com/", answer)

    def test_web_answer_reference_safeguard_separates_jammed_references(self) -> None:
        from server.services.response_formatter import ensure_references as _ensure_references

        answer = _ensure_references(
            "Short answer.References:\n[1] Example - https://example.com/",
            "",
        )
        self.assertEqual(answer, "Short answer.\n\nReferences:\n[1] Example - https://example.com/")

    def test_web_answer_reference_safeguard_strips_malformed_source_bleed(self) -> None:
        from server.services.response_formatter import ensure_references as _ensure_references

        noisy = (
            "The SEC is a U.S. agency.(https://bad.example/source)\n"
            "2. [How to cite SEC filings](https://bad.example/cite)\n"
        )
        tool_result = "References:\n[1] SEC.gov - https://www.sec.gov/about"
        answer = _ensure_references(noisy, tool_result)
        self.assertIn("The SEC is a U.S. agency.", answer)
        self.assertIn("[1] SEC.gov - https://www.sec.gov/about", answer)
        self.assertNotIn("How to cite", answer)
        self.assertNotIn("bad.example", answer)

    def test_web_answer_reference_safeguard_strips_inline_title_url_bleed(self) -> None:
        from server.services.response_formatter import ensure_references as _ensure_references

        noisy = (
            "Pool pump efficiency uses WEF. "
            "Choosing, Installing, and Operating an Efficient Swimming Pool Pump - "
            "https://www.energy.gov/energysaver/choosing-installing-and-operating-efficient-swimming-pool-pump"
        )
        tool_result = "References:\n[1] Energy Saver - https://www.energy.gov/energysaver/choosing-installing-and-operating-efficient-swimming-pool-pump"
        answer = _ensure_references(noisy, tool_result)
        self.assertEqual(
            answer,
            "Pool pump efficiency uses WEF.\n\nReferences:\n[1] Energy Saver - https://www.energy.gov/energysaver/choosing-installing-and-operating-efficient-swimming-pool-pump",
        )

    def test_direct_research_query_detection_handles_citations_typo(self) -> None:
        from server.services.command_parser import extract_direct_research_query as _extract_direct_research_query

        query = _extract_direct_research_query("/research what is SEC and include the sitations")
        self.assertEqual(query, "what is SEC")

    def test_direct_research_query_requires_slash_command(self) -> None:
        from server.services.command_parser import extract_direct_research_query as _extract_direct_research_query

        for prompt in (
            "what is SEC with citations",
            "research what is SEC and cite the references",
            "what's the latest news on the EU AI Act",
            "compare gpt and claude models",
            "what song is playing right now",
            "/researcher notes",
            "/research",
            "/research   ",
            "hey",
        ):
            with self.subTest(prompt=prompt):
                self.assertIsNone(_extract_direct_research_query(prompt))

    def test_direct_research_query_detection_strips_cite_references(self) -> None:
        from server.services.command_parser import extract_direct_research_query as _extract_direct_research_query

        query = _extract_direct_research_query("/research what is SEC and cite the references")
        self.assertEqual(query, "what is SEC")

    def test_direct_research_query_detection_ten_prompt_smoke(self) -> None:
        from server.services.command_parser import extract_direct_research_query as _extract_direct_research_query

        cases = {
            "/research what is SEC and cite the references": "what is SEC",
            "/research on how to find defects in solar panels": "how to find defects in solar panels",
            "/research how to find the effiency of the pumps in swimming pools and water useage across the USA through NAIP imagery": "how to find the effiency of the pumps in swimming pools and water useage across the USA through NAIP imagery",
            "/research what is SEC with citations": "what is SEC",
            "/Research what is SEC with references": "what is SEC",
            "/research find out about NAIP imagery and include sources": "NAIP imagery",
            "/research look up pool pump weighted energy factor with references": "pool pump weighted energy factor",
            "/research investigate solar panel microcrack detection and provide citations": "solar panel microcrack detection",
            "  /research source-backed comparison of pool pump WEF": "source-backed comparison of pool pump WEF",
            "/research github copilot pricing": "github copilot pricing",
        }
        for prompt, expected in cases.items():
            with self.subTest(prompt=prompt):
                self.assertEqual(_extract_direct_research_query(prompt), expected)

    async def test_web_download_rejects_non_http_url(self) -> None:
        from server.services.web_tools import web_download_file

        with self.assertRaises(ValueError):
            await web_download_file("file:///tmp/data.csv", "_tests/data.csv")


if __name__ == "__main__":
    unittest.main(verbosity=2)
