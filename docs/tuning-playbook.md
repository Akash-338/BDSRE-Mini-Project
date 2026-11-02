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



## Reproduce the layout experiment

Run `scripts/layout_variants.py` against a generated small-file Parquet dataset. Use a fresh output directory and results JSON for each run. The script leaves the source unchanged and builds three copies from the same input: a compacted copy without explicit ordering, a lexicographically sorted copy, and a custom Morton-key sorted copy. It records file counts and size distribution, per-query raw timings and summaries, output fingerprints, and optimization elapsed time.

The configured sort order is `l_shipdate, l_returnflag, l_orderkey, l_linenumber`. These leading fields reflect the date and return-flag predicates in the project's representative multi-column query; the final keys make row order deterministic for ties.

## Z-order terminology and implementation

DuckDB does not provide a native Z-order layout command. The `z_ordered` variant computes a 64-bit 2D Morton key by interleaving the low 32 bits of days since 1970-01-01 and a documented return-flag rank (`A=0`, `N=1`, `R=2`), then sorts by that key with order key and line number tie-breakers. This makes an experimental locality-oriented ordering for two query columns. It is a custom Morton ordering, not a general-purpose/native Z-order implementation; conclusions must be scoped accordingly.

## Verification and interpretation

The same three queries and settings run against baseline and every layout. The runner checks a row fingerprint and each query's output hash before writing the JSON. Compare actual per-query medians, not only one aggregate. Report file count, total bytes, optimization time, warmup/repeat count, DuckDB version, thread count, platform, and cache policy from the JSON. DuckDB's `FILE_SIZE_BYTES` is an approximate target, so cite actual measured sizes. The OS cache is not flushed; local timings are cache-sensitive and are not cloud-cost measurements.

There are currently no committed benchmark results: run the command on the team's local dataset before quoting performance claims. The compaction/sort step has a one-time cost; include it in the later energy and break-even analysis rather than hiding it.


## Estimated energy and electricity cost

Use `scripts/estimate_energy_cost.py` with an Issue #6 compaction JSON or Issue #7 layout comparison JSON. The formula is `Wh = duration_seconds × assumed_average_system_watts / 3600`; hypothetical electricity cost is `kWh × supplied_rate`. Query and optimization durations are measured by the benchmark; watts and tariff are user-supplied assumptions. No laptop power telemetry or meter reading is used. Keep those categories separate in the report.

The estimator reports per-query energy/cost, one-time optimization energy/cost, per-query result-hash equality when available, and break-even count `ceil(one-time optimization Wh / per-query Wh saved)`. A null break-even means the layout did not save energy for that query. A real workload mix needs query-frequency weights. Direct cash spend is a separate input (default ₹0 based on the team's stated no-spend constraint); the tariff calculation is hypothetical, not a bill or cloud cost.

Example only (50 W and ₹8/kWh are scenario assumptions, not measured facts):

```powershell
python scripts/estimate_energy_cost.py `
  --input data/layout-variants-issue7.json `
  --output data/energy-estimates-issue8.json `
  --assumed-system-watts 50 `
  --electricity-rate-inr-per-kwh 8
```

There are no benchmark measurements committed to Git. Generate local result JSON files before quoting performance or energy claims; the repository ignores `data/` by design.


## Data governance check

After generating the source and replaying micro-batches, run `scripts/governance_check.py` with the small-file directory and the generator's `manifest.json`. The checker automatically reads `ingestion-manifest.json` from that directory when present. It verifies the approved ordered `lineitem` columns for each Parquet file, provenance fields, row count, lineage back to the generated source SHA-256, and the ingestion manifest's row/schema/file checksum records. It writes an audit JSON even when one or more checks fail and returns a nonzero exit code for failures.

An extra column should cause a schema failure. Treat the result as evidence that the declared schema and provenance are consistent; it cannot show that values are non-personal or assess re-identification risk. Do not describe this as a privacy guarantee.
