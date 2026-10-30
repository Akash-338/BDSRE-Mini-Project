# Data card: TPC-H synthetic lineitem

## Status
Implemented. Generated locally for this project; no real personal records are used.

## Source and provenance
- Benchmark: TPC-H relational benchmark, generated with DuckDB's `tpch` extension `dbgen` function.
- Generator: DuckDB Python package version is written to each output's `manifest.json`.
- The course dataset list names GH Archive and NYC TLC for this topic. We use generated TPC-H data as a comparable public, reproducible benchmark substitution because the course prohibits real personal data and the project studies file layout rather than mobility or GitHub activity.
- DuckDB documents that its TPC-H extension generator may differ slightly from the official TPC-H specification. This project is a custom experiment and must not be presented as an official TPC-H result.

## Data contents
Only the TPC-H `lineitem` table is exported. The output is one Zstandard-compressed Parquet file plus a JSON manifest containing scale factor, row count, columns, DuckDB version, intended use, privacy note and SHA-256 digest. At scale factor 0.001 the expected row count is 6,005. The generator validates column names and row count after writing and reading the Parquet file.

Columns: `l_orderkey`, `l_partkey`, `l_suppkey`, `l_linenumber`, `l_quantity`, `l_extendedprice`, `l_discount`, `l_tax`, `l_returnflag`, `l_linestatus`, `l_shipdate`, `l_commitdate`, `l_receiptdate`, `l_shipinstruct`, `l_shipmode`, `l_comment`.

## License and access
The data is generated locally; no dataset download or account is required. TPC-H is a trademarked benchmark, and the TPC specification and generation tools have terms that must be checked before redistribution. DuckDB's bundled TPC-H extension was removed from current DuckDB releases; this project installs the DuckDB community `tpch` extension from the configured extension repository. Confirm current generator and extension terms before publishing generated files. The submitted repository should include the regeneration command and manifest, not large generated datasets unless the course explicitly requests them.

## Intended use
Teach and measure a custom small-file and file-layout workload: micro-batch ingestion, query latency, compaction, sorting and Z-ordering.

## Privacy, limitations and checks
- Generated benchmark rows do not originate from real people. TPC-H contains fictional business entities and textual comments; do not interpret this as a formal privacy guarantee.
- Tests verify the expected schema, scale-0.001 row count, Parquet round-trip, output digest and safe refusal to overwrite a non-empty directory.
- Scale factor 0.001 is a functional sample, not sufficient for general performance conclusions. Larger scales must be chosen based on available disk and memory.
- DuckDB's generator may have minor differences from official TPC-H data generation. Record generator/package version and scale factor for every run.
