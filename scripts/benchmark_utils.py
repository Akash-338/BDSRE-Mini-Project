"""Shared utilities for reproducible Parquet query benchmarks."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
import hashlib
import json
import platform
from pathlib import Path
import re
import statistics
import sys
from typing import Any

import duckdb


def discover_parquet_files(input_path: Path) -> list[Path]:
    path = input_path.expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(path)
    if path.is_file():
        if path.suffix.lower() != ".parquet":
            raise ValueError(f"input file must have a .parquet extension: {path}")
        files = [path]
    elif path.is_dir():
        files = sorted(candidate.resolve() for candidate in path.rglob("*.parquet") if candidate.is_file())
    else:
        raise ValueError(f"input must be a Parquet file or directory: {path}")
    if not files:
        raise ValueError(f"no Parquet files found under: {path}")
    return files


def quote_sql_string(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def parquet_scan_sql(files: list[Path]) -> str:
    if not files:
        raise ValueError("at least one Parquet file is required")
    paths = ", ".join(quote_sql_string(path.as_posix()) for path in files)
    return f"read_parquet([{paths}], union_by_name=true)"


def create_parquet_view(connection: duckdb.DuckDBPyConnection, files: list[Path], relation: str) -> None:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", relation):
        raise ValueError("relation must be a simple SQL identifier")
    connection.execute(f"CREATE OR REPLACE VIEW {relation} AS SELECT * FROM {parquet_scan_sql(files)}")


def _json_value(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, bytes):
        return value.hex()
    return value


def _rows_as_json(rows: list[tuple[Any, ...]]) -> list[list[Any]]:
    return [[_json_value(value) for value in row] for row in rows]


def query_definitions(relation: str) -> dict[str, str]:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", relation):
        raise ValueError("relation must be a simple SQL identifier")
    return {
        "full_scan": (
            f"SELECT COUNT(*) AS row_count, SUM(l_extendedprice) AS extendedprice_sum "
            f"FROM {relation}"
        ),
        "single_column_filter": (
            f"SELECT COUNT(*) AS row_count, SUM(l_extendedprice) AS extendedprice_sum "
            f"FROM {relation} WHERE l_returnflag = 'R'"
        ),
        "multi_column_filter_aggregation": (
            f"SELECT l_returnflag, l_linestatus, COUNT(*) AS row_count, "
            f"SUM(l_extendedprice) AS extendedprice_sum FROM {relation} "
            "WHERE l_shipdate >= DATE '1995-01-01' AND l_shipdate < DATE '1996-01-01' "
            "AND l_returnflag = 'R' GROUP BY l_returnflag, l_linestatus "
            "ORDER BY l_returnflag, l_linestatus"
        ),
    }


def row_fingerprint(connection: duckdb.DuckDBPyConnection, relation: str) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", relation):
        raise ValueError("relation must be a simple SQL identifier")
    row_hash = f"hash(to_json({relation}))"
    count, xor_hash, sum_hash = connection.execute(
        f"SELECT count(*), bit_xor({row_hash}), sum({row_hash}::HUGEINT) FROM {relation}"
    ).fetchone()
    return {"rows": count, "row_hash_xor": xor_hash, "row_hash_sum": str(sum_hash)}


def summarize_files(files: list[Path]) -> dict[str, Any]:
    entries = [{"path": str(path), "bytes": path.stat().st_size} for path in files]
    sizes = [entry["bytes"] for entry in entries]
    return {
        "file_count": len(entries),
        "total_bytes": sum(sizes),
        "min_bytes": min(sizes) if sizes else 0,
        "max_bytes": max(sizes) if sizes else 0,
        "mean_bytes": round(statistics.mean(sizes), 2) if sizes else 0,
        "files": entries,
    }


def run_query_suite(
    connection: duckdb.DuckDBPyConnection,
    relation: str,
    *,
    warmups: int,
    repeats: int,
) -> dict[str, Any]:
    if isinstance(warmups, bool) or not isinstance(warmups, int) or warmups < 0:
        raise ValueError("warmups must be a non-negative integer")
    if isinstance(repeats, bool) or not isinstance(repeats, int) or repeats < 1:
        raise ValueError("repeats must be a positive integer")
    results: dict[str, Any] = {}
    for name, sql in query_definitions(relation).items():
        expected: list[list[Any]] | None = None
        warmup_seconds = []
        run_seconds = []
        for _ in range(warmups):
            started = __import__("time").perf_counter()
            rows = _rows_as_json(connection.execute(sql).fetchall())
            warmup_seconds.append(__import__("time").perf_counter() - started)
            if expected is None:
                expected = rows
            elif rows != expected:
                raise RuntimeError(f"query {name} returned inconsistent results during warm-up")
        for _ in range(repeats):
            started = __import__("time").perf_counter()
            rows = _rows_as_json(connection.execute(sql).fetchall())
            run_seconds.append(__import__("time").perf_counter() - started)
            if expected is None:
                expected = rows
            elif rows != expected:
                raise RuntimeError(f"query {name} returned inconsistent results between runs")
        canonical = json.dumps(expected or [], sort_keys=True, separators=(",", ":"))
        results[name] = {
            "sql": sql,
            "warmup_runs_seconds": warmup_seconds,
            "runs_seconds": run_seconds,
            "summary_seconds": {
                "min": min(run_seconds),
                "median": statistics.median(run_seconds),
                "mean": statistics.mean(run_seconds),
                "max": max(run_seconds),
                "stdev": statistics.stdev(run_seconds) if len(run_seconds) > 1 else 0.0,
            },
            "columns_and_rows": expected or [],
            "result_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        }
    return results


def system_metadata(threads: int, warmups: int, repeats: int) -> dict[str, Any]:
    return {
        "platform": platform.platform(),
        "processor": platform.processor() or platform.machine(),
        "logical_cpu_count": __import__("os").cpu_count(),
        "python_version": platform.python_version(),
        "duckdb_version": duckdb.__version__,
        "duckdb_threads": threads,
        "warmups_per_query": warmups,
        "measured_repeats_per_query": repeats,
        "cache_policy": (
            "One warm-up per query by default; measured runs use the local filesystem and OS cache. "
            "The harness does not flush operating-system caches."
        ),
    }


def write_json_new(path: Path, payload: dict[str, Any]) -> Path:
    destination = path.expanduser().resolve()
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite existing results: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True)
        stream.write("\n")
    return destination