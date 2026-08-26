"""Deterministic E1-to-E2 normalization for the frozen formal results bundle."""

from __future__ import annotations

from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Any, Mapping

from src.formal_results import FrozenResearchBundle, FrozenRunResult, FROZEN_RUNS


class PresentationModelError(ValueError):
    """Raised when a frozen bundle cannot satisfy the presentation contract."""


@dataclass(frozen=True)
class FormalModelResult:
    """One model's point estimate and already-frozen uncertainty summaries."""

    analysis_label: str
    model_id: str
    point_rank: int
    point_score: float
    score_ci_low: float
    score_ci_high: float
    rank_median: float
    rank_ci_low: float
    rank_ci_high: float
    probability_rank_1: float


@dataclass(frozen=True)
class RobustnessResult:
    """Rank-only comparison for one frozen run versus Primary."""

    analysis_label: str
    run_id: str
    estimator: str
    outcome_policy: str
    population_id: str
    records: tuple["RobustnessRecord", ...]
    score_comparability: str


@dataclass(frozen=True)
class RobustnessRecord:
    analysis_label: str
    model_id: str
    point_rank: int
    rank_delta_vs_primary: int


@dataclass(frozen=True)
class HeterogeneityRecord:
    model_id: str
    primary_rank: int
    english_rank: int
    rank_delta: int


@dataclass(frozen=True)
class HeterogeneityResult:
    analysis_label: str
    classification: str
    causal_interpretation: str
    records: tuple[HeterogeneityRecord, ...]
    top4_set_preserved: bool
    top4_order_preserved: bool


@dataclass(frozen=True)
class ClaimMetadata:
    evidence_class: str = "E2_presentation_derivative"
    historical_population: bool = True
    current_leaderboard: bool = False
    capability_claim: bool = False
    causal_claim: bool = False
    external_generalization: bool = False


@dataclass(frozen=True)
class ReviewFacts:
    top4_set_preserved: bool
    top4_order_preserved: bool
    heterogeneity_classification: str
    forbidden_claims: tuple[str, ...]


@dataclass(frozen=True)
class FormalPresentationModel:
    """Immutable, claim-bounded presentation representation of E1 evidence."""

    source_dataset: str
    source_file_sha256: str
    source_snapshot_id: str
    source_revision: str
    primary: tuple[FormalModelResult, ...]
    robustness: tuple[RobustnessResult, ...]
    heterogeneity: HeterogeneityResult
    review_facts: ReviewFacts
    claims: ClaimMetadata = ClaimMetadata()


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PresentationModelError(f"{label} must be a mapping")
    return value


def _number(value: Any, label: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PresentationModelError(f"{label} must be numeric")
    if isinstance(value, float) and not math.isfinite(value):
        raise PresentationModelError(f"{label} must be finite")
    return value


def _run_model_records(run: FrozenRunResult) -> tuple[FormalModelResult, ...]:
    point = _mapping(run.point_estimate, f"{run.spec.analysis} point estimate")
    summary = _mapping(run.bootstrap_summary, f"{run.spec.analysis} bootstrap summary")
    model_ids = tuple(point.get("model_ids", ()))
    ranks = tuple(point.get("derived_rank", ()))
    scores = tuple(point.get("latent_scores", ()))
    rank_summary = _mapping(summary.get("rank_summary"), f"{run.spec.analysis} rank summary")
    score_intervals = _mapping(summary.get("score_intervals"), f"{run.spec.analysis} score intervals")
    if not model_ids or any(not isinstance(model_id, str) or not model_id for model_id in model_ids) or len(set(model_ids)) != len(model_ids) or len({*ranks}) != len(ranks) or len(model_ids) != len(ranks) or len(model_ids) != len(scores):
        raise PresentationModelError(f"{run.spec.analysis} model/rank/score vectors are inconsistent")
    if set(ranks) != set(range(1, len(model_ids) + 1)):
        raise PresentationModelError(f"{run.spec.analysis} point ranks are not a permutation")
    records: list[FormalModelResult] = []
    for index, model_id in enumerate(model_ids):
        interval = score_intervals.get(model_id)
        rank_values = _mapping(rank_summary.get(model_id), f"{run.spec.analysis} rank summary for {model_id}")
        if not isinstance(interval, (list, tuple)) or len(interval) != 2:
            raise PresentationModelError(f"{run.spec.analysis} score interval is invalid for {model_id}")
        if not isinstance(ranks[index], int) or isinstance(ranks[index], bool):
            raise PresentationModelError(f"{run.spec.analysis} point rank is not an integer for {model_id}")
        score_low = _number(interval[0], "score interval lower bound")
        score_high = _number(interval[1], "score interval upper bound")
        rank_low = _number(rank_values["lower_rank_quantile"], "rank lower bound")
        rank_median = _number(rank_values["median_rank"], "rank median")
        rank_high = _number(rank_values["upper_rank_quantile"], "rank upper bound")
        probability = _number(rank_values["probability_rank_1"], "rank-1 probability")
        n_models = len(model_ids)
        if score_low > score_high or not (1 <= rank_low <= rank_median <= rank_high <= n_models) or not 0 <= probability <= 1:
            raise PresentationModelError(f"{run.spec.analysis} presentation bounds are invalid for {model_id}")
        records.append(FormalModelResult(
            analysis_label=run.spec.analysis,
            model_id=model_id,
            point_rank=int(_number(ranks[index], "point rank")),
            point_score=float(_number(scores[index], "point score")),
            score_ci_low=float(score_low),
            score_ci_high=float(score_high),
            rank_median=float(rank_median),
            rank_ci_low=float(rank_low),
            rank_ci_high=float(rank_high),
            probability_rank_1=float(probability),
        ))
    return tuple(sorted(records, key=lambda record: record.point_rank))


def _review_claim(review: Mapping[str, Any]) -> Mapping[str, Any]:
    for claim in review.get("claim_classification", ()):
        if isinstance(claim, Mapping) and claim.get("claim_level") == "C3 heterogeneity":
            return claim
    raise PresentationModelError("comparative review is missing the frozen S6 heterogeneity claim")


def build_formal_presentation(bundle: FrozenResearchBundle) -> FormalPresentationModel:
    """Purely normalize one already-verified bundle; no filesystem access or inference."""
    if not isinstance(bundle, FrozenResearchBundle):
        raise TypeError("build_formal_presentation expects FrozenResearchBundle")
    expected_labels = tuple(spec.analysis for spec in FROZEN_RUNS)
    if len(bundle.runs) != len(FROZEN_RUNS) or tuple(run.spec.analysis for run in bundle.runs) != expected_labels:
        raise PresentationModelError("bundle does not contain the closed-world frozen run set")
    expected_ids = {spec.run_id for spec in FROZEN_RUNS}
    if {run.spec.run_id for run in bundle.runs} != expected_ids:
        raise PresentationModelError("bundle run identities differ from the frozen registry")
    review = _mapping(bundle.comparative_review, "comparative review")
    primary_manifest = _mapping(bundle.runs[0].manifest, "Primary manifest")
    source_dataset = primary_manifest.get("source_dataset")
    source_file_sha256 = primary_manifest.get("source_file_sha256")
    source_snapshot_id = primary_manifest.get("source_snapshot_id")
    source_revision = primary_manifest.get("source_revision")
    if not all(isinstance(value, str) for value in (source_dataset, source_file_sha256, source_snapshot_id, source_revision)):
        raise PresentationModelError("Primary manifest is missing frozen source provenance")

    primary_run = bundle.runs[0]
    primary = _run_model_records(primary_run)
    primary_ranks = {record.model_id: record.point_rank for record in primary}
    robustness: list[RobustnessResult] = []
    for run in bundle.runs:
        run_records = _run_model_records(run)
        run_by_model = {record.model_id: record for record in run_records}
        if set(run_by_model) != set(primary_ranks):
            raise PresentationModelError(f"{run.spec.analysis} model universe differs from Primary")
        records = tuple(RobustnessRecord(run.spec.analysis, model_id, run_by_model[model_id].point_rank, run_by_model[model_id].point_rank - primary_ranks[model_id]) for model_id in primary_ranks)
        if run.spec.analysis == "Primary" or (run.spec.estimator == primary_run.spec.estimator and run.spec.outcome_policy == primary_run.spec.outcome_policy):
            comparability = "same_estimator_parameterization_only"
        else:
            comparability = "latent_scores_not_comparable_with_primary"
        robustness.append(RobustnessResult(run.spec.analysis, run.spec.run_id, run.spec.estimator, run.spec.outcome_policy, run.spec.population_id, records, comparability))

    s6 = next(run for run in bundle.runs if run.spec.analysis == "S6-English")
    english = {record.model_id: record.point_rank for record in _run_model_records(s6)}
    s6_review = _mapping(review.get("s6_heterogeneity"), "S6 heterogeneity review")
    movement = _mapping(s6_review.get("rank_movement"), "S6 rank movement review")
    claim = _review_claim(review)
    classification = claim.get("classification")
    interpretation = s6_review.get("interpretation_boundary")
    if not isinstance(classification, str) or not classification.strip() or not isinstance(interpretation, str) or not interpretation.strip():
        raise PresentationModelError("S6 review classification and interpretation must be non-empty strings")
    if "not a causal" not in interpretation.lower():
        raise PresentationModelError("S6 review does not preserve its non-causal interpretation boundary")
    if movement.get("top4_set_preserved") is not True or movement.get("top4_order_preserved") is not True:
        raise PresentationModelError("frozen S6 top-four preservation facts are missing or false")
    heterogeneity = HeterogeneityResult(
        analysis_label="S6-English",
        classification=classification,
        causal_interpretation="NOT SUPPORTED",
        records=tuple(HeterogeneityRecord(model_id, primary_ranks[model_id], english[model_id], english[model_id] - primary_ranks[model_id]) for model_id in primary_ranks),
        top4_set_preserved=True,
        top4_order_preserved=True,
    )
    forbidden = review.get("forbidden_claims", ())
    if not isinstance(forbidden, (list, tuple)) or any(not isinstance(item, str) for item in forbidden):
        raise PresentationModelError("comparative review forbidden claims are malformed")
    facts = ReviewFacts(True, True, classification, tuple(forbidden))
    return FormalPresentationModel(source_dataset, source_file_sha256, source_snapshot_id, source_revision, primary, tuple(robustness), heterogeneity, facts)


__all__ = [
    "ClaimMetadata", "FormalModelResult", "FormalPresentationModel", "HeterogeneityRecord",
    "HeterogeneityResult", "PresentationModelError", "ReviewFacts", "RobustnessRecord",
    "RobustnessResult", "build_formal_presentation",
]
