# Phase 2C Estimator Contract

## Scope

Phase 2C estimates latent relative human preference within the frozen historical Arena research population. It is model-based and associational; it does not measure objective capability, universal user preference, current model quality, or causal effects.

This contract implements core point estimators only. Bootstrap uncertainty, confidence intervals, rank-stability reporting, and any real-data fit remain out of scope.

## Estimator Modes

**Primary: `davidson`.** Its likelihood accepts `model_a_win`, `model_b_win`, and ordinary `tie`. With `pi_i = exp(theta_i)`, `pi_j = exp(theta_j)`, and `nu > 0`, the probabilities are:

```text
denominator = pi_i + pi_j + nu * sqrt(pi_i * pi_j)
P(i wins) = pi_i / denominator
P(j wins) = pi_j / denominator
P(tie) = nu * sqrt(pi_i * pi_j) / denominator
```

The tie parameter is optimized as `log_nu`, then reported as positive `nu`. The likelihood is evaluated in log space.

**Sensitivity: `davidson_coalesced_ties`.** It is a sensitivity-only Davidson fit. It accepts decisive outcomes and maps both ordinary `tie` and `tie_bothbad` to one effective Davidson tie category in an explicit, copied likelihood view. This is a lossy outcome transformation for sensitivity analysis only. The canonical data contract is unchanged, the raw `tie_bothbad` count remains reportable, and it is never globally reclassified.

**Diagnostic sensitivity: `bradley_terry_decisive`.** It accepts only `model_a_win` and `model_b_win`, using a numerically stable logistic likelihood.

For primary `davidson`, `tie_bothbad` is valid research data but excluded from the likelihood. For `bradley_terry_decisive`, both tie categories are excluded. In all modes the excluded or coalesced counts remain visible in the fit result. `invalid_unknown` is an input error, never an exclusion shortcut.

Custom two-tie-category models, Rao-Kupper, bootstrap, and uncertainty reporting are not implemented by this task.

## Shared Fit Contract

The estimator accepts an explicit `PopulationResult` and uses only its `eligible` dataframe. It never selects a population, recanonicalizes rows, deduplicates bootstrap draws, or invokes legacy score-rate code.

Model IDs are sorted lexicographically for deterministic parameter layout. Scores use the symmetric gauge `sum(theta) = 0`, implemented with `K - 1` free score parameters and a final score equal to their negative sum. Derived ranks are dense ranks; model ID only stabilizes serialization order when point estimates are numerically equal within the explicit `1e-10` latent-score tolerance.

The estimator-effective undirected graph is built after outcome-policy filtering (and after the explicit coalescing view for `davidson_coalesced_ties`). It must contain at least two models and exactly one connected component. The estimator never silently selects a largest component. Self-comparisons (`model_a_id == model_b_id`) are invalid estimator-domain input and are rejected rather than discarded.

Davidson additionally enforces an outcome-aware directed support condition before fitting: a decisive result contributes an arc from winner to loser, while an effective Davidson tie contributes arcs in both directions. Thus `tie_bothbad` contributes bidirectional support only in the explicit coalesced sensitivity mode. This directed graph must be strongly connected; otherwise the fit raises `SEPARATION`. This is the explicit finite-MLE support guard implemented by this module, not a claim that optimizer success alone proves finite-MLE existence or a replacement for later mathematical review.

No regularization is applied. L-BFGS-B starts all free scores at zero and Davidson starts `log_nu` at zero (`nu = 1`). A fit is accepted only when the optimizer reports success and all parameters, the objective, scores, and Davidson tie parameter are finite.

## Failure and Result Semantics

Stable domain error codes distinguish missing required fields, invalid outcomes or model IDs, self-comparisons, zero likelihood rows, insufficient models, models dropped by an outcome policy, disconnected graphs, decisive Bradley-Terry separation, Davidson outcome-aware separation, an unidentifiable Davidson tie parameter, optimizer failure, and nonfinite results. A decisive Bradley-Terry fit requires a strongly connected directed win graph; Davidson additionally requires the outcome-aware directed support condition and at least one effective tie and one decisive outcome. Failed fits do not return partial rankings.

Successful results include estimator/configuration identity, population identity, lexical model IDs, latent scores, dense derived ranks, raw population outcome counts, effective likelihood and excluded outcome counts, estimator-effective graph diagnostics, optimizer diagnostics, and Davidson's tie parameter where applicable.

## Reproducibility

`PreferenceEstimatorConfig.to_dict()` is JSON-compatible and can be used in `RunManifest.analysis_config`. Formal run configuration must record the estimator, estimator version, outcome policy, sum-to-zero gauge, L-BFGS-B optimizer, no-regularization policy, and fitting tolerances.

## Boundaries

This task uses only synthetic test data. It neither reads nor fits the 33,000-row Arena snapshot, produces real model rankings, implements bootstrap, changes Phase 2B canonical/population contracts, nor changes legacy score-rate behavior.
