import json
import unittest
from unittest import mock

import synthesizer as sy

SRC = [
    {"source_type": "wikipedia", "title": "A", "content": "aaa", "url": "u1", "subtopic": "s"},
    {"source_type": "news_rss", "title": "B", "content": "bbb", "url": "u1", "subtopic": "s"},
    {"source_type": "news_rss", "title": "C", "content": "ccc", "url": "u2", "subtopic": "s"},
]


def fake_client(content):
    c = mock.MagicMock()
    c.chat.completions.create.return_value.choices = [
        mock.MagicMock(message=mock.MagicMock(content=content))]
    return c


class TestSynthesizer(unittest.TestCase):
    def test_one_number_per_unique_url(self):
        numbered, refs = sy.build_citation_map(SRC)
        self.assertEqual([n["num"] for n in numbered], [1, 1, 2])
        self.assertEqual(len(refs), 2)

    def test_no_sources_no_model_call(self):
        with mock.patch.object(sy, "DEEPSEEK_API_KEY", "x"), mock.patch.object(sy, "OpenAI") as o:
            rep = sy.synthesize_report("t", [])
        o.assert_not_called()
        self.assertEqual(rep["references"], [])

    def test_model_failure_falls_back(self):
        with mock.patch.object(sy, "DEEPSEEK_API_KEY", "x"), \
             mock.patch.object(sy, "OpenAI", side_effect=RuntimeError("down")):
            rep = sy.synthesize_report("t", SRC)
        self.assertIn("failed", rep["intro"])
        self.assertEqual(len(rep["references"]), 2)

    def test_unknown_citation_detected_and_stripped(self):
        content = json.dumps({"intro": "hi [1]", "sections": [{"heading": "h", "body": "x [2] [9]"}]})
        with mock.patch.object(sy, "DEEPSEEK_API_KEY", "x"), \
             mock.patch.object(sy, "OpenAI", return_value=fake_client(content)):
            rep = sy.synthesize_report("t", SRC)
        self.assertNotIn("[9]", rep["sections"][0]["body"])
        self.assertIn("[2]", rep["sections"][0]["body"])
        self.assertEqual(
            sy.find_unknown_citations({"intro": "[5]", "sections": [], "references": []}), [5])


if __name__ == "__main__":
    unittest.main()
