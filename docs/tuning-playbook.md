# Tuning playbook

## Current stage: reproduce the small-file input

1. Generate the synthetic lineitem source as described in the root README.
2. Replay it in small batches, for example `--batch-rows 100` for scale factor 0.001.
3. Keep the generated Parquet source and replay output in separate directories. The replay output is a set of one-file-per-batch Parquet objects that will serve as the small-file baseline input for later table-layout work.
4. Inspect `ingestion-manifest.json` for actual batch count, row counts, file sizes, source/output fingerprints and per-file checksums. The script fails if schema, row count or fingerprints differ.
5. Record that this is simulated sequential micro-batch replay; it is not a live stream. Report the file count actually produced. Do not claim millions of files unless that count was measured.

The manifest reports bytes on disk for each Parquet batch. It does not yet measure query latency or energy; those are separate follow-up issues.

## Current stage: compact the small-file baseline

1. Keep the original small-file Parquet directory unchanged as the baseline.
2. Choose an approximate target output file size that fits the machine and experiment. DuckDB may produce files slightly above the configured threshold.
3. Run `scripts/compact_parquet.py` with separate baseline, output and results paths. The command benchmarks the same full-scan, single-column filter, and multi-column filter/aggregation queries before and after compaction.
4. Inspect the JSON for schema and row-fingerprint preservation, query-result hashes, input/output file counts and byte distributions, raw timing runs, and one-time compaction duration.
5. Record the DuckDB/Python versions, thread counts, warm-ups and repeats. The compaction uses one writer thread so the size threshold controls file splitting; query benchmarks use the configured thread count.
6. Treat timings as warm local filesystem measurements. The process does not flush the Windows file cache. Repeat experiments under the same conditions and report variability and any cases where latency does not improve.

See [the compaction playbook](compaction-playbook.md) for the exact command, safety checks, and limitations. Results are local and Git-ignored under `data/`; regenerate them with the command instead of committing machine-specific timings.

