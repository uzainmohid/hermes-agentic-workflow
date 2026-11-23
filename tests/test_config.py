import os
import tempfile
import unittest
from unittest import mock

import config


class TestConfig(unittest.TestCase):
    def test_missing_env_does_not_raise(self):
        config.load_env("does_not_exist.env")

    def test_value_loaded_and_real_env_wins(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, ".env")
            with open(p, "w", encoding="utf-8") as f:
                f.write("# c\n\nRO_TEST_A=from_file\nRO_TEST_B=from_file\nnoequals\n")
            with mock.patch.dict(os.environ, {"RO_TEST_B": "real"}, clear=False):
                os.environ.pop("RO_TEST_A", None)
                config.load_env(p)
                self.assertEqual(os.environ["RO_TEST_A"], "from_file")
                self.assertEqual(os.environ["RO_TEST_B"], "real")
                os.environ.pop("RO_TEST_A", None)


if __name__ == "__main__":
    unittest.main()
