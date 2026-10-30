# Tuning playbook

## Current stage: reproduce the small-file input

1. Generate the synthetic lineitem source as described in the root README.
2. Replay it in small batches, for example `--batch-rows 100` for scale factor 0.001.
3. Keep the generated Parquet source and replay output in separate directories. The replay output is a set of one-file-per-batch Parquet objects that will serve as the small-file baseline input for later table-layout work.
4. Inspect `ingestion-manifest.json` for actual batch count, row counts, file sizes, source/output fingerprints and per-file checksums. The script fails if schema, row count or fingerprints differ.
5. Record that this is simulated sequential micro-batch replay; it is not a live stream. Report the file count actually produced. Do not claim millions of files unless that count was measured.

The manifest reports bytes on disk for each Parquet batch. It does not yet measure query latency or energy; those are separate follow-up issues.
