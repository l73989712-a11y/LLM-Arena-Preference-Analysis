# Phase 5 Ranking Robustness & Stability Contract

Status: **ACCEPTED - Phase 5 E2 derivation contract v1**

This document is the accepted P5-T2 Phase 5 E2 derivation contract. It governs
future Phase 5 E2 architecture and implementation, subject to the repository's
separate mutation, staging, and commit gates.

## 1. Scope and scientific question

Phase 5 is **Ranking Robustness & Stability**. It asks:

> How stable are the frozen historical Arena preference conclusions under the
> sampling uncertainty already represented in E1 and across the bounded,
> pre-specified E1 sensitivity specifications?

The research interpretation remains:

> estimated preference under the frozen historical Arena population

Phase 5 does not turn these estimates into objective capability, a universal
ranking, a present-day Arena ranking, a current recommendation, a causal
effect, or a posterior probability.

## 2. Evidence lineage and immutability

The evidence lineage is:

```text
E0  Frozen historical source snapshot
 |
 v
E1  Frozen Phase 2-4 inference evidence
 |
 v
E2  Deterministic Phase 5 robustness/stability derivation
```

E1 is immutable. E2 is derived scientific evidence, but it is not new source
evidence, a new estimator inference, a new bootstrap inference, or an
independent replication of E1. No E2 producer may write into:

```text
artifacts/frozen/formal-research-v1/
```

The frozen E1 authority is:

```text
bundle: formal-research-v1
payload files: 73
payload bytes: 3,626,761
payload_inventory_sha256: 392066c7a23408e97f0f2bcd3e2a530b167e596c9b382d999d959ba49abb7eb6
formal runs: 9
primary run: 9c1fd5abbe8681db45b535e5368c806caad8d8297914c7b86a598112900f2689
```

## 3. E1 input authority

Future E2 computation must consume the frozen bundle through the existing
closed-world loader:

```text
src/formal_results.py
  FROZEN_SOURCE
  FROZEN_RUNS
  load_frozen_formal_run
  load_frozen_formal_research
```

It must not trust arbitrary user-supplied artifact paths or re-discover runs.
The E2 provenance must bind to at least:

- E0 `source_snapshot_id`;
- E1 bundle name and version;
- E1 `payload_inventory_sha256`;
- the exact ordered E1 run registry;
- the exact primary run ID.

The comparative-review hash may be retained as contextual provenance. It is a
computational input only if the implementation actually consumes that review.

## 4. Sampling versus specification sensitivity

Within-run sampling uncertainty is represented by the 2,000 retained
successful bootstrap replicates for each run. Between-specification sensitivity
is represented by differences among the nine deliberately selected formal
specifications.

These are distinct concepts. E2 must never pool them:

```text
9 x 2000 retained rows != 18,000 draws from one common distribution
```

The primary run is the headline sampling-stability authority:

```text
9c1fd5abbe8681db45b535e5368c806caad8d8297914c7b86a598112900f2689
```

The other eight runs may receive the same deterministic metrics as
specification-specific diagnostics. They must not be silently averaged.

## 5. Required metrics

All formulas below use only successful retained replicates for the relevant
run. Let `B_s` be the successful replicate count for run `s` (2,000 for the
frozen E1 bundle), and let `R_{s,b,m}` be the persisted rank for model `m` in
replicate `b`.

### 5.1 Rank distribution

For model `m`, rank `r`, and run `s`:

```text
rank_frequency(s,m,r)
  = count_b [ R_{s,b,m} = r ] / B_s
```

This is an empirical bootstrap rank frequency under the frozen E1 resampling
design. It is not a posterior rank probability. Persisted E1 rank semantics
are authoritative; a new ranking algorithm must not be substituted.

### 5.2 Top-k inclusion

The only formal top-k values are:

```text
k in {1, 3, 5}
```

For each run, model, and required `k`:

```text
top_k_frequency(s,m,k)
  = count_b [ R_{s,b,m} <= k ] / B_s
```

Top-1 aligns with existing rank-1 stability, top-3 aligns with the frozen
historical headline top three, and top-5 is a bounded broader high-rank set.
Arbitrary additional k values are outside this contract.

E1 rank rows are validated as permutations of `1..20`, so no bootstrap
top-k-boundary tie rule is needed. If a future input violates this invariant,
the implementation must fail closed rather than invent a tie-breaking rule.

### 5.3 Pairwise ordering stability

Formal Phase 5 pairwise ordering stability is score-based and must reproduce
the existing E1 authority exactly. For each model pair `(i, j)` and retained
successful bootstrap replicate:

```text
difference = score_i - score_j
```

Using the frozen `RANK_EQUALITY_TOLERANCE`:

```text
gt: difference > +RANK_EQUALITY_TOLERANCE
eq: abs(difference) <= RANK_EQUALITY_TOLERANCE
lt: difference < -RANK_EQUALITY_TOLERANCE
```

The formal E2 output is:

```text
gt_frequency
eq_frequency
lt_frequency
```

These frequencies are empirical bootstrap ordering frequencies of latent
preference scores under the frozen estimator and resampling specification. They
are not the probability that a human battle between the two models is won by
that model. The persisted bootstrap rank matrices are not an alternative
implementation of this metric.

The derived result must cross-check the existing E1 authority:

```text
src/preference_bootstrap.py::_pairwise_stability
bootstrap_summary.json::pairwise_stability
```

The existing semantics compare latent score differences with the frozen rank
equality tolerance and report `gt_frequency`, `eq_frequency`, and
`lt_frequency`. A new definition may not be introduced silently.

This is distinct from Section 5.5:

```text
pairwise ordering stability: score-based E1 tolerance semantics
adjacent-rank reversal:     rank-based persisted-rank semantics
```

Neither quantity is human battle win probability.

### 5.4 Rank uncertainty interval

E2 must reuse the E1 percentile semantics and fields:

```text
lower_rank_quantile
median_rank
upper_rank_quantile
```

No second quantile convention is allowed. This metric is partly a
re-presentation of existing E1 evidence, not independent new inference.

### 5.5 Adjacent-rank reversal

The primary point-estimate canonical order defines exactly 19 ordered adjacent
pairs:

```text
rank 1 vs rank 2, rank 2 vs rank 3, ..., rank 19 vs rank 20
```

For each primary-adjacent pair `(higher, lower)`, E2 reports at minimum:

```text
bootstrap_support_frequency
  = frequency higher remains above lower

bootstrap_reversal_frequency
  = frequency lower ranks above higher
```

The reversal frequency must not be converted into an arbitrary
`ambiguous/not-ambiguous` label. If the primary point estimate cannot establish
a unique canonical `1..20` ordering, derivation must fail closed and the
adjacency definition must be reconsidered.

### 5.6 Cross-specification stability

Cross-specification summaries use exactly the nine named E1 specifications.
Required descriptive outputs include:

- run-by-model point-rank matrix;
- primary-relative rank shift;
- minimum observed rank across the nine specifications;
- maximum observed rank;
- maximum absolute rank shift from Primary;
- count of specifications in top-1, top-3, and top-5.

For example, `top-3 in 7 of 9 frozen specifications` is permitted. The nine
specifications are not a random sample, so this must never be described as
`78% probability of being top-3`.

Cross-specification confidence intervals are forbidden. Bootstrap rows must
not be pooled, and Davidson and Bradley-Terry latent scores must not be
averaged or compared as if they shared a scale. Ordinal rank comparisons are
permitted where the run semantics support them.

## 6. Frozen nine-run specification family

The exact run IDs come from `FROZEN_RUNS` and are recorded here for auditability.
All runs use 2,000 fixed attempts, PCG64, 95% percentile intervals, and the
frozen zero-failure formal gate.

| Role | Run ID | Specification | Estimator / tie policy | Resampling |
|---|---|---|---|---|
| Primary | `9c1fd5abbe8681db45b535e5368c806caad8d8297914c7b86a598112900f2689` | `base_research` | Davidson / ordinary ties | judge cluster |
| S1 | `fa59994fb1f9de6a093162858bda584f6241c4a42314f0b027e57e2ff04d33e7` | tie coalescing | Davidson coalesced ties | judge cluster |
| S2 | `3babe007af583d3f8a6b4e25731828a77dd6e91d1f1110c618f82aee531d49d3` | decisive-only estimator | Bradley-Terry decisive | judge cluster |
| S3 | `3c62408ca810a5aaa34a3c237333156b8f62ebeb7e1d94f4316264f898b3e2cf` | resampling-unit sensitivity | Davidson / ordinary ties | battle row |
| S4 | `33b992df5e34b50d69218931bbcbadeee9db8658bd0b697d785cc909e3bb7d1f` | exclude repeated `question_id` groups | Davidson / ordinary ties | judge cluster |
| S5-ge10 | `60c314ba7c6453b8227db0be16a73963df0bda1e8321cd1085ae698549d6a466` | pair support `>=10` | Davidson / ordinary ties | judge cluster |
| S5-ge20 | `29a6ad3a3e401210de5a0ac1ad915e92d86bdcd6d954223dbb73fcf2e6f5ab7f` | pair support `>=20` | Davidson / ordinary ties | judge cluster |
| S5-ge50 | `da1dbcf8f4a55403f1df8e8cd4ada2b903b93431486ce337849f116f2aadc7e2` | pair support `>=50` | Davidson / ordinary ties | judge cluster |
| S6-English | `8dba0d09c93abafe6c448a3ddb8ee22671792208e85b378f5c1b2328ee52624d` | `language_canonical == English` | Davidson / ordinary ties | judge cluster |

Phase 5 does not silently add arbitrary weighting schemes, high-activity judge
exclusions, extra language thresholds, additional estimator families, arbitrary
filters, or combinations selected after observing outcomes. A new
specification requires explicit methodology authorization and may require a
separate inference evidence layer.

## 7. E2 identity and provenance model

The semantic versions for this Phase 5 derivation contract are:

```text
derivation_contract_version: 1
metric_schema_version: 1
```

The document revision (`CANDIDATE v2`) is a working-tree review revision and
must not be confused with either scientific semantic version. In particular:

```text
candidate revision != scientific derivation contract version
```

E2 separates scientific derivation identity from implementation provenance:

```text
derivation_spec_id = identity of what is being derived
producer_git_sha   = identity of which implementation produced it
artifact_instance_id = identity of one produced E2 artifact instance
```

`derivation_spec_id` identifies the semantic derivation specification and is
bound to the E1 bundle/inventory identity, source snapshot, ordered selected run
IDs, primary run ID, `derivation_contract_version: 1`,
`metric_schema_version: 1`, and required `k = {1,3,5}`.

`producer_git_sha` is recorded separately as implementation provenance. A code
refactor that preserves the same derivation semantics must not silently become
a new scientific specification. Exact executable hashing details remain
implementation-gated until P5-T3 reviews the existing canonical JSON/hash
utilities.

`artifact_instance_id` identifies one implementation-produced E2 artifact
instance for an already identified derivation specification. It must be bound
to at least:

```text
derivation_spec_id
producer_git_sha
artifact_schema_version
```

The conceptual distinction is:

```text
derivation_spec_id = WHAT scientific derivation is specified
producer_git_sha = WHICH implementation produced it
artifact_instance_id = WHICH produced artifact instance is identified
```

Canonical serialization and the executable hashing algorithm remain
implementation-gated for P5-T3.

## 8. Candidate artifact boundary

No E2 artifacts are created by this acceptance finalization. Future Phase 5 E2
implementation uses the following working artifact namespace:

```text
artifacts/phase-5/ranking-robustness-v1/<artifact_instance_id>/
```

Possible structured output classes are:

```text
manifest
rank distributions
top-k frequencies
pairwise ordering
rank intervals
adjacent reversals
cross-specification ranks/stability
```

Machine-verifiable structured evidence should precede presentation figures.
The namespace must never reuse `formal-research-v1` as a writable destination.

## 9. Claim classes

### Existing E1 claim re-expression

Examples include persisted rank percentile intervals and persisted pairwise
stability. These must not be presented as independent new inference.

### New deterministic E2 summaries

Examples include full normalized rank distributions, top-3/top-5 inclusion
frequencies, pre-specified adjacent reversal summaries, and unified
cross-specification stability tables. They remain subordinate to E1
provenance.

### Forbidden extrapolation

No E2 output supports claims about current models, present Arena users,
objective capability, causality, future Arena populations, or arbitrary
untested specifications.

## 10. Reproducibility and implementation invariants

A later E2 producer must be deterministic, offline after checkout,
source-download-free, estimator-free, bootstrap-execution-free, closed over the
exact approved E1 registry, and machine-verifiable. It must be read-only with
respect to E1.

The implementation acceptance gate must verify:

1. E1 frozen bundle verification passes before derivation.
2. Exactly the authorized E1 runs are consumed.
3. No estimator fitting occurs.
4. No bootstrap resampling occurs.
5. No Arena/source download occurs.
6. No E1 file changes.
7. Rank-distribution rows normalize to 1 from exact retained successful counts.
8. Top-k frequencies equal exact rank-matrix counts for `k = {1,3,5}`.
9. Top-1 results agree with E1 `probability_rank_1` semantics.
10. Rank intervals agree with E1 rank-summary semantics.
11. Pairwise ordering agrees with E1 pairwise-stability semantics.
12. Adjacent pairs are defined before reversal frequencies are inspected.
13. Cross-specification summaries never pool score scales or bootstrap draws.
14. E2 provenance identifies exact E1 identities.
15. Repeated derivation is deterministic for identical inputs and specification.

Whether byte-for-byte artifact determinism is required must be decided during
implementation review; byte-stable structured artifacts are preferred where
reasonably achievable.

## 11. Explicit Phase 5 non-goals

- no new Arena snapshot;
- no new models;
- no live leaderboard;
- no objective capability ranking;
- no causal analysis;
- no external benchmark fusion;
- no demographic inference;
- no new estimator family;
- no new bootstrap run;
- no post-hoc specification shopping;
- no full web product;
- no mutation of E1.

## 12. Review and gate status

```text
P5-T2:
ACCEPTED
```

This contract does not itself authorize production implementation, artifact
generation, staging, commit, push, or Phase 5 closeout.

The next technical gate is a separate P5-T3 read-only implementation
architecture audit. P5-T3 has not started.
