# Pipeline scripts

Run commands from the repository root with the project's Python 3.12 environment active. The generation, ingestion, benchmark, compaction, layout, energy, and governance commands refresh their generated outputs when rerun; preserve a copy elsewhere if you need earlier results.

| Script | Purpose |
|---|---|
| `generate_tpch.py` | Generate synthetic TPC-H `lineitem` Parquet and a provenance manifest. |
| `ingest_small_files.py` | Replay lineitem rows in sequential micro-batches and write a checksum manifest. |
| `benchmark_queries.py` | Measure baseline full-scan and filter workloads with raw repeated timings. |
| `compact_parquet.py` | Compact one Parquet source and compare before/after query results and timings. |
| `layout_variants.py` | Compare compacted, sorted, and custom Morton-ordered output layouts. |
| `estimate_energy_cost.py` | Estimate energy and tariff cost from timings and explicit assumptions. |
| `governance_check.py` | Check an allowlisted schema, generator provenance, row count, and optional ingestion checksums. |
| `analyze_results.py` | Validate benchmark, energy, and audit JSON consistency for the results notebook. |
| `output_refresh.py` | Stage command-line outputs and replace known generated artifacts on successful reruns. |
| `smoke_test.py` | Exercise Spark/Delta independently of the benchmark; download pinned Delta JARs into a unique run directory and load them on Spark's classpath. |

Use `python scripts/<name>.py --help` for command-line arguments; `output_refresh.py` is a shared helper, not a command. The refreshed directory and its JSON are published separately, so rerun a stage if publication is interrupted. `analyze_results.py` still requires a new output path. The governance audit is a narrow control, not a privacy guarantee. Generated Parquet files and result JSON belong in the ignored `data/` directory.
