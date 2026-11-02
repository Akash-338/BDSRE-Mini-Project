# Small Files, Compaction and Energy

Big Data Systems and Responsible AI Engineering project by Akash Kiran Vernekar (PES1UG24AM338) and Anish A Kunder (PES1UG24AM343).

## Project status

This issue implements sequential micro-batch replay of synthetic TPC-H lineitem Parquet data. It creates small files and writes an ingestion manifest with file sizes, checksums, schema, row counts, and source/output fingerprints. This is a controlled streaming simulation, not a live stream.

## Architecture

```mermaid
flowchart LR
    A[Synthetic TPC-H lineitem] --> B[Micro-batch replay]
    B --> C[Small-file Parquet layout]
    C --> D[Baseline and optimized queries]
    D --> E[Notebook, report and tuning playbook]
```

The project is a custom local workload, not an official TPC-H benchmark. It uses generated benchmark data and does not use real personal records.

## Windows setup

Prerequisites: Git, Python 3.12, and a Java 17 JDK. Open PowerShell in the repository root and choose a tools directory on the desired drive. The script keeps its virtual environment, temporary files, and package cache under `ToolsRoot`.

```powershell
.\scripts\setup-windows.ps1 -ProjectRoot (Get-Location).Path -ToolsRoot 'D:\BDSRE-Tools'
. 'D:\BDSRE-Tools\venv\Scripts\Activate.ps1'
$env:BDSRE_TOOLS_ROOT = 'D:\BDSRE-Tools'
python -m unittest discover -s tests -v
python scripts\smoke_test.py
```

The setup script checks the Python and Java versions, installs the pinned direct dependencies from `requirements.txt`, and runs `pip check`. It sets per-session Spark, Jupyter, Python and temporary paths. Use the same PowerShell session for subsequent commands. Dependency downloads and Delta's first use require network access. The initial Spark setup may print routine JVM startup messages.

### Smoke test coverage

The smoke test generates TPC-H lineitem data at scale factor 0.001 and checks its expected 6,005 rows. It then writes a synthetic Delta table in four batches, applies compaction and Z-ordering, and checks that row count and ID sum are unchanged and compaction reduces active files. It is a functional setup check, not a performance benchmark.

On the tested Windows setup, Spark 3.5.7 / Delta Lake 3.3.2 prints a shutdown warning when it cannot delete a temporary copy of a JAR that the JVM still has open. The smoke test exits successfully; data checks pass. This known Windows file-lock behavior does not indicate a failed compaction or Z-order operation. Keep temporary and Ivy cache paths on the tools drive. See [Spark issue SPARK-50628](https://issues.apache.org/jira/browse/SPARK-50628).

### Existing D: setup

Akash's current checkout is `D:\BDSRE-Mini-Project`; its local tools and virtual environment are in `D:\BDSRE-Tools`. In a new PowerShell window, run the local helper, which configures paths for this machine:

```powershell
. D:\BDSRE-Tools\activate-project.ps1
python -m unittest discover -s tests -v
python scripts\smoke_test.py
```

That helper is machine-specific and is not needed on another computer. The checked-in `scripts/setup-windows.ps1` is the teammate setup path.

## Generate and replay the data

Generate the lineitem source with the project generator:

```powershell
python scripts\generate_tpch.py --scale-factor 0.001 --output .\data\tpch-sf001-issue3
```

Replay it in batches of 100 rows:

```powershell
python scripts\ingest_small_files.py --input .\data\tpch-sf001-issue3\lineitem.parquet --output .\data\small-files-100rows-issue4 --batch-rows 100
```

The scale 0.001 sample contains 6,005 rows and produces 61 batches at 100 rows per batch. The script refuses to overwrite a non-empty output directory, checks row count, schema and row fingerprints, and writes `ingestion-manifest.json` with each file's byte size and SHA-256. Report the measured file count; do not extrapolate it to millions of files.

See [the tuning playbook](docs/tuning-playbook.md) and [script guide](scripts/README.md) for evidence and limitations. The replay is not a live streaming system.

## Run the baseline query benchmark

```powershell
python scripts\benchmark_queries.py --input .\data\small-files-100rows-issue4 --output .\data\benchmark-baseline.json --warmups 1 --repeats 5 --threads 4
```

The input can be one Parquet file or a directory tree of Parquet files with the TPC-H lineitem columns. The output JSON contains raw run timings, result rows and hashes, input/file statistics, and local system details. See [the benchmark protocol](docs/benchmark-protocol.md) for the workload and timing assumptions. The output must be new so an earlier raw result cannot be overwritten.

## Compact and compare

```powershell
python scripts\compact_parquet.py --input .\data\small-files-100rows-issue4 --output .\data\compacted-256k --results .\data\compaction-256k.json --file-size-bytes 262144 --warmups 1 --repeats 5 --threads 4
```

The baseline is preserved. The command records its file layout and raw query timings, writes a separate compacted layout with an approximate file-size target, validates schema/rows/query outputs, and records compaction duration and post-compaction timings. Read [the compaction playbook](docs/compaction-playbook.md) for cache conditions and limitations.

## Compare layouts

Generate or ingest the synthetic lineitem data using the existing pipeline scripts, then run the layout comparison against its Parquet output:

```powershell
python scripts/layout_variants.py `
  --input data/small-files-100rows-issue4 `
  --output-root data/layout-variants-issue7 `
  --results data/layout-variants-issue7.json `
  --file-size-bytes 262144 --warmups 1 --repeats 5 --threads 4
```

The output root and results JSON must be new paths. The script preserves its source and records the baseline plus compacted, sorted, and Morton-ordered layouts, actual file sizes, repeated query timings, optimization time, and equivalence checks. See [the tuning playbook](docs/tuning-playbook.md) for interpretation and limitations.

## Estimate energy and cost

For energy estimates, supply explicit assumed whole-system watts and a hypothetical electricity tariff. Neither is measured by the project.

```powershell
python scripts/estimate_energy_cost.py `
  --input data/layout-variants-issue7.json `
  --output data/energy-estimates-issue8.json `
  --assumed-system-watts 50 `
  --electricity-rate-inr-per-kwh 8
```

Replace the example 50 W and ₹8/kWh scenario inputs with values your report can justify. The estimator records direct cash project spend separately (defaults to the team's reported ₹0) and includes optimization energy and per-query break-even calculations. See [the tuning playbook](docs/tuning-playbook.md).

## Deliverables

- Reproducible data generation, ingestion, layout and benchmark scripts
- Results notebook with before-and-after measurements
- Tuning playbook and technical report
- Data card and measured governance evidence
- Three-minute in-class demo

No production-scale, measured-power, or privacy guarantees are claimed.
