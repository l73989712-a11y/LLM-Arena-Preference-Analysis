# LLM Arena User Preference Analysis

This repository studies historical LLM Arena pairwise human-preference data.
The formal research product estimates preference under a frozen historical
Arena population. It is not an objective capability ranking, a universal
user-preference claim, a current Arena leaderboard, or a causal analysis.

The scientific interpretation is defined in the [Phase 2 research contract](docs/phase-2/RESEARCH-CONTRACT.md).
The accepted formal evidence history is recorded in the [Phase 2C closeout](docs/phase-2/PHASE-2C-CLOSEOUT.md),
and the presentation/report history is recorded in the [Phase 3 closeout](docs/phase-3/PHASE-3-CLOSEOUT.md).

## Current Status

- Phase 3: **CLOSED / PUBLICLY FROZEN**
- Phase 4: **CLOSED / PUBLICLY FROZEN**
- Phase 5: **CLOSED LOCALLY / PUBLIC FREEZE ON VERIFIED ORIGIN PUBLICATION**
- Phase 6: **NOT STARTED**

The Phase 4 frozen bundle, canonical verifier, reproducible dependency
constraints, clean-checkout workflow, and hosted Ubuntu acceptance are
recorded in the [Phase 4 closeout](docs/phase-4/PHASE-4-CLOSEOUT.md).

Phase 5 adds deterministic ranking-robustness evidence derived from the
immutable frozen E1 bundle. Its formal artifact, four-layer identity, bounded
historical interpretation, and independent verification evidence are recorded
in the [Phase 5 closeout](docs/phase-5/PHASE-5-CLOSEOUT.md).

The committed formal E2 artifact is:

```text
artifacts/phase-5/82239159eecc2067b7b89f9e13b9cf34d36497b8fdd7105e6babbcc2668e9a1e/
```

Verify it with:

```powershell
python -B verify_ranking_robustness.py artifacts/phase-5/82239159eecc2067b7b89f9e13b9cf34d36497b8fdd7105e6babbcc2668e9a1e
```

The formal identities are `derivation_spec_id`, `producer_git_sha`,
`artifact_instance_id`, and `e2_payload_inventory_sha256`; the closeout records
their exact values. Phase 5 is publicly frozen once the commit containing the
accepted closeout is present on `origin/main` and the post-push identity is
verified.

## Quick Reproducibility

The canonical environment supports Python `>=3.12,<3.13`. The reference
resolution was CPython 3.12.5 on Windows AMD64. Use the explicit virtual
environment interpreter after creating the environment.

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt -c requirements-constraints.txt
.\.venv\Scripts\python -m pip check
.\.venv\Scripts\python verify_frozen_bundle.py
.\.venv\Scripts\python -m pytest -q
```

POSIX shell:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt -c requirements-constraints.txt
.venv/bin/python -m pip check
.venv/bin/python verify_frozen_bundle.py
.venv/bin/python -m pytest -q
```

The verifier is read-only. A successful run confirms the tracked frozen
bundle's structure, closed-world inventory, byte identities, run manifests,
and frozen semantic consumption. It does not download Arena data or rerun
formal inference.

## Formal Application

The formal frozen-evidence interface is `formal_app.py`:

```powershell
.\.venv\Scripts\python -m streamlit run formal_app.py
```

```bash
.venv/bin/python -m streamlit run formal_app.py
```

It presents the tracked frozen evidence and does not require
`outputs/research`, regenerate E1, or produce new estimates.

The existing `app.py` and sample pipeline remain legacy synthetic/demo
surfaces. They are useful for demonstrations and exploration but do not have
the scientific authority of the formal frozen bundle.

## Data Boundary

- `data/sample/arena_sample.csv` is a deterministic synthetic fixture; it does not contain real Arena conversations or users.
- Raw Arena data is external and is not required for frozen verification.
- `requirements_optional.txt` is outside the canonical Phase 4 verification and test environment.
- Generated paths such as `outputs/` remain local/ignored outputs.

## Detailed Guide

See [Frozen Research Reproducibility](docs/reproducibility/FROZEN-RESEARCH-REPRODUCIBILITY.md)
for the public bundle identity, clean-checkout procedure, verifier contract,
formal/demo authority boundary, CI contract, provenance, licenses, and
limitations.

For upstream rights and attribution, see the [frozen bundle notice](artifacts/frozen/formal-research-v1/NOTICE.md).

## Development Checks

```powershell
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m compileall -q .
```

The repository also contains exploratory notebooks and SQL examples. They are
not part of the frozen formal verification contract.
