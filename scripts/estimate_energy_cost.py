"""Estimate query energy and electricity cost from timings and explicit assumptions."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import statistics
from typing import Any

SECONDS_PER_HOUR = 3600.0
WH_PER_KWH = 1000.0


def _median_seconds(query: dict[str, Any], label: str) -> float:
    try:
        summary = query["summary_seconds"]
        value = float(summary["median"])
    except (KeyError, TypeError, ValueError) as exc:
        try:
            runs = [float(value) for value in query["runs_seconds"]]
            value = statistics.median(runs)
        except (KeyError, TypeError, ValueError) as nested:
            raise ValueError(f"{label} has no valid median query duration") from nested
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{label} median duration must be finite and non-negative")
    return value


def _queries_from(source: dict[str, Any], layout: str) -> dict[str, Any]:
    if layout == "baseline":
        queries = source.get("baseline_queries")
        if queries is None:
            queries = source.get("baseline", {}).get("query_benchmarks")
    elif layout == "compacted" and "compacted_queries" in source:
        queries = source.get("compacted_queries")
    else:
        queries = source.get("layouts", {}).get(layout, {}).get("query_benchmarks")
    if not isinstance(queries, dict) or not queries:
        raise ValueError(f"results file does not contain query benchmarks for layout '{layout}'")
    return queries


def _optimization_seconds(source: dict[str, Any], layout: str) -> float:
    if layout == "baseline":
        return 0.0
    value = source.get("optimization_duration_seconds")
    if value is None:
        value = source.get("layouts", {}).get(layout, {}).get("optimization_duration_seconds")
    if value is None and layout == "compacted":
        raise ValueError("results file does not contain optimization_duration_seconds")
    if value is None:
        raise ValueError(f"results file has no optimization duration for layout '{layout}'")
    seconds = float(value)
    if not math.isfinite(seconds) or seconds < 0:
        raise ValueError("optimization duration must be finite and non-negative")
    return seconds


def estimate(
    source: dict[str, Any],
    *,
    assumed_system_watts: float,
    electricity_rate_inr_per_kwh: float,
    direct_cash_cost_inr: float = 0.0,
    layouts: list[str] | None = None,
) -> dict[str, Any]:
    """Estimate energy from elapsed time and assumed average system power.

    Power is a scenario input, not measured device telemetry.  Direct cash cost
    records externally paid project spend; electricity cost is an estimate.
    """
    watts = float(assumed_system_watts)
    rate = float(electricity_rate_inr_per_kwh)
    direct_cash = float(direct_cash_cost_inr)
    if not math.isfinite(watts) or watts <= 0:
        raise ValueError("assumed system watts must be positive and finite")
    if not math.isfinite(rate) or rate < 0:
        raise ValueError("electricity rate must be non-negative and finite")
    if not math.isfinite(direct_cash) or direct_cash < 0:
        raise ValueError("direct cash cost must be non-negative and finite")

    chosen = layouts or sorted(set(source.get("layouts", {})) | {"baseline", "compacted"})
    if len(chosen) < 2 or "baseline" not in chosen:
        raise ValueError("choose baseline and at least one optimized layout")
    output: dict[str, Any] = {}
    baseline_queries = _queries_from(source, "baseline")
    for layout in chosen:
        queries = _queries_from(source, layout)
        missing_queries = sorted(set(baseline_queries) - set(queries))
        if missing_queries:
            raise ValueError(f"layout '{layout}' is missing baseline queries: {', '.join(missing_queries)}")
        duration = _optimization_seconds(source, layout)
        optimization_wh = duration * watts / SECONDS_PER_HOUR
        per_query: dict[str, Any] = {}
        for name, baseline_query in baseline_queries.items():
            optimized_query = queries[name]
            median = _median_seconds(optimized_query, f"{layout}.{name}")
            query_wh = median * watts / SECONDS_PER_HOUR
            query_kwh = query_wh / WH_PER_KWH
            per_query[name] = {
                "median_duration_seconds": median,
                "assumed_query_energy_wh": query_wh,
                "assumed_query_energy_kwh": query_kwh,
                "hypothetical_electricity_cost_inr_per_query": query_kwh * rate,
                "baseline_result_sha256": baseline_query.get("result_sha256"),
                "layout_result_sha256": optimized_query.get("result_sha256"),
                "result_hashes_match": (
                    baseline_query.get("result_sha256") == optimized_query.get("result_sha256")
                    if baseline_query.get("result_sha256") is not None and optimized_query.get("result_sha256") is not None
                    else None
                ),
            }
        output[layout] = {
            "optimization_duration_seconds": duration,
            "assumed_optimization_energy_wh": optimization_wh,
            "hypothetical_optimization_electricity_cost_inr": optimization_wh / WH_PER_KWH * rate,
            "queries": per_query,
        }

    baseline = output["baseline"]
    for layout, estimate_row in output.items():
        if layout == "baseline":
            estimate_row["break_even_query_count_by_workload"] = {name: None for name in baseline["queries"]}
            continue
        break_even: dict[str, int | None] = {}
        for name, optimized_query in estimate_row["queries"].items():
            energy_saved_wh = baseline["queries"][name]["assumed_query_energy_wh"] - optimized_query["assumed_query_energy_wh"]
            if energy_saved_wh <= 0:
                break_even[name] = None
            elif estimate_row["assumed_optimization_energy_wh"] <= 0:
                break_even[name] = 0
            else:
                break_even[name] = math.ceil(estimate_row["assumed_optimization_energy_wh"] / energy_saved_wh)
        estimate_row["break_even_query_count_by_workload"] = break_even

    return {
        "schema_version": 1,
        "estimation_method": "elapsed time multiplied by assumed average whole-system power; no power meter or device telemetry is used",
        "assumptions": {
            "assumed_average_system_power_watts": watts,
            "electricity_rate_inr_per_kwh": rate,
            "direct_cash_cost_inr": direct_cash,
            "direct_cash_cost_note": "User-reported project spend is zero; electricity cost below is a hypothetical estimate from the supplied tariff.",
            "one_time_optimization_energy_included": True,
            "break_even_definition": "ceil(one-time optimization energy / per-query energy saved), evaluated separately for each query; null means no savings.",
        },
        "layouts": output,
        "limitations": [
            "Energy values are estimates, not measurements; assumed power is not calibrated for the laptop or workload.",
            "Timings inherit the source benchmark's filesystem, warm-cache policy, thread settings, and local machine effects.",
            "Electricity cost is hypothetical and excludes billing tiers, power supply losses, cooling, and cloud charges.",
            "Break-even assumes the selected query repeats alone; a mixed workload needs query-frequency weights.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="benchmark JSON from Issue #6 or #7")
    parser.add_argument("--output", required=True, type=Path, help="new JSON output path")
    parser.add_argument("--assumed-system-watts", type=float, required=True, help="scenario assumption, not measured power")
    parser.add_argument("--electricity-rate-inr-per-kwh", type=float, required=True, help="hypothetical tariff assumption")
    parser.add_argument("--direct-cash-cost-inr", type=float, default=0.0, help="externally paid project spend; defaults to user-reported zero")
    parser.add_argument("--layouts", nargs="+", help="layouts to compare (default: all available plus baseline)")
    args = parser.parse_args()
    if args.output.expanduser().resolve().exists():
        raise FileExistsError(f"refusing to overwrite existing results: {args.output.resolve()}")
    source = json.loads(args.input.expanduser().resolve().read_text(encoding="utf-8"))
    result = estimate(source, assumed_system_watts=args.assumed_system_watts,
                      electricity_rate_inr_per_kwh=args.electricity_rate_inr_per_kwh,
                      direct_cash_cost_inr=args.direct_cash_cost_inr, layouts=args.layouts)
    destination = args.output.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(f"Saved estimates to {destination}")
    for layout, values in result["layouts"].items():
        total_queries = sum(query["assumed_query_energy_wh"] for query in values["queries"].values())
        print(f"{layout}: one-time={values['assumed_optimization_energy_wh']:.8f} Wh, "
              f"sum of one query per benchmark={total_queries:.8f} Wh (assumed {args.assumed_system_watts:g} W)")


if __name__ == "__main__":
    main()
