"""Numerically stable paired-comparison preference estimators.

This module deliberately consumes an explicit ``PopulationResult`` rather than
selecting a population itself.  It implements the Phase 2C core estimators only;
bootstrap, uncertainty intervals, and real-data execution remain out of scope.
"""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
from enum import Enum
import math
from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from src.battle_contract import CanonicalOutcome
from src.population import PopulationResult


ESTIMATOR_VERSION = 1
SUM_TO_ZERO_CONSTRAINT = "sum_to_zero"
L_BFGS_B_OPTIMIZER = "L-BFGS-B"
RANK_EQUALITY_TOLERANCE = 1e-10


class EstimationErrorCode(str, Enum):
    """Stable failure codes for formal estimator input and fit failures."""

    MISSING_REQUIRED_COLUMNS = "MISSING_REQUIRED_COLUMNS"
    INVALID_OUTCOME = "INVALID_OUTCOME"
    INVALID_MODEL_ID = "INVALID_MODEL_ID"
    ZERO_LIKELIHOOD_ROWS = "ZERO_LIKELIHOOD_ROWS"
    INSUFFICIENT_MODELS = "INSUFFICIENT_MODELS"
    MODEL_DROPPED_BY_OUTCOME_POLICY = "MODEL_DROPPED_BY_OUTCOME_POLICY"
    DISCONNECTED_GRAPH = "DISCONNECTED_GRAPH"
    SEPARATION = "SEPARATION"
    UNIDENTIFIABLE_TIE_PARAMETER = "UNIDENTIFIABLE_TIE_PARAMETER"
    OPTIMIZATION_FAILED = "OPTIMIZATION_FAILED"
    NONFINITE_RESULT = "NONFINITE_RESULT"


class PreferenceEstimationError(ValueError):
    """A deterministic domain error that never exposes optimizer internals."""

    def __init__(self, code: EstimationErrorCode, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code.value}: {message}")


@dataclass(frozen=True)
class PreferenceEstimatorConfig:
    """Frozen configuration for one core paired-comparison fit."""

    estimator_name: str
    identifiability_constraint: str = SUM_TO_ZERO_CONSTRAINT
    optimizer: str = L_BFGS_B_OPTIMIZER
    regularization: None = None
    max_iterations: int = 1_000
    tolerance: float = 1e-9

    def __post_init__(self) -> None:
        if self.estimator_name not in {"davidson", "bradley_terry_decisive"}:
            raise ValueError("estimator_name must be 'davidson' or 'bradley_terry_decisive'")
        if self.identifiability_constraint != SUM_TO_ZERO_CONSTRAINT:
            raise ValueError("identifiability_constraint must be 'sum_to_zero'")
        if self.optimizer != L_BFGS_B_OPTIMIZER:
            raise ValueError("optimizer must be 'L-BFGS-B'")
        if self.regularization is not None:
            raise ValueError("regularization must be None for the core estimators")
        if isinstance(self.max_iterations, bool) or not isinstance(self.max_iterations, int) or self.max_iterations <= 0:
            raise ValueError("max_iterations must be a positive integer")
        if isinstance(self.tolerance, bool) or not math.isfinite(self.tolerance) or self.tolerance <= 0:
            raise ValueError("tolerance must be a finite positive number")

    def to_dict(self) -> dict[str, str | int | float | None]:
        """Return JSON-compatible configuration suitable for a RunManifest."""
        return {
            "estimator": self.estimator_name,
            "estimator_version": ESTIMATOR_VERSION,
            "outcome_policy": _outcome_policy_name(self),
            "identifiability": self.identifiability_constraint,
            "optimizer": self.optimizer,
            "regularization": self.regularization,
            "max_iterations": self.max_iterations,
            "tolerance": self.tolerance,
        }


@dataclass(frozen=True)
class PreferenceEstimationResult:
    """A successful core estimator fit; rank is derived, not the sole output."""

    estimator_name: str
    estimator_version: int
    estimator_config: dict[str, str | int | float | None]
    outcome_policy: str
    population_id: str
    population_spec_version: int
    model_ids: tuple[str, ...]
    latent_scores: tuple[float, ...]
    derived_rank: tuple[int, ...]
    identifiability_constraint: str
    population_eligible_battle_count: int
    likelihood_battle_count: int
    likelihood_outcome_counts: dict[str, int]
    excluded_outcome_counts: dict[str, int]
    population_model_count: int
    estimator_model_count: int
    dropped_models_due_to_outcome_policy: tuple[str, ...]
    graph_node_count: int
    graph_edge_count: int
    graph_component_count: int
    converged: bool
    optimizer_name: str
    iterations: int
    objective: float
    tie_parameter: float | None
    warnings: tuple[str, ...]


_REQUIRED_COLUMNS = frozenset({"model_a_id", "model_b_id", "canonical_outcome", "battle_id"})
_ALL_KNOWN_OUTCOMES = frozenset(outcome.value for outcome in CanonicalOutcome)
_DAVIDSON_OUTCOMES = frozenset({
    CanonicalOutcome.MODEL_A_WIN.value,
    CanonicalOutcome.MODEL_B_WIN.value,
    CanonicalOutcome.TIE.value,
})
_BT_DECISIVE_OUTCOMES = frozenset({
    CanonicalOutcome.MODEL_A_WIN.value,
    CanonicalOutcome.MODEL_B_WIN.value,
})


def _error(code: EstimationErrorCode, message: str) -> None:
    raise PreferenceEstimationError(code, message)


def _validate_population_frame(frame: pd.DataFrame) -> None:
    missing = sorted(_REQUIRED_COLUMNS.difference(frame.columns))
    if missing:
        _error(EstimationErrorCode.MISSING_REQUIRED_COLUMNS, f"missing required columns: {missing}")
    for column in ("model_a_id", "model_b_id"):
        invalid = ~frame[column].map(lambda value: isinstance(value, str) and bool(value.strip()))
        if invalid.any():
            _error(EstimationErrorCode.INVALID_MODEL_ID, f"invalid model identifier in {column}")
    unknown = set(frame["canonical_outcome"].astype("string").dropna()).difference(_ALL_KNOWN_OUTCOMES)
    if unknown or frame["canonical_outcome"].isna().any():
        _error(EstimationErrorCode.INVALID_OUTCOME, "population contains an unsupported canonical outcome")
    if frame["canonical_outcome"].eq(CanonicalOutcome.INVALID_UNKNOWN.value).any():
        _error(EstimationErrorCode.INVALID_OUTCOME, "population contains invalid_unknown")


def _outcome_policy(config: PreferenceEstimatorConfig) -> frozenset[str]:
    return _DAVIDSON_OUTCOMES if config.estimator_name == "davidson" else _BT_DECISIVE_OUTCOMES


def _outcome_policy_name(config: PreferenceEstimatorConfig) -> str:
    return "ordinary_tie_only" if config.estimator_name == "davidson" else "decisive_only"


def _ordered_model_ids(frame: pd.DataFrame) -> tuple[str, ...]:
    return tuple(sorted(set(frame["model_a_id"]).union(frame["model_b_id"])))


def _graph_diagnostics(frame: pd.DataFrame, model_ids: tuple[str, ...]) -> tuple[int, int]:
    adjacency = {model: set() for model in model_ids}
    edges: set[tuple[str, str]] = set()
    for model_a, model_b in frame[["model_a_id", "model_b_id"]].itertuples(index=False, name=None):
        if model_a == model_b:
            continue
        left, right = sorted((model_a, model_b))
        edges.add((left, right))
        adjacency[left].add(right)
        adjacency[right].add(left)

    remaining = set(model_ids)
    components = 0
    while remaining:
        components += 1
        queue: deque[str] = deque([min(remaining)])
        while queue:
            model = queue.popleft()
            if model not in remaining:
                continue
            remaining.remove(model)
            queue.extend(sorted(adjacency[model].intersection(remaining)))
    return len(edges), components


def _is_strongly_connected_decisive_graph(frame: pd.DataFrame, model_ids: tuple[str, ...]) -> bool:
    """Check the finite-MLE condition for a decisive Bradley-Terry fit."""
    forward = {model: set() for model in model_ids}
    reverse = {model: set() for model in model_ids}
    for model_a, model_b, outcome in frame[["model_a_id", "model_b_id", "canonical_outcome"]].itertuples(
        index=False, name=None
    ):
        winner, loser = (
            (model_a, model_b)
            if outcome == CanonicalOutcome.MODEL_A_WIN.value
            else (model_b, model_a)
        )
        if winner != loser:
            forward[winner].add(loser)
            reverse[loser].add(winner)

    def reachable(adjacency: dict[str, set[str]]) -> set[str]:
        seen: set[str] = set()
        queue: deque[str] = deque([model_ids[0]])
        while queue:
            model = queue.popleft()
            if model in seen:
                continue
            seen.add(model)
            queue.extend(sorted(adjacency[model].difference(seen)))
        return seen

    return reachable(forward) == set(model_ids) and reachable(reverse) == set(model_ids)


def _scores_from_free_parameters(free_parameters: np.ndarray) -> np.ndarray:
    return np.concatenate((free_parameters, np.array([-np.sum(free_parameters)])))


def _dense_ranks(model_ids: tuple[str, ...], scores: np.ndarray) -> tuple[int, ...]:
    sorted_indices = sorted(range(len(model_ids)), key=lambda index: (-scores[index], model_ids[index]))
    ranks = [0] * len(model_ids)
    rank = 0
    previous_score: float | None = None
    for index in sorted_indices:
        score = float(scores[index])
        if previous_score is None or not math.isclose(
            score, previous_score, abs_tol=RANK_EQUALITY_TOLERANCE, rel_tol=0.0
        ):
            rank += 1
            previous_score = score
        ranks[index] = rank
    return tuple(ranks)


def _negative_log_likelihood(
    parameters: np.ndarray,
    *,
    estimator_name: str,
    model_a_indices: np.ndarray,
    model_b_indices: np.ndarray,
    outcomes: np.ndarray,
    weights: np.ndarray,
    model_count: int,
) -> float:
    scores = _scores_from_free_parameters(parameters[: model_count - 1])
    score_a = scores[model_a_indices]
    score_b = scores[model_b_indices]
    if estimator_name == "bradley_terry_decisive":
        losses = np.where(
            outcomes == CanonicalOutcome.MODEL_A_WIN.value,
            np.logaddexp(0.0, score_b - score_a),
            np.logaddexp(0.0, score_a - score_b),
        )
        return float(np.sum(weights * losses))

    log_nu = parameters[-1]
    tie_term = log_nu + 0.5 * (score_a + score_b)
    log_denominator = np.logaddexp(np.logaddexp(score_a, score_b), tie_term)
    chosen_term = np.where(
        outcomes == CanonicalOutcome.MODEL_A_WIN.value,
        score_a,
        np.where(outcomes == CanonicalOutcome.MODEL_B_WIN.value, score_b, tie_term),
    )
    return float(np.sum(weights * (log_denominator - chosen_term)))


def _negative_log_likelihood_gradient(
    parameters: np.ndarray,
    *,
    estimator_name: str,
    model_a_indices: np.ndarray,
    model_b_indices: np.ndarray,
    outcomes: np.ndarray,
    weights: np.ndarray,
    model_count: int,
) -> np.ndarray:
    """Return an analytic gradient for the constrained score parameterization."""
    scores = _scores_from_free_parameters(parameters[: model_count - 1])
    score_a = scores[model_a_indices]
    score_b = scores[model_b_indices]
    gradient = np.zeros(model_count, dtype=float)

    if estimator_name == "bradley_terry_decisive":
        probability_a = np.exp(-np.logaddexp(0.0, score_b - score_a))
        gradient_delta = np.where(
            outcomes == CanonicalOutcome.MODEL_A_WIN.value,
            probability_a - 1.0,
            probability_a,
        )
        np.add.at(gradient, model_a_indices, weights * gradient_delta)
        np.add.at(gradient, model_b_indices, -weights * gradient_delta)
        return gradient[:-1] - gradient[-1]

    log_nu = parameters[-1]
    tie_term = log_nu + 0.5 * (score_a + score_b)
    log_denominator = np.logaddexp(np.logaddexp(score_a, score_b), tie_term)
    probability_a = np.exp(score_a - log_denominator)
    probability_b = np.exp(score_b - log_denominator)
    probability_tie = np.exp(tie_term - log_denominator)
    observed_a = (outcomes == CanonicalOutcome.MODEL_A_WIN.value).astype(float)
    observed_b = (outcomes == CanonicalOutcome.MODEL_B_WIN.value).astype(float)
    observed_tie = (outcomes == CanonicalOutcome.TIE.value).astype(float)
    gradient_a = probability_a + 0.5 * probability_tie - observed_a - 0.5 * observed_tie
    gradient_b = probability_b + 0.5 * probability_tie - observed_b - 0.5 * observed_tie
    np.add.at(gradient, model_a_indices, weights * gradient_a)
    np.add.at(gradient, model_b_indices, weights * gradient_b)
    free_gradient = gradient[:-1] - gradient[-1]
    tie_gradient = np.sum(weights * (probability_tie - observed_tie))
    return np.concatenate((free_gradient, np.array([tie_gradient])))


def fit_preference(
    population: PopulationResult,
    config: PreferenceEstimatorConfig,
) -> PreferenceEstimationResult:
    """Fit one frozen Phase 2C core estimator to an explicit population view."""
    frame = population.eligible.copy()
    _validate_population_frame(frame)
    allowed_outcomes = _outcome_policy(config)
    population_models = _ordered_model_ids(frame)
    likelihood = frame.loc[frame["canonical_outcome"].isin(allowed_outcomes)].copy()
    if likelihood.empty:
        _error(EstimationErrorCode.ZERO_LIKELIHOOD_ROWS, "no rows satisfy the estimator outcome policy")

    estimator_models = _ordered_model_ids(likelihood)
    if len(estimator_models) < 2:
        _error(EstimationErrorCode.INSUFFICIENT_MODELS, "at least two estimator-effective models are required")
    dropped_models = tuple(model for model in population_models if model not in set(estimator_models))
    if dropped_models:
        _error(
            EstimationErrorCode.MODEL_DROPPED_BY_OUTCOME_POLICY,
            "an outcome policy removed one or more population models",
        )

    graph_edge_count, graph_component_count = _graph_diagnostics(likelihood, estimator_models)
    if graph_component_count != 1:
        _error(EstimationErrorCode.DISCONNECTED_GRAPH, "estimator-effective comparison graph is disconnected")
    if config.estimator_name == "bradley_terry_decisive" and not _is_strongly_connected_decisive_graph(
        likelihood, estimator_models
    ):
        _error(EstimationErrorCode.SEPARATION, "decisive outcome graph does not admit a finite Bradley-Terry MLE")
    if config.estimator_name == "davidson":
        has_tie = likelihood["canonical_outcome"].eq(CanonicalOutcome.TIE.value).any()
        has_decisive = likelihood["canonical_outcome"].isin(_BT_DECISIVE_OUTCOMES).any()
        if not has_tie or not has_decisive:
            _error(
                EstimationErrorCode.UNIDENTIFIABLE_TIE_PARAMETER,
                "Davidson requires at least one ordinary tie and one decisive outcome",
            )

    index_by_model = {model: index for index, model in enumerate(estimator_models)}
    aggregated = (
        pd.DataFrame({
            "model_a_index": likelihood["model_a_id"].map(index_by_model),
            "model_b_index": likelihood["model_b_id"].map(index_by_model),
            "outcome": likelihood["canonical_outcome"],
        })
        .groupby(["model_a_index", "model_b_index", "outcome"], sort=True, as_index=False)
        .size()
    )
    model_a_indices = aggregated["model_a_index"].to_numpy(dtype=int)
    model_b_indices = aggregated["model_b_index"].to_numpy(dtype=int)
    outcomes = aggregated["outcome"].to_numpy(dtype=str)
    weights = aggregated["size"].to_numpy(dtype=float)
    initial = np.zeros(len(estimator_models) if config.estimator_name == "davidson" else len(estimator_models) - 1)

    def objective(parameters: np.ndarray) -> float:
        return _negative_log_likelihood(
            parameters,
            estimator_name=config.estimator_name,
            model_a_indices=model_a_indices,
            model_b_indices=model_b_indices,
            outcomes=outcomes,
            weights=weights,
            model_count=len(estimator_models),
        )

    def objective_gradient(parameters: np.ndarray) -> np.ndarray:
        return _negative_log_likelihood_gradient(
            parameters,
            estimator_name=config.estimator_name,
            model_a_indices=model_a_indices,
            model_b_indices=model_b_indices,
            outcomes=outcomes,
            weights=weights,
            model_count=len(estimator_models),
        )

    optimization = minimize(
        objective,
        initial,
        jac=objective_gradient,
        method=config.optimizer,
        tol=config.tolerance,
        options={"maxiter": config.max_iterations},
    )
    if not optimization.success:
        _error(EstimationErrorCode.OPTIMIZATION_FAILED, "optimizer did not converge")
    if not np.isfinite(optimization.fun) or not np.isfinite(optimization.x).all():
        _error(EstimationErrorCode.NONFINITE_RESULT, "optimizer returned nonfinite parameters or objective")

    scores = _scores_from_free_parameters(optimization.x[: len(estimator_models) - 1])
    tie_parameter: float | None = None
    if config.estimator_name == "davidson":
        with np.errstate(over="ignore", invalid="ignore"):
            tie_parameter = float(np.exp(optimization.x[-1]))
        if not math.isfinite(tie_parameter) or tie_parameter <= 0:
            _error(EstimationErrorCode.NONFINITE_RESULT, "Davidson tie parameter is nonfinite")
    if not np.isfinite(scores).all() or not math.isclose(float(np.sum(scores)), 0.0, abs_tol=1e-10):
        _error(EstimationErrorCode.NONFINITE_RESULT, "sum-to-zero scores are nonfinite or invalid")

    all_counts = Counter(frame["canonical_outcome"])
    likelihood_counts = {outcome: int(all_counts[outcome]) for outcome in sorted(allowed_outcomes)}
    excluded_counts = {
        outcome: int(all_counts[outcome])
        for outcome in sorted(_ALL_KNOWN_OUTCOMES.difference(allowed_outcomes))
        if all_counts[outcome]
    }
    return PreferenceEstimationResult(
        estimator_name=config.estimator_name,
        estimator_version=ESTIMATOR_VERSION,
        estimator_config=config.to_dict(),
        outcome_policy=_outcome_policy_name(config),
        population_id=population.spec.population_id,
        population_spec_version=population.spec.population_spec_version,
        model_ids=estimator_models,
        latent_scores=tuple(float(score) for score in scores),
        derived_rank=_dense_ranks(estimator_models, scores),
        identifiability_constraint=config.identifiability_constraint,
        population_eligible_battle_count=len(frame),
        likelihood_battle_count=len(likelihood),
        likelihood_outcome_counts=likelihood_counts,
        excluded_outcome_counts=excluded_counts,
        population_model_count=len(population_models),
        estimator_model_count=len(estimator_models),
        dropped_models_due_to_outcome_policy=dropped_models,
        graph_node_count=len(estimator_models),
        graph_edge_count=graph_edge_count,
        graph_component_count=graph_component_count,
        converged=True,
        optimizer_name=config.optimizer,
        iterations=int(optimization.nit),
        objective=float(optimization.fun),
        tie_parameter=tie_parameter,
        warnings=(),
    )
