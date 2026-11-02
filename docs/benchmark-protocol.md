# Baseline benchmark protocol

## Workload

The harness expects the TPC-H `lineitem` Parquet schema. It runs three fixed queries against the same discovered Parquet file set:

1. A full scan that counts rows and sums `l_extendedprice`.
2. A single-column filter on `l_returnflag` with the same aggregates.
3. A date and return-flag filter followed by aggregation on return flag and line status.

The SQL and result rows are saved with the measurements. A SHA-256 digest of each query result and an order-independent input row fingerprint make it possible to check that later layouts return equivalent data.

## Timing conditions

By default each query gets one warm-up and five measured runs. Timing covers query execution and fetching the small aggregate result, measured with Python's monotonic performance counter. The report records every raw duration and min, median, mean, max and sample standard deviation. Use the same input, thread count, warm-up count and repeat count for every layout comparison.

The harness does not flush the Windows filesystem cache. Runs therefore represent local repeated access with operating-system caching, not cold-storage latency. Warm-ups are reported separately. Do not compare runs with different cache conditions as if they were equivalent.

## Environment and layout

Every JSON result records DuckDB and Python versions, OS, processor string, logical CPU count, thread setting, query/run counts, file count, per-file bytes and aggregate size statistics. Before sharing a result, record any system load or power mode that could affect timing. The harness records no electricity use or cash cost; those estimates belong to the later energy/cost issue and must state their assumptions.

## Reproduce

```powershell
python scripts\benchmark_queries.py --input .\data\small-files-100rows-issue4 --output .\data\benchmark-baseline.json --warmups 1 --repeats 5 --threads 4
```

The results path must not already exist. Raw data and measurements are local under the ignored `data/` directory; regenerate the source with the documented TPC-H generator when needed. These are local custom-workload measurements, not official TPC-H benchmark results.