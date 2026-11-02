"""Tests for benchmark input validation, output schema, and query consistency."""
import json
from pathlib import Path
import tempfile
import unittest

import duckdb

from scripts.benchmark_queries import benchmark
from scripts.benchmark_utils import discover_parquet_files, run_query_suite


def make_lineitem_fixture(path: Path) -> None:
    connection = duckdb.connect()
    try:
        destination = path.as_posix().replace("'", "''")
        connection.execute(
            "COPY (SELECT (i + 1)::BIGINT AS l_orderkey, "
            "DATE '1995-01-01' + (i % 400)::INTEGER AS l_shipdate, "
            "CASE WHEN i % 2 = 0 THEN 'R' ELSE 'N' END AS l_returnflag, "
            "'O' AS l_linestatus, (i * 1.25)::DECIMAL(12,2) AS l_extendedprice "
            f"FROM range(30) AS values(i)) TO '{destination}' (FORMAT PARQUET)"
        )
    finally:
        connection.close()


class BenchmarkQueryTests(unittest.TestCase):
    def test_benchmark_records_repeats_files_results_and_fingerprint(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_dir = root / "small-files"
            source_dir.mkdir()
            make_lineitem_fixture(source_dir / "lineitem.parquet")
            output = root / "results.json"
            result_path = benchmark(source_dir, output, warmups=1, repeats=3, threads=2)
            result = json.loads(result_path.read_text(encoding="utf-8"))
            self.assertEqual(result["file_layout"]["file_count"], 1)
            self.assertEqual(result["input_fingerprint"]["rows"], 30)
            self.assertEqual(set(result["queries"]), {
                "full_scan", "single_column_filter", "multi_column_filter_aggregation"
            })
            for query in result["queries"].values():
                self.assertEqual(len(query["runs_seconds"]), 3)
                self.assertTrue(all(value >= 0 for value in query["runs_seconds"]))
                self.assertEqual(len(query["result_sha256"]), 64)
            self.assertEqual(result["queries"]["full_scan"]["columns_and_rows"][0][0], 30)
            with self.assertRaises(FileExistsError):
                benchmark(source_dir, output, warmups=0, repeats=1, threads=1)

    def test_input_directory_discovers_nested_parquet_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            nested = root / "nested"
            nested.mkdir()
            make_lineitem_fixture(nested / "part.parquet")
            self.assertEqual(len(discover_parquet_files(root)), 1)

    def test_query_repeats_must_be_positive(self):
        connection = duckdb.connect()
        try:
            with self.assertRaises(ValueError):
                run_query_suite(connection, "missing", warmups=0, repeats=0)
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()