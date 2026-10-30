# Small Files, Compaction and Energy

Big Data Systems and Responsible AI Engineering project by Akash Kiran Vernekar (PES1UG24AM338) and Anish A Kunder (PES1UG24AM343).

## Project status

Initial project structure. The TPC-H data generator, simulated ingestion, storage optimizations, benchmarks, energy estimates, and final deliverables are not implemented yet.

## Planned architecture

```mermaid
flowchart LR
    A[TPC-H synthetic data] --> B[Simulated batch ingestion]
    B --> C[Many small files]
    C --> D[Baseline queries]
    C --> E[Compaction / sorting / Z-order]
    E --> F[Optimized queries]
    D --> G[Results and estimates]
    F --> G
    G --> H[Notebook and report]
```

The storage engine and its Z-order support remain to be selected and validated on Windows. This will be a custom experiment, not an official TPC-H benchmark.

## Windows setup and checks

This is an initial local setup, not yet a complete reproducible experiment. Git, Python 3.12, and Java 17 are required for the proposed Spark/Delta setup. Direct Python dependencies are listed in `requirements.txt`; compaction and Z-ordering still need end-to-end validation.

### Existing D: setup on Akash's laptop

Use the project checkout at `D:\BDSRE-Mini-Project` for day-to-day work. The separate tools and virtual environment are in `D:\BDSRE-Tools`. The desktop copy is separate and does not sync automatically.

In PowerShell, run this in each new session:

```powershell
. D:\BDSRE-Tools\activate-project.ps1
python --version
python -m pip check
python -m unittest discover -s tests -v
```

The helper is machine-specific and lives on D:, not in this repository. It sets Java, Python and temporary/cache paths for that session and changes to the D: checkout. If PowerShell blocks the helper, run `Set-ExecutionPolicy -Scope Process Bypass` in that session before the first command. This does not change the permanent execution policy.

Installed and smoke-tested locally: Python 3.12.10, Java 17, imports of the listed packages, a basic Spark job, and Delta table write/read. Spark reported a Windows temporary-file cleanup warning. TPC-H generation, compaction and Z-ordering have not yet been verified end to end.

### Set up another Windows computer

Install Git, Python 3.12, and a Java 17 JDK. From a PowerShell terminal in the project checkout:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

If `py` is unavailable, use the full path to a Python 3.12 executable. Set `JAVA_HOME` to the JDK directory for Spark. Delta's Java dependencies need network access on their first use. If you require all project data and caches on a specific drive, configure the environment's temporary, pip, Jupyter, Spark/Ivy and Java cache paths for that drive; package installation alone does not guarantee every program uses that drive.

The virtual environment and generated data are excluded from Git. Full pipeline commands and pinned transitive dependencies will be added after the experiment is implemented and validated.

## Planned deliverables

- Reproducible data generation, ingestion, tuning and benchmark scripts
- Results notebook and measured before/after results
- Tuning playbook and 3–5 page technical report
- Data card and evidence for a responsible AI component
- Three-minute in-class demo

No measurements or privacy guarantees are claimed at this stage.
