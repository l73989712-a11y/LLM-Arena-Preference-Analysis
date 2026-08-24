# Phase 2C Implementation Status

## Scope

Phase 2C implements latent relative human-preference estimators and uncertainty infrastructure for the frozen historical Arena research population. It does not claim objective model capability, universal user preference, current model quality, causality, or external generalization.

This document records accepted implementation readiness. It is not a formal empirical result report or Phase 2C research closeout.

## Accepted Task Chain

```text
T1   estimator integration and mathematical-contract audit       ACCEPTED
T2   core preference estimators                                  ACCEPTED
T2a  Davidson existence and input-domain correction              ACCEPTED
T3   estimator diagnostics and coalesced-tie sensitivity          ACCEPTED
T4   bootstrap mathematical and execution-contract audit         ACCEPTED
T5   bootstrap engine v1                                         ACCEPTED
T6a  real Parquet conversation-container compatibility           ACCEPTED
T6   formal-run performance audit                                ACCEPTED
T7   judge-cluster bootstrap performance optimization             ACCEPTED
```

## Accepted Implementation Commits

```text
98e55fbc206a96065298ed3f9f0b0dd3b288e904  feat: add core preference estimators
a6c3fc069b9435d197258f2fce165c47c2bcdb31  fix: validate preference estimator existence
b7d72902308d19998cb581f11b0c6507dff387be  feat: add estimator sensitivity diagnostics
259239f1d84966737abf4fca3b9e0c1b42f2b42d  feat: add preference bootstrap engine
6da1838ab0c23455ab4fe2f013580470f066cfb2  fix: support parquet conversation arrays
47dff01643cfdb331d92106b5c37b57a05112ac7  perf: optimize cluster bootstrap resampling
```

## Point-Estimator Contract

```text
primary: Davidson ordinary-tie
sensitivity: Davidson with ordinary tie + tie_bothbad coalesced in an explicit likelihood view
diagnostic sensitivity: decisive-only Bradley-Terry
gauge: sum(theta) = 0
optimizer: L-BFGS-B
regularization: none
```

`tie` and `tie_bothbad` remain distinct in canonical data. Primary Davidson excludes `tie_bothbad` from its likelihood while retaining and reporting it. Coalescing occurs only in the copied sensitivity likelihood view.

The estimator layer includes explicit graph, separation, self-comparison, invalid-outcome, finite-result, and fixed-model-universe guards. It does not silently select a population or return partial rankings after a failed fit.

## Bootstrap Contract

```text
primary resampling: judge-cluster bootstrap
sensitivity resampling: battle-row bootstrap
RNG: numpy Generator + PCG64
attempt policy: exactly B fixed attempts, no redraw
formal target: >= 2,000 attempts
formal CI gate: zero failed replicates
CI: 95% equal-tailed percentile, linear quantiles
execution: serial v1
```

The optimized cluster implementation builds a deterministic cluster-to-row-position plan and materializes narrow physical replicate rows by indexed selection. This changes execution representation only; every sampled cluster still contributes every eligible battle row with its sampled multiplicity, and `battle_id` is unchanged.

## Real Operational Evidence

The exact pinned snapshot was used only for controlled compatibility, point-fit health, and performance smoke:

```text
source rows: 33,000
BASE_RESEARCH eligible: 33,000
models: 20
judge clusters: 13,383
canonical/population compatibility: complete
point-fit health: successful at approximately one-second scale
optimized cluster benchmark: approximately 1.02 seconds/attempt at 20 attempts
projected 2,000-attempt serial primary run: approximately 34 minutes
```

These are operational measurements and projections only. No model names, scores, rankings, pairwise findings, confidence intervals, or public preference conclusions are recorded here.

## Formal-Run Boundary

Formal empirical execution requires all of the following:

- a published immutable Git SHA;
- exact verification of the pinned source SHA-256;
- an explicit preregistered formal seed;
- RunManifest-bound estimator and bootstrap configuration;
- a formal artifact writer and integrity checks;
- a final preflight with clean repository and dependency verification;
- exactly 2,000 or more attempted primary judge-cluster replicates;
- zero failed replicates for `formal_ci_valid`.

The formal seed is not selected in this status document. Formal bootstrap, formal confidence intervals, and public empirical results are not yet run.

## Remaining Tasks

1. Reconcile and review this documentation baseline.
2. Publish the immutable implementation SHA.
3. Implement and review formal manifest/artifact writing and seed preregistration.
4. Run the final preflight and formal primary bootstrap.
5. Run predeclared sensitivities and perform a result/claim audit.
