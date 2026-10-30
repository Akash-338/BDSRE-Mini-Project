# Pipeline scripts

- `benchmark_utils.py`: shared Parquet discovery, row fingerprint, exact-result checks, and repeated query timing.
- `layout_variants.py`: writes compacted, sorted, and custom Morton-key ordered Parquet copies and benchmarks the same queries against each.

Run `python scripts/layout_variants.py --help` for options. Input data and generated results belong under the ignored `data/` directory, not in Git.
