# Future Work

Ideas for extending this project beyond its current CLI-based scope:

- **GUI**: Replace the terminal CLI with an actual graphical interface (e.g. a web dashboard using Streamlit/Dash, or a desktop GUI) for interactive data exploration instead of command-line only.

## Known Issues

Problems found during a review of the current codebase:

- **Inconsistent CLI error handling**: in `cli_dashboard.py`, menu choices "6", "7", "8" wrap their operations in try/except, but choices "2" (filter/fetch) and "9" (read with limit) do not. Bad input (invalid filter column, wrong date format, non-numeric limit) raises an uncaught exception and crashes the whole CLI session instead of returning to the menu.
- **`bulk_insert` is not bulk**: `src/db_engine.py:184-229` opens and commits a brand-new SQLAlchemy session for every single record in the input list. This will be very slow on the full OWID dataset (hundreds of thousands of rows) and defeats the purpose of a "bulk" operation.
- **`data_analyzer.py` is effectively dead code**: `cli_dashboard.py:11` imports `run_analysis` from `src.data_analyzer` but comments it out, and the plotting menu (choice "4") hardcodes its own inline `groupby`/column logic instead of calling `generate_grouped_summary`/`generate_time_trend`. The analysis module is unit-tested but never actually exercised by the application.
- **`fig.show()` won't render headlessly**: `cli_dashboard.py` calls `fig.show()` after building plots (choice "4"). On a machine/container without a GUI-capable matplotlib backend (common in CI, Docker, or SSH sessions), this silently does nothing — there's no `savefig()` fallback to write the plot to disk.
- **Stale docstring in `data_visualization.py`**: `src/data_visualization.py:3` describes the module as "Creates matplotlib figures for Streamlit/Flask web applications," but no Streamlit/Flask integration exists anywhere in the repo — the only consumer is the CLI's `fig.show()`.
- **Stale file-path comment in `data_cleaner.py`**: `src/data_cleaner.py:1` still has a header comment `# src/data_cleaning.py`, the file's old name.

## Reproducibility & Architecture Improvements

- **Pin dependency versions**: `requirements.txt` uses open-ended `>=` bounds for every package (pandas, sqlalchemy, matplotlib, seaborn, numpy, pytest). A future pandas/numpy release could silently change groupby/resample or dtype behavior used in `data_analyzer.py` and `helper_data_cleaning.py`. Pin exact versions (or add a lockfile) so installs are reproducible across machines and time.
- **Document how to get the full dataset**: the README notes only a 15K-row subset of `data/raw/owid-covid-data.csv` ships in the repo (Git LFS size limits), and links the full source, but doesn't document where to place a full download so `PipelineConfig.RAW_CSV_PATH` in `src/pipeline_integration.py` picks it up. Add explicit steps (or a small download script) to the README/Installation section.
- **No packaging metadata**: there's no `pyproject.toml`/`setup.py`, so the project can't be `pip install -e .`'d and only works if scripts are run from the repo root (relying on `src.*` imports resolving via CWD). Adding packaging metadata would make the project usable as a library and installable in other environments.
- **No CI workflow**: there's no `.github/workflows/` (or equivalent) running `pytest`/coverage on push or PR, so regressions aren't caught automatically before merge.
- **No containerized/environment-pinned setup**: there's no Dockerfile or `environment.yml`, so reproducing the exact runtime (Python version, OS-level deps for matplotlib/seaborn) depends entirely on the developer's local setup. A Dockerfile would make results reproducible independent of host OS.
- **Plot export option**: given the headless `fig.show()` limitation above, add a "save to file" option in the CLI plotting menu (e.g. `fig.savefig(...)`) so generated charts are usable/reproducible outside an interactive session — this would also benefit a future GUI/web version.
