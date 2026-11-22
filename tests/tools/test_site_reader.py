"""Reading a site in the user's browser: LinkedIn post cards from OCR, exact age
filtering ("posted within 20 minutes"), scrolling, "Load more", and when to stop."""
from __future__ import annotations

import asyncio
import json
import unittest
from unittest import mock

from tests.tools import _bootstrap  # noqa: F401

from server.services import site_reader as R
from server.services.files.ocr import OcrBox


def row(y, *texts):
    boxes, x = [], 24
    for t in texts:
        boxes.append(OcrBox(t, x, y, x + 9 * len(t), y + 18, 0.95))
        x += 9 * len(t) + 30
    return boxes


def post_rows(y, author, headline, age, text, actions=True):
    rows = row(y, author + " • 3rd+", "+ Follow") + row(y + 22, headline) + row(y + 42, age + " •") + row(y + 74, text)
    if actions:
        rows += row(y + 150, "Like", "Comment", "Repost", "Send")
    return rows


FILTERS = row(187, "Posts", "Latest", "Past 24 hours", "Content type", "All filters", "Reset")


class ParseTests(unittest.TestCase):
    def test_cards_ages_and_widgets(self):
        boxes = (FILTERS
                 + post_rows(270, "Nur Shamil", "Operation Engineer at Easygo", "now", "A New Chapter… more")
                 + post_rows(520, "Tiara Soto in", "Student @ Baruch College", "15m", "Posting all of my wins", actions=False)
                 + row(900, "Are these results helpful?") + row(925, "Your feedback helps us improve search results"))
        posts = R.parse_linkedin_posts(boxes, 974)
        self.assertEqual([(p.author, p.age, p.minutes_ago) for p in posts],
                         [("Nur Shamil", "now", 0), ("Tiara Soto", "15m", 15)])
        self.assertEqual(posts[0].headline, "Operation Engineer at Easygo")
        self.assertEqual(posts[0].text, "A New Chapter")
        self.assertEqual(posts[1].text, "Posting all of my wins", "image posts have no action row on screen")

    def test_ages(self):
        for text, minutes in (("now •", 0), ("3m •", 3), ("15m", 15), ("2h • Edited", 120), ("1d", 1440),
                              ("3w", 30240), ("2mo", 86400), ("Job Title", None)):
            self.assertEqual(R.age_minutes(text), minutes, text)

    def test_plan(self):
        plan = R.plan_read({"site": "LinkedIn", "query": "internship", "limit": 10, "max_age_minutes": 20})
        self.assertTrue(plan["read"]["linkedin_posts"])
        self.assertIn("keywords=internship", plan["read"]["url"])
        self.assertIn("sortBy=%22date_posted%22", plan["read"]["url"])
        self.assertIn("datePosted=%22past-24h%22", plan["read"]["url"])
        yt = R.plan_read({"site": "youtube", "query": "lofi"})
        self.assertEqual(yt["read"]["url"], "https://www.youtube.com/results?search_query=lofi")
        self.assertFalse(yt["read"]["linkedin_posts"])
        self.assertIn("error", R.plan_read({"site": "somewhere unknown"}))


class RequestTests(unittest.TestCase):
    def test_reading_requests(self):
        cases = {
            "find 10 posts with internship posted within 20 mins on linkedin": ("linkedin", "internship", 10, 20),
            "find 10 posts with internship posted within 20 mins as follow to open linked in": ("linkedin", "internship", 10, 20),
            "show me the latest AI agent posts on LinkedIn from the last 2 hours": ("linkedin", "AI agent", 10, 120),
            "find data analyst jobs on linkedin posted today": ("linkedin", "data analyst", 10, 1440),
            "get 5 posts about react hiring on linkedin": ("linkedin", "react hiring", 5, None),
            "find 3 videos about lofi on youtube": ("youtube", "lofi", 3, None),
        }
        for message, (site, query, limit, age) in cases.items():
            with self.subTest(message=message):
                ask = R.parse_read_request(message)
                self.assertEqual((ask["site"], ask["query"], ask["limit"], ask["max_age_minutes"]), (site, query, limit, age))
        for message in ("search for open AI in it", "open linkedin", "open the LinkedIn page", "what is linkedin",
                        "find priya in my mail", "search OpenAI on youtube"):
            with self.subTest(message=message):
                self.assertIsNone(R.parse_read_request(message))

    def test_dispatch_reads_linkedin_instead_of_web_search(self):
        from server.services.chat_pipeline.context import ChatContext
        from server.services.chat_pipeline.stage_dispatch import dispatch_direct_commands
        fake = R.ReadResult(site="linkedin", url="u", screens=6, stopped_because="reached older posts",
                            posts=[R.Post("Hasnae Atif", "Member at Aperture", "2m", 2, "AI & IoT Research Intern | Remote")])
        ctx = ChatContext(db=mock.Mock(), user_message="find 10 posts with internship posted within 20 mins on linkedin")
        ctx.conv = mock.Mock(id=77)
        with mock.patch.object(R, "read_site", return_value=fake) as read, \
             mock.patch("server.services.chat_pipeline.stage_dispatch.run_web_search") as web_search:
            asyncio.run(dispatch_direct_commands(ctx))
        web_search.assert_not_called()
        self.assertEqual(read.call_args.kwargs["max_age_minutes"], 20)
        self.assertEqual(ctx.direct_command_type, "read_website")
        self.assertIn("Found 1 LinkedIn post about “internship” from the last 20 min — that's all", ctx.full_response)
        self.assertIn("**Hasnae Atif** — Member at Aperture · 2 min ago", ctx.full_response)


class FakeImage:
    def __init__(self, n):
        self.n, self.size = n, (974, 1039)


class FakeKeys:
    def __init__(self):
        self.log = []

    def foreground(self):
        return 1

    def focus_window(self, hwnd, timeout=2.0):
        return True

    def scroll(self, hwnd, notches):
        self.log.append(("scroll", notches))

    def click(self, hwnd, x, y):
        self.log.append(("click", x, y))


class LoopTests(unittest.TestCase):
    def run_read(self, screens, *, limit=10, max_age=20, same_after=None):
        """screens: list of OCR box lists, one per capture. same_after: index from which the page stops moving."""
        keys, captures = FakeKeys(), {"n": 0}

        def capture():
            n = captures["n"]
            captures["n"] += 1
            return FakeImage(n)

        position = {"screen": 0}

        def ocr(image):
            boxes = screens[min(position["screen"], len(screens) - 1)]
            position["screen"] += 1
            return boxes

        with mock.patch.object(R, "_same_picture", side_effect=lambda a, b: same_after is not None and position["screen"] > same_after), \
             mock.patch("server.services.verification.save_screenshot", return_value="shot.png"):
            result = R.read_site("https://linkedin", "linkedin", title_hint="linkedin", linkedin_posts=True,
                                 limit=limit, max_age_minutes=max_age, scrolls=8, sleep=lambda s: None,
                                 opener=lambda req: {"error": ""}, find_window=lambda: {"hwnd": 7},
                                 capture=capture, keys=keys, ocr=ocr)
        return result, keys

    def test_stops_when_posts_get_older_than_asked(self):
        screens = [FILTERS + post_rows(270, "A One", "h1", "2m", "intern 1") + post_rows(520, "B Two", "h2", "9m", "intern 2"),
                   post_rows(270, "C Three", "h3", "18m", "intern 3") + post_rows(520, "D Four", "h4", "31m", "intern 4")]
        result, keys = self.run_read(screens)
        self.assertEqual([p.author for p in result.posts], ["A One", "B Two", "C Three"])
        self.assertIn("older than 20 minutes", result.stopped_because)
        self.assertEqual(keys.log, [("scroll", 5)], "no clicks; stopped after the second screen")

    def test_stops_at_the_limit(self):
        screens = [FILTERS + post_rows(270, "A One", "h1", "1m", "x") + post_rows(520, "B Two", "h2", "2m", "y")]
        result, _ = self.run_read(screens, limit=2)
        self.assertEqual(len(result.posts), 2)
        self.assertEqual(result.stopped_because, "found 2 posts")

    def test_load_more_is_the_only_click_and_a_stuck_page_stops(self):
        end = post_rows(270, "A One", "h1", "1m", "x") + row(860, "Load more")
        result, keys = self.run_read([FILTERS + end, end, end], same_after=0)
        clicks = [e for e in keys.log if e[0] == "click"]
        self.assertEqual(len(clicks), 1)
        self.assertEqual(result.loaded_more, 1)
        self.assertIn("stopped scrolling", result.stopped_because)

    def test_same_post_on_two_screens_counts_once_with_more_text(self):
        screens = [FILTERS + post_rows(700, "Emmanuel G", "Founder", "5m", "", actions=False),
                   post_rows(270, "Emmanuel G", "Founder at X", "5m", "Progress can be pain staking")]
        result, _ = self.run_read(screens, max_age=None, limit=5)
        self.assertEqual(len(result.posts), 1)
        self.assertEqual(result.posts[0].text, "Progress can be pain staking")


class ToolTests(unittest.TestCase):
    def test_tool_returns_posts_with_ages(self):
        from server.services.tool_runner.executor import execute_tool_call
        fake = R.ReadResult(site="linkedin", url="u", posts=[R.Post("A One", "h", "3m", 3, "Intern role")],
                            screens=4, stopped_because="found 1 posts")
        with mock.patch.object(R, "read_site", return_value=fake) as read, \
             mock.patch("server.services.audit_log.record_audit"):
            out = asyncio.run(execute_tool_call({"tool": "read_website", "args": {
                "site": "linkedin", "query": "internship", "limit": 10, "max_age_minutes": 20}}, None, 1))
        data = json.loads(out)
        self.assertEqual(data["posts"][0]["minutes_ago"], 3)
        self.assertIn("at most 20 minutes old", data["note"])
        self.assertTrue(read.call_args.kwargs["linkedin_posts"])


if __name__ == "__main__":
    unittest.main()
