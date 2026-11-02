"""Generate reproducible TPC-H lineitem Parquet data and a provenance manifest."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import duckdb

EXPECTED_COLUMNS = [
    "l_orderkey", "l_partkey", "l_suppkey", "l_linenumber", "l_quantity",
    "l_extendedprice", "l_discount", "l_tax", "l_returnflag", "l_linestatus",
    "l_shipdate", "l_commitdate", "l_receiptdate", "l_shipinstruct",
    "l_shipmode", "l_comment",
]


def validate_scale_factor(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("scale factor must be a positive finite number")
    if not math.isfinite(value) or value <= 0:
        raise ValueError("scale factor must be a positive finite number")
    return float(value)


def generate(scale_factor: float, output_dir: Path, extension_dir: Path) -> dict:
    """Generate lineitem.parquet and manifest.json; refuse to overwrite output."""
    scale_factor = validate_scale_factor(scale_factor)
    output_dir = output_dir.resolve()
    extension_dir = extension_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"output directory is not empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    extension_dir.mkdir(parents=True, exist_ok=True)
    db = duckdb.connect()
    try:
        db.execute(f"SET extension_directory='{extension_dir.as_posix()}'")
        db.execute("INSTALL tpch")
        db.execute("LOAD tpch")
        db.execute(f"CALL dbgen(sf={scale_factor!r})")
        schema = db.execute("DESCRIBE SELECT * FROM lineitem").fetchall()
        columns = [row[0] for row in schema]
        if columns != EXPECTED_COLUMNS:
            raise RuntimeError(f"unexpected TPC-H lineitem schema: {columns}")
        rows = db.execute("SELECT count(*) FROM lineitem").fetchone()[0]
        parquet = output_dir / "lineitem.parquet"
        quoted_path = parquet.as_posix().replace("'", "''")
        db.execute(f"COPY lineitem TO '{quoted_path}' (FORMAT PARQUET, COMPRESSION ZSTD)")
        check = duckdb.connect()
        try:
            check.execute(f"SET extension_directory='{extension_dir.as_posix()}'")
            read_rows = check.execute(
                "SELECT count(*) FROM read_parquet(?)", [str(parquet)]
            ).fetchone()[0]
            read_columns = [r[0] for r in check.execute(
                "DESCRIBE SELECT * FROM read_parquet(?)", [str(parquet)]
            ).fetchall()]
        finally:
            check.close()
        if read_rows != rows or read_columns != EXPECTED_COLUMNS:
            raise RuntimeError("Parquet validation failed: schema or row count changed")
        digest = hashlib.sha256(parquet.read_bytes()).hexdigest()
        manifest = {
            "dataset": "TPC-H synthetic lineitem",
            "generator": "DuckDB tpch extension dbgen",
            "duckdb_version": duckdb.__version__,
            "scale_factor": scale_factor,
            "rows": rows,
            "columns": columns,
            "format": "Parquet",
            "compression": "ZSTD",
            "sha256": digest,
            "intended_use": "custom small-file and file-layout study; not an official TPC-H result",
            "privacy": "generated benchmark data; no real-person source records are ingested",
        }
        (output_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        return manifest
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scale-factor", type=float, default=0.001)
    parser.add_argument("--output", type=Path, default=Path("data/tpch"))
    parser.add_argument(
        "--extension-dir", type=Path,
        default=Path(__import__("os").environ.get("BDSRE_TOOLS_ROOT", ".tools"))
        / "cache/duckdb-extensions",
    )
    args = parser.parse_args()
    from output_refresh import refresh_directory
    manifest = refresh_directory(args.output, lambda stage: generate(args.scale_factor, stage, args.extension_dir),
                                 ("lineitem.parquet", "manifest.json"), inputs=(args.extension_dir,))
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
