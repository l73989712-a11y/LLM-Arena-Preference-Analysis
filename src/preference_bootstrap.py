"""Deterministic bootstrap uncertainty engine for explicit populations.

This module resamples an already-selected ``PopulationResult`` and delegates
each replicate to the accepted point-estimator layer.  It does not select
populations, recanonicalize rows, or access real Arena data.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd

from src.preference_estimation import (
    EstimationErrorCode,
    PreferenceEstimationError,
    PreferenceEstimationResult,
    PreferenceEstimatorConfig,
    RANK_EQUALITY_TOLERANCE,
    fit_preference,
)
from src.population import PopulationResult


FORMAL_REPLICATE_TARGET = 2_000
DEFAULT_CONFIDENCE_LEVEL = 0.95
DEFAULT_BIT_GENERATOR = "PCG64"
DEFAULT_CI_METHOD = "percentile"
DEFAULT_FAILURE_POLICY = "fixed_attempts_zero_failure_formal_gate"


class BootstrapErrorCode(str, Enum):
    """Stable wrapper-level bootstrap errors."""

    INVALID_CONFIG = "INVALID_CONFIG"
    MISSING_JUDGE_CLUSTER = "MISSING_JUDGE_CLUSTER"
    INVALID_JUDGE_CLUSTER = "INVALID_JUDGE_CLUSTER"
    BOOTSTRAP_INPUT_ERROR = "BOOTSTRAP_INPUT_ERROR"
    POINT_ESTIMATE_FAILED = "POINT_ESTIMATE_FAILED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    MODEL_ABSENT = "MODEL_ABSENT"


class PreferenceBootstrapError(ValueError):
    """A deterministic bootstrap-domain error."""

    def __init__(
        self,
        code: BootstrapErrorCode,
        message: str,
        *,
        underlying_code: str | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.underlying_code = underlying_code
        super().__init__(f"{code.value}: {message}")


@dataclass(frozen=True)
class BootstrapConfig:
    """Immutable execution and reporting contract for one bootstrap run."""

    resampling_unit: str
    replicate_count: int
    seed: int
    bit_generator: str = DEFAULT_BIT_GENERATOR
    confidence_level: float = DEFAULT_CONFIDENCE_LEVEL
    ci_method: str = DEFAULT_CI_METHOD
    failure_policy: str = DEFAULT_FAILURE_POLICY
    estimator_config: PreferenceEstimatorConfig = PreferenceEstimatorConfig("davidson")

    def __post_init__(self) -> None:
        if self.resampling_unit not in {"judge_cluster", "battle_row"}:
            raise ValueError("resampling_unit must be 'judge_cluster' or 'battle_row'")
        if isinstance(self.replicate_count, bool) or not isinstance(self.replicate_count, int) or self.replicate_count <= 0:
            raise ValueError("replicate_count must be a positive integer")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError("seed must be a non-negative integer")
        if self.bit_generator != DEFAULT_BIT_GENERATOR:
            raise ValueError("bit_generator must be 'PCG64'")
        if not np.isfinite(self.confidence_level) or not 0 < self.confidence_level < 1:
            raise ValueError("confidence_level must be between 0 and 1")
        if self.ci_method != DEFAULT_CI_METHOD:
            raise ValueError("ci_method must be 'percentile'")
        if self.failure_policy != DEFAULT_FAILURE_POLICY:
            raise ValueError("failure_policy must be the fixed zero-failure formal gate")

    @property
    def formal_replicate_target_met(self) -> bool:
        return self.replicate_count >= FORMAL_REPLICATE_TARGET

    def to_dict(self) -> dict[str, Any]:
        return {
            "resampling_unit": self.resampling_unit,
            "replicate_count": self.replicate_count,
            "seed": self.seed,
            "bit_generator": self.bit_generator,
            "confidence_level": self.confidence_level,
            "ci_method": self.ci_method,
            "failure_policy": self.failure_policy,
            "estimator": self.estimator_config.to_dict(),
        }


@dataclass(frozen=True)
class BootstrapResult:
    """Full replicate outputs plus explicitly gated summaries."""

    point_estimate: PreferenceEstimationResult
    bootstrap_config: BootstrapConfig
    model_ids: tuple[str, ...]
    attempted_replicates: int
    successful_replicates: int
    failed_replicates: int
    formal_replicate_target_met: bool
    formal_ci_valid: bool
    failure_counts: dict[str, int]
    replicate_status: tuple[str, ...]
    score_replicates: np.ndarray
    rank_replicates: np.ndarray
    tie_parameter_replicates: np.ndarray
    score_intervals: dict[str, tuple[float, float]] | None
    rank_summary: dict[str, dict[str, float]]
    pairwise_stability: dict[str, dict[str, float]]
    tie_parameter_interval: tuple[float, float] | None
    warnings: tuple[str, ...]


def _bootstrap_error(code: BootstrapErrorCode, message: str, *, underlying_code: str | None = None) -> None:
    raise PreferenceBootstrapError(code, message, underlying_code=underlying_code)


def _valid_identifier(value: Any) -> bool:
    if value is None or value is pd.NA:
        return False
    try:
        if bool(pd.isna(value)):
            return False
    except (TypeError, ValueError):
        pass
    return bool(str(value).strip())


def _deterministic_frame(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"battle_id", "model_a_id", "model_b_id", "canonical_outcome"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        _bootstrap_error(BootstrapErrorCode.BOOTSTRAP_INPUT_ERROR, f"population is missing columns: {missing}")
    sort_columns = ["battle_id", "model_a_id", "model_b_id", "canonical_outcome"]
    if "source_row_index" in frame.columns:
        sort_columns.insert(1, "source_row_index")
    if "judge_cluster_id" in frame.columns:
        sort_columns.append("judge_cluster_id")
    return frame.sort_values(sort_columns, kind="mergesort").reset_index(drop=True).copy()


def _cluster_groups(frame: pd.DataFrame) -> tuple[tuple[str, ...], dict[str, pd.DataFrame]]:
    if "judge_cluster_id" not in frame.columns:
        _bootstrap_error(BootstrapErrorCode.MISSING_JUDGE_CLUSTER, "judge_cluster_id is required for cluster bootstrap")
    if not frame["judge_cluster_id"].map(_valid_identifier).all():
        _bootstrap_error(BootstrapErrorCode.INVALID_JUDGE_CLUSTER, "every eligible row needs a non-empty judge cluster")
    cluster_keys = frame["judge_cluster_id"].map(str)
    groups = {
        cluster: frame.loc[cluster_keys.eq(cluster)].copy().reset_index(drop=True)
        for cluster in sorted(cluster_keys.unique())
    }
    return tuple(groups), groups


def _resample_cluster_rows(
    frame: pd.DataFrame,
    rng: np.random.Generator,
) -> pd.DataFrame:
    cluster_ids, groups = _cluster_groups(frame)
    return _resample_cluster_rows_from_groups(cluster_ids, groups, rng)


def _resample_cluster_rows_from_groups(
    cluster_ids: tuple[str, ...],
    groups: dict[str, pd.DataFrame],
    rng: np.random.Generator,
) -> pd.DataFrame:
    draw_indices = rng.integers(0, len(cluster_ids), size=len(cluster_ids))
    pieces = [groups[cluster_ids[int(index)]] for index in draw_indices]
    return pd.concat(pieces, ignore_index=True) if pieces else next(iter(groups.values())).iloc[0:0].copy()


def _resample_rows(frame: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    if frame.empty:
        _bootstrap_error(BootstrapErrorCode.BOOTSTRAP_INPUT_ERROR, "cannot resample an empty population")
    indices = rng.integers(0, len(frame), size=len(frame))
    return frame.iloc[indices].reset_index(drop=True).copy()


def _replicate_model_ids(frame: pd.DataFrame) -> set[str]:
    return set(frame["model_a_id"].tolist()).union(frame["model_b_id"].tolist())


def _percentile_interval(values: np.ndarray, confidence_level: float) -> tuple[float, float]:
    alpha = 1.0 - confidence_level
    quantiles = np.quantile(values, [alpha / 2.0, 1.0 - alpha / 2.0], method="linear")
    return float(quantiles[0]), float(quantiles[1])


def _score_intervals(
    scores: np.ndarray,
    model_ids: tuple[str, ...],
    confidence_level: float,
) -> dict[str, tuple[float, float]]:
    return {
        model_id: _percentile_interval(scores[:, index], confidence_level)
        for index, model_id in enumerate(model_ids)
    }


def _rank_summary(
    ranks: np.ndarray,
    model_ids: tuple[str, ...],
    confidence_level: float,
) -> dict[str, dict[str, float]]:
    summary: dict[str, dict[str, float]] = {}
    alpha = 1.0 - confidence_level
    for index, model_id in enumerate(model_ids):
        values = ranks[:, index]
        quantiles = np.quantile(values, [alpha / 2.0, 0.5, 1.0 - alpha / 2.0], method="linear")
        summary[model_id] = {
            "lower_rank_quantile": float(quantiles[0]),
            "median_rank": float(quantiles[1]),
            "upper_rank_quantile": float(quantiles[2]),
            "probability_rank_1": float(np.mean(values == 1)),
        }
    return summary


def _pairwise_stability(scores: np.ndarray, model_ids: tuple[str, ...]) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    for left_index, left in enumerate(model_ids):
        for right_index in range(left_index + 1, len(model_ids)):
            right = model_ids[right_index]
            difference = scores[:, left_index] - scores[:, right_index]
            equal = np.abs(difference) <= RANK_EQUALITY_TOLERANCE
            result[f"{left}|{right}"] = {
                "gt_frequency": float(np.mean(difference > RANK_EQUALITY_TOLERANCE)),
                "eq_frequency": float(np.mean(equal)),
                "lt_frequency": float(np.mean(difference < -RANK_EQUALITY_TOLERANCE)),
            }
    return result


def _validate_full_population(population: PopulationResult, config: BootstrapConfig) -> None:
    if population.eligible.empty:
        _bootstrap_error(BootstrapErrorCode.BOOTSTRAP_INPUT_ERROR, "bootstrap population is empty")
    if config.resampling_unit == "judge_cluster":
        _cluster_groups(population.eligible)


def _formal_ci_valid(config: BootstrapConfig, failed_replicates: int) -> bool:
    return config.formal_replicate_target_met and failed_replicates == 0


def run_bootstrap(
    population: PopulationResult,
    config: BootstrapConfig,
) -> BootstrapResult:
    """Run fixed-attempt bootstrap over an explicit population view."""
    _validate_full_population(population, config)
    try:
        point_estimate = fit_preference(population, config.estimator_config)
    except PreferenceEstimationError as error:
        _bootstrap_error(
            BootstrapErrorCode.POINT_ESTIMATE_FAILED,
            "full-sample point estimate failed",
            underlying_code=error.code.value,
        )

    source_frame = _deterministic_frame(population.eligible)
    cluster_plan = _cluster_groups(source_frame) if config.resampling_unit == "judge_cluster" else None
    expected_models = set(point_estimate.model_ids)
    model_ids = point_estimate.model_ids
    model_count = len(model_ids)
    score_replicates = np.full((config.replicate_count, model_count), np.nan, dtype=float)
    rank_replicates = np.full((config.replicate_count, model_count), np.nan, dtype=float)
    tie_parameter_replicates = np.full(config.replicate_count, np.nan, dtype=float)
    statuses: list[str] = []
    failure_counts: Counter[str] = Counter()
    rng = np.random.Generator(np.random.PCG64(config.seed))

    for replicate_index in range(config.replicate_count):
        if config.resampling_unit == "judge_cluster":
            assert cluster_plan is not None
            replicate_frame = _resample_cluster_rows_from_groups(*cluster_plan, rng)
        else:
            replicate_frame = _resample_rows(source_frame, rng)
        observed_models = _replicate_model_ids(replicate_frame)
        missing_models = expected_models.difference(observed_models)
        if missing_models:
            status = BootstrapErrorCode.MODEL_ABSENT.value
            statuses.append(status)
            failure_counts[status] += 1
            continue
        try:
            estimate = fit_preference(replace(population, eligible=replicate_frame), config.estimator_config)
        except PreferenceEstimationError as error:
            status = error.code.value
            statuses.append(status)
            failure_counts[status] += 1
            continue
        if estimate.model_ids != model_ids:
            _bootstrap_error(
                BootstrapErrorCode.INTERNAL_ERROR,
                "successful replicate returned a different model universe",
            )
        score_replicates[replicate_index, :] = estimate.latent_scores
        rank_replicates[replicate_index, :] = estimate.derived_rank
        if estimate.tie_parameter is not None:
            tie_parameter_replicates[replicate_index] = estimate.tie_parameter
        statuses.append("SUCCESS")

    successful = sum(status == "SUCCESS" for status in statuses)
    failed = config.replicate_count - successful
    formal_target_met = config.formal_replicate_target_met
    formal_ci_valid = _formal_ci_valid(config, failed)
    successful_scores = score_replicates[np.isfinite(score_replicates).all(axis=1)]
    successful_ranks = rank_replicates[np.isfinite(rank_replicates).all(axis=1)]
    score_intervals = (
        _score_intervals(successful_scores, model_ids, config.confidence_level)
        if successful and failed == 0
        else None
    )
    rank_summary = _rank_summary(successful_ranks, model_ids, config.confidence_level) if successful else {}
    pairwise = _pairwise_stability(successful_scores, model_ids) if successful else {}
    tie_values = tie_parameter_replicates[np.isfinite(tie_parameter_replicates)]
    tie_interval = _percentile_interval(tie_values, config.confidence_level) if failed == 0 and len(tie_values) else None
    warnings: list[str] = []
    if not formal_target_met:
        warnings.append("replicate_count is below the formal 2,000-attempt target")
    if failed:
        warnings.append("formal confidence intervals are invalid because one or more replicates failed")
    return BootstrapResult(
        point_estimate=point_estimate,
        bootstrap_config=config,
        model_ids=model_ids,
        attempted_replicates=config.replicate_count,
        successful_replicates=successful,
        failed_replicates=failed,
        formal_replicate_target_met=formal_target_met,
        formal_ci_valid=formal_ci_valid,
        failure_counts=dict(sorted(failure_counts.items())),
        replicate_status=tuple(statuses),
        score_replicates=score_replicates,
        rank_replicates=rank_replicates,
        tie_parameter_replicates=tie_parameter_replicates,
        score_intervals=score_intervals,
        rank_summary=rank_summary,
        pairwise_stability=pairwise,
        tie_parameter_interval=tie_interval,
        warnings=tuple(warnings),
    )
