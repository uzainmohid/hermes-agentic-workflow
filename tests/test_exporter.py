import os
import tempfile
import unittest

import exporter as ex

REPORT = {"intro": "Intro [1]", "sections": [{"heading": "H", "body": "Body [2]"}],
          "references": [(1, "wikipedia", "Alpha", "https://a"), (2, "news_rss", "Beta", "")]}


class TestExporter(unittest.TestCase):
    def test_markdown_has_all_references(self):
        md = ex.export_to_markdown("Topic", REPORT)
        self.assertIn("[1] wikipedia: [Alpha](https://a)", md)
        self.assertIn("[2] news_rss: Beta", md)

    def test_docx_created(self):
        with tempfile.TemporaryDirectory() as d:
            p = ex.export_to_docx("Topic", REPORT, os.path.join(d, "r.docx"))
            self.assertGreater(os.path.getsize(p), 0)

    def test_safe_filename(self):
        self.assertEqual(ex.safe_filename("a/b: c*d?"), "ab_cd")
        self.assertLessEqual(len(ex.safe_filename("x " * 100)), 50)
        self.assertEqual(ex.safe_filename("///"), "report")


if __name__ == "__main__":
    unittest.main()
