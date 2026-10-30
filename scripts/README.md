# Pipeline scripts

## Compact and compare Parquet layouts

```powershell
python scripts\compact_parquet.py --input .\data\small-files-100rows-issue4 --output .\data\compacted-256k --results .\data\compaction-256k.json --file-size-bytes 262144 --warmups 1 --repeats 5 --threads 4
```

The original input is preserved. The script writes a new compacted directory and a separate before/after JSON report. It verifies schema, row fingerprints and query-result hashes before reporting success. Existing output and result paths are refused to prevent accidental overwrite.