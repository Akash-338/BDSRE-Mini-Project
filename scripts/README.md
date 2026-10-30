# Pipeline scripts

- `governance_check.py`: checks approved synthetic lineitem schema, provenance and optional ingestion-manifest integrity.

Use `python scripts/governance_check.py --help` to see inputs. The audit output belongs in ignored `data/`; it records failed checks as well as passes. A passing schema audit is not a privacy guarantee.
