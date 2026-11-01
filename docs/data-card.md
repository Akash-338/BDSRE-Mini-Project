# Data Card for a Dataset Derived from TPC-H

## Summary

This project uses a small synthetic `lineitem` table to measure how Parquet file layout affects a fixed local query workload. The data was generated with DuckDB's `tpch` extension at scale factor 0.001. The recorded sample contains 6,005 rows and 16 columns. It contains generated benchmark values, not records collected from people.

The BDSRE Small Files Layout Study is derived from the TPC-H and as such is not comparable to published TPC-H results, as the BDSRE Small Files Layout Study results do not comply with the TPC-H Specification.

## Provenance and terms

- Generator: DuckDB `tpch` extension `dbgen`; the generator output manifest records the DuckDB version, scale factor, row count, schema, compression, and SHA-256.
- Table: TPC-H `lineitem`, exported to Parquet with ZSTD compression and replayed into small Parquet micro-batches.
- Source documentation: [DuckDB TPC-H extension](https://duckdb.org/docs/current/core_extensions/tpch).
- TPC-H is not described here as openly licensed. TPC lists its tools as available without charge but requires users to register and agree to the [TPC End User License Agreement, version 2.2](https://www.tpc.org/TPC_Documents_Current_Versions/txt/EULA_v2.2.0.txt). The EULA limits use and distribution of TPC Materials and allows certain academic/research disclosure subject to conditions. This project generates rows through DuckDB's implementation rather than bundling the TPC tools. Review the applicable terms before redistributing generated data or TPC-derived material; this repository omits the generated Parquet files.
- TPC's [Fair Use Quick Reference](https://www.tpc.org/TPC_Documents_Current_Versions/pdf/Fair_Use_Quick_Reference_v1.0.0.pdf) requires derived workloads/results to be clearly identified, disclaimed as non-comparable to official results, and sufficiently disclosed. The disclaimer above is included wherever project results are presented.

## Schema and minimization

The experiment reads only the standard 16 TPC-H lineitem columns: `l_orderkey`, `l_partkey`, `l_suppkey`, `l_linenumber`, `l_quantity`, `l_extendedprice`, `l_discount`, `l_tax`, `l_returnflag`, `l_linestatus`, `l_shipdate`, `l_commitdate`, `l_receiptdate`, `l_shipinstruct`, `l_shipmode`, and `l_comment`. The sample contains no direct identifiers by design. No external or personal dataset is joined to it.

## Responsible AI and governance control

The narrow governance control compares each Parquet file's ordered column names to the approved allowlist, checks generator provenance and row counts, and can validate the ingestion manifest's source and file checksums. The audit writes the number of files that passed and failed. On the recorded run, 61 of 61 files passed, observed rows matched the 6,005-row provenance manifest, and the source SHA-256 lineage check passed. Deliberately non-compliant test fixtures are also rejected.

This schema/provenance check cannot establish that every value is non-personal, detect every sensitive value, measure re-identification risk, or guarantee privacy. It is evidence for one governance control only.

## Collection, use, and sharing

The table is generated locally and is used only for this course experiment. Input Parquet data and full local benchmark outputs live under the Git-ignored `data/` directory and are regenerated with the project scripts. The repository contains scripts and documentation rather than the generated dataset. Do not publish a TPC-derived performance result as an official TPC-H result.

## Limitations

- Scale factor 0.001 is a laptop-sized sample; it does not represent a distributed production workload or millions of files.
- Synthetic data does not model the full variety, errors, or privacy concerns of real operational data.
- The allowlist audits names, provenance, and integrity; it does not perform a content-level privacy analysis.
- Measurements depend on the local Windows machine, DuckDB version, thread count, and warm OS cache.
- DuckDB has no native Z-order command in this experiment. The `z_ordered` layout is a documented custom Morton ordering of date and return-flag values.
