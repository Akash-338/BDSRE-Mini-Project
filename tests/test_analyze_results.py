import unittest
import json
from pathlib import Path

from scripts.analyze_results import analyze


def timing(median: float, digest: str):
    return {"summary_seconds": {"median": median}, "runs_seconds": [median * 0.9, median, median * 1.1], "result_sha256": digest}


def fixture_results():
    baseline = {"scan": timing(0.010, "rows-ok"), "filter": timing(0.020, "filter-ok")}
    layout_names = ("compacted", "sorted", "z_ordered")
    per_layout = {}
    energy_layouts = {"baseline": {"queries": {}}}
    for name, scale in zip(layout_names, (0.7, 0.5, 0.6)):
        q = {query_name: timing(values["summary_seconds"]["median"] * scale, values["result_sha256"])
             for query_name, values in baseline.items()}
        per_layout[name] = {
            "query_benchmarks": q,
            "file_summary": {"file_count": 1, "total_bytes": 900, "min_bytes": 900, "max_bytes": 900, "mean_bytes": 900},
            "optimization_duration_seconds": 0.25,
        }
        energy_layouts[name] = {"queries": {query_name: {
            "median_duration_seconds": value["summary_seconds"]["median"],
            "assumed_query_energy_wh": value["summary_seconds"]["median"] * 0.01,
            "hypothetical_electricity_cost_inr_per_query": value["summary_seconds"]["median"] * 0.00001,
        } for query_name, value in q.items()}}
    energy_layouts["baseline"]["queries"] = {query_name: {
        "median_duration_seconds": value["summary_seconds"]["median"],
        "assumed_query_energy_wh": value["summary_seconds"]["median"] * 0.01,
        "hypothetical_electricity_cost_inr_per_query": value["summary_seconds"]["median"] * 0.00001,
    } for query_name, value in baseline.items()}
    layouts = {
        "created_at_utc": "2026-10-30T12:00:00+00:00",
        "input": {"path": "sample", "rows": 10, "file_summary": {"file_count": 10, "total_bytes": 5000}},
        "settings": {"duckdb_version": "2.0.0", "duckdb_threads": 4, "warmups_per_query": 1,
                     "measured_repeats_per_query": 3, "cache_policy": "warm"},
        "baseline": {"query_benchmarks": baseline},
        "layouts": per_layout,
    }
    energy = {"layouts": energy_layouts, "assumptions": {"assumed_average_system_power_watts": 36}}
    governance = {"measured": {"overall_passed": True, "parquet_files": 10, "schema_passed_files": 10,
                                "schema_failed_files": 0, "row_count_matches": True}}
    return layouts, energy, governance


class AnalyzeResultsTests(unittest.TestCase):
    def test_builds_complete_comparison_and_includes_caveats(self):
        layouts, energy, governance = fixture_results()
        report = analyze(layouts, energy, governance)
        self.assertEqual(len(report["query_comparisons"]), 8)
        self.assertEqual(len(report["storage_and_tuning"]), 4)
        self.assertAlmostEqual(report["query_comparisons"][2]["speedup_vs_baseline"], 1 / 0.7)
        self.assertTrue(all(row["result_hash_match"] for row in report["query_comparisons"]))
        self.assertTrue(any("not metered" in item for item in report["limitations"]))

    def test_rejects_different_query_results_and_failed_governance(self):
        layouts, energy, governance = fixture_results()
        layouts["layouts"]["sorted"]["query_benchmarks"]["scan"]["result_sha256"] = "different"
        with self.assertRaisesRegex(ValueError, "query outputs differ"):
            analyze(layouts, energy, governance)
        layouts, energy, governance = fixture_results()
        governance["measured"]["overall_passed"] = False
        with self.assertRaisesRegex(ValueError, "governance audit did not pass"):
            analyze(layouts, energy, governance)

    def test_rejects_energy_benchmark_timing_mismatch(self):
        layouts, energy, governance = fixture_results()
        energy["layouts"]["z_ordered"]["queries"]["filter"]["median_duration_seconds"] += 1
        with self.assertRaisesRegex(ValueError, "timing does not match"):
            analyze(layouts, energy, governance)

    def test_notebook_is_valid_json_and_contains_traceable_analysis_cells(self):
        notebook_path = Path(__file__).resolve().parents[1] / "notebooks" / "results_analysis.ipynb"
        notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
        self.assertEqual(notebook["nbformat"], 4)
        self.assertGreaterEqual(len(notebook["cells"]), 8)
        source = "\n".join("".join(cell.get("source", [])) for cell in notebook["cells"])
        for artifact in ("layout-variants-issue7.json", "energy-estimates-issue8.json", "governance-issue9.json"):
            self.assertIn(artifact, source)
        self.assertIn("analyze_files", source)
        self.assertIn("matplotlib", source)
        self.assertIn("estimated_energy_wh", source)
        self.assertIn("hypothetical_cost_inr", source)


if __name__ == "__main__":
    unittest.main()
