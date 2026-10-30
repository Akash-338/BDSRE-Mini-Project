# Results notebook

Open `results_analysis.ipynb` with Jupyter and execute it from the repository root or the `notebooks/` directory. It reads the three generated JSON artifacts under the ignored `data/` directory: layout timings and file statistics, energy/cost estimates, and governance audit results. It rejects missing query results, hash mismatches, mismatched benchmark/energy medians, or a failed governance audit.

Generate the artifacts using the commands in the notebook's first cell. The notebook does not fabricate substitute results. A fresh checkout must first generate data and run the benchmark/estimate/governance commands; no benchmark output is committed. Install the optional plotting dependencies with `python -m pip install -r requirements-notebook.txt`.

For headless validation from the repository root:

```powershell
python -m nbconvert --to notebook --execute notebooks/results_analysis.ipynb --output results_analysis.executed.ipynb --output-dir data
```

The executed notebook is a local validation artifact and should not be added to Git.
