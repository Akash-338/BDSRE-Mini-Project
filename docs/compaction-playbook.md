# Parquet compaction playbook

## What the command does

`compact_parquet.py` reads a baseline Parquet file set without modifying it, writes a separate Zstandard-compressed layout, and runs the same three lineitem queries against both layouts. DuckDB's `FILE_SIZE_BYTES` option is used as an approximate output-file threshold; Parquet files can exceed the target slightly. The command uses one writer thread for compaction so the thread count does not create extra files below the target. The output directory must be new. Keep the baseline directory intact for fair comparisons.

Before and after writes, the command records file counts and byte sizes, row count, schema, and an order-independent row fingerprint. It stops if the schema, row fingerprint, or any benchmark query result differs. It records compaction duration and per-run query timings; query timing uses the same warm-up, repeat and thread settings for both layouts.

## Reproduce

```powershell
python scripts\compact_parquet.py --input .\data\small-files-100rows-issue4 --output .\data\compacted-256k --results .\data\compaction-256k.json --file-size-bytes 262144 --warmups 1 --repeats 5 --threads 4
```

Use a different output/results name for every run because existing outputs are protected from overwrite. The file-size setting is a target, not a guaranteed exact size; DuckDB documents it as approximate and output can slightly exceed the threshold. Compare observed output sizes in the JSON. Keep DuckDB version, input, threads, query protocol, warm-up and repeat counts fixed across layouts.

## Read the results honestly

The JSON stores raw baseline and compacted timings, result hashes, input/output file statistics and one-time compaction duration. Small local inputs can be dominated by process setup and operating-system cache. The protocol does not flush the Windows file cache; these are warm local comparisons, not cold-storage or cluster measurements. Do not claim a speedup if repeated results do not support one. Cost and energy estimates are handled separately and must state their assumptions.