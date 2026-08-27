# Phase 3 Closeout Record

Status: **CLOSED**

This document records the completed Phase 3 implementation and its
independent acceptance evidence. Phase 3 is CLOSED at the accepted
documentation baseline. Public synchronization remains subject to the final
push gate.

## Objective

Phase 3 - Research Results & Reproducible Reporting transforms frozen Phase 2
formal empirical evidence into provenance-preserving, uncertainty-aware,
reproducible, presentation-ready research outputs without reopening formal
inference.

The evidence flow is:

```text
frozen E1 evidence
    -> verified read-only loader
    -> normalized E2 presentation model
    -> E3 figures, tables, and report
    -> read-only formal explorer
```

Phase 3 consumes evidence; it does not create a new formal-analysis result.

## Frozen Starting Baseline

Phase 3 started from the Phase 2 public baseline:

```text
7af0bce7306573879f98b8be53bcf086f7570f83
```

Phase 3 did not reopen Phase 2 formal inference, rerun a formal seed, refresh
Arena data, or modify finalized Phase 2 artifacts.

## Scope Boundaries

The implementation contains no new estimator, bootstrap, confidence interval,
sensitivity analysis, subgroup inference, causal analysis, current Arena
refresh, current leaderboard, or arbitrary uploaded-data formal inference.

Synthetic/demo processing is a separate evidence class from frozen formal
research. The legacy `app.py` remains the synthetic/demo surface; formal
research is exposed through the independent `formal_app.py` entrypoint.

## Implementation Chain

The six Phase 3 implementation commits form a linear, non-merge chain from
the frozen baseline:

| Task | Commit | Subject |
|---|---|---|
| P3-T2 | `972ff168ba15d66b0c7cce8ea8d5c272302a4571` | `feat: add verified frozen results loader` |
| P3-T3 | `a2152aa34bac6c15909c26f667005907f351f238` | `feat: add formal presentation model` |
| P3-T4 | `8c09041359be2b2d28c8ad207b8becdb2c85b8b8` | `feat: add formal research figures` |
| P3-T5 | `f14b644ff8fc94b56ab086947f8255ebd479b083` | `feat: add reproducible formal report` |
| P3-T6a | `5f6b169cdc5c34311382f551b418bf05328f309d` | `feat: add formal results explorer model` |
| P3-T6b | `3a93447966516dc8787a2ab121cb6e2a6fb2f9d1` | `feat: add formal results explorer app` |

The implementation paths are:

```text
src/formal_results.py          verified frozen E1 loader
src/formal_presentation.py    immutable E1 -> E2 normalization
src/formal_figures.py         E2 -> E3 figure/table specifications
src/formal_report.py          deterministic E2/E3 report and Markdown
src/formal_explorer.py        immutable UI-ready explorer model
formal_app.py                 independent Streamlit composition root
```

Each implementation path has a corresponding focused test module under
`tests/`. No generated figures, tables, HTML, Markdown files, or runtime
outputs are committed by this implementation.

## Frozen Provenance

The formal evidence refers to the following pinned historical source:

```text
dataset: lmsys/chatbot_arena_conversations
revision: 1b6335d42a1d2c7e34870c905d03ab964f7f2bd8
source file: data/train-00000-of-00001-cced8514c7ed782a.parquet
source SHA-256: 3726a6352e9bfc34e206460646f6e5e99bb837751966a671ddd30c7f64e5b06e
source_snapshot_id: 2f8937a5f46ea4c3ed4ac7d59a5e51a6b3fb9bae79918b1050c6420b34ce1fa4
```

The Primary formal run is:

```text
run_id: 9c1fd5abbe8681db45b535e5368c806caad8d8297914c7b86a598112900f2689
bootstrap: 2000 attempted, 2000 successful, 0 failed
```

The frozen comparative review is:

```text
path: outputs/research/comparative_review/review.json
size: 89996 bytes
SHA-256: 452192dabbb8e8ad428a023ab8bb78052688965473a2736c5be352d021f26ffa
```

The authoritative E1 input boundary is nine frozen run directories, each
with eight finalized files, plus the comparative review: 73 files total.

## Research Presentation Facts

Under the frozen historical Arena population, the Primary point ordering
begins:

```text
1. gpt-4
2. claude-v1
3. claude-instant-v1
```

`gpt-4` has Primary point rank 1 under that frozen historical population.
This is an estimated historical preference result, not a claim that it is the
best model or a current capability leaderboard.

Across Primary, S1, S2, S3, S4, S5-ge10, S5-ge20, and S5-ge50, the frozen
point-rank ordering is preserved. S1 and S2 provide rank evidence only; their
latent scores are not numerically compared with the Primary Davidson scale.

The S6 English subgroup is classified as:

```text
PARTIALLY ROBUST / HETEROGENEOUS
top-four set: preserved
top-four order: preserved
maximum displayed rank displacement: 2
causal interpretation: NOT SUPPORTED
```

## Deliverables

Phase 3 provides:

- strict verification of the closed-world frozen formal evidence registry;
- deterministic uncertainty-aware E2 presentation records;
- claim-bounded publication figures and machine-readable tables;
- deterministic Markdown research-report generation;
- a read-only explorer semantic model with display-only filters;
- an independent Streamlit formal-results interface.

The explorer and report do not accept arbitrary artifact directories, upload
data, rerun estimators, configure bootstrap policies, refresh the current
Arena, or generate dynamic scientific interpretations. Formal input failures
are visible and fail closed; there is no demo fallback.

## Reproducibility Contract

The accepted deterministic contract is:

```text
same verified frozen input
    + same Phase 3 code/configuration
    = same presentation model
    = same publication specification
    = same formal report
    = same Markdown
    = same explorer model
```

This contract covers semantic records, specifications, ordering, labels,
captions, tables, and Markdown. Cross-platform binary identity of rendered
Matplotlib PNG files is not promised.

## Acceptance Evidence

The independent P3-T7a audit confirmed:

```text
focused formal_results:       19 passed, 1 skipped
focused formal_presentation:  15 passed
focused formal_figures:       16 passed
focused formal_report:        11 passed
focused formal_explorer:       8 passed
focused formal_app:            8 passed
full safe suite:             229 passed, 1 skipped
Python compile:              PASS
git diff --check:            PASS
```

The skipped test is the Windows symlink test, skipped because the host lacks
the required privilege (`WinError 1314`). It is an accepted host-level
limitation, not a Phase 3 correctness failure.

The real frozen pipeline produced:

```text
formal runs: 9
review entries: 9
Primary models: 20
robustness rows: 180
S6 rows: 20
provenance rows: 12
report sections: 10
report Markdown: 13,717 characters
figures: 4
frozen identities: 73 files unchanged
```

Two independent in-process builds produced equal publication packages,
reports, Markdown, and explorer models.

## Claim Boundary

The supported object is historical, observational, model-based preference
evidence within the pinned Arena population. Phase 3 does not support:

- objective model capability ranking;
- universal user-preference claims;
- causal effects of language or other covariates;
- a current Arena leaderboard;
- external generalization beyond the pinned historical dataset;
- recommendations about which model to use today.

## Formal and Demo Isolation

`formal_app.py` is the formal frozen-evidence interface. The existing `app.py`
is a legacy synthetic/demo surface and remained unchanged throughout Phase 3.
The two surfaces do not share scientific authority: demo outputs are not
formal empirical evidence, and formal evidence is not routed through the demo
data path.

## Residual Risks and Deferred Scope

Known residual risks:

1. The Windows symlink regression requires host privileges unavailable in the
   acceptance environment.
2. A failure during partial Matplotlib figure construction before runtime
   ownership is fully established remains a low-probability defensive
   hardening opportunity; no reproducible runtime failure was found.

Deferred work includes L2 German, Spanish, French, Portuguese, and Russian
audits; new methodology such as Bayesian or hierarchical models; new subgroup
inference; current Arena refreshes; arbitrary-data analysis; and deployment or
SaaS packaging. Phase 4 is **NOT STARTED**.

## Documentation Candidate Baseline

The documentation work started from:

```text
branch: main
HEAD: 3a93447966516dc8787a2ab121cb6e2a6fb2f9d1
origin/main: 7af0bce7306573879f98b8be53bcf086f7570f83
ahead/behind: 6/0
baseline worktree: clean
```

After preparing this candidate:

```text
index: empty
worktree changes are limited to:
- README.md
- docs/phase-3/PHASE-3-CLOSEOUT.md
```

No formal artifact, test, source, generated output, commit, or push was
changed or performed by the documentation candidate.
