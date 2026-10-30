import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import duckdb

from scripts.governance_check import APPROVED_COLUMNS, audit_dataset


def write_lineitem(path: Path, *, extra_column: bool = False, rows: int = 2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    aliases = [
        "i::BIGINT AS l_orderkey", "i::BIGINT AS l_partkey", "i::BIGINT AS l_suppkey",
        "1::INTEGER AS l_linenumber", "1.0::DOUBLE AS l_quantity", "2.0::DOUBLE AS l_extendedprice",
        "0.0::DOUBLE AS l_discount", "0.0::DOUBLE AS l_tax", "'R'::VARCHAR AS l_returnflag",
        "'F'::VARCHAR AS l_linestatus", "DATE '1995-01-01' AS l_shipdate", "DATE '1995-01-02' AS l_commitdate",
        "DATE '1995-01-03' AS l_receiptdate", "'DELIVER IN PERSON'::VARCHAR AS l_shipinstruct",
        "'AIR'::VARCHAR AS l_shipmode", "'synthetic fixture'::VARCHAR AS l_comment",
    ]
    if extra_column:
        aliases.append("'not-approved'::VARCHAR AS customer_email")
    connection = duckdb.connect()
    try:
        connection.execute(f"COPY (SELECT {', '.join(aliases)} FROM range({rows}) AS r(i)) TO '{path.as_posix()}' (FORMAT PARQUET)")
    finally:
        connection.close()


def write_generator_manifest(path: Path, source_file: Path, rows: int) -> dict:
    manifest = {
        "dataset": "TPC-H synthetic lineitem",
        "generator": "DuckDB tpch extension dbgen",
        "duckdb_version": duckdb.__version__,
        "scale_factor": 0.001,
        "rows": rows,
        "columns": APPROVED_COLUMNS,
        "format": "Parquet",
        "compression": "ZSTD",
        "sha256": hashlib.sha256(source_file.read_bytes()).hexdigest(),
        "intended_use": "small-file layout research",
        "privacy": "synthetic benchmark rows; no real-person data",
    }
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest


class GovernanceCheckTests(unittest.TestCase):
    def test_approved_schema_and_provenance_pass(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            parquet = root / "lineitem.parquet"
            write_lineitem(parquet)
            manifest_path = root / "manifest.json"
            write_generator_manifest(manifest_path, parquet, 2)
            result = audit_dataset(parquet, manifest_path)
            self.assertTrue(result["measured"]["overall_passed"], result["findings"])
            self.assertEqual(result["measured"]["schema_passed_files"], 1)
            self.assertEqual(result["measured"]["schema_failed_files"], 0)
            self.assertEqual(result["measured"]["observed_rows"], 2)
            self.assertIsNone(result["measured"]["source_lineage_sha256_verified"])

    def test_rejects_unapproved_field_and_reports_measured_pass_fail_counts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "generated.parquet"
            write_lineitem(source, rows=2)
            input_dir = root / "microbatches"
            write_lineitem(input_dir / "good.parquet", rows=2)
            write_lineitem(input_dir / "bad.parquet", extra_column=True, rows=1)
            manifest_path = root / "manifest.json"
            write_generator_manifest(manifest_path, source, 3)
            result = audit_dataset(input_dir, manifest_path)
            self.assertFalse(result["measured"]["overall_passed"])
            self.assertEqual(result["measured"]["schema_passed_files"], 1)
            self.assertEqual(result["measured"]["schema_failed_files"], 1)
            self.assertEqual(result["measured"]["observed_rows"], 3)
            self.assertTrue(any("unexpected=['customer_email']" in " ".join(row["schema_findings"])
                                for row in result["files"] if row["schema_findings"]))

    def test_validates_ingestion_chain_and_detects_checksum_tampering(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "generated.parquet"
            write_lineitem(source)
            provenance_path = root / "manifest.json"
            write_generator_manifest(provenance_path, source, 2)
            batches = root / "batches"
            batch = batches / "batch-000000.parquet"
            write_lineitem(batch)
            digest = hashlib.sha256(batch.read_bytes()).hexdigest()
            ingestion_path = batches / "ingestion-manifest.json"
            ingestion_path.write_text(json.dumps({
                "input": str(source), "input_rows": 2, "output_rows": 2,
                "schema": APPROVED_COLUMNS, "files_created": 1,
                "files": [{"path": batch.name, "rows": 2, "sha256": digest}],
            }), encoding="utf-8")
            result = audit_dataset(batches, provenance_path, ingestion_path)
            self.assertTrue(result["measured"]["source_lineage_sha256_verified"])
            self.assertTrue(result["measured"]["overall_passed"], result["findings"])
            ingestion_path.write_text(ingestion_path.read_text(encoding="utf-8").replace(digest, "0" * 64), encoding="utf-8")
            bad_result = audit_dataset(batches, provenance_path, ingestion_path)
            self.assertFalse(bad_result["measured"]["overall_passed"])
            self.assertTrue(any("checksum" in finding for finding in bad_result["findings"]))

    def test_recovers_moved_source_by_matching_provenance_digest(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "lineitem.parquet"
            write_lineitem(source)
            provenance_path = root / "manifest.json"
            write_generator_manifest(provenance_path, source, 2)
            batches = root / "batches"
            batch = batches / "batch-000000.parquet"
            write_lineitem(batch)
            ingestion_path = batches / "ingestion-manifest.json"
            ingestion_path.write_text(json.dumps({
                "input": str(root / "old-location" / "lineitem.parquet"),
                "input_rows": 2, "output_rows": 2, "schema": APPROVED_COLUMNS,
                "files_created": 1,
                "files": [{"path": batch.name, "rows": 2, "sha256": hashlib.sha256(batch.read_bytes()).hexdigest()}],
            }), encoding="utf-8")
            result = audit_dataset(batches, provenance_path, ingestion_path)
            self.assertTrue(result["measured"]["overall_passed"], result["findings"])
            self.assertTrue(Path(result["measured"]["lineage_source_path_used"]).samefile(source))


if __name__ == "__main__":
    unittest.main()
