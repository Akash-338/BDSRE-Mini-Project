"""Validate and summarize recorded layout, energy, and governance experiment JSON."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

REQUIRED_LAYOUTS = ("compacted", "sorted", "z_ordered")


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not read JSON result {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"JSON result must be an object: {path}")
    return value


def analyze(layouts: dict[str, Any], energy: dict[str, Any], governance: dict[str, Any]) -> dict[str, Any]:
    """Build traceable comparison tables and reject missing/inconsistent evidence."""
    if not isinstance(layouts.get("baseline", {}).get("query_benchmarks"), dict):
        raise ValueError("layout results are missing baseline query_benchmarks")
    baseline_queries = layouts["baseline"]["query_benchmarks"]
    if not baseline_queries:
        raise ValueError("baseline query_benchmarks is empty")
    layout_values = layouts.get("layouts")
    if not isinstance(layout_values, dict) or any(name not in layout_values for name in REQUIRED_LAYOUTS):
        raise ValueError("layout results must include compacted, sorted, and z_ordered variants")
    energy_values = energy.get("layouts")
    if not isinstance(energy_values, dict) or "baseline" not in energy_values:
        raise ValueError("energy results are missing the baseline layout")
    for layout_name in REQUIRED_LAYOUTS:
        if layout_name not in energy_values:
            raise ValueError(f"energy results are missing layout '{layout_name}'")

    query_rows: list[dict[str, Any]] = []
    all_layout_queries = {"baseline": baseline_queries}
    all_layout_queries.update({name: layout_values[name].get("query_benchmarks", {}) for name in REQUIRED_LAYOUTS})
    for layout_name, query_set in all_layout_queries.items():
        missing = sorted(set(baseline_queries) - set(query_set))
        if missing:
            raise ValueError(f"layout '{layout_name}' is missing queries: {', '.join(missing)}")
        for query_name, baseline in baseline_queries.items():
            actual = query_set[query_name]
            try:
                median = float(actual["summary_seconds"]["median"])
                runs = [float(value) for value in actual["runs_seconds"]]
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"layout '{layout_name}' query '{query_name}' has incomplete timings") from exc
            baseline_median = float(baseline["summary_seconds"]["median"])
            if (
                not math.isfinite(median)
                or not math.isfinite(baseline_median)
                or any(not math.isfinite(value) for value in runs)
                or median < 0
                or baseline_median < 0
                or any(value < 0 for value in runs)
                or not runs
            ):
                raise ValueError(f"layout '{layout_name}' query '{query_name}' has invalid timings")
            baseline_hash = baseline.get("result_sha256")
            result_hash = actual.get("result_sha256")
            hash_match = baseline_hash == result_hash if baseline_hash is not None and result_hash is not None else None
            if hash_match is False:
                raise ValueError(f"query outputs differ for '{layout_name}.{query_name}'")
            energy_query = energy_values[layout_name].get("queries", {}).get(query_name)
            if not isinstance(energy_query, dict):
                raise ValueError(f"energy results are missing query '{layout_name}.{query_name}'")
            if energy_query.get("result_hashes_match") is False:
                raise ValueError(f"energy results report mismatched query outputs for '{layout_name}.{query_name}'")
            energy_baseline_hash = energy_query.get("baseline_result_sha256")
            if baseline_hash is not None and energy_baseline_hash is not None and energy_baseline_hash != baseline_hash:
                raise ValueError(f"energy baseline hash does not match layout benchmark for '{layout_name}.{query_name}'")
            energy_layout_hash = energy_query.get("layout_result_sha256")
            if result_hash is not None and energy_layout_hash is not None and energy_layout_hash != result_hash:
                raise ValueError(f"energy layout hash does not match layout benchmark for '{layout_name}.{query_name}'")
            energy_duration = float(energy_query["median_duration_seconds"])
            if abs(energy_duration - median) > max(1e-9, abs(median) * 1e-6):
                raise ValueError(f"energy timing does not match layout benchmark for '{layout_name}.{query_name}'")
            query_rows.append({
                "layout": layout_name,
                "query": query_name,
                "median_seconds": median,
                "run_count": len(runs),
                "min_seconds": min(runs),
                "max_seconds": max(runs),
                "speedup_vs_baseline": baseline_median / median if median > 0 else None,
                "estimated_energy_wh": energy_query["assumed_query_energy_wh"],
                "hypothetical_cost_inr": energy_query["hypothetical_electricity_cost_inr_per_query"],
                "result_hash_match": hash_match,
            })

    baseline_storage = layouts.get("input", {}).get("file_summary")
    if not isinstance(baseline_storage, dict):
        raise ValueError("layout results are missing baseline input file_summary")
    storage_rows = [{"layout": "baseline", **baseline_storage, "optimization_seconds": 0.0}]
    for layout_name in REQUIRED_LAYOUTS:
        item = layout_values[layout_name]
        summary = item.get("file_summary")
        if not isinstance(summary, dict):
            raise ValueError(f"layout '{layout_name}' is missing file_summary")
        storage_rows.append({"layout": layout_name, **summary,
                             "optimization_seconds": item.get("optimization_duration_seconds")})

    governance_metrics = governance.get("measured")
    if not isinstance(governance_metrics, dict):
        raise ValueError("governance results are missing measured audit fields")
    if not governance_metrics.get("overall_passed", False):
        raise ValueError("governance audit did not pass; review findings before interpreting results")

    return {
        "source_metadata": {
            "layout_created_at_utc": layouts.get("created_at_utc"),
            "input_path": layouts.get("input", {}).get("path"),
            "rows": layouts.get("input", {}).get("rows"),
            "duckdb_version": layouts.get("settings", {}).get("duckdb_version"),
            "threads": layouts.get("settings", {}).get("duckdb_threads"),
            "warmups_per_query": layouts.get("settings", {}).get("warmups_per_query"),
            "measured_repeats_per_query": layouts.get("settings", {}).get("measured_repeats_per_query"),
            "cache_policy": layouts.get("settings", {}).get("cache_policy"),
        },
        "query_comparisons": query_rows,
        "storage_and_tuning": storage_rows,
        "governance": governance_metrics,
        "energy_assumptions": energy.get("assumptions", {}),
        "limitations": [
            "This report summarizes the supplied local JSON artifacts; it does not rerun or independently verify the underlying timings.",
            "Latency is cache-sensitive and measured on one local Windows system and sample size.",
            "Energy and electricity cost are estimates based on supplied power and tariff assumptions, not metered values.",
            "The Z-ordered label refers to the project's documented custom Morton ordering because DuckDB has no native Z-order command.",
            "A passing column/provenance governance audit is a narrow control, not a privacy guarantee.",
        ],
    }


def analyze_files(layout_path: Path, energy_path: Path, governance_path: Path) -> dict[str, Any]:
    return analyze(load_json(layout_path), load_json(energy_path), load_json(governance_path))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--layouts", required=True, type=Path)
    parser.add_argument("--energy", required=True, type=Path)
    parser.add_argument("--governance", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = args.output.expanduser().resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite results: {output}")
    result = analyze_files(args.layouts, args.energy, args.governance)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(f"Validated {len(result['query_comparisons'])} query-layout comparisons; governance passed for "
          f"{result['governance']['parquet_files']} Parquet files.")
    print(f"Summary saved to {output}")


if __name__ == "__main__":
    main()
