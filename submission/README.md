# Option A submission package

The prepared archive `PES1UG24AM338.zip` contains the complete project source snapshot and requested Option A artifacts: architecture/setup README, reproducible scripts, tests/CI, results notebook, technical report, data card, tuning playbook, and the three-minute demo video/deck/script.

The package omits generated Parquet data, raw JSON outputs, virtual environments, caches, and the course reference document. Use the included README commands to regenerate experiment data and notebook outputs.

Validation on the assembled snapshot: 31 unit tests passed in a clean Python 3.12 environment with only `duckdb==2.0.0`; the end-to-end sample generated 6,005 rows and 61 micro-batch files; the governance audit passed 61/61 files; the results notebook executed; and the Spark/Delta smoke test preserved data through compaction and Z-order (`4 -> 1 -> 1` files). The included MP4 is 180.595 seconds with computer-generated narration disclosed on its opening slide.

This archive is prepared for the team to review. It has not been uploaded through the course form. The latest presentation notice says the video will be evaluated in class and need not be in the ZIP; it is included here to satisfy the broader Option A checklist. Submit one team ZIP through the course form and retain its confirmation before 11 November 2026 EOD.
