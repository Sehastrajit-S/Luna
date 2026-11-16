"""News: category feeds, the chat answer (cards + category buttons) and the News tab API."""
from __future__ import annotations

import asyncio
import json
import unittest
from datetime import datetime, timezone
from unittest import mock

from tests.tools import _bootstrap  # noqa: F401

from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.services import news_feed
from server.services.news_feed import Story, news_category_request

RSS = b"""<?xml version="1.0"?>
<rss xmlns:media="http://search.yahoo.com/mrss/"><channel>
<item><title>Rocket lands on the Moon after record flight</title><link>https://www.bbc.co.uk/news/a1</link>
<description>The &lt;b&gt;probe&lt;/b&gt; touched down near the south pole.</description>
<pubDate>Sun, 15 Nov 2026 21:30:00 GMT</pubDate>
<media:thumbnail width="240" height="135" url="https://ichef.bbci.co.uk/ace/standard/240/cpsprodpb/abc.jpg"/></item>
<item><title>Markets rally as inflation cools across Europe</title><link>https://www.theguardian.com/b2</link>
<pubDate>Sun, 15 Nov 2026 20:00:00 GMT</pubDate>
<media:content width="140" url="https://i.guim.co.uk/small.jpg"/><media:content width="460" url="https://i.guim.co.uk/large.jpg"/></item>
<item><title>Short</title><link>https://x/c</link></item>
</channel></rss>"""

NOW = datetime(2026, 11, 15, 23, 30, tzinfo=timezone.utc)


def run(coro):
    return asyncio.run(coro)


def story(n, source="BBC", image=True, hours=1):
    return Story(title=f"Headline number {n} about events", link=f"https://example.com/{n}", source=source,
                 image=f"https://ichef.bbci.co.uk/{n}.jpg" if image else "", summary="",
                 published=datetime(2026, 11, 15, 23 - hours, 0, tzinfo=timezone.utc).isoformat())


class RequestTests(unittest.TestCase):
    def test_categories_and_general_requests(self) -> None:
        cases = {
            "Whats the news update today": "top",
            "what's the news?": "top",
            "news": "top",
            "latest headlines": "top",
            "tech news": "tech",
            "any sports headlines today?": "sports",
            "World news update": "world",
            "give me business news": "business",
            "news on the economy": "business",
            "entertainment news": "entertainment",
            "US news": "us",
            "Top news": "top",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(news_category_request(text), expected)

    def test_topics_and_other_requests_are_left_alone(self) -> None:
        for text in ("news about Tesla", "what's the latest on the Fed rate decision", "plan a trip to Kyoto",
                     "summarize this news article for me please", "is there any good news in my inbox"):
            with self.subTest(text=text):
                self.assertIsNone(news_category_request(text))


class FeedTests(unittest.TestCase):
    def test_parse_feed_picks_images_dates_and_clean_text(self) -> None:
        stories = news_feed.parse_feed("BBC", RSS)
        self.assertEqual(len(stories), 2, "titles under 12 characters are dropped")
        first, second = stories
        self.assertEqual(first.image, "https://ichef.bbci.co.uk/ace/standard/480/cpsprodpb/abc.jpg", "BBC thumbs upgraded")
        self.assertEqual(second.image, "https://i.guim.co.uk/large.jpg", "widest image wins")
        self.assertEqual(first.summary, "The probe touched down near the south pole.")
        self.assertEqual(first.published, "2026-11-15T21:30:00+00:00")

    def test_mix_interleaves_sources_and_drops_duplicates(self) -> None:
        bbc = [story(i, "BBC", hours=1) for i in range(5)]
        guardian = [story(10 + i, "The Guardian", hours=3) for i in range(3)]
        dupe = Story(**{**bbc[0].__dict__, "source": "NPR"})
        mixed = news_feed._mix([bbc, guardian, [dupe]], 20)
        sources = [s.source for s in mixed]
        self.assertTrue(all(not (a == b == c) for a, b, c in zip(sources, sources[1:], sources[2:])), sources)
        self.assertEqual(len({s.title for s in mixed}), len(mixed))

    def test_ago(self) -> None:
        self.assertEqual(news_feed.ago("2026-11-15T23:10:00+00:00", NOW), "20m ago")
        self.assertEqual(news_feed.ago("2026-11-15T20:30:00+00:00", NOW), "3h ago")
        self.assertEqual(news_feed.ago("", NOW), "")


class AnswerTests(unittest.TestCase):
    def test_answer_has_cards_more_headlines_and_other_categories(self) -> None:
        stories = [story(i, image=i < 7) for i in range(10)]
        text = news_feed.render_answer("tech", stories, now=NOW)
        cards = json.loads(text.split("<!--luna-cards:")[1].split("-->")[0])
        suggest = json.loads(text.split("<!--luna-suggest:")[1].split("-->")[0])
        self.assertEqual(len(cards), 6)
        self.assertTrue(all(c["image"] and c["url"].startswith("https://") for c in cards))
        self.assertIn("1h ago", cards[0]["site"])
        self.assertIn("More headlines:", text)
        self.assertIn("[Headline number 6 about events](https://example.com/6)", text)
        self.assertNotIn("Tech", [s["label"] for s in suggest], "the current category isn't offered again")
        self.assertIn({"label": "Sports", "message": "Sports news"}, suggest)

    def test_unreachable_feeds_still_offer_categories(self) -> None:
        text = news_feed.render_answer("top", [], now=NOW)
        self.assertIn("couldn't reach", text)
        self.assertIn("<!--luna-suggest:", text)

    def test_plain_text_surfaces_drop_cards_and_buttons(self) -> None:
        from server.services.response_formatter import strip_cards
        text = news_feed.render_answer("top", [story(1)], now=NOW)
        plain = strip_cards(text)
        self.assertNotIn("<!--", plain)
        self.assertIn("Top stories", plain)


class RoutingTests(unittest.TestCase):
    def test_dispatch_answers_news_from_the_feeds(self) -> None:
        from server.services.chat_pipeline import stage_dispatch
        from server.services.chat_pipeline.context import ChatContext
        ctx = ChatContext(db=None, user_message="Whats the news update today")
        ctx.conv = mock.Mock(id=1)
        ctx.history = []
        with mock.patch.object(news_feed, "get_category", mock.AsyncMock(return_value=[story(1)])) as get:
            run(stage_dispatch.dispatch_direct_commands(ctx))
        get.assert_awaited_once_with("top", limit=12)
        self.assertEqual(ctx.direct_command_type, "news:top")
        self.assertIn("<!--luna-cards:", ctx.full_response)

    def test_news_api(self) -> None:
        from server.routers.news import router
        app = FastAPI()
        app.include_router(router)
        with mock.patch.object(news_feed, "get_category", mock.AsyncMock(return_value=[story(1)])) as get:
            data = TestClient(app).get("/api/news", params={"category": "nonsense"}).json()
        self.assertEqual(get.await_args.args[0], "top", "unknown categories fall back to top")
        self.assertEqual(data["category"], "top")
        self.assertEqual(len(data["categories"]), len(news_feed.CATEGORIES))
        self.assertEqual(data["stories"][0]["source"], "BBC")
        self.assertIn("ago", data["stories"][0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
