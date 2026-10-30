# Ingestion pipeline scripts

## Generate synthetic source data

```powershell
python scripts\generate_tpch.py --scale-factor 0.001 --output D:\BDSRE-Tools\data\tpch-source
```

## Simulate micro-batch ingestion

```powershell
python scripts\ingest_small_files.py --input D:\BDSRE-Tools\data\tpch-source\lineitem.parquet --output D:\BDSRE-Tools\data\small-files-100rows --batch-rows 100
```

This is a sequential replay of a Parquet source, not a live stream. One Parquet file is written per batch. The output manifest records the batch size, row counts, schema, individual file sizes and SHA-256 values, aggregate fingerprints and total file-size statistics. The destination must be empty or absent; existing output is preserved and rejected. The script verifies that all source rows are represented in the output before writing the success manifest.
