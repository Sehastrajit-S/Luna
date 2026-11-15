"""The skill runtime is generic; use cases live in server/skills/*. These tests cover
both halves: the engine (with made-up skills) and the shipped skill folders."""
import asyncio
import re
import unittest
from types import SimpleNamespace
from unittest import mock


def _skill(**overrides):
    from server.services.skill_runtime.registry import SearchSkill
    base = dict(id="thing-search", name="Thing Search", description="Find things.",
                slots={"things": "things to find", "place": "where"}, fan_out="things", grounded=["place"],
                queries=["{item} {place} site:things.example"], max_items=2)
    base.update(overrides)
    return SearchSkill(**base)


class ShippedSkillsTests(unittest.TestCase):
    """Every skill folder must be valid data the engine can run."""

    def test_all_skills_load_and_are_well_formed(self) -> None:
        from server.services.skill_runtime import load_search_skills

        skills = {s.id: s for s in load_search_skills()}
        for expected in ("job-search", "paper-search", "product-search", "local-search", "news-search", "docs-search"):
            self.assertIn(expected, skills)
        for skill in skills.values():
            with self.subTest(skill=skill.id):
                self.assertTrue(skill.description and skill.guidelines and skill.intents and skill.queries)
                for template in skill.queries:
                    placeholders = set(re.findall(r"\{(\w+)\}", template)) - {"item"}
                    self.assertTrue(placeholders <= set(skill.slots), f"{template} uses undeclared slots")
                for pattern in skill.keep_urls + skill.drop_urls + [r["match"] for r in skill.status_apis + skill.labels]:
                    re.compile(pattern)
                if skill.requires.get("any"):
                    self.assertTrue(skill.ask, "a skill that can refuse must say what it needs")

    def test_routing_picks_the_right_skill_and_leaves_chat_alone(self) -> None:
        from server.services.command_parser.research import is_search_request, refers_to_own_content
        from server.services.skill_runtime import pick_search_skill

        def route(text):
            explicit = is_search_request(text)
            skill = pick_search_skill(text, strong_only=not explicit) if (explicit or not refers_to_own_content(text)) else None
            return skill.id if skill else ("web" if explicit else "model")

        cases = {
            "find me some job postings that fit my resume": "job-search",
            "any ML engineer openings in Phoenix?": "job-search",
            "find me papers on retrieval augmented generation from 2024": "paper-search",
            "what's the state of the art in speech recognition": "paper-search",
            "best noise cancelling headphones under $200": "product-search",
            "ramen restaurants near me": "local-search",
            "latest news on Nvidia": "news-search",
            "search for ModuleNotFoundError: No module named 'pypdf'": "docs-search",
            "find me a good recipe for lasagna": "web",
            "summarize this paper": "model",
            "search the pdf for python": "model",
            "how are you": "model",
            "explain transformers to me": "model",
            "price of bitcoin": "model",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(route(text), expected)


class SlotTests(unittest.TestCase):
    def test_grounded_slots_must_be_typed_by_the_user(self) -> None:
        from server.services.skill_runtime import runner

        async def fake(prompt, system="", temperature=0.0):
            return '{"things": ["red widgets", "notes.pdf"], "place": "Arizona State University"}'

        with mock.patch("server.services.llm.ollama.complete", side_effect=fake):
            slots = asyncio.run(runner.extract_slots(_skill(), "find me red widgets", [], documents="ASU"))
        self.assertEqual(slots["things"], ["red widgets"])        # file names dropped
        self.assertEqual(slots["place"], "")                      # never typed → dropped

    def test_items_echoing_the_slot_description_are_dropped(self) -> None:
        from server.services.skill_runtime import runner

        async def fake(prompt, system="", temperature=0.0):
            return '{"things": ["company"], "place": ""}'      # model echoed the description

        with mock.patch("server.services.llm.ollama.complete", side_effect=fake):
            slots = asyncio.run(runner.extract_slots(_skill(), "latest news on Nvidia", [], ""))
        self.assertEqual(slots["things"], [])
        queries = runner.build_queries(_skill(queries=["{item}"]), "latest news on Nvidia", slots)
        self.assertEqual(queries, ["latest news on Nvidia"])           # falls back to the user's words

    def test_model_picks_a_skill_when_no_pattern_matches(self) -> None:
        from server.services.skill_runtime import registry

        async def fake(prompt, system="", temperature=0.0):
            self.assertIn("local-search:", prompt)                      # skills offered by description
            return "local-search"

        with mock.patch("server.services.llm.ollama.complete", side_effect=fake):
            skill = asyncio.run(registry.choose_skill_with_model("find me good ramen"))
        self.assertEqual(skill.id, "local-search")
        with mock.patch("server.services.llm.ollama.complete", new=mock.AsyncMock(return_value="none")):
            self.assertIsNone(asyncio.run(registry.choose_skill_with_model("find me a lasagna recipe")))

    def test_near_me_uses_the_home_city(self) -> None:
        from server.services.skill_runtime import runner

        async def fake(prompt, system="", temperature=0.0):
            return '{"things": ["tacos"], "location": ""}'

        skill = _skill(slots={"things": "x", "location": "y"}, grounded=["location"])
        with mock.patch("server.services.llm.ollama.complete", side_effect=fake), \
             mock.patch.object(runner.settings, "weather_city", "Tempe"):
            slots = asyncio.run(runner.extract_slots(skill, "tacos near me", [], ""))
        self.assertEqual(slots["location"], "Tempe")

    def test_queries_fan_out_per_item_and_drop_empty_slots(self) -> None:
        from server.services.skill_runtime.runner import build_queries

        skill = _skill(queries=['"{item}" {place} site:a.example', "{item} review"])
        queries = build_queries(skill, "req", {"things": ["alpha", "beta", "gamma"], "place": ""})
        self.assertEqual(queries, ['"alpha" site:a.example', "alpha review", '"beta" site:a.example', "beta review"])

    def test_missing_requirements_ask_instead_of_searching(self) -> None:
        from server.services.skill_runtime import runner

        skill = _skill(requires={"any": ["slot:place", "documents"], "ask": "Where should I look?"})
        with mock.patch.object(runner, "extract_slots", new=mock.AsyncMock(return_value={"things": ["x"], "place": ""})), \
             mock.patch.object(runner.sources, "run_searches") as search:
            run = asyncio.run(runner.run_search_skill(skill, "find x", []))
        self.assertTrue(run.asked)
        self.assertEqual(run.answer, "Where should I look?")
        search.assert_not_called()


class LinkCheckTests(unittest.TestCase):
    def test_generic_and_skill_supplied_liveness_checks(self) -> None:
        import httpx
        from server.services.skill_runtime import sources

        calls = {}

        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            calls[url] = calls.get(url, 0) + 1
            routes = {
                "https://api.example/boards/acme/items/111": httpx.Response(404),                 # status API: gone
                "https://api.example/boards/acme/items/222": httpx.Response(200, json={}),        # status API: open
                "https://api.example/lists/beta": httpx.Response(200, json={"items": [{"id": "open-1"}]}),
                "https://site.example/old/12345": httpx.Response(302, headers={"location": "https://site.example/"}),
                "https://site.example/": httpx.Response(200, text="home"),
                "https://site.example/closed": httpx.Response(200, headers={"content-type": "text/html"},
                                                              text="<p>Sorry, this listing has ended.</p>"),
                "https://blocked.example/x": httpx.Response(403),
            }
            if url == "https://flaky.example/y" and calls[url] == 1:
                return httpx.Response(429)
            if url == "https://slow.example/z":
                raise httpx.ReadTimeout("slow")
            return routes.get(url, httpx.Response(200, text="ok"))

        urls = ["https://things.example/acme/111", "https://things.example/acme/222", "https://list.example/beta/open-1",
                "https://list.example/beta/gone-2", "https://site.example/old/12345", "https://site.example/closed",
                "https://blocked.example/x", "https://flaky.example/y", "https://slow.example/z"]
        results = [sources.Result("q", f"t{i}", "s", u) for i, u in enumerate(urls)]
        apis = [
            {"match": r"things\.example/(\w+)/(\d+)", "url": "https://api.example/boards/{1}/items/{2}"},
            {"match": r"list\.example/(\w+)/([\w-]+)", "list_url": "https://api.example/lists/{1}", "ids": "items.id"},
        ]
        real_client = httpx.AsyncClient
        with mock.patch("httpx.AsyncClient", lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw)):
            kept, removed = asyncio.run(sources.drop_dead(results, ["listing has ended"], apis))
        kept_urls = [r.url for r in kept]
        self.assertEqual(removed, 4)
        self.assertEqual(kept_urls, ["https://things.example/acme/222", "https://list.example/beta/open-1",
                                     "https://blocked.example/x", "https://flaky.example/y", "https://slow.example/z"])
        self.assertEqual(calls["https://flaky.example/y"], 2)                 # 429 retried once
        self.assertEqual(calls["https://api.example/lists/beta"], 1)          # list fetched once, shared

    def test_rewrites_filters_and_labels_come_from_the_skill(self) -> None:
        from server.services.skill_runtime import sources

        results = [sources.Result("q", "A", "s", "https://x.example/org1/item/9/confirmation"),
                   sources.Result("q", "B", "s", "https://x.example/search?q=a"),
                   sources.Result("q", "C", "s", "https://other.example/page")]
        results = sources.rewrite_urls(results, [{"match": r"(/item/\d+)/confirmation", "replace": r"\1"}])
        results = sources.filter_results(results, keep=[r"x\.example/\w+/item/\d+"], drop=[r"[?&]q="])
        results = sources.apply_labels(results, [{"match": r"x\.example/(\w+)/", "name": "Org"}])
        self.assertEqual([r.url for r in results], ["https://x.example/org1/item/9"])
        text = sources.format_results(results, ["q"])
        self.assertIn("Org (from link): org1", text)
        self.assertIn("[1] A - https://x.example/org1/item/9", text)


class RunnerEndToEndTests(unittest.TestCase):
    def test_skill_run_searches_filters_and_links_every_item(self) -> None:
        from server.services.skill_runtime import runner, sources

        skill = _skill(keep_urls=[r"things\.example/item/"], guidelines="List things with links.")
        fake_results = [sources.Result("red widgets site:things.example", "Red Widget Pro", "great", "https://things.example/item/1"),
                        sources.Result("red widgets site:things.example", "Widget search", "list", "https://things.example/search")]

        async def fake_verify(tool, args, result, user_message="", context="", guidelines=""):
            self.assertEqual(guidelines, "List things with links.")
            self.assertNotIn("things.example/search", result)                    # filtered before answering
            return "- **[Red Widget Pro]** — best pick\n- [made up](https://invented.example/deep/link)"

        with mock.patch.object(runner, "extract_slots", new=mock.AsyncMock(return_value={"things": ["red widgets"], "place": ""})), \
             mock.patch.object(runner.sources, "run_searches", new=mock.AsyncMock(return_value=fake_results)), \
             mock.patch("server.services.tool_runner.verify_tool_result", side_effect=fake_verify):
            run = asyncio.run(runner.run_search_skill(skill, "find me red widgets", []))
        self.assertIn("[Red Widget Pro](https://things.example/item/1)", run.answer)
        self.assertNotIn("invented.example", run.answer)
        self.assertEqual(run.skill_id, "thing-search")


class CardTests(unittest.TestCase):
    def test_page_meta_from_structured_data_open_graph_and_skill_patterns(self) -> None:
        from server.services.skill_runtime.sources import extract_page_meta

        ld = ('<script type="application/ld+json">{"@context":"https://schema.org","@type":"Product",'
              '"name":"Soundcore Space Q45","image":["https://img.example/q45.jpg"],'
              '"offers":{"@type":"Offer","price":"99.99","priceCurrency":"USD"}}</script>')
        meta = extract_page_meta(ld, "https://shop.example/p/1")
        self.assertEqual((meta["title"], meta["image"], meta["price"], meta["currency"]),
                         ("Soundcore Space Q45", "https://img.example/q45.jpg", "99.99", "USD"))

        og = '<meta property="og:title" content="Widget &amp; Co"><meta property="og:image" content="/img/w.png">'
        meta = extract_page_meta(og, "https://shop.example/p/2")
        self.assertEqual(meta["title"], "Widget & Co")
        self.assertEqual(meta["image"], "https://shop.example/img/w.png")        # made absolute

        custom = '<img id="landingImage" data-old-hires="https://m.media.example/big.jpg"><span class="a-offscreen">$1,249.00</span>'
        meta = extract_page_meta(custom, "https://store.example/dp/X",
                                 image_patterns=[r'id="landingImage"[^>]*?data-old-hires="(https[^"]+)"'],
                                 price_patterns=[r'class="a-offscreen">\s*\$([\d,]+\.\d{2})'])
        self.assertEqual((meta["image"], meta["price"]), ("https://m.media.example/big.jpg", "1,249.00"))

        self.assertIsNone(extract_page_meta('<meta property="og:image" content="http://insecure/x.jpg">', "https://a.b/")["image"])

    def test_cards_skip_pages_without_images_and_duplicates(self) -> None:
        import httpx
        from server.services.skill_runtime import sources

        pages = {
            "https://shop.example/p/1": '<meta property="og:title" content="Alpha Headphones"><meta property="og:image" content="https://i.example/a.jpg"><meta property="product:price:amount" content="79.5">',
            "https://shop.example/p/2": '<meta property="og:title" content="No Image Thing">',
            "https://other.example/p/9": '<meta property="og:title" content="Alpha Headphones"><meta property="og:image" content="https://i.example/a2.jpg">',
        }

        def handler(request):
            return httpx.Response(200, headers={"content-type": "text/html"}, text=pages.get(str(request.url), ""))

        results = [sources.Result("q", "t", "s", u) for u in pages]
        real_client = httpx.AsyncClient
        with mock.patch("httpx.AsyncClient", lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw)):
            cards = asyncio.run(sources.fetch_cards(results, limit=6))
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["title"], "Alpha Headphones")
        self.assertEqual((cards[0]["price"], cards[0]["currency"]), ("79.50", "USD"))

    def test_named_items_must_come_from_the_results(self) -> None:
        from server.services.skill_runtime import runner

        results_text = "[1] Best budget ANC\nSnippet: The Anker Soundcore Space Q45 and Sony WH-CH720N lead.\nURL: https://r.example/1"

        async def fake(prompt, system="", temperature=0.0):
            return "1. Anker Soundcore Space Q45\n2. Sony WH-CH720N\n3. Bose QuietComfort Ultra\n"   # #3 not in results

        with mock.patch("server.services.llm.ollama.complete", side_effect=fake):
            names = asyncio.run(runner.extract_item_names("best anc under $200", results_text, "products", 5))
        self.assertEqual(names, ["Anker Soundcore Space Q45", "Sony WH-CH720N"])

    def test_lookup_mode_cards_each_named_item_from_its_own_search(self) -> None:
        from server.services.skill_runtime import runner, sources

        spec = {"lookup": '"{name}" site:shop.example', "keep_urls": [r"shop\.example/p/"], "max": 5}
        found = [sources.Result('"Alpha" site:shop.example', "Alpha", "s", "https://shop.example/c/category"),
                 sources.Result('"Alpha" site:shop.example', "Alpha", "s", "https://shop.example/p/alpha"),
                 sources.Result('"Beta" site:shop.example', "Beta", "s", "https://shop.example/p/beta")]

        async def fake_cards(pages, limit, *_a, **_k):
            return [{"title": p.title, "url": p.url, "image": "https://i.example/x.jpg", "price": "", "currency": "", "site": "shop"}
                    for p in pages][:limit]

        with mock.patch.object(runner, "extract_item_names", new=mock.AsyncMock(return_value=["Alpha", "Beta"])), \
             mock.patch.object(runner.sources, "run_searches", new=mock.AsyncMock(return_value=found)), \
             mock.patch.object(runner.sources, "fetch_cards", side_effect=fake_cards):
            cards = asyncio.run(runner._build_cards(spec, "req", [], "results"))
        self.assertEqual([c["url"] for c in cards], ["https://shop.example/p/alpha", "https://shop.example/p/beta"])

    def test_store_branding_is_removed_from_titles(self) -> None:
        from server.services.skill_runtime.sources import extract_page_meta

        for raw, clean in (("Amazon.com: Soundcore Space Q45 Headphones", "Soundcore Space Q45 Headphones"),
                           ("Soundcore Space Q45 : Target", "Soundcore Space Q45"),
                           ("Soundcore Space Q45 - Walmart.com", "Soundcore Space Q45")):
            html = f'<meta property="og:title" content="{raw}">'
            self.assertEqual(extract_page_meta(html, "https://a.b/")["title"], clean)

    def test_cards_ride_along_in_the_reply_and_are_stripped_for_text_surfaces(self) -> None:
        from server.services.response_formatter import strip_cards
        from server.services.skill_runtime.runner import embed_cards

        cards = [{"title": "A -- B", "url": "https://x.example/p/1", "image": "https://i.example/1.jpg"}]
        reply = embed_cards("Here are options.", cards)
        self.assertIn("<!--luna-cards:", reply)
        self.assertNotIn("A -- B", reply)                                  # "--" can't end the comment early
        self.assertEqual(strip_cards(reply), "Here are options.")
        import json, re
        payload = re.search(r"<!--luna-cards:(.*?)-->", reply, re.DOTALL).group(1)
        self.assertEqual(json.loads(payload)[0]["title"], "A -- B")
        self.assertEqual(embed_cards("x", []), "x")


def _ctx(message, history=(), attachment_ids=()):
    return SimpleNamespace(
        user_message=message, history=list(history), attachment_ids=list(attachment_ids),
        messages=list(history) + [{"role": "user", "content": message}],
        dispatched=False, direct_command_type=None, had_tool_call=False, tool_succeeded=False,
        full_response="", full_response_parts=[], db=None, conv=SimpleNamespace(id=1), is_business=False, cli=True,
    )


class PendingRequestTests(unittest.TestCase):
    """Generic across use cases: "I'll send it later", clarifying answers, own-file questions."""

    def test_upload_later_waits_for_any_kind_of_file(self) -> None:
        from server.services.chat_pipeline import stage_dispatch as d

        for message, noun in (("great, ill upload my resume find me some jobs", "your resume"),
                              ("let me attach the contract, then summarize it", "your contract"),
                              ("I'll send it in a sec, tell me what's wrong", "it")):
            ctx = _ctx(message)
            with self.subTest(message=message), mock.patch.object(d, "run_search_skill") as run:
                asyncio.run(d.dispatch_direct_commands(ctx))
                self.assertTrue(ctx.full_response.startswith(d.WAIT_PREFIX))
                self.assertIn(noun, ctx.full_response)
                run.assert_not_called()

    def test_file_arrival_completes_the_pending_request(self) -> None:
        from server.services.chat_pipeline import stage_dispatch as d

        history = [{"role": "user", "content": "great, ill upload my resume find me some jobs"},
                   {"role": "assistant", "content": d.wait_for_upload_reply("my resume")}]
        ctx = _ctx("find me", history, attachment_ids=["a" * 32])
        fake_run = SimpleNamespace(answer="postings…", asked=False, skill_id="job-search", results_text="[1] x")
        with mock.patch.object(d, "_search_answer_context", new=mock.AsyncMock(return_value=("ctx", "<documents>cv</documents>"))), \
             mock.patch.object(d, "run_search_skill", new=mock.AsyncMock(return_value=fake_run)) as run:
            asyncio.run(d.dispatch_direct_commands(ctx))
        skill_arg, request_arg = run.await_args.args[0], run.await_args.args[1]
        self.assertEqual(skill_arg.id, "job-search")
        self.assertIn("find me some jobs", request_arg)
        self.assertEqual(run.await_args.kwargs["documents"], "<documents>cv</documents>")
        self.assertIn("find me some jobs", ctx.messages[-1]["content"])          # model sees the full request too

    def test_non_search_pending_request_reaches_the_model_complete(self) -> None:
        from server.services.chat_pipeline import stage_dispatch as d

        history = [{"role": "user", "content": "let me attach the contract, then tell me the notice period"},
                   {"role": "assistant", "content": d.wait_for_upload_reply("contract")}]
        ctx = _ctx("here", history, attachment_ids=["b" * 32])
        with mock.patch.object(d, "run_search_skill") as run, mock.patch.object(d, "run_web_search") as web:
            asyncio.run(d.dispatch_direct_commands(ctx))
        run.assert_not_called()
        web.assert_not_called()
        self.assertFalse(ctx.dispatched)                                           # the model answers, with the file
        self.assertIn("notice period", ctx.user_message)

    def test_a_new_instruction_is_not_merged(self) -> None:
        from server.services.chat_pipeline import stage_dispatch as d

        history = [{"role": "user", "content": "ill upload my resume, find me jobs"},
                   {"role": "assistant", "content": d.wait_for_upload_reply("resume")}]
        self.assertEqual(d._carried_request("rate my resume", history, has_files=True), "rate my resume")
        done = [{"role": "user", "content": "find me ML jobs"}, {"role": "assistant", "content": "Here are 4 postings."}]
        self.assertEqual(d._carried_request("ok", done, has_files=False), "ok")

    def test_skill_question_then_answer(self) -> None:
        from server.services.chat_pipeline import stage_dispatch as d
        from server.services.skill_runtime import get_search_skill

        ask = get_search_skill("local-search").ask
        history = [{"role": "user", "content": "find me good ramen"}, {"role": "assistant", "content": ask}]
        self.assertEqual(d._carried_request("in Tempe", history, has_files=False), "find me good ramen in Tempe")

    def test_questions_about_an_attached_file_never_hit_the_web(self) -> None:
        from server.services.chat_pipeline import stage_dispatch as d

        ctx = _ctx("what are the key findings of this paper", attachment_ids=["c" * 32])
        with mock.patch.object(d, "run_search_skill") as run, mock.patch.object(d, "run_web_search") as web:
            asyncio.run(d.dispatch_direct_commands(ctx))
        run.assert_not_called()
        web.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
