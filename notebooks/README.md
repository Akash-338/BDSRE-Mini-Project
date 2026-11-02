# Results notebook

Open `results_analysis.ipynb` with Jupyter and execute it from the repository root or the `notebooks/` directory. It searches `data/` and its subdirectories for the newest complete run, ordered by the layout JSON's last-modified time. A complete run has `layout-variants-issue7.json`, `energy-estimates-issue8.json`, and `governance-issue9.json` (or `governance-issue9-rerun.json`) in the same directory. The notebook prints the chosen paths and rejects missing query results, hash mismatches, mismatched benchmark/energy medians, or a failed governance audit. An invalid newest complete run reports an error rather than silently selecting older results.

Generate the artifacts using the commands in the notebook's first cell. The notebook does not fabricate substitute results. A fresh checkout must first generate data and run the benchmark/estimate/governance commands; no benchmark output is committed. Install the optional plotting dependencies with `python -m pip install -r requirements-notebook.txt`.

The documented pipeline refreshes its generated outputs at the same paths when rerun. Run layout comparison, energy estimation, and governance in sequence before executing the notebook, and retain copies elsewhere if historical results are needed. A standalone baseline JSON and the independent Spark/Delta smoke test are not notebook inputs.

For headless validation from the repository root:

```powershell
python -m nbconvert --to notebook --execute notebooks/results_analysis.ipynb --output results_analysis.executed.ipynb --output-dir data
```

The executed notebook is a local validation artifact and should not be added to Git.
