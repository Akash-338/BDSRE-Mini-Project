# Tuning playbook

## Current stage: compact the small-file baseline

1. Keep the original small-file Parquet directory unchanged as the baseline.
2. Choose an approximate target output file size that fits the machine and experiment. DuckDB may produce files slightly above the configured threshold.
3. Run `scripts/compact_parquet.py` with separate baseline, output and results paths. The command benchmarks the same full-scan, single-column filter, and multi-column filter/aggregation queries before and after compaction.
4. Inspect the JSON for schema and row-fingerprint preservation, query-result hashes, input/output file counts and byte distributions, raw timing runs, and one-time compaction duration.
5. Record the DuckDB/Python versions, thread counts, warm-ups and repeats. The compaction uses one writer thread so the size threshold controls file splitting; query benchmarks use the configured thread count.
6. Treat timings as warm local filesystem measurements. The process does not flush the Windows file cache. Repeat experiments under the same conditions and report variability and any cases where latency does not improve.

See [the compaction playbook](compaction-playbook.md) for the exact command, safety checks, and limitations. Results are local and Git-ignored under `data/`; regenerate them with the command instead of committing machine-specific timings.

## Still to implement

Sorting and Z-order layouts, end-to-end energy/cost estimates, and the results notebook remain separate project work. Do not claim energy or cash costs until their assumptions and calculations are recorded.