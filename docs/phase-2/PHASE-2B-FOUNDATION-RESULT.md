# Phase 2B Foundation Result

## A. Scope

Phase 2B established and documented the engineering foundation and pinned-snapshot policy for uncertainty-aware, bias-audited pairwise LLM preference research. It did not implement a ranking estimator or produce preference results.

## B. Accepted Tasks

```text
T1  source/schema audit: PASS WITH EXTERNAL DATA-ACCESS BLOCK
T2  canonical battle contract: ACCEPTED
T2a canonical semantic correction: ACCEPTED
T3  population specifications: ACCEPTED
T3a exclusion-audit correction: ACCEPTED
T4  reproducible run manifest: ACCEPTED
T4a manifest provenance-integrity correction: ACCEPTED
T5  documentation closeout: ACCEPTED
T6  Hugging Face access recovery: ACCEPTED — ACCESS READY
T7  read-only real-data support audit: ACCEPTED
T8  real-data parameter freeze and anonymous population contract: IMPLEMENTED / PENDING GPT ACCEPTANCE
```

## C. Implementation Commits

The accepted implementation chain is:

```text
d1d998656f34eff1cb691aecd7aeb084567dcf5c  feat: add canonical battle data contract
6978357854a36f7b66febdbb9464873cef711b40  fix: preserve canonical battle semantics
007f3b3caf41fc8a331f3e9cbe203a40715e98b5  feat: add research population specifications
c01c46232969846c62a9e8eaf8580d91d1c693ac  fix: clarify population exclusion reasons
077f09ce95f4e69da6915455caeace9ad885913d  feat: add reproducible run manifest
c641828c9670bca846f01fcddbd05ef74b91673f  fix: validate run manifest provenance
```

The T5 documentation closeout commit is:

```text
4ba208236068b6c6c9a9b598f59a13a9037a94bc  docs: close phase 2b research foundation
```

The subsequent T5a documentation-state correction is recorded separately in Git history.

## D. Implemented Foundation

```text
lossless canonical battle representation
stable source and battle identity
explicit validity flags
canonical outcome taxonomy
versioned population specifications
multi-reason exclusion audit
deterministic reproducible run manifest
source_snapshot_id -> run_id provenance integrity
anonymous/blinded population requirement
snapshot-bound support and sensitivity policy
```

## E. Validation

The foundation test suite and T5 documentation checks are run with the project virtual environment:

```text
pytest: 39 passed
compileall: PASS
git diff --check: PASS
synthetic sample pipeline: PASS
```

The synthetic sample pipeline is permitted for local reproduction with:

```text
PYTHONIOENCODING=utf-8 .\\.venv\\Scripts\\python.exe run_pipeline.py --mode sample --skip-kmeans --skip-ml
```

It does not access the real dataset. Generated data, tables, charts, and model outputs remain ignored local artifacts.

## F. Real-Data Parameter Freeze

The exact pinned snapshot is `lmsys/chatbot_arena_conversations`, revision `1b6335d42a1d2c7e34870c905d03ab964f7f2bd8`, with SHA-256 `3726a6352e9bfc34e206460646f6e5e99bb837751966a671ddd30c7f64e5b06e` and 33,000 rows. T6 confirmed authenticated access and T7 completed a read-only outcome-blind support audit.

T7 evidence supports retaining all 20 models and all observed 190 pairs in the primary connected component, retaining repeated question IDs as distinct battles, retaining exact duplicates, using pair-support sensitivities at 10/20/50, using English as the formal language subgroup, treating other language tiers as exploratory or descriptive, and retaining high-activity judges for primary analysis. Judge-cluster bootstrap remains primary uncertainty, battle-row bootstrap is sensitivity, with 95% confidence and a target of at least 2,000 replicates.

## G. Deferred Work

```text
final GPT closeout of the Phase 2B parameter freeze
Bradley-Terry estimator
final tie-aware estimator decision
judge-cluster bootstrap
battle-row bootstrap sensitivity
language heterogeneity analysis
validated topic taxonomy
formal result/claim manifest
```

## H. Phase Status

```text
Phase 2A: CLOSED / FROZEN
Phase 2B Foundation: IMPLEMENTED / DOCUMENTED
Phase 2B real-data parameter freeze: IMPLEMENTED / FROZEN
Phase 2C estimator work: NOT STARTED
```

```text
Phase 2B: READY FOR FINAL GPT CLOSEOUT
```

This document does not declare the whole research project complete, does not authorize real-data conclusions before estimator implementation, and does not start Phase 2C.
