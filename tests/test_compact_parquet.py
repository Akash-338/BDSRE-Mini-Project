"""Tests for compaction correctness and comparable before/after benchmarks."""
import json
from pathlib import Path
import tempfile
import unittest

import duckdb

from scripts.compact_parquet import compact_parquet


def make_small_file_layout(directory: Path, rows: int = 300) -> None:
    directory.mkdir(parents=True)
    connection = duckdb.connect()
    try:
        for start in range(0, rows, 50):
            output = (directory / f"small-{start // 50:03d}.parquet").as_posix().replace("'", "''")
            connection.execute(
                "COPY (SELECT (i + 1)::BIGINT AS l_orderkey, "
                "DATE '1995-01-01' + (i % 400)::INTEGER AS l_shipdate, "
                "CASE WHEN i % 2 = 0 THEN 'R' ELSE 'N' END AS l_returnflag, "
                "'O' AS l_linestatus, (i * 1.25)::DECIMAL(12,2) AS l_extendedprice "
                f"FROM range({start}, {start + 50}) AS values(i)) "
                f"TO '{output}' (FORMAT PARQUET, COMPRESSION ZSTD)"
            )
    finally:
        connection.close()


class CompactParquetTests(unittest.TestCase):
    def test_compaction_preserves_rows_and_query_results(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "small-files"
            make_small_file_layout(source)
            output = root / "compacted"
            results = root / "compaction-results.json"
            result_path = compact_parquet(
                source, output, results, file_size_bytes=16_384, warmups=0, repeats=2, threads=1
            )
            result = json.loads(result_path.read_text(encoding="utf-8"))
            self.assertTrue(result["row_preservation_verified"])
            self.assertEqual(result["source_fingerprint"]["rows"], 300)
            self.assertEqual(result["baseline_layout"]["file_count"], 6)
            self.assertLess(result["compacted_layout"]["file_count"], 6)
            self.assertTrue(all(result["query_results_equal"].values()))
            self.assertGreaterEqual(result["optimization_duration_seconds"], 0)
            self.assertTrue(all(run >= 0 for q in result["compacted_queries"].values() for run in q["runs_seconds"]))
            self.assertEqual(len(list(source.glob("*.parquet"))), 6)

    def test_existing_output_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "small-files"
            make_small_file_layout(source)
            output = root / "compacted"
            output.mkdir()
            marker = output / "keep.txt"
            marker.write_text("keep")
            with self.assertRaises(FileExistsError):
                compact_parquet(source, output, root / "results.json", warmups=0, repeats=1)
            self.assertEqual(marker.read_text(), "keep")

    def test_output_must_be_outside_baseline_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "small-files"
            make_small_file_layout(source)
            with self.assertRaises(ValueError):
                compact_parquet(source, source / "compacted", root / "results.json", warmups=0, repeats=1)
            with self.assertRaises(ValueError):
                compact_parquet(source, root / "compacted", source / "results.json", warmups=0, repeats=1)
    def test_invalid_size_is_rejected(self):
        for value in (0, -1, True, 1.5):
            with self.subTest(value=value), self.assertRaises(ValueError):
                compact_parquet(Path("missing"), Path("out"), Path("results"), file_size_bytes=value)


if __name__ == "__main__":
    unittest.main()