# Tuning playbook

## Data governance check

After generating the source and replaying micro-batches, run `scripts/governance_check.py` with the small-file directory and the generator's `manifest.json`. The checker automatically reads `ingestion-manifest.json` from that directory when present. It verifies the approved ordered `lineitem` columns for each Parquet file, provenance fields, row count, lineage back to the generated source SHA-256, and the ingestion manifest's row/schema/file checksum records. It writes an audit JSON even when one or more checks fail and returns a nonzero exit code for failures.

An extra column should cause a schema failure. Treat the result as evidence that the declared schema and provenance are consistent; it cannot show that values are non-personal or assess re-identification risk. Do not describe this as a privacy guarantee.
