# Frozen Research Reproducibility

## 1. Purpose and Scope

This guide describes how to inspect and consume the public frozen formal
research product from a clean checkout. It covers delivery, verification,
environment setup, and presentation. It does not define a new analysis.

Phase 4 reproducibility does not rerun E1 inference, refresh Arena data,
support arbitrary uploaded datasets, or create a current leaderboard.

## 2. Research Interpretation

The formal product is historical, observational, model-based preference
research under a frozen Arena population. Its estimates are not objective
model capability measurements, universal user-preference claims, causal
effects, current Arena rankings, or recommendations about which model to use
today.

The [Phase 2 research contract](../phase-2/RESEARCH-CONTRACT.md) is the
interpretation authority. The [Phase 2C closeout](../phase-2/PHASE-2C-CLOSEOUT.md)
records the frozen E1 methodology, source, runs, and findings. The
[Phase 3 closeout](../phase-3/PHASE-3-CLOSEOUT.md) records the accepted
presentation, report, explorer, and application layers.

## 3. Public Frozen Bundle

The public bundle is named `formal-research-v1`.

```text
payload root: artifacts/frozen/formal-research-v1/payload
payload files: 73
payload bytes: 3,626,761
payload inventory SHA-256: 392066c7a23408e97f0f2bcd3e2a530b167e596c9b382d999d959ba49abb7eb6
source snapshot ID: 2f8937a5f46ea4c3ed4ac7d59a5e51a6b3fb9bae79918b1050c6420b34ce1fa4
formal runs: 9
comparative review: artifacts/frozen/formal-research-v1/payload/comparative_review/review.json
comparative review bytes: 89,996
comparative review SHA-256: 452192dabbb8e8ad428a023ab8bb78052688965473a2736c5be352d021f26ffa
```

The 73 files are the frozen E1 payload: nine run directories with their
finalized artifacts plus the comparative review. `bundle_manifest.json`,
`NOTICE.md`, and the CI workflow are Phase 4 delivery metadata; they are not
additional scientific evidence.

The upstream source is `lmsys/chatbot_arena_conversations`, pinned to revision
`1b6335d42a1d2c7e34870c905d03ab964f7f2bd8` and the published Parquet identity
recorded in [NOTICE.md](../../artifacts/frozen/formal-research-v1/NOTICE.md).

## 4. Canonical Environment

The supported Python policy is `>=3.12,<3.13`. The accepted reference
resolution is CPython 3.12.5 on Windows AMD64.

Runtime intent is declared in `requirements.txt`. Development/test setup is
`requirements-dev.txt`, which includes the runtime file and `pytest`.
`requirements-constraints.txt` pins the accepted 58-package resolution.
`requirements_optional.txt` is outside the canonical verification/test
environment and is not needed for this guide.

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt -c requirements-constraints.txt
.\.venv\Scripts\python -m pip check
```

POSIX shell:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt -c requirements-constraints.txt
.venv/bin/python -m pip check
```

The constraints provide version-resolution reproducibility. They are not an
E1-generation contract and do not lock package wheel hashes.

## 5. Clean-Checkout Verification

An independent reviewer can verify the public product without Arena data or
local generated outputs:

```text
git clone <repository>
cd <repository>
create the Python 3.12 virtual environment
install requirements-dev.txt with requirements-constraints.txt
run pip check
run verify_frozen_bundle.py
run the safe pytest suite
```

Windows commands:

```powershell
.\.venv\Scripts\python verify_frozen_bundle.py
.\.venv\Scripts\python -m pytest -q
```

POSIX commands:

```bash
.venv/bin/python verify_frozen_bundle.py
.venv/bin/python -m pytest -q
```

This procedure does not require Hugging Face authentication, the raw Arena
Parquet, `outputs/research`, optional requirements, E1 generation, bootstrap
reruns, or formal statistical fitting.

## 6. Canonical Verifier

Run:

```text
python verify_frozen_bundle.py
```

The canonical command performs these read-only checks:

1. required public bundle structure;
2. closed-world payload enumeration;
3. exact payload paths, sizes, SHA-256 values, and inventory digest;
4. frozen run registry and run-level artifact manifests;
5. frozen semantic loader validation;
6. complete `FrozenResearchBundle` consumption.

It does not run estimators, bootstrap generation, data acquisition, or
artifact writing. Exit codes are:

```text
0  verification passed
1  expected verification failure
2  unexpected/internal verifier error
```

A successful result reports the bundle name, payload count and size,
inventory digest, source snapshot, nine verified runs, comparative review,
and semantic validation.

## 7. Formal Application

The formal application is a presentation and inspection layer over the
verified frozen evidence:

Windows:

```powershell
.\.venv\Scripts\python -m streamlit run formal_app.py
```

POSIX:

```bash
.venv/bin/python -m streamlit run formal_app.py
```

Its default root is the tracked `artifacts/frozen/formal-research-v1/payload`
bundle. It does not require `outputs/research`, rerun E1, or produce new
estimates.

## 8. Formal vs Legacy/Demo Authority

`formal_app.py` is the formal frozen-evidence interface. `app.py`,
`run_pipeline.py --mode sample`, notebooks, and related exploratory paths are
legacy synthetic/demo or development surfaces. They remain useful for
demonstration and experimentation, but their outputs do not carry the frozen
scientific authority of E1.

## 9. Hosted Reproducibility Workflow

The committed workflow is
`.github/workflows/frozen-reproducibility.yml`. Its intended gate uses one
`ubuntu-latest` job with Python 3.12 and read-only `contents: read`
permissions. It runs on pushes to `main`, pull requests targeting `main`, and
manual `workflow_dispatch`.

The logical checks are canonical constrained installation, `pip check`, the
frozen verifier, the safe pytest suite, and `git diff --exit-code` to confirm
tracked checkout content is unchanged.

The workflow is the hosted Linux reproducibility gate. Until a hosted run on
the published Phase 4 implementation is independently accepted, this guide
does not claim hosted GitHub Actions acceptance or proven Linux portability.
Run-specific workflow identity, results, and acceptance evidence are recorded
in the Phase 4 closeout rather than in this durable guide.

## 10. Provenance and Licensing

See [NOTICE.md](../../artifacts/frozen/formal-research-v1/NOTICE.md) for the
complete source identity, citation, upstream terms, and contents boundary.
In summary, the upstream dataset identifies user prompts as CC BY 4.0 and
model outputs as CC BY-NC 4.0. The published payload contains aggregate and
statistical research derivatives only; it contains no raw prompts, raw model
responses, conversation rows, or user identifiers.

The repository MIT license applies to original repository material. It does
not supersede or relicense upstream or other third-party material.

## 11. Limitations and Non-Goals

This reproducibility contract does not:

- rerun or alter frozen E1 inference;
- refresh Arena data or establish a current leaderboard;
- establish objective model capability or universal ranking;
- establish causal effects or external generalization;
- analyze arbitrary uploaded datasets;
- make legacy/demo output formal evidence;
- lock package wheel hashes;
- claim hosted Linux verification before the hosted workflow runs.

Cross-platform binary identity of rendered Matplotlib images is not promised.

## 12. Related Records

- [Phase 2 research contract](../phase-2/RESEARCH-CONTRACT.md)
- [Phase 2C closeout](../phase-2/PHASE-2C-CLOSEOUT.md)
- [Phase 3 closeout](../phase-3/PHASE-3-CLOSEOUT.md)
- [Frozen bundle notice](../../artifacts/frozen/formal-research-v1/NOTICE.md)
