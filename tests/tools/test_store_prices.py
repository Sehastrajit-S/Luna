"""Store price comparison (Google Shopping via SerpApi): matching, budgets, errors, routing."""
from __future__ import annotations

import asyncio
import json
import unittest
from unittest import mock

from tests.tools import _bootstrap  # noqa: F401

import httpx

from server.config import settings
from server.services.shopping import compare as compare_mod
from server.services.shopping import ShoppingError, compare_store_prices, format_for_chat
from server.services.shopping.stores import resolve_stores
from server.services.agent_loop.tool_selection import is_store_price_request, select_tools
from server.services.tool_registry import get_tool, validate_tool_args

KEY = "sk-test-secret-key-123"


def item(title, source, price, pos=1, image="https://img/x.jpg"):
    return {"position": pos, "title": title, "source": source, "price": f"${price:.2f}", "extracted_price": price,
            "product_link": f"https://www.google.com/shopping/product/{pos}", "thumbnail": image}


GENERAL = {"shopping_results": [
    item("Tide PODS Laundry Detergent, Original, 81 Count", "Walmart", 21.97, 1),
    item("Tide PODS Laundry Detergent Original 81 ct", "Target", 22.99, 2),
    item("Tide PODS Original 81-count", "Walmart - QuickShip Deals", 15.00, 3),   # marketplace seller
    item("Tide PODS Original, 156 count", "Costco", 34.99, 4),
    item("Gain Flings 81 count", "Costco", 19.99, 5),                            # a different product
]}


def run(coro):
    return asyncio.run(coro)


def transport(responses):
    """responses: list of (status, json) returned in order; records the queries asked."""
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(dict(request.url.params))
        status, body = responses[min(len(seen) - 1, len(responses) - 1)]
        return httpx.Response(status, json=body)

    return httpx.MockTransport(handler), seen


class CompareTests(unittest.TestCase):
    def setUp(self) -> None:
        patcher = mock.patch.multiple(settings, serpapi_api_key=KEY, shopping_location="", shopping_max_searches=3)
        patcher.start()
        self.addCleanup(patcher.stop)
        audit = mock.patch.object(compare_mod, "record_audit")
        self.audit = audit.start()
        self.addCleanup(audit.stop)

    def _compare(self, responses, stores=None):
        t, seen = transport(responses)
        client = httpx.AsyncClient(transport=t)
        try:
            return run(compare_store_prices("Tide Pods 81 count", stores, client=client)), seen
        finally:
            run(client.aclose())

    def test_prices_each_store_and_finds_cheapest(self) -> None:
        sams = {"shopping_results": [item("Tide PODS Original 81 Count", "Sam's Club", 19.98, 1)]}
        safeway = {"error": "Google Shopping hasn't returned any results for this query."}
        result, seen = self._compare([(200, GENERAL), (200, sams), (200, safeway)])
        by_store = {r["store"]: r for r in result["stores"]}
        self.assertEqual(by_store["Walmart"]["price"], 21.97, "marketplace seller must not count as Walmart")
        self.assertEqual(by_store["Target"]["price"], 22.99)
        self.assertEqual(by_store["Costco"]["price"], 34.99, "Gain Flings is not the product")
        self.assertEqual(by_store["Sam's Club"]["price"], 19.98)
        self.assertEqual(by_store["Safeway"]["status"], "not_found")
        self.assertEqual(result["cheapest"]["store"], "Sam's Club")
        self.assertEqual(result["searches_used"], 3)
        self.assertEqual([p["q"] for p in seen], ["Tide Pods 81 count", "Tide Pods 81 count Sam's Club", "Tide Pods 81 count Safeway"])

    def test_search_budget_limits_follow_ups(self) -> None:
        settings.shopping_max_searches = 1
        result, seen = self._compare([(200, GENERAL)])
        self.assertEqual(len(seen), 1)
        statuses = {r["store"]: r["status"] for r in result["stores"]}
        self.assertEqual(statuses["Sam's Club"], "not_searched")
        self.assertEqual(statuses["Safeway"], "not_searched")

    def test_only_requested_stores(self) -> None:
        result, seen = self._compare([(200, GENERAL)], stores=["walmart", "TARGET"])
        self.assertEqual([r["store"] for r in result["stores"]], ["Walmart", "Target"])
        self.assertEqual(len(seen), 1, "both found in the first search")

    def test_quota_during_follow_up_keeps_partial_results(self) -> None:
        quota = {"error": "Your account has run out of searches."}
        result, seen = self._compare([(200, GENERAL), (429, quota)])
        statuses = {r["store"]: r["status"] for r in result["stores"]}
        self.assertEqual(statuses["Walmart"], "found")
        self.assertEqual(statuses["Sam's Club"], "quota_exhausted")
        self.assertEqual(statuses["Safeway"], "not_searched")
        self.assertEqual(len(seen), 2, "no more searches after the quota ran out")

    def test_not_configured(self) -> None:
        settings.serpapi_api_key = ""
        with self.assertRaises(ShoppingError) as ctx:
            self._compare([(200, GENERAL)])
        self.assertEqual(ctx.exception.kind, "not_configured")
        self.assertIn("serpapi_api_key", ctx.exception.message)

    def test_auth_and_provider_errors_are_typed_and_never_leak_the_key(self) -> None:
        cases = [
            ((401, {"error": "Invalid API key. Your API key should be here: https://serpapi.com/manage-api-key"}), "invalid_key"),
            ((200, {"error": "Your account has run out of searches."}), "quota_exhausted"),
            ((429, {"error": "Too many requests"}), "rate_limited"),
            ((500, {"error": "Internal error"}), "upstream_error"),
        ]
        for response, kind in cases:
            with self.subTest(kind=kind):
                with self.assertRaises(ShoppingError) as ctx:
                    self._compare([response])
                self.assertEqual(ctx.exception.kind, kind)
                self.assertNotIn(KEY, ctx.exception.message)

    def test_network_failure_is_upstream_error_without_key(self) -> None:
        def boom(request):
            raise httpx.ConnectError(f"failed to connect to {request.url}")
        client = httpx.AsyncClient(transport=httpx.MockTransport(boom))
        try:
            with self.assertRaises(ShoppingError) as ctx:
                run(compare_store_prices("Tide Pods", client=client))
        finally:
            run(client.aclose())
        self.assertEqual(ctx.exception.kind, "upstream_error")
        self.assertNotIn(KEY, ctx.exception.message)

    def test_external_read_is_audited_without_the_key(self) -> None:
        self._compare([(200, GENERAL)], stores=["Walmart"])
        self.audit.assert_called_once()
        call = self.audit.call_args
        self.assertEqual(call.args[0], "external_read")
        self.assertEqual(call.kwargs["args"]["provider"], "serpapi")
        self.assertNotIn(KEY, json.dumps(call.kwargs, default=str))

    def test_chat_format_has_facts_guidance_and_cards_cheapest_first(self) -> None:
        sams = {"shopping_results": [item("Tide PODS Original 81 Count", "Sam's Club", 19.98, 1)]}
        result, _ = self._compare([(200, GENERAL), (200, sams), (200, {"shopping_results": []})])
        text = format_for_chat(result)
        facts = json.loads(text.split("\n\n")[0])
        self.assertEqual(facts["cheapest"]["store"], "Sam's Club")
        self.assertIn("table", text)
        cards = json.loads(text.split("<!--luna-cards:")[1].rsplit("-->", 1)[0])
        self.assertEqual(cards[0]["site"], "Sam's Club")
        self.assertEqual([c["price"] for c in cards], sorted((c["price"] for c in cards), key=lambda p: float(p.replace(",", ""))))


class WiringTests(unittest.TestCase):
    def test_tool_is_registered_read_only_and_coerces_store_lists(self) -> None:
        tool = get_tool("compare_store_prices")
        self.assertIsNotNone(tool)
        self.assertTrue(tool.read_only)
        args, error = validate_tool_args("compare_store_prices", {"product": "eggs", "stores": "walmart, Sam's Club"})
        self.assertIsNone(error)
        self.assertEqual(args["stores"], ["walmart", "Sam's Club"])
        self.assertEqual([s.name for s in resolve_stores(args["stores"])], ["Walmart", "Sam's Club"])

    def test_routing_recognises_store_price_requests(self) -> None:
        yes = [
            "how much is a rotisserie chicken at costco",
            "compare prices for tide pods",
            "is milk cheaper at walmart or safeway",
            "price of airpods at target",
            "which store has the cheapest paper towels",
            "sams club vs walmart for diapers",
        ]
        no = ["what's our target audience", "recommend good headphones under $200", "plan a trip to kyoto"]
        for text in yes:
            with self.subTest(text=text):
                self.assertTrue(is_store_price_request(text))
                self.assertIn("compare_store_prices", select_tools(text))
        for text in no:
            with self.subTest(text=text):
                self.assertFalse(is_store_price_request(text))


if __name__ == "__main__":
    unittest.main(verbosity=2)


class DirectAnswerTests(unittest.TestCase):
    """The + menu's Compare store prices: answered from the listings, no model."""

    RESULT = {
        "product": "Tide Pods 81 count", "location": "United States (online prices)", "searches_used": 3,
        "stores": [
            {"store": "Walmart", "status": "found", "title": "Tide PODS | Original 81 ct", "price": 21.97, "price_text": "$21.97",
             "url": "https://g/1", "image": "https://i/1"},
            {"store": "Sam's Club", "status": "found", "title": "Tide PODS 81 Count", "price": 19.98, "price_text": "$19.98",
             "url": "https://g/2", "image": "https://i/2"},
            {"store": "Safeway", "status": "not_found"},
        ],
        "cheapest": {"store": "Sam's Club", "price": 19.98, "title": "Tide PODS 81 Count"},
        "note": compare_mod.NOTE,
    }

    def test_markdown_table_cheapest_first_with_missing_stores(self) -> None:
        text = compare_mod.render_markdown(self.RESULT)
        self.assertIn("cheapest at **Sam's Club** ($19.98)", text)
        rows = [l for l in text.splitlines() if l.startswith("| ") and "Store" not in l]
        self.assertEqual([r.split("|")[1].strip() for r in rows], ["Sam's Club", "Walmart"])
        self.assertIn("Tide PODS / Original 81 ct", text, "pipes in titles must not break the table")
        self.assertIn("Not priced: Safeway (no listing from this store matched)", text)
        self.assertIn("<!--luna-cards:", text)

    def test_nothing_found(self) -> None:
        result = {**self.RESULT, "stores": [{"store": "Walmart", "status": "not_found"}], "cheapest": None}
        self.assertIn("couldn't find", compare_mod.render_markdown(result))

    def _ctx(self, message: str, skill: str):
        from server.services.chat_pipeline.context import ChatContext
        ctx = ChatContext(db=None, user_message=message, skill=skill)
        ctx.conv = mock.Mock(id=1)
        ctx.history = []
        return ctx

    def test_dispatch_answers_picked_store_prices_directly(self) -> None:
        from server.services.chat_pipeline import stage_dispatch
        ctx = self._ctx("Tide Pods 81 count", "store-prices")
        with mock.patch("server.services.shopping.compare_store_prices", mock.AsyncMock(return_value=self.RESULT)) as compare:
            run(stage_dispatch.dispatch_direct_commands(ctx))
        compare.assert_awaited_once_with("Tide Pods 81 count")
        self.assertTrue(ctx.dispatched)
        self.assertEqual(ctx.direct_command_type, "skill:store-prices")
        self.assertIn("| Sam's Club |", ctx.full_response)

    def test_dispatch_relays_setup_errors(self) -> None:
        from server.services.chat_pipeline import stage_dispatch
        ctx = self._ctx("eggs", "store-prices")
        error = ShoppingError("not_configured", "Store price comparison needs a SerpApi key.")
        with mock.patch("server.services.shopping.compare_store_prices", mock.AsyncMock(side_effect=error)):
            run(stage_dispatch.dispatch_direct_commands(ctx))
        self.assertEqual(ctx.full_response, error.message)
        self.assertFalse(ctx.tool_succeeded)

    def test_dispatch_runs_a_picked_lookup_skill_even_without_search_wording(self) -> None:
        from server.services.chat_pipeline import stage_dispatch
        ctx = self._ctx("quantum error correction", "paper-search")
        fake_run = mock.Mock(answer="papers", results_text="r", asked=False, skill_id="paper-search")
        with mock.patch.object(stage_dispatch, "run_search_skill", mock.AsyncMock(return_value=fake_run)) as runner, \
             mock.patch.object(stage_dispatch, "_search_answer_context", mock.AsyncMock(return_value=("", ""))):
            run(stage_dispatch.dispatch_direct_commands(ctx))
        self.assertEqual(runner.await_args.args[0].id, "paper-search")
        self.assertEqual(ctx.full_response, "papers")

    def test_picked_skill_skips_small_talk(self) -> None:
        from server.services.chat_pipeline.stage_small_talk import answer_small_talk
        self.assertFalse(answer_small_talk(self._ctx("thanks", "store-prices")))

    def test_pickable_lists_store_prices_first_and_lookup_skills(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from server.routers.skills import router
        app = FastAPI()
        app.include_router(router)
        with mock.patch.object(settings, "serpapi_api_key", ""):
            skills = TestClient(app).get("/api/skills/pickable").json()["skills"]
        self.assertEqual(skills[0]["id"], "store-prices")
        self.assertFalse(skills[0]["ready"], "no key yet: the menu points to Settings")
        self.assertIn("paper-search", [s["id"] for s in skills])


@unittest.skipUnless(__import__("shutil").which("node"), "node is required")
class MarkdownTableTests(unittest.TestCase):
    def test_pipe_tables_render_escaped(self) -> None:
        import subprocess
        from pathlib import Path
        md = Path(_bootstrap.ROOT) / "interfaces" / "desktop" / "src" / "renderer" / "markdown.js"
        script = (
            "const fs=require('fs');const vm=require('vm');const w={};vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),{window:w});"
            "process.stdout.write(w.renderMarkdown('| Store | Price |\\n|---|---:|\\n| Walmart | $21.97 |\\n| <b>x</b> | $1 |\\n\\nafter'))"
        )
        html = subprocess.run(["node", "-e", script, str(md)], capture_output=True, text=True, timeout=30, check=True).stdout
        self.assertIn('<table class="md-table">', html)
        self.assertIn("<th>Store</th>", html)
        self.assertIn("<td>Walmart</td><td>$21.97</td>", html)
        self.assertIn("&lt;b&gt;x&lt;/b&gt;", html, "cells are escaped")
        self.assertIn("<p>after</p>", html)


class SizeAndIconTests(unittest.TestCase):
    def setUp(self) -> None:
        patcher = mock.patch.multiple(settings, serpapi_api_key=KEY, shopping_location="", shopping_max_searches=1)
        patcher.start()
        self.addCleanup(patcher.stop)
        audit = mock.patch.object(compare_mod, "record_audit")
        audit.start()
        self.addCleanup(audit.stop)

    def _compare(self, listings, product="Tide Pods 81 count"):
        t, _ = transport([(200, {"shopping_results": listings})])
        client = httpx.AsyncClient(transport=t)
        try:
            return run(compare_store_prices(product, client=client))
        finally:
            run(client.aclose())

    def test_bigger_pack_is_not_called_cheapest(self) -> None:
        result = self._compare([
            item("Tide PODS Original 81 Count", "Walmart", 21.97, 1),
            item("Tide PODS Original, 42 Count", "Target", 12.49, 2),   # cheaper, but half the pods
        ])
        by_store = {r["store"]: r for r in result["stores"]}
        self.assertTrue(by_store["Walmart"]["same_size"])
        self.assertFalse(by_store["Target"]["same_size"])
        self.assertEqual(result["cheapest"]["store"], "Walmart")
        self.assertIn("(different size)", compare_mod.render_markdown(result))

    def test_same_size_listing_wins_within_a_store(self) -> None:
        result = self._compare([
            item("Tide PODS Original, 42 Count", "Walmart", 12.49, 1),
            item("Tide PODS Original 81 Count", "Walmart", 21.97, 2),
        ])
        self.assertEqual(next(r for r in result["stores"] if r["store"] == "Walmart")["price"], 21.97)

    def test_store_icons_prefer_google_source_icon_and_fall_back_to_favicon(self) -> None:
        listing = item("Tide PODS 81 Count", "Walmart", 21.97, 1)
        listing["source_icon"] = "https://encrypted-tbn2.gstatic.com/favicon-tbn?q=tbn:abc"
        other = item("Tide PODS 81 Count", "Target", 22.99, 2)
        other["source_icon"] = "https://evil.example/pixel.png"
        result = self._compare([listing, other])
        icons = {r["store"]: r["icon"] for r in result["stores"]}
        self.assertTrue(icons["Walmart"].startswith("https://encrypted-tbn2.gstatic.com/"))
        self.assertEqual(icons["Target"], "https://www.google.com/s2/favicons?domain=target.com&sz=64")
        self.assertTrue(icons["Costco"].endswith("domain=costco.com&sz=64"), "unpriced stores keep their logo")
        md = compare_mod.render_markdown(result)
        self.assertIn("| ![](https://www.google.com/s2/favicons?domain=target.com&sz=64) Target |", md)
        cards = json.loads(md.split("<!--luna-cards:")[1].rsplit("-->", 1)[0])
        self.assertTrue(all(c["icon"] for c in cards))


@unittest.skipUnless(__import__("shutil").which("node"), "node is required")
class MarkdownIconTests(unittest.TestCase):
    def test_only_google_favicon_hosts_render_as_icons(self) -> None:
        import subprocess
        from pathlib import Path
        md = Path(_bootstrap.ROOT) / "interfaces" / "desktop" / "src" / "renderer" / "markdown.js"
        source = ("![](https://www.google.com/s2/favicons?domain=walmart.com&sz=64) Walmart "
                  "![x](https://evil.example/p.png) ![](https://encrypted-tbn1.gstatic.com/i?q=1)")
        script = ("const fs=require('fs');const vm=require('vm');const w={};"
                  "vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),{window:w});"
                  "process.stdout.write(w.renderMarkdown(process.argv[2]))")
        html = subprocess.run(["node", "-e", script, str(md), source], capture_output=True, text=True, timeout=30, check=True).stdout
        self.assertEqual(html.count('class="md-icon"'), 2)
        self.assertIn('src="https://www.google.com/s2/favicons?domain=walmart.com&amp;sz=64"', html)
        self.assertNotIn("evil.example", html)
