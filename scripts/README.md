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
