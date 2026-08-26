# LLM Arena User Preference Analysis

This repository is the long-term development workspace for an analysis project based on pairwise LLM preference data. It evolved from a course project; course submissions and private materials are kept outside this Git repository.

The current code provides a small, synthetic-data workflow for data cleaning, descriptive model statistics, topic labeling, visualizations, a Streamlit dashboard, and a demonstration preference classifier. It also contains the accepted Phase 2C paired-comparison estimator and bootstrap infrastructure. Phase 2 formal analysis is now closed/frozen; the durable formal-run registry, robustness findings, claim boundaries, and limitations are recorded in [docs/phase-2/PHASE-2C-CLOSEOUT.md](docs/phase-2/PHASE-2C-CLOSEOUT.md). Phase 3 has not started.

The Phase 2B research foundation is documented in [docs/phase-2/RESEARCH-CONTRACT.md](docs/phase-2/RESEARCH-CONTRACT.md) and [docs/phase-2/PHASE-2B-FOUNDATION-RESULT.md](docs/phase-2/PHASE-2B-FOUNDATION-RESULT.md). Canonical battle identity, population audit, reproducible run-manifest contracts, pinned-snapshot support audit, estimator contracts, and bootstrap infrastructure are implemented. Synthetic fixtures are for testing and reproduction only; formal empirical evidence remains bound to the published immutable baselines and finalized artifacts listed in the Phase 2C closeout.

## Quick Start

Create an isolated environment and install the declared dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt -r requirements-dev.txt
```

The commands above use the native Windows virtual-environment layout. In a
POSIX or MSYS environment, use `.venv/bin/python` instead.

Run the synthetic sample pipeline:

```powershell
.\.venv\Scripts\python run_pipeline.py --mode sample
```

Then start the dashboard:

```powershell
.\.venv\Scripts\python -m streamlit run app.py
```

The pipeline writes processed data, charts, tables, and model artifacts to ignored local paths. They are generated outputs, not source-controlled results.

## Data and Reproducibility

- `data/sample/arena_sample.csv` is a small deterministic synthetic fixture for local demos and tests. It does not contain real Arena conversations or users.
- Real/raw Arena data must not be committed. Review license, privacy, and redistribution conditions before using a new data source.
- `data/raw/`, `data/processed/`, `outputs/`, and serialized model artifacts are ignored for future development because they can be generated locally.
- The current ML workflow is a demo baseline. Its saved metrics must not be interpreted as validated real-world or research performance.

`docs/DEVELOPMENT_SAFETY.md` defines the repository safety rules. Always inspect `git status` before staging files.

## Development Checks

```powershell
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m compileall -q .
```

The repository also contains exploratory notebooks and SQL examples. Notebook output cleanup and research-method development are intentionally outside the current hygiene phase.
