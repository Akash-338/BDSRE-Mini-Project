import json
from pathlib import Path
import tempfile
import unittest

import duckdb

from scripts.layout_variants import build_layouts, z_order_key_sql


def make_fixture(root: Path, rows: int = 48) -> Path:
    source = root / "input"
    source.mkdir()
    connection = duckdb.connect()
    try:
        connection.execute(
            "CREATE TABLE lineitem AS SELECT "
            "i::BIGINT AS l_orderkey, (i % 7 + 1)::INTEGER AS l_linenumber, "
            "DATE '1995-01-01' + (i % 700)::INTEGER AS l_shipdate, "
            "CASE i % 3 WHEN 0 THEN 'A' WHEN 1 THEN 'N' ELSE 'R' END AS l_returnflag, "
            "CASE i % 2 WHEN 0 THEN 'O' ELSE 'F' END AS l_linestatus, "
            "(i * 1.25)::DOUBLE AS l_extendedprice "
            "FROM range(?) AS r(i)", [rows]
        )
        for batch in range(6):
            connection.execute(
                f"COPY (SELECT * FROM lineitem WHERE l_orderkey % 6 = {batch}) "
                f"TO '{(source / f'part-{batch}.parquet').as_posix()}' (FORMAT PARQUET)"
            )
    finally:
        connection.close()
    return source


class LayoutVariantsTests(unittest.TestCase):
    def test_builds_equivalent_layouts_and_keeps_source_unchanged(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = make_fixture(root)
            before = sorted(source.glob("*.parquet"))
            results = root / "layout-results.json"
            payload = build_layouts(source, root / "variants", results, file_size_bytes=2048,
                                    warmups=0, repeats=2, threads=2)
            self.assertEqual(len(list(source.glob("*.parquet"))), len(before))
            self.assertEqual(set(payload["layouts"]), {"compacted", "sorted", "z_ordered"})
            expected = payload["baseline"]["row_fingerprint"]
            for layout in payload["layouts"].values():
                self.assertEqual(layout["row_fingerprint"], expected)
                for name, baseline in payload["baseline"]["query_benchmarks"].items():
                    self.assertEqual(layout["query_benchmarks"][name]["result_sha256"], baseline["result_sha256"])
                self.assertEqual(layout["file_summary"]["file_count"], 1)
            self.assertIn("Morton key", payload["layouts"]["z_ordered"]["ordering"])
            self.assertEqual(json.loads(results.read_text(encoding="utf-8"))["schema_version"], 1)

    def test_rejects_unexpected_return_flag(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = make_fixture(root)
            connection = duckdb.connect()
            try:
                connection.execute("COPY (SELECT * REPLACE ('X' AS l_returnflag) FROM read_parquet(?) LIMIT 1) TO ? (FORMAT PARQUET)",
                                   [str(next(source.glob("*.parquet"))), str(source / "invalid.parquet")])
            except Exception:
                # Construct invalid fixture using a safe, quoted path if COPY parameter parsing differs by DuckDB version.
                bad = source / "invalid.parquet"
                connection.execute(
                    f"COPY (SELECT * REPLACE ('X' AS l_returnflag) FROM read_parquet('{next(source.glob('*.parquet')).as_posix()}') LIMIT 1) "
                    f"TO '{bad.as_posix()}' (FORMAT PARQUET)"
                )
            finally:
                connection.close()
            with self.assertRaisesRegex(ValueError, "unexpected return flags"):
                build_layouts(source, root / "variants", root / "results.json", repeats=1, warmups=0)

    def test_z_order_expression_runs_and_output_paths_are_protected(self):
        connection = duckdb.connect()
        try:
            value = connection.execute(f"SELECT {z_order_key_sql()} FROM (SELECT DATE '1995-01-01' AS l_shipdate, 'R' AS l_returnflag)").fetchone()[0]
            self.assertGreaterEqual(value, 0)
        finally:
            connection.close()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = make_fixture(root)
            variants = root / "variants"
            variants.mkdir()
            with self.assertRaises(FileExistsError):
                build_layouts(source, variants, root / "results.json")


if __name__ == "__main__":
    unittest.main()
