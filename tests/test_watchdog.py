import os
import tempfile
import unittest
from unittest import mock

import topic_watchdog as tw


def src(u):
    return {"source_type": "wikipedia", "title": u, "url": u, "subtopic": "s"}


class TestWatchdog(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        patches = [
            mock.patch.object(tw, "STATE_PATH", os.path.join(self.d, "state.json")),
            mock.patch.object(tw, "DIGEST_PATH", os.path.join(self.d, "digest.json")),
            mock.patch.object(tw, "build_research_plan",
                              return_value=[{"subtopic": "s", "search_query": "q"}]),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def check(self, sources):
        with mock.patch.object(tw, "gather_sources_for_plan", return_value=sources):
            return tw.check_topic("t", log_fn=lambda *_: None)

    def test_three_checks_2_1_0(self):
        self.assertEqual(self.check([src("a"), src("b")])["new_sources_found"], 2)
        self.assertEqual(self.check([src("a"), src("b"), src("c")])["new_sources_found"], 1)
        self.assertEqual(self.check([src("a"), src("b"), src("c")])["new_sources_found"], 0)

    def test_fetch_failure_records_zero(self):
        with mock.patch.object(tw, "gather_sources_for_plan", side_effect=RuntimeError("x")):
            e = tw.check_topic("t", log_fn=lambda *_: None)
        self.assertEqual(e["new_sources_found"], 0)

    def test_cli_usage_exit_code(self):
        self.assertEqual(tw.main(["x"]), 1)


if __name__ == "__main__":
    unittest.main()
