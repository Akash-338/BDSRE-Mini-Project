"""Tests for simulated micro-batch ingestion and row preservation."""
import json
import os
from pathlib import Path
import tempfile
import unittest

from scripts.generate_tpch import generate
from scripts.ingest_small_files import ingest_small_files


class SmallFileIngestionTests(unittest.TestCase):
    def test_ingestion_creates_batches_and_preserves_all_rows(self):
        extensions = Path(os.environ.get("BDSRE_TOOLS_ROOT", ".tools")) / "cache" / "duckdb-extensions"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            generate(0.001, source, extensions)
            output = root / "small-files"
            result = ingest_small_files(source / "lineitem.parquet", output, 1000)
            self.assertEqual(result["input_rows"], 6005)
            self.assertEqual(result["output_rows"], 6005)
            self.assertEqual(result["files_created"], 7)
            self.assertEqual([f["rows"] for f in result["files"]], [1000] * 6 + [5])
            self.assertEqual(result["source_fingerprint"], result["output_fingerprint"])
            self.assertTrue(all(f["bytes"] > 0 and len(f["sha256"]) == 64 for f in result["files"]))
            saved = json.loads((output / "ingestion-manifest.json").read_text())
            self.assertEqual(saved, result)

    def test_invalid_batch_size_rejected(self):
        for value in (0, -1, True, 1.5):
            with self.subTest(value=value), self.assertRaises(ValueError):
                ingest_small_files(Path("missing.parquet"), Path("unused"), value)

    def test_nonempty_output_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.parquet"
            source.write_bytes(b"input")
            output = root / "output"
            output.mkdir()
            marker = output / "keep.txt"
            marker.write_text("keep")
            with self.assertRaises(FileExistsError):
                ingest_small_files(source, output, 10)
            self.assertEqual(marker.read_text(), "keep")


if __name__ == "__main__":
    unittest.main()
