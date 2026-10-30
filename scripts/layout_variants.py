"""Create compacted, sorted, and custom Morton-ordered Parquet layouts."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
import time
from typing import Any

import duckdb

try:
    from .benchmark_utils import (
        create_parquet_view,
        discover_parquet_files,
        row_fingerprint,
        run_query_suite,
        summarize_files,
        system_metadata,
        write_json_new,
    )
except ImportError:  # direct `python scripts/layout_variants.py`
    from benchmark_utils import (
        create_parquet_view,
        discover_parquet_files,
        row_fingerprint,
        run_query_suite,
        summarize_files,
        system_metadata,
        write_json_new,
    )

REQUIRED_COLUMNS = {"l_shipdate", "l_returnflag", "l_orderkey", "l_linenumber"}
SORT_ORDER = "l_shipdate, l_returnflag, l_orderkey, l_linenumber"


def z_order_key_sql() -> str:
    """Return a 64-bit Morton key interleaving ship-date days and flag rank."""
    day = "date_diff('day', DATE '1970-01-01', l_shipdate)::UBIGINT"
    flag = "CASE l_returnflag WHEN 'A' THEN 0::UBIGINT WHEN 'N' THEN 1::UBIGINT WHEN 'R' THEN 2::UBIGINT END"
    terms = []
    for bit in range(32):
        terms.append(f"((({day} >> {bit}) & 1::UBIGINT) << {2 * bit + 1})")
        terms.append(f"((({flag} >> {bit}) & 1::UBIGINT) << {2 * bit})")
    return "(" + " | ".join(terms) + ")"


def _validate_source(connection: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    description = connection.execute("DESCRIBE baseline_data").fetchall()
    columns = {row[0] for row in description}
    missing = sorted(REQUIRED_COLUMNS - columns)
    if missing:
        raise ValueError("TPC-H lineitem input is missing required columns: " + ", ".join(missing))
    bad = connection.execute(
        "SELECT count(*) FROM baseline_data "
        "WHERE l_shipdate IS NULL OR l_returnflag IS NULL OR l_returnflag NOT IN ('A','N','R') "
        "OR l_orderkey IS NULL OR l_linenumber IS NULL"
    ).fetchone()[0]
    if bad:
        raise ValueError(f"input has {bad} rows with null layout keys or unexpected return flags")
    return {"columns": [row[0] for row in description], "rows": connection.execute("SELECT count(*) FROM baseline_data").fetchone()[0]}


def _copy_layout(
    connection: duckdb.DuckDBPyConnection,
    destination: Path,
    order_by: str | None,
    file_size_bytes: int,
) -> float:
    select = "SELECT * FROM baseline_data"
    if order_by:
        select += " ORDER BY " + order_by
    destination_sql = str(destination.resolve()).replace("'", "''").replace("\\", "/")
    started = time.perf_counter()
    connection.execute("SET threads = 1")
    try:
        connection.execute(
            f"COPY ({select}) TO '{destination_sql}' "
            f"(FORMAT PARQUET, COMPRESSION ZSTD, FILE_SIZE_BYTES {file_size_bytes}, "
            "PER_THREAD_OUTPUT, FILENAME_PATTERN 'part-{i}.parquet')"
        )
    finally:
        connection.execute("SET threads = 4")
    return time.perf_counter() - started


def build_layouts(
    input_path: Path,
    output_root: Path,
    results_path: Path,
    *,
    file_size_bytes: int = 256 * 1024,
    warmups: int = 1,
    repeats: int = 5,
    threads: int = 4,
) -> dict[str, Any]:
    source_files = discover_parquet_files(input_path)
    root = output_root.expanduser().resolve()
    result_destination = results_path.expanduser().resolve()
    if file_size_bytes < 1 or repeats < 1 or warmups < 0 or threads < 1:
        raise ValueError("file size and threads must be positive; repeats >= 1 and warmups >= 0")
    if root.exists():
        raise FileExistsError(f"refusing to overwrite layout directory: {root}")
    if result_destination.exists():
        raise FileExistsError(f"refusing to overwrite results: {result_destination}")
    if result_destination == root or root in result_destination.parents:
        raise ValueError("results JSON must be outside the layout output directory")
    if any(file == root or root in file.parents for file in source_files):
        raise ValueError("layout output directory cannot contain or replace the input data")
    root.parent.mkdir(parents=True, exist_ok=True)
    root.mkdir()

    connection = duckdb.connect()
    connection.execute(f"SET threads = {threads}")
    try:
        create_parquet_view(connection, source_files, "baseline_data")
        source = _validate_source(connection)
        baseline_fingerprint = row_fingerprint(connection, "baseline_data")
        baseline_queries = run_query_suite(connection, "baseline_data", warmups=warmups, repeats=repeats)
        variants = {
            "compacted": {"order_by": None, "ordering": "No explicit ordering; compacted copy of the source."},
            "sorted": {"order_by": SORT_ORDER, "ordering": SORT_ORDER},
            "z_ordered": {
                "order_by": f"{z_order_key_sql()}, l_orderkey, l_linenumber",
                "ordering": "Custom 2D Morton key interleaving l_shipdate (days since 1970-01-01) and l_returnflag rank A=0,N=1,R=2; tie-breakers l_orderkey,l_linenumber.",
            },
        }
        outputs: dict[str, Any] = {}
        for name, config in variants.items():
            destination = root / name
            destination.mkdir()
            duration = _copy_layout(connection, destination, config["order_by"], file_size_bytes)
            files = discover_parquet_files(destination)
            create_parquet_view(connection, files, "optimized_data")
            fingerprint = row_fingerprint(connection, "optimized_data")
            if fingerprint != baseline_fingerprint:
                raise RuntimeError(f"{name} layout did not preserve the full input rows")
            queries = run_query_suite(connection, "optimized_data", warmups=warmups, repeats=repeats)
            for query_name, baseline in baseline_queries.items():
                if queries[query_name]["result_sha256"] != baseline["result_sha256"]:
                    raise RuntimeError(f"{name} changed results for query {query_name}")
            outputs[name] = {
                "directory": str(destination),
                "ordering": config["ordering"],
                "optimization_duration_seconds": duration,
                "file_summary": summarize_files(files),
                "row_fingerprint": fingerprint,
                "query_benchmarks": queries,
            }
        payload: dict[str, Any] = {
            "schema_version": 1,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "input": {"path": str(Path(input_path).expanduser().resolve()), "file_summary": summarize_files(source_files), **source},
            "settings": {"file_size_bytes_target": file_size_bytes, **system_metadata(threads, warmups, repeats)},
            "baseline": {"row_fingerprint": baseline_fingerprint, "query_benchmarks": baseline_queries},
            "layouts": outputs,
            "notes": [
                "DuckDB has no native Z-order table-layout command; z_ordered is an explicit custom Morton-key sort, not a native DuckDB Z-order feature.",
                "FILE_SIZE_BYTES is an approximate Parquet file target and can be exceeded; reported actual file sizes are authoritative.",
                "Elapsed times use the local filesystem and OS cache; this harness does not flush caches.",
            ],
        }
    finally:
        connection.close()
    write_json_new(result_destination, payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="source Parquet file or directory")
    parser.add_argument("--output-root", type=Path, required=True, help="new directory for three layout variants")
    parser.add_argument("--results", type=Path, required=True, help="new JSON results path outside output-root")
    parser.add_argument("--file-size-bytes", type=int, default=256 * 1024)
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--threads", type=int, default=4)
    args = parser.parse_args()
    payload = build_layouts(args.input, args.output_root, args.results, file_size_bytes=args.file_size_bytes,
                            warmups=args.warmups, repeats=args.repeats, threads=args.threads)
    for name, layout in payload["layouts"].items():
        query_medians = [query["summary_seconds"]["median"] for query in layout["query_benchmarks"].values()]
        print(f"{name}: {layout['file_summary']['file_count']} files, {layout['file_summary']['total_bytes']} bytes, "
              f"optimization {layout['optimization_duration_seconds']:.4f}s, median query range "
              f"{min(query_medians):.6f}-{max(query_medians):.6f}s")
    print(f"Results: {args.results.resolve()}")


if __name__ == "__main__":
    main()
