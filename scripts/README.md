# Ingestion pipeline scripts

## Generate synthetic source data

```powershell
python scripts\generate_tpch.py --scale-factor 0.001 --output .\data\tpch-sf001-issue3
```

## Simulate micro-batch ingestion

```powershell
python scripts\ingest_small_files.py --input .\data\tpch-sf001-issue3\lineitem.parquet --output .\data\small-files-100rows-issue4 --batch-rows 100
```

This is a sequential replay of a Parquet source, not a live stream. One Parquet file is written per batch. The output manifest records the batch size, row counts, schema, individual file sizes and SHA-256 values, aggregate fingerprints and total file-size statistics. The destination must be empty or absent; existing output is preserved and rejected. The script verifies that all source rows are represented in the output before writing the success manifest.

## Compact and compare Parquet layouts

```powershell
python scripts\compact_parquet.py --input .\data\small-files-100rows-issue4 --output .\data\compacted-256k --results .\data\compaction-256k.json --file-size-bytes 262144 --warmups 1 --repeats 5 --threads 4
```

The original input is preserved. The script writes a new compacted directory and a separate before/after JSON report. It verifies schema, row fingerprints and query-result hashes before reporting success. Existing output and result paths are refused to prevent accidental overwrite.


- `benchmark_utils.py`: shared Parquet discovery, row fingerprint, exact-result checks, and repeated query timing.
- `layout_variants.py`: writes compacted, sorted, and custom Morton-key ordered Parquet copies and benchmarks the same queries against each.

Run `python scripts/layout_variants.py --help` for options. Input data and generated results belong under the ignored `data/` directory, not in Git.


- `estimate_energy_cost.py`: derives explicitly assumed energy and hypothetical electricity costs from Issue #6 or #7 timing results; it does not claim power-meter measurements.

Run `python scripts/estimate_energy_cost.py --help` for options. Input data and generated results belong under the ignored `data/` directory, not in Git.
