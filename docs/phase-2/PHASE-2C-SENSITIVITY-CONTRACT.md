# Phase 2C Sensitivity Analysis Contract

## Status and Scope

This document freezes the sensitivity-analysis contract for the accepted first
formal primary run. It is design-only: T13 does not execute a sensitivity,
consume a sensitivity seed, rerun the primary, or interpret any sensitivity
result.

The immutable primary identity is:

```text
Git SHA: 2dad21a4816931b0dddf4ae77282ffde1c713512
source SHA: 3726a6352e9bfc34e206460646f6e5e99bb837751966a671ddd30c7f64e5b06e
source snapshot ID: 2f8937a5f46ea4c3ed4ac7d59a5e51a6b3fb9bae79918b1050c6420b34ce1fa4
primary seed: 15832207067816131242
primary run_id: 9c1fd5abbe8681db45b535e5368c806caad8d8297914c7b86a598112900f2689
status: COMPLETE - INFERENCE VALID
```

The primary run directory is immutable and no sensitivity artifact may be
written below it.

## Classification

- **FORMAL ROBUSTNESS:** S1 coalesced ties, S2 decisive Bradley-Terry, S3
  battle-row bootstrap, S4 repeated-question exclusion.
- **SECONDARY ROBUSTNESS:** S5 pair-support thresholds at 10, 20, and 50.
- **FORMAL HETEROGENEITY:** S6 English subgroup.
- **EXPLORATORY HETEROGENEITY:** German, Spanish, French, Portuguese, and
  Russian language audits. They remain audit-only until a later task authorizes
  inference.

Formal robustness and formal heterogeneity runs use 2,000 fixed attempts.
Secondary pair-support runs also use 2,000 attempts for comparable uncertainty
evidence. No 20/50/100-attempt result is formal robustness evidence.

## Central Execution Matrix

| ID | Purpose | Changed axis | Estimator | Population view | Bootstrap | Replicates | Class | Readiness |
|---|---|---|---|---|---|---:|---|---|
| S1-COALESCED-TIES | tie-policy sensitivity | effective tie policy only | `davidson_coalesced_ties` | `base_research` | `judge_cluster` | 2000 | formal robustness | READY BY CONFIG |
| S2-DECISIVE-BT | decisive-only estimator | estimator and outcome policy only | `bradley_terry_decisive` | `base_research` | `judge_cluster` | 2000 | formal robustness | READY BY CONFIG |
| S3-ROW-BOOTSTRAP | dependence-unit sensitivity | resampling unit only | `davidson` | `base_research` | `battle_row` | 2000 | formal robustness | READY BY CONFIG |
| S4-REPEATED-QID-EXCLUSION | repeated-question sensitivity | whole repeated-`question_id` groups excluded | `davidson` | named repeated-qid exclusion view | `judge_cluster` | 2000 | formal robustness | READY BY VIEW TOOLING |
| S5-PAIR-GE10 | low-support robustness | pair support threshold only | `davidson` | named pair-support >=10 view | `judge_cluster` | 2000 | secondary robustness | READY BY VIEW TOOLING |
| S5-PAIR-GE20 | low-support robustness | pair support threshold only | `davidson` | named pair-support >=20 view | `judge_cluster` | 2000 | secondary robustness | READY BY VIEW TOOLING |
| S5-PAIR-GE50 | low-support robustness | pair support threshold only | `davidson` | named pair-support >=50 view | `judge_cluster` | 2000 | secondary robustness | READY BY VIEW TOOLING |
| S6-ENGLISH | language heterogeneity | source language filter only | `davidson` | English `BASE_RESEARCH` equivalent | `judge_cluster` | 2000 | formal heterogeneity | READY BY VIEW TOOLING |
| L2-* | language support audits | source language filter only | none in T13 | one L2 language at a time | none in T13 | 0 | exploratory heterogeneity | NEEDS SUPPORT AUDIT |

Every sensitivity that changes `analysis_config` receives its own
`RunManifest`, deterministic `run_id`, and directory:

```text
outputs/research/<sensitivity_run_id>/
```

No sensitivity reuses the primary run ID or primary artifact directory.

## Seed and Run Identity Policy

T13 freezes the derivation rule and stable IDs, but does not select actual
sensitivity seed values. A later execution task must preregister each seed
before that sensitivity's estimator or bootstrap is run.

For sensitivity ID `<ID>`, use the exact UTF-8 string:

```text
LLM-Arena-Preference-Analysis|Phase2C|Sensitivity|<ID>|v1|2026-08-25
```

Hash with SHA-256, take the first 8 digest bytes, and interpret them as a
big-endian unsigned integer accepted by `PCG64`. The primary seed is never a
generic sensitivity default. A sensitivity seed is used only by its own
authorized run and is never used for a smoke, benchmark, or development run.

Each sensitivity manifest records the same source snapshot, Git SHA, canonical
schema, population spec version, estimator configuration, bootstrap
configuration, and formal failure policy as applicable. Its changed
configuration fields determine a new run ID.

## Frozen Axes

### S1 - Coalesced Tie Davidson

Changed: only the effective estimator outcome view. The copied likelihood view
maps `tie_bothbad` to ordinary `tie` for `davidson_coalesced_ties`.

Frozen: canonical rows and raw outcome taxonomy, `base_research`, source and Git
identity, sum-to-zero gauge, L-BFGS-B, no regularization, judge-cluster
bootstrap, 0.95 percentile CI, PCG64, 2,000 fixed attempts, and no redraw.
The separate raw `tie_bothbad` count remains reportable. Canonical data is never
rewritten.

### S2 - Decisive Bradley-Terry

Changed: only estimator/outcome policy to `bradley_terry_decisive`; ordinary and
bothbad ties are excluded from its likelihood.

Frozen: source, population, canonical data, gauge, optimizer, bootstrap unit,
2,000 attempts, confidence method, RNG family, and fixed-attempt failure gate.
Bradley-Terry has no Davidson `nu`; comparison is by ordering and uncertainty,
not raw score scale.

### S3 - Battle-Row Bootstrap

Changed: only `resampling_unit`, from `judge_cluster` to `battle_row`.

Frozen: primary Davidson point estimator, `base_research`, source/Git identity,
seed derivation rule, 2,000 attempts, PCG64, confidence/CI method, and fixed
attempt/no-redraw semantics. Row resampling is a dependence-structure
sensitivity, not an automatically superior method.

### S4 - Repeated-Question Exclusion

Changed: exclude every row whose non-missing `question_id_raw` belongs to a
group occurring more than once. No representative row is retained and no
question identity is fabricated; missing IDs are not treated as a repeated
group.

Frozen: all other canonical validity and anonymity rules, Davidson estimator,
judge-cluster bootstrap, and formal execution settings. The expected audit
anchor is 19 repeated groups and 39 rows, with approximately 32,961 eligible
rows subject to exact data checks.

### S5 - Pair-Support Thresholds

Changed: only the outcome-blind unordered-pair support threshold: eligible
`BASE_RESEARCH` battle count per pair must be at least 10, 20, or 50.

Support is counted before estimator outcome-policy filtering, using the frozen
Phase 2B pair definition. All rows for a qualifying pair are retained; rows
are not deduplicated and no model is selected by outcome. After filtering, the
estimator-effective graph must still be connected. A disconnected graph is a
formal blocker, not permission to drop components.

Frozen: source, canonical semantics, Davidson, judge-cluster bootstrap, 2,000
attempts, and all uncertainty settings. Each threshold is a separate run.
Every threshold reports eligible battle count, qualifying pair count, model
universe, and graph connectivity before any inference claim.

### S6 - English Subgroup

Changed: only the source-provenance language filter
`language_canonical == "English"` applied to a `BASE_RESEARCH` equivalent.
Language is not redetected or inferred.

Frozen: Davidson, judge-cluster bootstrap, 2,000 attempts, source/Git identity,
and all estimator/uncertainty settings. The frozen support audit anchor is
29,206 rows, 20 models, 190 pairs, and a connected graph. This is a formal
heterogeneity view, never an alternative global ranking.

### L2 Language Audits

Audit German, Spanish, French, Portuguese, and Russian separately using the
canonical source language field. Before any inference authorization, report
only row count, model count, pair count, graph connectivity, judge-cluster
count, and outcome counts. No L2 bootstrap is part of T13; inadequate support
blocks promotion to a later exploratory run. No causal claim is permitted.

## Bootstrap and Failure Contract

Formal and secondary sensitivity bootstraps use fixed attempts, no redraw, and
the same failure semantics as the primary:

```text
formal_ci_valid = (attempted >= required_target and failed == 0)
```

Failed replicates remain represented with status and NaN matrix rows. A
program/tool interruption is an execution-level interruption: preserve the
partial state, do not retry automatically, and require a new authorization.

## Comparison Metrics

Every executed sensitivity is compared with the immutable primary using:

1. point-rank displacement;
2. Spearman rank correlation;
3. top-1 identity;
4. top-4 set overlap;
5. top-k ordering stability where meaningful;
6. score shift under the same gauge when the estimator scale is comparable;
7. pairwise bootstrap direction-frequency changes;
8. rank-distribution changes.

Raw score differences are not compared across Davidson and Bradley-Terry as if
they shared a common scale. No post-result arbitrary significance threshold is
introduced. Qualitative labels are frozen as follows:

- **ROBUST:** key primary ordering/conclusion is preserved across the relevant
  major sensitivities;
- **PARTIALLY ROBUST:** high-level grouping is preserved but local ordering
  changes;
- **SENSITIVE:** the major ordering or top-group conclusion materially changes.

## Primary Claims Under Test

Sensitivity work challenges these already-defined primary claims rather than
searching for new stories:

- **P1:** `gpt-4` is primary rank 1;
- **P2:** the top-four ordering is highly stable under primary bootstrap;
- **P3:** ranks 5-8 contain meaningful ordering uncertainty;
- **P4:** ranks 11-15 contain highly exchangeable local orderings;
- **P5:** the ordinary tie component is non-zero and stable under primary
  Davidson.

No T13 result is used to accept or reject these claims.

## Implementation Readiness Audit

- **S1:** READY BY CONFIG. `PreferenceEstimatorConfig` accepts
  `davidson_coalesced_ties`; `fit_preference()` implements an explicit copied
  coalescing view; `BootstrapConfig` accepts the existing cluster unit.
  References: `src/preference_estimation.py`, `src/preference_bootstrap.py`.
- **S2:** READY BY CONFIG. `bradley_terry_decisive` and decisive-only outcome
  validation are implemented in `src/preference_estimation.py`; existing
  bootstrap orchestration accepts the estimator config.
- **S3:** READY BY CONFIG. `BootstrapConfig` and `run_bootstrap()` already
  support `battle_row` with fixed-attempt semantics in
  `src/preference_bootstrap.py`.
- **S4:** NEEDS POPULATION TOOLING. `question_id_raw` is preserved by
  `src/battle_contract.py`, but `PopulationSpec`/`apply_population()` has no
  named repeated-question exclusion policy and `formal_run.py` only registers
  existing populations.
- **S5:** NEEDS POPULATION TOOLING. No frozen pair-support population/filter
  exists in `src/population.py`; an outcome-blind pair-count view, graph gate,
  and manifest-addressable population identity are required.
- **S6:** NEEDS POPULATION TOOLING. `LANGUAGE_RESEARCH` checks language
  presence, but there is no named English value filter or language-specific
  manifest population in `src/population.py`/`src/formal_run.py`.
- **L2:** NEEDS SUPPORT AUDIT. Canonical language fields exist, but a
  non-inferential per-language support audit and promotion gate are not a
  frozen executable API.

No production code change is authorized by T13. The missing population and
orchestration representations must be implemented and reviewed before S4-S6
execution.

## Artifact Strategy and Execution Order

Sensitivity artifacts reuse research artifact schema version 1 where the same
point/bootstrap structure applies:

```text
outputs/research/<sensitivity_run_id>/
```

Recommended execution order:

1. S1 coalesced ties;
2. S2 decisive Bradley-Terry;
3. S3 battle-row bootstrap;
4. S4 repeated-question exclusion;
5. S5 pair-support thresholds 10, 20, 50;
6. S6 English subgroup;
7. L2 support audits.

This order runs the three configuration-ready core robustness checks first,
then population-tooling-dependent views, and leaves lower-support language
heterogeneity as audit-only until it passes support review.

Using the accepted primary end-to-end time of about 13m39s as a planning basis,
the eight planned 2,000-attempt runs (S1, S2, S3, S4, S5 x3, S6) are roughly
1h50m serial, excluding data preparation variation and L2 audits. This is a
planning estimate, not an execution result.

## Blockers and Stop Rules

Stop before execution when any of the following occurs:

- primary Git/source/run identity or artifact hashes differ;
- a sensitivity attempts to mutate or reuse the primary directory/run ID;
- an actual seed is not derived and preregistered before its first use;
- a required population/filter definition is not represented losslessly and
  outcome-blindly;
- support or estimator-effective graph connectivity is inadequate;
- a formal run has failed attempts or an execution-level interruption;
- a tool would require changing frozen primary semantics or adding an
  unreviewed sensitivity family.

No automatic retry, redraw, seed substitution, sensitivity combination, public
ranking interpretation, or causal conclusion is allowed.

## T13 Boundary

```text
Sensitivity contract: FROZEN
Actual sensitivity seeds selected: NO
Formal sensitivity run executed: NO
Primary rerun: NO
Code semantics changed: NO
```
