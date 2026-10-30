# Tuning playbook

## Estimated energy and electricity cost

Use `scripts/estimate_energy_cost.py` with an Issue #6 compaction JSON or Issue #7 layout comparison JSON. The formula is `Wh = duration_seconds × assumed_average_system_watts / 3600`; hypothetical electricity cost is `kWh × supplied_rate`. Query and optimization durations are measured by the benchmark; watts and tariff are user-supplied assumptions. No laptop power telemetry or meter reading is used. Keep those categories separate in the report.

The estimator reports per-query energy/cost, one-time optimization energy/cost, per-query result-hash equality when available, and break-even count `ceil(one-time optimization Wh / per-query Wh saved)`. A null break-even means the layout did not save energy for that query. A real workload mix needs query-frequency weights. Direct cash spend is a separate input (default ₹0 based on the team's stated no-spend constraint); the tariff calculation is hypothetical, not a bill or cloud cost.

Example only (50 W and ₹8/kWh are scenario assumptions, not measured facts):

```powershell
python scripts/estimate_energy_cost.py `
  --input data/layout-variants-issue7.json `
  --output data/energy-estimates-issue8.json `
  --assumed-system-watts 50 `
  --electricity-rate-inr-per-kwh 8
```

There are no benchmark measurements committed to Git. Generate local result JSON files before quoting performance or energy claims; the repository ignores `data/` by design.
