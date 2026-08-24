# Phase 2C Bootstrap Contract

## Scope

This contract defines uncertainty execution around an already-selected
`PopulationResult` and an accepted point-estimator configuration. Bootstrap
does not select populations, recanonicalize rows, rerun support thresholds, or
read the real Arena snapshot.

The primary uncertainty method is judge-cluster bootstrap. Battle-row
bootstrap is a sensitivity method. Version 1 is serial and has passed synthetic
semantic tests plus controlled pinned-snapshot operational/performance smoke.
The formal 2,000-attempt empirical bootstrap has not been run.

## Bootstrap Configuration

`BootstrapConfig` is immutable and records:

```text
resampling_unit: judge_cluster | battle_row
replicate_count
seed
bit_generator: PCG64
confidence_level: 0.95
ci_method: percentile
failure_policy: fixed_attempts_zero_failure_formal_gate
estimator_config
```

`analysis_config` in `RunManifest` can contain the JSON-compatible result of
`BootstrapConfig.to_dict()` without a manifest schema bump. The empirical seed
is run-specific and is not fixed by this document.

## Resampling Semantics

For judge-cluster bootstrap, let `G` be the number of unique valid judge
clusters in the frozen eligible population. Each replicate draws `G` cluster
indices with replacement. A selected cluster contributes all of its eligible
battle rows; multiplicity `m` repeats every row in that cluster `m` times.

Version 1 physically duplicates rows. The implementation may represent cluster
membership as deterministic source-row positions and materialize one narrow
replicate view with indexed selection; this is an execution optimization only
and is observationally equivalent to concatenating each selected cluster's
full rows. `battle_id` remains the canonical battle identity and is never
suffixed or regenerated. Bootstrap occurrence metadata is execution metadata
only.

For battle-row bootstrap, let `N` be the number of eligible rows. Each replicate
draws exactly `N` row positions with replacement. Repeated `battle_id` values
are valid and are not deduplicated.

Population and sensitivity views are formed before resampling. Bootstrap does
not rerun `apply_population()`, remove repeated questions, or recompute pair
support thresholds inside a replicate.

## Determinism

Version 1 uses `numpy.random.Generator(numpy.random.PCG64(seed))`. Source rows
are sorted by stable canonical identity (`battle_id`, with deterministic
secondary fields) and cluster IDs are sorted before drawing. Therefore the same
substantive population, configuration, and seed produce the same draw sequence
independently of input dataframe order.

Version 1 is serial. Future parallel execution must predeclare per-replicate
draw plans or independent child seeds so worker scheduling cannot affect draws.

## Fixed Model Universe and Failures

The full-sample point estimate runs first. Its `model_ids` define the fixed
bootstrap model universe. A replicate missing any of those models fails with
`MODEL_ABSENT`; it is never refit on a smaller universe.

Wrapper-level failures include `MODEL_ABSENT`, `BOOTSTRAP_INPUT_ERROR`, and
missing/invalid judge-cluster input. Point-estimator failures retain their
underlying stable codes, including `SEPARATION`, `DISCONNECTED_GRAPH`,
`UNIDENTIFIABLE_TIE_PARAMETER`, `OPTIMIZATION_FAILED`, and
`NONFINITE_RESULT`.

Exactly `replicate_count` attempts are made. Failed attempts are recorded and
never redrawn or replaced. Unexpected programming errors are not silently
converted into replicate failures.

## Formal Gate and Intervals

Development runs may use fewer than 2,000 attempts. A formal run requires:

```text
replicate_count >= 2,000
failed_replicates == 0
```

Only then is `formal_ci_valid` true. Failed runs retain diagnostic successful
replicates, but formal score intervals are unavailable.

Version 1 uses equal-tailed percentile intervals with
`numpy.quantile(..., method="linear")` at the configured confidence level.
Basic, BCa, and studentized intervals are deferred.

## Result and Uncertainty Outputs

`BootstrapResult` retains fixed-shape matrices:

```text
score_replicates: (B, K)
rank_replicates: (B, K)
tie_parameter_replicates: (B,)
```

Failed rows contain `NaN` values. Results also retain attempt/success/failure
counts, per-replicate status, failure-code counts, score intervals, rank
distribution summaries, pairwise stability frequencies, and tie-parameter
intervals.

Rank summaries are distributions, not parameter confidence intervals. They may
include median rank, linear rank quantiles, and `P_boot(rank = 1)`. Pairwise
quantities such as `P_boot(theta_i > theta_j)` are empirical bootstrap
stability frequencies, not posterior probabilities.

Davidson primary `nu` and coalesced-tie Davidson `nu` are summarized separately;
they represent different effective tie mechanisms. Bradley-Terry has no tie
parameter.

## Privacy Boundary

Bootstrap results do not expose judge-cluster IDs, per-judge counts, prompts,
responses, or raw rows. They may expose aggregate cluster counts, resampling
unit, anonymous replicate statuses, scores, ranks, and stability summaries.

## Status

```text
synthetic semantic tests: COMPLETE
pinned real-data compatibility smoke: COMPLETE
controlled real point-fit smoke: COMPLETE
controlled real performance benchmark: COMPLETE
formal 2,000-attempt empirical bootstrap: NOT RUN
```
