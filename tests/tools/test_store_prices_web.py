"""Store prices without a SerpApi key: free web search of each store's site."""
from __future__ import annotations

import asyncio
import unittest
from unittest import mock

from tests.tools import _bootstrap  # noqa: F401

import httpx

from server.config import settings
from server.services.shopping import compare as compare_mod
from server.services.shopping import compare_store_prices
from server.services.shopping.stores import resolve_stores
from server.services.skill_runtime.sources import Result

TARGET_PAGE = ('<script type="application/ld+json">{"@type":"Product","name":"Tide PODS Original 81ct",'
               '"image":"https://img/t.jpg","offers":{"price":"22.99","priceCurrency":"USD"}}</script>')


def run(coro):
    return asyncio.run(coro)


class FreeWebSearchTests(unittest.TestCase):
    def setUp(self) -> None:
        patcher = mock.patch.multiple(settings, serpapi_api_key="", shopping_location="")
        patcher.start()
        self.addCleanup(patcher.stop)
        audit = mock.patch.object(compare_mod, "record_audit")
        self.audit = audit.start()
        self.addCleanup(audit.stop)
        self.queries: list[str] = []

    async def _search(self, queries, per_query=8):
        self.queries = queries
        return [
            Result("q", "Tide PODS Laundry Detergent, 81 Count - Walmart.com", "Buy Tide PODS 81 ct for $21.97 today",
                   "https://www.walmart.com/ip/Tide-PODS-81/123"),
            Result("q", "Tide PODS Original 81ct : Target", "Shop Tide PODS.", "https://www.target.com/p/tide-pods-81ct/-/A-1"),
            Result("q", "Tide Pods 81-count | Costco", "Members only.", "https://www.costco.com/tide-pods-81.product.100.html"),
            Result("q", "Tide Pods - Sam's Club search", "Results", "https://www.samsclub.com/s/tide%20pods"),
            Result("q", "Gain Flings Moonlight Breeze - Safeway", "$9.99", "https://www.safeway.com/shop/product-details.555.html"),
        ]

    def _run(self) -> dict:
        def pages(request: httpx.Request) -> httpx.Response:
            if "target.com" in request.url.host:
                return httpx.Response(200, html=TARGET_PAGE)
            return httpx.Response(403, text="Access Denied")      # bot protection

        client = httpx.AsyncClient(transport=httpx.MockTransport(pages))
        try:
            return run(compare_mod._compare_via_web("Tide Pods 81 count", resolve_stores(None),
                                                    client=client, search=self._search))
        finally:
            run(client.aclose())

    def test_prices_from_snippets_and_pages_with_honest_gaps(self) -> None:
        result = self._run()
        by_store = {r["store"]: r for r in result["stores"]}
        self.assertEqual(by_store["Walmart"]["price"], 21.97, "price read from the search snippet")
        self.assertEqual(by_store["Target"]["price"], 22.99, "price read from the page's JSON-LD")
        self.assertEqual(by_store["Costco"]["status"], "price_hidden", "page found but blocked: link, no price")
        self.assertEqual(by_store["Sam's Club"]["status"], "not_found", "a search page is not a product page")
        self.assertEqual(by_store["Safeway"]["status"], "not_found", "Gain Flings is not the product")
        self.assertEqual(result["cheapest"]["store"], "Walmart")
        self.assertEqual(result["source"], "web")
        self.assertIn("SerpApi", result["note"])
        self.assertTrue(self.queries and all("site:" in q for q in self.queries))
        self.assertEqual(self.audit.call_args.kwargs["args"]["provider"], "duckduckgo")

    def test_markdown_links_stores_whose_page_hides_the_price(self) -> None:
        md = compare_mod.render_markdown(self._run())
        self.assertIn("cheapest at **Walmart** ($21.97)", md)
        self.assertIn("- **Costco**: [see price](https://www.costco.com/tide-pods-81.product.100.html)", md)
        self.assertNotIn("Sam's Club", md, "stores without a match aren't shown")
        self.assertIn("free web search", md)

    def test_compare_uses_web_when_no_key(self) -> None:
        with mock.patch.object(compare_mod, "_compare_via_web", mock.AsyncMock(return_value={"source": "web"})) as web:
            self.assertEqual(run(compare_store_prices("eggs"))["source"], "web")
        web.assert_awaited_once()

    def test_brand_must_match(self) -> None:
        score = compare_mod.match_score
        self.assertEqual(score("Kirkland paper towels 12 rolls", "Brawny Paper Towels, 12 Double Rolls"), 0.0)
        self.assertGreater(score("Kirkland paper towels 12 rolls", "Kirkland Signature Paper Towels, 12 Rolls"), 0.5)
        self.assertGreater(score("paper towels 12 rolls", "Bounty Paper Towels, 12 Double Rolls"), 0.5, "no brand given")
        self.assertGreater(score("12 count eggs", "Great Value Large White Eggs, 12 Count"), 0.0, "numbers aren't brands")

    def test_search_failure_is_a_friendly_error(self) -> None:
        from server.services.shopping import ShoppingError

        async def broken(queries, per_query=8):
            raise RuntimeError("ddgs exploded")

        with self.assertRaises(ShoppingError) as ctx:
            run(compare_mod._compare_via_web("eggs", resolve_stores(None), search=broken))
        self.assertEqual(ctx.exception.kind, "upstream_error")


if __name__ == "__main__":
    unittest.main(verbosity=2)
