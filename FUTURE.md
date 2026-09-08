# Future Work

Ideas for extending this project beyond its current CLI-based scope:

- **GUI**: Replace the terminal CLI with an actual graphical interface (e.g. a web dashboard using Streamlit/Dash, or a desktop GUI) for interactive data exploration instead of command-line only.

## Known Issues

Problems found during a review of the current codebase:


## Reproducibility & Architecture Improvements

- **No CI workflow**: there's no `.github/workflows/` (or equivalent) running `pytest`/coverage on push or PR, so regressions aren't caught automatically before merge.
- **No containerized/environment-pinned setup**: there's no Dockerfile or `environment.yml`, so reproducing the exact runtime (Python version, OS-level deps for matplotlib/seaborn) depends entirely on the developer's local setup. A Dockerfile would make results reproducible independent of host OS.
