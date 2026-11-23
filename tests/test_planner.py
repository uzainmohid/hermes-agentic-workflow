import json
import unittest
from unittest import mock

import research_planner as rp

FALLBACK = [{"subtopic": "topic", "search_query": "topic"}]


def fake_client(content):
    client = mock.MagicMock()
    client.chat.completions.create.return_value.choices = [
        mock.MagicMock(message=mock.MagicMock(content=content))]
    return client


class TestPlanner(unittest.TestCase):
    def run_plan(self, content, key="x"):
        with mock.patch.object(rp, "DEEPSEEK_API_KEY", key), \
             mock.patch.object(rp, "OpenAI", return_value=fake_client(content)):
            return rp.build_research_plan("topic")

    def test_valid(self):
        data = [{"subtopic": "a", "search_query": "b"}]
        self.assertEqual(self.run_plan(json.dumps(data)), data)

    def test_fenced(self):
        data = [{"subtopic": "a", "search_query": "b"}]
        self.assertEqual(self.run_plan("```json\n" + json.dumps(data) + "\n```"), data)

    def test_invalid_json_falls_back(self):
        self.assertEqual(self.run_plan("not json"), FALLBACK)

    def test_empty_falls_back(self):
        self.assertEqual(self.run_plan(""), FALLBACK)

    def test_missing_key_falls_back(self):
        self.assertEqual(self.run_plan("[]", key=""), FALLBACK)

    def test_malformed_items_dropped(self):
        data = [{"subtopic": "a"}, "x", {"subtopic": "ok", "search_query": "q"}]
        self.assertEqual(self.run_plan(json.dumps(data)), [{"subtopic": "ok", "search_query": "q"}])


if __name__ == "__main__":
    unittest.main()
