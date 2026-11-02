"""Replay a Parquet input as small-file micro-batches for the experiment."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import duckdb


def _quoted(path: Path) -> str:
    return path.resolve().as_posix().replace("'", "''")


def _fingerprint(db: duckdb.DuckDBPyConnection, relation: str) -> dict:
    # Hash every row, then aggregate the unsigned hashes. This detects practical
    # accidental loss/duplication while staying bounded-memory for our data sizes.
    row_hash = f"hash(to_json({relation}))"
    count, xor_hash, sum_hash = db.execute(
        f"SELECT count(*), bit_xor({row_hash}), sum({row_hash}::HUGEINT) FROM {relation}"
    ).fetchone()
    return {"rows": count, "row_hash_xor": xor_hash, "row_hash_sum": str(sum_hash)}


def _file_sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def ingest_small_files(input_parquet: Path, output_dir: Path, batch_rows: int) -> dict:
    if isinstance(batch_rows, bool) or not isinstance(batch_rows, int) or batch_rows <= 0:
        raise ValueError("batch_rows must be a positive integer")
    source = input_parquet.resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    output = output_dir.resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    db = duckdb.connect()
    try:
        db.execute(f"CREATE VIEW source_data AS SELECT * FROM read_parquet('{_quoted(source)}')")
        schema = [row[0] for row in db.execute("DESCRIBE source_data").fetchall()]
        source_fingerprint = _fingerprint(db, "source_data")
        total_rows = source_fingerprint["rows"]
        files = []
        for index, offset in enumerate(range(0, total_rows, batch_rows)):
            target = output / f"batch-{index:06d}.parquet"
            db.execute(
                f"COPY (SELECT * FROM source_data LIMIT {batch_rows} OFFSET {offset}) "
                f"TO '{_quoted(target)}' (FORMAT PARQUET, COMPRESSION ZSTD)"
            )
            files.append({
                "path": target.name,
                "rows": min(batch_rows, total_rows - offset),
                "bytes": target.stat().st_size,
                "sha256": _file_sha256(target),
            })
        if files:
            pattern = _quoted(output / "batch-*.parquet")
            db.execute(f"CREATE VIEW replayed_data AS SELECT * FROM read_parquet('{pattern}', union_by_name=true)")
            replayed = _fingerprint(db, "replayed_data")
            replay_schema = [row[0] for row in db.execute("DESCRIBE replayed_data").fetchall()]
        else:
            replayed = {"rows": 0, "row_hash_xor": None, "row_hash_sum": "0"}
            replay_schema = schema
        if source_fingerprint != replayed or replay_schema != schema:
            raise RuntimeError(f"row preservation check failed: {source_fingerprint} != {replayed}")
        sizes = [entry["bytes"] for entry in files]
        manifest = {
            "input": str(source),
            "output": str(output),
            "ingestion_model": "simulated sequential micro-batch replay; not a live streaming system",
            "batch_rows": batch_rows,
            "input_rows": total_rows,
            "output_rows": replayed["rows"],
            "schema": schema,
            "files_created": len(files),
            "file_size_bytes": {
                "min": min(sizes) if sizes else 0,
                "max": max(sizes) if sizes else 0,
                "mean": round(sum(sizes) / len(sizes), 2) if sizes else 0,
                "total": sum(sizes),
            },
            "source_fingerprint": source_fingerprint,
            "output_fingerprint": replayed,
            "files": files,
        }
        (output / "ingestion-manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        return manifest
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="lineitem Parquet from generate_tpch.py")
    parser.add_argument("--output", type=Path, required=True, help="new/empty directory for micro-batch files")
    parser.add_argument("--batch-rows", type=int, default=1000)
    args = parser.parse_args()
    print(json.dumps(ingest_small_files(args.input, args.output, args.batch_rows), indent=2))


if __name__ == "__main__":
    main()




