# Operational Tuning Playbook

This playbook reproduces a small local comparison of Parquet layouts for the synthetic TPC-H `lineitem` workload. Commands use PowerShell from the repository root and assume the project Python environment is active. Generated data and raw JSON go under the ignored `data/` directory. The documented pipeline commands refresh generated artifacts at the same paths; use separate paths or save copies to retain prior results.

The BDSRE Small Files Layout Study is derived from the TPC-H and as such is not comparable to published TPC-H results, as the BDSRE Small Files Layout Study results do not comply with the TPC-H Specification.

## Prerequisites

- Windows 11, Python 3.12, DuckDB 2.0.0.
- About 1 GB free disk space is enough for the sample and output variants; remove old ignored `data/` experiment outputs only when you no longer need them.
- Optional notebook dependencies: `python -m pip install -r requirements-notebook.txt`.
- The DuckDB `tpch` extension must be available to the generator. On a first run it may need network access to install the extension. Keep the generated files out of Git.

Check versions and unit tests:

```powershell
python --version
python -c "import duckdb; print(duckdb.__version__)"
python -m unittest discover -s tests -v
```

## Reproduce the sample

Create a new synthetic source, then replay it in 100-row sequential micro-batches. This is a controlled streaming simulation, not a live stream.

```powershell
python scripts/generate_tpch.py --scale-factor 0.001 --output data/tpch-sf001-issue3
python scripts/ingest_small_files.py --input data/tpch-sf001-issue3/lineitem.parquet --output data/small-files-100rows-issue4 --batch-rows 100
```

Expected shape for this scale: 6,005 rows, 61 output files, with 60 batches of 100 rows and a final batch of 5. Use the generated manifests as the authority for actual file counts, checksums, and sizes. The pipeline verifies row preservation; do not extrapolate this run to millions of files.

## Record a baseline

```powershell
python scripts/benchmark_queries.py --input data/small-files-100rows-issue4 --output data/benchmark-baseline.json --warmups 1 --repeats 5 --threads 4
```

The same three queries run on each layout:

1. Full scan with row count and extended-price sum.
2. Single-column filter on `l_returnflag = 'R'`.
3. Date-range and return-flag filter followed by grouped aggregation.

The harness records every raw duration, result rows and hash, summary statistics, file sizes, hardware/software metadata, and a warm-cache policy. It does not flush the OS cache. Compare medians and spread; a handful of microsecond-scale runs on a warmed filesystem are noisy.

## Create compacted, sorted, and Morton-ordered layouts

Compaction from the same unchanged baseline:

```powershell
python scripts/compact_parquet.py --input data/small-files-100rows-issue4 --output data/compacted-256k --results data/compaction-256k.json --file-size-bytes 262144 --warmups 1 --repeats 5 --threads 4
```

Side-by-side layout comparison:

```powershell
python scripts/layout_variants.py --input data/small-files-100rows-issue4 --output-root data/layout-variants-issue7 --results data/layout-variants-issue7.json --file-size-bytes 262144 --warmups 1 --repeats 5 --threads 4
```

The sorted layout orders by `l_shipdate, l_returnflag, l_orderkey, l_linenumber`, matching the workload's date and flag predicates and then making ties deterministic. DuckDB does not provide a native Z-order table command here. The custom `z_ordered` variant interleaves a 32-bit day number and a return-flag rank into a Morton key; it is an experiment over two columns, not native or general-purpose Z-ordering. Both transformations build separate copies and check row fingerprints and all query output hashes.

DuckDB's requested `FILE_SIZE_BYTES` target is approximate. Use actual recorded sizes. Keep the baseline input unchanged while comparing layouts, and save each result set separately if comparing runs. The layout directory and JSON are published separately; rerun the stage if publication is interrupted.

## Validate governance and estimate energy

The schema/provenance audit discovers `ingestion-manifest.json` in the input folder:

```powershell
python scripts/governance_check.py --input data/small-files-100rows-issue4 --provenance data/tpch-sf001-issue3/manifest.json --output data/governance-issue9.json
```

Energy uses explicit scenario assumptions, not laptop telemetry:

```powershell
python scripts/estimate_energy_cost.py --input data/layout-variants-issue7.json --output data/energy-estimates-issue8.json --assumed-system-watts 50 --electricity-rate-inr-per-kwh 8
```

The formula is `Wh = elapsed_seconds * assumed_watts / 3600`; hypothetical rupee cost is `kWh * supplied_rate`. Direct project cash spend is reported separately (₹0 according to the team's stated constraint). Replace 50 W and ₹8/kWh with justifiable scenario assumptions for the report. Include one-time optimization duration/energy and query-specific break-even counts. A null break-even means that query did not save energy under the chosen assumption.

## Historical sample results

The following values are from an earlier local run, not necessarily the current JSON files, with 1 warm-up and 5 timed repeats per query, DuckDB 2.0.0, 4 query threads, Python 3.12.10, Windows 11, and the local warm filesystem cache. The input was 6,005 rows across 61 files and 404,691 bytes. The CPU is the team's Ryzen 7 7840HS laptop with 15.2 GB reported RAM. These are local measurements, not a distributed benchmark.

| Layout | Files | Bytes | Build seconds | Full scan median (ms) | Single filter median (ms) | Multi-filter aggregation median (ms) |
|---|---:|---:|---:|---:|---:|---:|
| Small-file baseline | 61 | 404,691 | 0 | 13.953 | 14.565 | 18.758 |
| Compacted | 1 | 138,378 | 0.043 | 2.128 | 1.956 | 2.794 |
| Sorted | 1 | 134,081 | 0.056 | 1.716 | 2.419 | 3.096 |
| Custom Morton ordering | 1 | 134,960 | 0.122 | 1.596 | 1.980 | 3.015 |

Compaction reduced the file count and all three query medians in this run. Sorting and Morton ordering had mixed query-level results relative to compaction: the full scan was lower, but both selective-query medians were higher. This sample does not support a general claim that sorting or Morton ordering improves selective queries.

With the illustrative 50 W and ₹8/kWh assumptions, one-time optimization energy was 0.000594 Wh compacted, 0.000783 Wh sorted, and 0.001697 Wh Morton-ordered. These are derived estimates, not meter readings. The current local JSON files are `data/layout-variants-issue7.json`, `data/energy-estimates-issue8.json`, and `data/governance-issue9.json`; they may describe a later run and different timings.

## Run the notebook

```powershell
python -m pip install -r requirements-notebook.txt
python -m nbconvert --to notebook --execute notebooks/results_analysis.ipynb --output results_analysis.executed.ipynb --output-dir data
```

The notebook checks that layout hashes match, energy medians match benchmark medians, and the governance audit passed before plotting. It displays latency, size/file-count, assumed energy/cost, and audit metrics. Preserve the input JSON if you need to reproduce a figure.

## Troubleshooting and limits

- **Output already exists:** pipeline commands refresh their generated outputs. Save old results to a different directory first if you need them; do not mix measurements from different runs. `analyze_results.py` still requires a new output path.
- **No Parquet files:** verify `--input` points to the source Parquet file or the intended micro-batch directory.
- **DuckDB extension unavailable:** run the generator with network access on first use or check the configured extension cache; later queries only need DuckDB.
- **Governance check fails:** read the audit JSON's `findings`, schema failed count, provenance row count, and source/file checksum results. A moved source can still be verified by an identical SHA-256 in the generator output directory.
- **Unexpected timing changes:** report raw runs, thread count, platform, warm-up count and cache policy. Rerun the whole comparison and preserve separate outputs when comparing runs; do not cherry-pick the fastest run.
- **No energy savings:** report the estimated result and break-even as null; do not force an optimization recommendation.

The experiment does not flush OS caches, measure watts, price a cloud service, model a cluster, or prove privacy. The schema allowlist cannot detect sensitive meaning in field values. Review the [data card](data-card.md) and the [TPC-H license](https://www.tpc.org/TPC_Documents_Current_Versions/txt/EULA_v2.2.0.txt) before redistributing TPC-derived materials.
