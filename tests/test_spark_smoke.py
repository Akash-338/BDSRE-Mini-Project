"""Unit checks for the Spark smoke test's safe per-run artifact handling."""
from pathlib import Path
import tempfile
import unittest

from scripts.smoke_test import new_run_directory


class SparkSmokeSafetyTests(unittest.TestCase):
    def test_each_run_gets_a_new_directory_and_preserves_prior_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            tools_root = Path(temporary)
            first = new_run_directory(tools_root)
            marker = first / "keep.txt"
            marker.write_text("previous run", encoding="utf-8")

            second = new_run_directory(tools_root)

            self.assertNotEqual(first, second)
            self.assertEqual(first.parent, tools_root.resolve())
            self.assertEqual(second.parent, tools_root.resolve())
            self.assertEqual(marker.read_text(encoding="utf-8"), "previous run")
            self.assertTrue(first.is_dir())
            self.assertTrue(second.is_dir())


if __name__ == "__main__":
    unittest.main()
