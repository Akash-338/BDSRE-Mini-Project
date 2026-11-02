"""Run the repeatable TPC-H lineitem baseline query suite on Parquet files."""
from __future__ import annotations

import argparse
from pathlib import Path
import json

import duckdb

if __package__:
    from .benchmark_utils import (
        create_parquet_view,
        discover_parquet_files,
        row_fingerprint,
        run_query_suite,
        summarize_files,
        system_metadata,
        write_json_new,
    )
else:
    from benchmark_utils import (
        create_parquet_view,
        discover_parquet_files,
        row_fingerprint,
        run_query_suite,
        summarize_files,
        system_metadata,
        write_json_new,
    )


def benchmark(input_path: Path, output_path: Path, *, warmups: int = 1, repeats: int = 5, threads: int = 4) -> dict:
    if isinstance(threads, bool) or not isinstance(threads, int) or threads < 1:
        raise ValueError("threads must be a positive integer")
    files = discover_parquet_files(input_path)
    connection = duckdb.connect()
    try:
        connection.execute(f"SET threads = {threads}")
        create_parquet_view(connection, files, "benchmark_data")
        schema = [row[0] for row in connection.execute("DESCRIBE benchmark_data").fetchall()]
        payload = {
            "benchmark": "local DuckDB TPC-H lineitem baseline; not an official TPC-H result",
            "input": str(input_path.expanduser().resolve()),
            "file_layout": summarize_files(files),
            "schema": schema,
            "input_fingerprint": row_fingerprint(connection, "benchmark_data"),
            "system": system_metadata(threads, warmups, repeats),
            "queries": run_query_suite(connection, "benchmark_data", warmups=warmups, repeats=repeats),
        }
    finally:
        connection.close()
    return write_json_new(output_path, payload)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Parquet file or directory containing Parquet files")
    parser.add_argument("--output", type=Path, required=True, help="new JSON path for raw benchmark results")
    parser.add_argument("--warmups", type=int, default=1, help="warm-up runs per query (default: 1)")
    parser.add_argument("--repeats", type=int, default=5, help="measured runs per query (default: 5)")
    parser.add_argument("--threads", type=int, default=4, help="DuckDB thread count (default: 4)")
    args = parser.parse_args()
    from output_refresh import refresh_json
    if args.output.resolve() == args.input.resolve():
        raise ValueError("benchmark output cannot replace input")
    refresh_json(args.output, lambda stage: benchmark(args.input, stage, warmups=args.warmups, repeats=args.repeats, threads=args.threads))
    output = args.output.resolve()
    print(json.dumps({"results": str(output), "status": "complete"}, indent=2))


if __name__ == "__main__":
    main()
