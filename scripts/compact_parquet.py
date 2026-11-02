"""Compact a small-file Parquet layout and compare the same queries before/after."""
from __future__ import annotations

import argparse
from pathlib import Path
import json
import time

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


def compact_parquet(
    input_path: Path,
    output_dir: Path,
    results_path: Path,
    *,
    file_size_bytes: int = 256 * 1024,
    warmups: int = 1,
    repeats: int = 5,
    threads: int = 4,
) -> Path:
    if isinstance(file_size_bytes, bool) or not isinstance(file_size_bytes, int) or file_size_bytes < 1:
        raise ValueError("file_size_bytes must be a positive integer")
    if isinstance(threads, bool) or not isinstance(threads, int) or threads < 1:
        raise ValueError("threads must be a positive integer")
    if isinstance(warmups, bool) or not isinstance(warmups, int) or warmups < 0:
        raise ValueError("warmups must be a non-negative integer")
    if isinstance(repeats, bool) or not isinstance(repeats, int) or repeats < 1:
        raise ValueError("repeats must be a positive integer")

    input_files = discover_parquet_files(input_path)
    output = output_dir.expanduser().resolve()
    result_file = results_path.expanduser().resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing output directory: {output}")
    if result_file.exists():
        raise FileExistsError(f"refusing to overwrite existing results: {result_file}")
    if output == result_file or output in result_file.parents:
        raise ValueError("results JSON must be outside the compacted Parquet output directory")
    resolved_input = input_path.expanduser().resolve()
    if resolved_input.is_dir() and resolved_input in output.parents:
        raise ValueError("compacted output directory must be outside the baseline input directory")
    if resolved_input.is_dir() and resolved_input in result_file.parents:
        raise ValueError("results JSON must be outside the baseline input directory")
    if any(output == source or output in source.parents for source in input_files):
        raise ValueError("output directory must not contain or replace any input Parquet file")

    connection = duckdb.connect()
    try:
        connection.execute(f"SET threads = {threads}")
        create_parquet_view(connection, input_files, "baseline_data")
        schema_before = [row[0] for row in connection.execute("DESCRIBE baseline_data").fetchall()]
        fingerprint_before = row_fingerprint(connection, "baseline_data")
        if fingerprint_before["rows"] == 0:
            raise ValueError("cannot compact an empty Parquet layout")
        baseline_queries = run_query_suite(
            connection, "baseline_data", warmups=warmups, repeats=repeats
        )

        output.parent.mkdir(parents=True, exist_ok=True)
        copy_sql = (
            "COPY (SELECT * FROM baseline_data) TO "
            f"'{output.as_posix().replace(chr(39), chr(39) * 2)}' "
            "(FORMAT PARQUET, COMPRESSION ZSTD, "
            f"FILE_SIZE_BYTES {file_size_bytes}, PER_THREAD_OUTPUT, "
            "FILENAME_PATTERN 'part-{i}.parquet')"
        )
        connection.execute('SET threads = 1')
        started = time.perf_counter()
        connection.execute(copy_sql)
        compaction_seconds = time.perf_counter() - started
        connection.execute(f'SET threads = {threads}')

        compacted_files = discover_parquet_files(output)
        create_parquet_view(connection, compacted_files, "compacted_data")
        schema_after = [row[0] for row in connection.execute("DESCRIBE compacted_data").fetchall()]
        fingerprint_after = row_fingerprint(connection, "compacted_data")
        if schema_before != schema_after:
            raise RuntimeError(f"schema changed during compaction: {schema_before} != {schema_after}")
        if fingerprint_before != fingerprint_after:
            raise RuntimeError(
                f"row preservation check failed: {fingerprint_before} != {fingerprint_after}"
            )
        compacted_queries = run_query_suite(
            connection, "compacted_data", warmups=warmups, repeats=repeats
        )
        query_results_equal = {
            name: baseline_queries[name]["result_sha256"] == compacted_queries[name]["result_sha256"]
            for name in baseline_queries
        }
        if not all(query_results_equal.values()):
            raise RuntimeError(f"query outputs changed during compaction: {query_results_equal}")

        payload = {
            "experiment": "DuckDB Parquet compaction; local custom workload, not an official TPC-H result",
            "input": str(input_path.expanduser().resolve()),
            "output": str(output),
            "configuration": {
                "file_size_bytes_target": file_size_bytes,
                "file_size_target_is_approximate": True,
                "compaction_writer_threads": 1,
                "compression": "ZSTD",
                "duckdb_threads": threads,
                "warmups_per_query": warmups,
                "measured_repeats_per_query": repeats,
            },
            "system": system_metadata(threads, warmups, repeats),
            "schema_before": schema_before,
            "schema_after": schema_after,
            "source_fingerprint": fingerprint_before,
            "compacted_fingerprint": fingerprint_after,
            "row_preservation_verified": fingerprint_before == fingerprint_after,
            "query_results_equal": query_results_equal,
            "optimization_duration_seconds": compaction_seconds,
            "baseline_layout": summarize_files(input_files),
            "compacted_layout": summarize_files(compacted_files),
            "baseline_queries": baseline_queries,
            "compacted_queries": compacted_queries,
        }
    finally:
        connection.close()
    return write_json_new(result_file, payload)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="baseline Parquet file or directory")
    parser.add_argument("--output", type=Path, required=True, help="new directory for compacted Parquet files")
    parser.add_argument("--results", type=Path, required=True, help="new JSON path for before/after metrics")
    parser.add_argument("--file-size-bytes", type=int, default=256 * 1024, help="approximate target Parquet file size")
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--threads", type=int, default=4)
    args = parser.parse_args()
    output = compact_parquet(
        args.input,
        args.output,
        args.results,
        file_size_bytes=args.file_size_bytes,
        warmups=args.warmups,
        repeats=args.repeats,
        threads=args.threads,
    )
    print(json.dumps({"results": str(output), "status": "complete"}, indent=2))


if __name__ == "__main__":
    main()