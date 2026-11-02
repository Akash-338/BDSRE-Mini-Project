"""Audit synthetic TPC-H Parquet schema and provenance without claiming privacy proof."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any

import duckdb

APPROVED_COLUMNS = [
    "l_orderkey", "l_partkey", "l_suppkey", "l_linenumber", "l_quantity",
    "l_extendedprice", "l_discount", "l_tax", "l_returnflag", "l_linestatus",
    "l_shipdate", "l_commitdate", "l_receiptdate", "l_shipinstruct",
    "l_shipmode", "l_comment",
]
REQUIRED_PROVENANCE = [
    "dataset", "generator", "duckdb_version", "scale_factor", "rows", "columns",
    "format", "compression", "sha256", "intended_use", "privacy",
]
SHA256_PATTERN = re.compile(r"^[a-fA-F0-9]{64}$")


def sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _parquet_columns(path: Path) -> list[str]:
    escaped = path.resolve().as_posix().replace("'", "''")
    connection = duckdb.connect()
    try:
        return [row[0] for row in connection.execute(f"DESCRIBE SELECT * FROM read_parquet('{escaped}')").fetchall()]
    finally:
        connection.close()


def _parquet_rows(files: list[Path]) -> int:
    paths = [str(path.resolve()).replace("'", "''") for path in files]
    list_sql = ", ".join("'" + path.replace("\\", "/") + "'" for path in paths)
    connection = duckdb.connect()
    try:
        return int(connection.execute(f"SELECT count(*) FROM read_parquet([{list_sql}], union_by_name=true)").fetchone()[0])
    finally:
        connection.close()


def _load_json(path: Path, label: str, findings: list[str]) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        findings.append(f"{label} could not be read as JSON: {exc}")
        return {}
    if not isinstance(payload, dict):
        findings.append(f"{label} must contain a JSON object")
        return {}
    return payload


def _check_provenance(manifest: dict[str, Any], findings: list[str]) -> None:
    missing = [field for field in REQUIRED_PROVENANCE if field not in manifest]
    if missing:
        findings.append("provenance manifest is missing fields: " + ", ".join(missing))
        return
    if manifest["dataset"] != "TPC-H synthetic lineitem":
        findings.append("provenance dataset must identify 'TPC-H synthetic lineitem'")
    if manifest["generator"] != "DuckDB tpch extension dbgen":
        findings.append("provenance generator is not the approved DuckDB TPC-H generator")
    if not isinstance(manifest["duckdb_version"], str) or not manifest["duckdb_version"].strip():
        findings.append("provenance DuckDB version must be a non-empty string")
    try:
        scale = float(manifest["scale_factor"])
        if not math.isfinite(scale) or scale <= 0:
            raise ValueError
    except (TypeError, ValueError):
        findings.append("provenance scale_factor must be positive and finite")
    if isinstance(manifest["rows"], bool) or not isinstance(manifest["rows"], int) or manifest["rows"] < 0:
        findings.append("provenance rows must be a non-negative integer")
    if manifest["columns"] != APPROVED_COLUMNS:
        findings.append("provenance columns must exactly match the ordered approved TPC-H lineitem allowlist")
    if manifest["format"] != "Parquet":
        findings.append("provenance format must be Parquet")
    if not isinstance(manifest["compression"], str) or not manifest["compression"].strip():
        findings.append("provenance compression must be a non-empty string")
    if not isinstance(manifest["sha256"], str) or not SHA256_PATTERN.fullmatch(manifest["sha256"]):
        findings.append("provenance sha256 must be a 64-character hexadecimal digest")
    for field in ("intended_use", "privacy"):
        if not isinstance(manifest[field], str) or not manifest[field].strip():
            findings.append(f"provenance {field} must be a non-empty note")


def audit_dataset(input_path: Path, provenance_path: Path, ingestion_manifest_path: Path | None = None) -> dict[str, Any]:
    """Return measured schema/provenance audit results and limitations."""
    findings: list[str] = []
    input_path = input_path.expanduser().resolve()
    provenance_path = provenance_path.expanduser().resolve()
    if input_path.is_file() and input_path.suffix.lower() == ".parquet":
        files = [input_path]
    elif input_path.is_dir():
        files = sorted(file.resolve() for file in input_path.rglob("*.parquet") if file.is_file())
    else:
        files = []
        findings.append("input must be a Parquet file or directory")
    if not files:
        findings.append("no Parquet files found")

    provenance = _load_json(provenance_path, "provenance manifest", findings)
    _check_provenance(provenance, findings)
    # A direct generator-file audit can and should bind the manifest digest to
    # the exact Parquet bytes being checked. For ingested directories, lineage is
    # checked below through the ingestion manifest instead.
    if input_path.is_file() and input_path.suffix.lower() == ".parquet":
        declared_digest = provenance.get("sha256")
        if isinstance(declared_digest, str) and SHA256_PATTERN.fullmatch(declared_digest):
            if sha256_file(input_path).lower() != declared_digest.lower():
                findings.append("provenance sha256 does not match the input Parquet file")
    file_results = []
    for file in files:
        row: dict[str, Any] = {"path": str(file), "sha256": sha256_file(file)}
        try:
            columns = _parquet_columns(file)
            row["columns"] = columns
            row["schema_passed"] = columns == APPROVED_COLUMNS
            row["schema_findings"] = [] if row["schema_passed"] else [
                f"column mismatch: missing={sorted(set(APPROVED_COLUMNS) - set(columns))}, "
                f"unexpected={sorted(set(columns) - set(APPROVED_COLUMNS))}, order_matches={columns == [c for c in APPROVED_COLUMNS if c in columns]}"
            ]
        except Exception as exc:  # report corrupt/unreadable files as audit failures
            row.update({"columns": None, "schema_passed": False, "schema_findings": [f"Parquet schema could not be read: {exc}"]})
        file_results.append(row)

    if files:
        try:
            observed_rows = _parquet_rows(files)
        except Exception as exc:
            observed_rows = None
            findings.append(f"dataset rows could not be counted: {exc}")
    else:
        observed_rows = 0
    expected_rows = provenance.get("rows")
    row_count_matches = isinstance(expected_rows, int) and not isinstance(expected_rows, bool) and observed_rows == expected_rows
    if not row_count_matches:
        findings.append(f"observed row count {observed_rows} does not match provenance rows {expected_rows}")

    ingestion_path = ingestion_manifest_path
    if ingestion_path is None and input_path.is_dir():
        candidate = input_path / "ingestion-manifest.json"
        ingestion_path = candidate if candidate.is_file() else None
    lineage_verified: bool | None = None
    lineage_source_path_used: str | None = None
    if ingestion_path is not None:
        ingestion_path = ingestion_path.expanduser().resolve()
        ingestion = _load_json(ingestion_path, "ingestion manifest", findings)
        source_value = ingestion.get("input")
        if not source_value:
            findings.append("ingestion manifest has no source input path")
            lineage_verified = False
        else:
            source_file = Path(source_value).expanduser().resolve()
            source_digest = provenance.get("sha256")
            candidate = source_file if source_file.is_file() else provenance_path.parent / "lineitem.parquet"
            lineage_source_path_used = str(candidate.resolve()) if candidate.is_file() else None
            lineage_verified = candidate.is_file() and isinstance(source_digest, str) and sha256_file(candidate) == source_digest
            if not lineage_verified:
                findings.append("ingestion source file cannot be verified against the provenance SHA-256")
        if ingestion.get("output_rows") != observed_rows or ingestion.get("input_rows") != observed_rows:
            findings.append("ingestion manifest input/output row counts do not match audited Parquet rows")
        if ingestion.get("schema") != APPROVED_COLUMNS:
            findings.append("ingestion manifest schema does not match the approved column allowlist")
        manifest_files = ingestion.get("files", [])
        manifest_by_name = {entry.get("path"): entry for entry in manifest_files if isinstance(entry, dict)}
        if len(manifest_by_name) != len(files):
            findings.append("ingestion manifest file list does not match the number of Parquet files")
        for row in file_results:
            entry = manifest_by_name.get(Path(row["path"]).name)
            if not entry or entry.get("sha256") != row["sha256"]:
                findings.append(f"ingestion manifest checksum is missing or mismatched for {Path(row['path']).name}")
        if ingestion.get("files_created") != len(files):
            findings.append("ingestion manifest files_created does not match audited Parquet file count")

    passed_files = sum(bool(row.get("schema_passed")) for row in file_results)
    failed_files = len(file_results) - passed_files
    if failed_files:
        findings.append(f"schema allowlist rejected {failed_files} of {len(file_results)} Parquet files")
    provenance_passed = not any("provenance" in finding or "ingestion" in finding for finding in findings)
    checks_passed = not findings and all(row.get("schema_passed") for row in file_results) and row_count_matches
    return {
        "schema_version": 1,
        "control": "approved TPC-H lineitem column allowlist plus provenance and optional ingestion-manifest integrity checks",
        "input": str(input_path),
        "provenance_manifest": str(provenance_path),
        "approved_columns": APPROVED_COLUMNS,
        "measured": {
            "parquet_files": len(files),
            "schema_passed_files": passed_files,
            "schema_failed_files": failed_files,
            "observed_rows": observed_rows,
            "provenance_rows": expected_rows,
            "row_count_matches": row_count_matches,
            "provenance_valid": provenance_passed,
            "source_lineage_sha256_verified": lineage_verified,
            "lineage_source_path_used": lineage_source_path_used,
            "overall_passed": checks_passed,
        },
        "files": file_results,
        "findings": findings,
        "limitations": [
            "The column allowlist can detect unexpected or missing field names; it does not prove that values contain no personal data.",
            "This check does not measure re-identification risk, infer sensitive attributes, or validate every data value.",
            "A passing schema and provenance audit is a narrow governance control, not a privacy guarantee.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="generated Parquet file or small-file directory")
    parser.add_argument("--provenance", required=True, type=Path, help="manifest.json from generate_tpch.py")
    parser.add_argument("--ingestion-manifest", type=Path, help="optional ingestion-manifest.json for lineage and file checksums")
    parser.add_argument("--output", required=True, type=Path, help="new audit JSON path")
    args = parser.parse_args()
    if args.output.expanduser().resolve() in {p.expanduser().resolve() for p in (args.input, args.provenance, args.ingestion_manifest) if p}:
        raise ValueError("audit output cannot replace input")
    result = audit_dataset(args.input, args.provenance, args.ingestion_manifest)
    destination = args.output.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    from output_refresh import refresh_json
    def write(stage):
        stage.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    refresh_json(destination, write)
    print(json.dumps(result["measured"], indent=2, sort_keys=True))
    print(f"Audit report: {destination}")
    return 0 if result["measured"]["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
