import math
import unittest

from scripts.estimate_energy_cost import estimate


def query(median: float, digest: str):
    return {"summary_seconds": {"median": median}, "result_sha256": digest}


class EnergyCostEstimateTests(unittest.TestCase):
    def setUp(self):
        self.source = {
            "baseline_queries": {
                "scan": query(360.0, "same-a"),
                "filter": query(180.0, "same-b"),
            },
            "compacted_queries": {
                "scan": query(180.0, "same-a"),
                "filter": query(180.0, "same-b"),
            },
            "optimization_duration_seconds": 360.0,
        }

    def test_energy_cost_and_break_even_known_values(self):
        result = estimate(self.source, assumed_system_watts=50, electricity_rate_inr_per_kwh=10)
        compacted = result["layouts"]["compacted"]
        self.assertAlmostEqual(compacted["assumed_optimization_energy_wh"], 5.0)
        self.assertAlmostEqual(compacted["queries"]["scan"]["assumed_query_energy_wh"], 2.5)
        self.assertAlmostEqual(compacted["queries"]["scan"]["hypothetical_electricity_cost_inr_per_query"], 0.025)
        self.assertEqual(compacted["break_even_query_count_by_workload"]["scan"], 2)
        self.assertIsNone(compacted["break_even_query_count_by_workload"]["filter"])
        self.assertTrue(compacted["queries"]["scan"]["result_hashes_match"])
        self.assertFalse(result["assumptions"]["direct_cash_cost_inr"])

    def test_reads_issue7_layout_schema(self):
        source = {
            "baseline": {"query_benchmarks": {"scan": query(10, "x")}},
            "layouts": {
                "baseline": {"query_benchmarks": {"scan": query(10, "x")}, "optimization_duration_seconds": 0},
                "sorted": {"query_benchmarks": {"scan": query(5, "x")}, "optimization_duration_seconds": 2},
            },
        }
        result = estimate(source, assumed_system_watts=20, electricity_rate_inr_per_kwh=0.0,
                          layouts=["baseline", "sorted"])
        self.assertEqual(result["layouts"]["sorted"]["break_even_query_count_by_workload"]["scan"], 1)
        self.assertEqual(result["layouts"]["sorted"]["queries"]["scan"]["hypothetical_electricity_cost_inr_per_query"], 0.0)

    def test_rejects_invalid_assumptions_or_missing_comparison(self):
        with self.assertRaisesRegex(ValueError, "watts"):
            estimate(self.source, assumed_system_watts=0, electricity_rate_inr_per_kwh=10)
        with self.assertRaisesRegex(ValueError, "tariff|rate"):
            estimate(self.source, assumed_system_watts=30, electricity_rate_inr_per_kwh=-1)
        with self.assertRaisesRegex(ValueError, "at least one optimized"):
            estimate(self.source, assumed_system_watts=30, electricity_rate_inr_per_kwh=10, layouts=["baseline"])


if __name__ == "__main__":
    unittest.main()
