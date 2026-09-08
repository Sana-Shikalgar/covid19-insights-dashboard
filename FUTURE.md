# Future Work

Ideas for extending this project beyond its current CLI-based scope:

- **GUI**: Replace the terminal CLI with an actual graphical interface (e.g. a web dashboard using Streamlit/Dash, or a desktop GUI) for interactive data exploration instead of command-line only.

## Known Issues

Problems found during a review of the current codebase:


## Reproducibility & Architecture Improvements

- **Pin dependency versions**: `requirements.txt` uses open-ended `>=` bounds for every package (pandas, sqlalchemy, matplotlib, seaborn, numpy, pytest). A future pandas/numpy release could silently change groupby/resample or dtype behavior used in `data_analyzer.py` and `helper_data_cleaning.py`. Pin exact versions (or add a lockfile) so installs are reproducible across machines and time.
- **Document how to get the full dataset**: the README notes only a 15K-row subset of `data/raw/owid-covid-data.csv` ships in the repo (Git LFS size limits), and links the full source, but doesn't document where to place a full download so `PipelineConfig.RAW_CSV_PATH` in `src/pipeline_integration.py` picks it up. Add explicit steps (or a small download script) to the README/Installation section.
- **No packaging metadata**: there's no `pyproject.toml`/`setup.py`, so the project can't be `pip install -e .`'d and only works if scripts are run from the repo root (relying on `src.*` imports resolving via CWD). Adding packaging metadata would make the project usable as a library and installable in other environments.
- **No CI workflow**: there's no `.github/workflows/` (or equivalent) running `pytest`/coverage on push or PR, so regressions aren't caught automatically before merge.
- **No containerized/environment-pinned setup**: there's no Dockerfile or `environment.yml`, so reproducing the exact runtime (Python version, OS-level deps for matplotlib/seaborn) depends entirely on the developer's local setup. A Dockerfile would make results reproducible independent of host OS.
