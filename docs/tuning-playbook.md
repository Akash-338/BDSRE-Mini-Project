# Tuning playbook

## Reproduce the layout experiment

Run `scripts/layout_variants.py` against a generated small-file Parquet dataset. Use a fresh output directory and results JSON for each run. The script leaves the source unchanged and builds three copies from the same input: a compacted copy without explicit ordering, a lexicographically sorted copy, and a custom Morton-key sorted copy. It records file counts and size distribution, per-query raw timings and summaries, output fingerprints, and optimization elapsed time.

The configured sort order is `l_shipdate, l_returnflag, l_orderkey, l_linenumber`. These leading fields reflect the date and return-flag predicates in the project's representative multi-column query; the final keys make row order deterministic for ties.

## Z-order terminology and implementation

DuckDB does not provide a native Z-order layout command. The `z_ordered` variant computes a 64-bit 2D Morton key by interleaving the low 32 bits of days since 1970-01-01 and a documented return-flag rank (`A=0`, `N=1`, `R=2`), then sorts by that key with order key and line number tie-breakers. This makes an experimental locality-oriented ordering for two query columns. It is a custom Morton ordering, not a general-purpose/native Z-order implementation; conclusions must be scoped accordingly.

## Verification and interpretation

The same three queries and settings run against baseline and every layout. The runner checks a row fingerprint and each query's output hash before writing the JSON. Compare actual per-query medians, not only one aggregate. Report file count, total bytes, optimization time, warmup/repeat count, DuckDB version, thread count, platform, and cache policy from the JSON. DuckDB's `FILE_SIZE_BYTES` is an approximate target, so cite actual measured sizes. The OS cache is not flushed; local timings are cache-sensitive and are not cloud-cost measurements.

There are currently no committed benchmark results: run the command on the team's local dataset before quoting performance claims. The compaction/sort step has a one-time cost; include it in the later energy and break-even analysis rather than hiding it.
