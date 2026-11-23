import unittest
from unittest import mock

import requests

import source_gatherer as sg


def resp(json_data=None, content=b""):
    r = mock.MagicMock()
    r.json.return_value = json_data
    r.content = content
    return r


class TestGatherer(unittest.TestCase):
    def test_wikipedia_search_then_summary(self):
        search = resp({"query": {"search": [{"title": "Foo Bar"}]}})
        summary = resp({"title": "Foo Bar", "extract": "x" * 50,
                        "content_urls": {"desktop": {"page": "https://w/Foo"}}})
        with mock.patch.object(sg.requests, "get", side_effect=[search, summary]) as g:
            out = sg.fetch_wikipedia_for_subtopic("foo")
        self.assertEqual(out["url"], "https://w/Foo")
        self.assertIn("api.php", g.call_args_list[0][0][0])
        self.assertIn("summary", g.call_args_list[1][0][0])

    def test_wikipedia_failure_returns_none(self):
        with mock.patch.object(sg.requests, "get", side_effect=requests.RequestException("boom")):
            self.assertIsNone(sg.fetch_wikipedia_for_subtopic("foo"))

    def test_one_failure_does_not_stop_rest(self):
        plan = [{"subtopic": "a", "search_query": "a"}, {"subtopic": "b", "search_query": "b"}]
        wiki = {"source_type": "wikipedia", "title": "T", "content": "c" * 40, "url": "u"}
        with mock.patch.object(sg, "fetch_wikipedia_for_subtopic", side_effect=[None, dict(wiki)]), \
             mock.patch.object(sg, "fetch_news_for_subtopic", return_value=[]):
            out = sg.gather_sources_for_plan(plan, log_fn=lambda *_: None)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["subtopic"], "b")

    def test_empty_plan(self):
        self.assertEqual(sg.gather_sources_for_plan([], log_fn=lambda *_: None), [])

    def test_news_skips_entries_without_title(self):
        feed = mock.MagicMock()
        feed.entries = [{"link": "u1"}, {"title": "Hi", "link": "u2", "summary": "s"}]
        with mock.patch.object(sg.requests, "get", return_value=resp(content=b"x")), \
             mock.patch.object(sg.feedparser, "parse", return_value=feed):
            out = sg.fetch_news_for_subtopic("q")
        self.assertEqual([o["title"] for o in out], ["Hi"])

    def test_news_timeout_returns_empty(self):
        with mock.patch.object(sg.requests, "get", side_effect=requests.Timeout("t")):
            self.assertEqual(sg.fetch_news_for_subtopic("q"), [])


if __name__ == "__main__":
    unittest.main()
