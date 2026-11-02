# Three-minute demo narration

The accompanying MP4 is a timed slide video (nine slides at 20 seconds each) with computer-generated English narration. The synthetic voice does not represent either teammate. Use this script to record your own voice-over if you prefer; play the final copy on another device before class.

The narration and video describe the historical recorded run. Current local JSON can change when the experiment commands are rerun; do not present the historical timings as the latest measurements without checking the current results. The benchmark uses DuckDB and Parquet; Spark/Delta is a separate environment smoke test.

| Time | Speaker | Script |
|---|---|---|
| 0:00-0:20 | Akash | We studied a common storage problem: streaming-style ingestion can create many tiny files, adding metadata and scan overhead. We used a small synthetic TPC-H lineitem sample so the pipeline runs locally without paid infrastructure. This is a measured prototype, not a distributed-scale claim. |
| 0:20-0:40 | Anish | The flow starts with generated rows, writes them in small batches, then runs the same query set on the fragmented baseline and on compacted, sorted, and custom Morton-ordered copies. We compare file count, stored bytes, build time, and query latency, while checking the results remain equal. |
| 0:40-1:00 | Akash | The sample contains 6,005 synthetic rows and sixteen standard lineitem fields. Writing batches of one hundred rows produced sixty-one Parquet files. We ran a full scan, a return-flag filter, and a grouped date and flag query. Each layout had one warm-up and five measured repetitions. |
| 1:00-1:20 | Anish | The baseline has sixty-one files totaling 404,691 bytes. Its median query times are about fourteen milliseconds for the scan and filter, and 18.8 milliseconds for the grouped aggregation. These timings are a local comparison point, not a cluster or production estimate. |
| 1:20-1:40 | Akash | All three optimized copies reduced the file count from sixty-one to one and cut stored bytes by about two-thirds. Compaction lowered the median for every workload in this run. Sorting and Morton ordering improved the full scan further, but their selective-query medians were slower than compaction. |
| 1:40-2:00 | Anish | The result is not that one layout always wins. Compaction was the most consistent: it improved all three medians relative to the baseline. Sorted and Morton layouts were fastest for the scan, but slower than compaction on both selective workloads. Query result hashes matched. |
| 2:00-2:20 | Akash | Energy was not measured with a power meter. We estimated it from query duration using an assumed fifty-watt whole-system draw. At an illustrative tariff of eight rupees per kilowatt-hour, costs are scenarios, not bills. Including one-time layout construction, estimated scan break-even is four, five, and ten runs. |
| 2:20-2:40 | Anish | Responsible AI evidence here is about governance and privacy scope. The data is synthetic. The audit checked allowed field names, source provenance, row counts, and checksums; all sixty-one files passed. These controls do not measure re-identification risk, so a passing audit is not a privacy guarantee. |
| 2:40-3:00 | Akash + Anish | Our conclusion is limited to this local benchmark: compaction was the most consistent option, while sorting and Morton ordering favored full scans. Next we should scale the input, vary the query mix, and test cold-cache behavior. This custom study is derived from TPC-H and is not an official result. |

## Before class

- Record the narration or speak over the video, keeping the nine 20-second sections in sequence.
- Play the final narrated copy on another device and confirm total runtime, audio level, and text readability.
- Akash and Anish: rehearse once together and divide hand-offs at the timestamps above.

