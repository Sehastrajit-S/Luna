import asyncio
import unittest
from unittest import mock


class SearchIntentTests(unittest.TestCase):
    def test_requests_that_need_live_results_trigger_search(self) -> None:
        from server.services.command_parser.research import is_search_request

        for message in (
            "can you search and find me some job postings that is good for my experience",
            "give me links for these",
            "links to those please",
            "find me ML engineer openings in Phoenix",
            "where can I apply for this",
            "search for vLLM benchmarks",
            "web search qwen3 release notes",
        ):
            with self.subTest(message=message):
                self.assertTrue(is_search_request(message))

    def test_own_data_and_documents_are_not_web_searches(self) -> None:
        from server.services.command_parser.research import is_search_request

        for message in (
            "search my inbox for invoices",
            "find the positions in this spreadsheet",
            "search the pdf for python",
            "what roles am i good for",
            "rate my resume",
            "/research job markets",
        ):
            with self.subTest(message=message):
                self.assertFalse(is_search_request(message))


class MultiQueryTests(unittest.TestCase):
    HISTORY = [
        {"role": "user", "content": "find me job postings"},
        {"role": "assistant", "content": "1. **Machine Learning Engineer at AWS**\n2. **AI Systems Engineer at Google Cloud**"},
    ]

    def test_links_for_these_becomes_one_query_per_item(self) -> None:
        from server.services import search_query

        async def fake_complete(prompt, system="", temperature=0.3):
            self.assertIn("Machine Learning Engineer at AWS", prompt)
            return "1. Machine Learning Engineer AWS job posting\n2. AI Systems Engineer Google Cloud careers\n"

        with mock.patch("server.services.llm.ollama.complete", side_effect=fake_complete):
            queries = asyncio.run(search_query.resolve_search_queries("give me links for these", self.HISTORY))
        self.assertEqual(queries, ["Machine Learning Engineer AWS job posting", "AI Systems Engineer Google Cloud careers"])

    def test_single_item_requests_stay_single(self) -> None:
        from server.services import search_query

        with mock.patch("server.services.llm.ollama.complete") as complete:
            queries = asyncio.run(search_query.resolve_search_queries("latest qwen3 release notes for tool calling", self.HISTORY))
        self.assertEqual(queries, ["latest qwen3 release notes for tool calling"])
        complete.assert_not_called()

    def test_merged_results_are_numbered_continuously(self) -> None:
        from server.services import web_tools

        async def fake_search(query, max_results=6):
            return (f"[1] {query} A\nSnippet: first\nURL: https://a.example/{len(query)}\n\n"
                    f"[2] {query} B\nSnippet: second\nURL: https://b.example/{len(query)}\n\nReferences:\n...")

        with mock.patch.object(web_tools, "web_search", side_effect=fake_search):
            merged = asyncio.run(web_tools.multi_web_search(["aws ml", "google ai eng"], check_links=False))
        self.assertIn("Results for: aws ml", merged)
        self.assertIn("[3] google ai eng A", merged)
        self.assertIn("[4] google ai eng B - https://b.example/13", merged)


class CitationLinkTests(unittest.TestCase):
    def test_bracket_citations_become_links(self) -> None:
        from server.services.response_formatter import link_citations

        result = "References:\n[1] Job A - https://boards.greenhouse.io/a/jobs/1\n[2] Job B - https://jobs.lever.co/b/2"
        out = link_citations("- **[1]** Job A. See [2] and [9].\n\nReferences:\n[1] Job A - x", result)
        self.assertIn("[1](https://boards.greenhouse.io/a/jobs/1)", out)
        self.assertIn("[2](https://jobs.lever.co/b/2)", out)
        self.assertIn("[9].", out)                            # unknown numbers untouched
        self.assertTrue(out.endswith("References:\n[1] Job A - x"))


class ResultLinkTests(unittest.TestCase):
    RESULT = (
        "[1] Job Application for Machine Learning Engineer at DoorDash\nSnippet: Build ETA models.\n"
        "URL: https://boards.greenhouse.io/doordashusa/jobs/5908507\n\n"
        "[2] Affirm - Machine Learning Engineer II (Underwriting ML)\nSnippet: Real-time decisions.\n"
        "URL: https://jobs.lever.co/affirm/abc\n\nReferences:\n..."
    )

    def test_labels_without_urls_get_the_matching_result_link(self) -> None:
        from server.services.response_formatter import attach_result_links

        answer = ("- **[Machine Learning Engineer — DoorDash]** — 8/10\n"
                  "- **[Machine Learning Engineer II (Underwriting ML) at Affirm]** — 9/10\n"
                  "- **[Quantum Chef at Nowhere Inc]** — 5/10")
        out = attach_result_links(answer, self.RESULT)
        self.assertIn("[Machine Learning Engineer — DoorDash](https://boards.greenhouse.io/doordashusa/jobs/5908507)", out)
        self.assertIn("(https://jobs.lever.co/affirm/abc)", out)
        self.assertIn("**Quantum Chef at Nowhere Inc**", out)   # no match → plain text, no fake link

    def test_bold_titles_and_placeholders_get_their_result_link(self) -> None:
        from server.services.response_formatter import attach_result_links

        result = ("[1] RankRAG: Unifying Context Ranking with Retrieval-Augmented Generation\nSnippet: s\n"
                  "URL: https://arxiv.org/abs/2407.02485\n\n"
                  "[2] Unified Active Retrieval for RAG\nSnippet: s\nURL: https://arxiv.org/abs/2406.12534\n")
        answer = ("## RAG Frameworks\n"
                  "- **RankRAG: Unifying Context Ranking with Retrieval-Augmented Generation**\n"
                  "  [Paper] — Sep 2024\n"
                  "- **Some Paper That Was Not In The Results**\n  [Paper] — 2024")
        out = attach_result_links(answer, result)
        self.assertIn("**[RankRAG: Unifying Context Ranking with Retrieval-Augmented Generation](https://arxiv.org/abs/2407.02485)**", out)
        self.assertIn("[Paper](https://arxiv.org/abs/2407.02485)", out)
        self.assertIn("**Some Paper That Was Not In The Results**", out)   # unmatched: no link invented
        self.assertIn("## RAG Frameworks\n", out)                        # headings untouched

    def test_existing_links_are_left_alone(self) -> None:
        from server.services.response_formatter import attach_result_links

        answer = "[Machine Learning Engineer — DoorDash](https://example.com/x)"
        self.assertEqual(attach_result_links(answer, self.RESULT), answer)


class DedupeTests(unittest.TestCase):
    def test_same_posting_listed_twice_is_collapsed(self) -> None:
        from server.services.response_formatter import dedupe_linked_items

        answer = (
            "### AI roles\n"
            "- **[Sr. AI Systems Engineer @ AiFi](https://jobs.x/aifi/1)** – spatial AI\n  Rating: 9/10\n"
            "- **[Sr. AI Engineer at AiFi](https://jobs.x/aifi/1?src=li)** – same job, reworded\n  Rating: 8/10\n"
            "- **[Product Data Scientist](https://jobs.x/bestegg/2)** – analytics\n"
            "\nReferences:\n[1] a - https://jobs.x/aifi/1"
        )
        out = dedupe_linked_items(answer)
        self.assertEqual(out.count("jobs.x/aifi/1"), 2)          # first item + References only
        self.assertNotIn("same job, reworded", out)
        self.assertIn("Rating: 9/10", out)
        self.assertIn("Product Data Scientist", out)
        self.assertIn("### AI roles", out)


class DedupeByTitleTests(unittest.TestCase):
    def test_same_bold_title_listed_twice_is_collapsed(self) -> None:
        from server.services.response_formatter import dedupe_linked_items

        answer = ("- **Anker Soundcore Space Q45 Wireless** — budget pick\n"
                  "- **Sony WH-1000XM6** — premium\n"
                  "- **Anker Soundcore Space Q45 Wireless** — said again")
        out = dedupe_linked_items(answer)
        self.assertEqual(out.count("Anker Soundcore Space Q45"), 1)
        self.assertIn("Sony WH-1000XM6", out)
        self.assertNotIn("said again", out)


class UnverifiedLinkTests(unittest.TestCase):
    def test_invented_links_are_removed_and_disclosed(self) -> None:
        from server.services.chat_pipeline.stage_tools import strip_unverified_links

        reply = ("1. **ML Engineer at AWS** — [Job Posting Link](https://aws.amazon.com/careers/jobsearch-listing/254697/)\n"
                 "2. **Docs** — see https://learn.microsoft.com/en-us/azure/devops/?view=azurermps-2.0\n"
                 "3. Python lives at https://www.python.org/")
        out = strip_unverified_links(reply, known="nothing relevant")
        self.assertNotIn("254697", out)
        self.assertNotIn("learn.microsoft.com", out)
        self.assertIn("(link removed)", out)
        self.assertIn("https://www.python.org/", out)          # bare homepage kept
        self.assertIn("I removed 2 links I couldn't verify", out)

    def test_links_from_results_or_documents_are_kept(self) -> None:
        from server.services.chat_pipeline.stage_tools import strip_unverified_links

        known = "URL: https://jobs.example.com/view/123?src=ddg\n"
        reply = "Apply here: [ML Engineer](https://jobs.example.com/view/123?src=ddg)."
        self.assertEqual(strip_unverified_links(reply, known), reply)

    def test_text_without_links_is_untouched(self) -> None:
        from server.services.chat_pipeline.stage_tools import strip_unverified_links

        self.assertEqual(strip_unverified_links("No links here.", ""), "No links here.")


if __name__ == "__main__":
    unittest.main(verbosity=2)
