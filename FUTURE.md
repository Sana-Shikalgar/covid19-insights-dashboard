# Future Work

Ideas for extending this project beyond its current CLI-based scope:

- **GUI**: Replace the terminal CLI with an actual graphical interface (e.g. a web dashboard using Streamlit/Dash, or a desktop GUI) for interactive data exploration instead of command-line only.

## Reproducibility & Architecture Improvements

Considered and deliberately deferred until the project's scope grows past a single-developer CLI tool:

- **Packaging metadata** (`pyproject.toml`/`setup.py`): would let the project be `pip install -e .`'d and used as a library instead of only working when scripts are run from the repo root (relying on `src.*` imports resolving via CWD). Not worth the overhead while it's a standalone CLI run from the repo root.
- **CI workflow** (`.github/workflows/` or equivalent running `pytest`/coverage on push or PR): useful once there are multiple contributors or branches to protect; not providing much value against a single-branch, single-author repo.
- **Containerized setup** (Dockerfile/`environment.yml`): would pin the exact runtime (Python version, OS-level deps for matplotlib/seaborn) independent of host OS. Not worth maintaining without a deployment target or a second developer's environment to reconcile against.

## Privacy / PII to Clean Up

PII previously found in this repo's files and commit history has been resolved via a git history rewrite.
