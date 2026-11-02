"""Tests for reproducible synthetic TPC-H generation."""
import json
import os
from pathlib import Path
import tempfile
import unittest

from scripts.generate_tpch import EXPECTED_COLUMNS, generate, validate_scale_factor


class TpchGenerationTests(unittest.TestCase):
    def setUp(self):
        self.extension_dir = (Path(os.environ.get("BDSRE_TOOLS_ROOT", ".tools"))
                              / "cache" / "duckdb-extensions")

    def test_scale_factor_validation(self):
        for value in (0, -1, float("inf"), float("nan"), True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_scale_factor(value)

    def test_generator_output_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = generate(0.001, root / "dataset", self.extension_dir)
            self.assertEqual(result["rows"], 6005)
            self.assertEqual(result["columns"], EXPECTED_COLUMNS)
            self.assertEqual(len(result["sha256"]), 64)
            self.assertTrue((root / "dataset" / "lineitem.parquet").is_file())
            saved = json.loads((root / "dataset" / "manifest.json").read_text())
            self.assertEqual(saved, result)

    def test_nonempty_output_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "dataset"
            output.mkdir()
            marker = output / "keep.txt"
            marker.write_text("keep")
            with self.assertRaises(FileExistsError):
                generate(0.001, output, self.extension_dir)
            self.assertEqual(marker.read_text(), "keep")


if __name__ == "__main__":
    unittest.main()
