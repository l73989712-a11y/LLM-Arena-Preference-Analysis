from __future__ import annotations

from dataclasses import FrozenInstanceError
from types import MappingProxyType

import numpy as np
import pytest

import src.formal_presentation as presentation
import src.formal_results as formal_results
from src.formal_results import FrozenResearchBundle, FrozenRunResult


MODEL_IDS = tuple(f"model-{index:02d}" for index in range(20))


def _bundle() -> FrozenResearchBundle:
    runs: list[FrozenRunResult] = []
    primary_ranks = {model: index + 1 for index, model in enumerate(MODEL_IDS)}
    storage_ids = tuple(reversed(MODEL_IDS))
    for spec in formal_results.FROZEN_RUNS:
        ranks = dict(primary_ranks)
        if spec.analysis == "S6-English":
            ranks[MODEL_IDS[4]], ranks[MODEL_IDS[5]] = 6, 5
        ordered_ranks = [ranks[model] for model in storage_ids]
        point = {
            "model_ids": list(storage_ids),
            "derived_rank": ordered_ranks,
            "latent_scores": [float(-rank) for rank in ordered_ranks],
        }
        summary = {
            "score_intervals": {model: [-float(rank) - 0.1, -float(rank) + 0.1] for model, rank in ranks.items()},
            "rank_summary": {model: {"median_rank": float(rank), "lower_rank_quantile": float(rank), "upper_rank_quantile": float(rank), "probability_rank_1": 1.0 if rank == 1 else 0.0} for model, rank in ranks.items()},
        }
        manifest = {"source_dataset": formal_results.FROZEN_SOURCE.dataset, "source_file_sha256": formal_results.FROZEN_SOURCE.file_sha256, "source_snapshot_id": formal_results.FROZEN_SOURCE.snapshot_id, "source_revision": formal_results.FROZEN_SOURCE.revision}
        runs.append(FrozenRunResult(spec, formal_results._freeze(manifest), formal_results._freeze(point), formal_results._freeze(summary), MappingProxyType({}), np.empty((0,)), np.empty((0,)), np.empty((0,))))
    review = {
        "s6_heterogeneity": {
            "interpretation_boundary": "subgroup heterogeneity evidence; not a causal language effect",
            "rank_movement": {"top4_set_preserved": True, "top4_order_preserved": True},
        },
        "claim_classification": [{"claim_level": "C3 heterogeneity", "classification": "partially robust / heterogeneous"}],
        "forbidden_claims": ["causal claims", "current leaderboard claims"],
    }
    return FrozenResearchBundle(tuple(runs), formal_results._freeze(review))


def test_primary_records_are_exactly_once_and_trace_to_e1() -> None:
    model = presentation.build_formal_presentation(_bundle())
    assert len(model.primary) == 20
    assert tuple(record.model_id for record in model.primary) == MODEL_IDS
    assert tuple(record.point_rank for record in model.primary) == tuple(range(1, 21))
    assert model.primary[0].point_score == -1.0
    assert model.primary[0].score_ci_low == -1.1
    assert model.primary[0].rank_median == 1.0
    assert model.source_dataset == formal_results.FROZEN_SOURCE.dataset
    assert model.source_file_sha256 == formal_results.FROZEN_SOURCE.file_sha256
    assert model.source_snapshot_id == formal_results.FROZEN_SOURCE.snapshot_id


def test_storage_order_is_normalized_to_ascending_point_rank() -> None:
    model = presentation.build_formal_presentation(_bundle())
    assert tuple(record.point_rank for record in model.primary) == tuple(range(1, 21))
    assert tuple(record.model_id for record in model.primary) == MODEL_IDS
    for result in model.robustness:
        assert tuple(record.model_id for record in result.records) == MODEL_IDS
    assert tuple(record.model_id for record in model.heterogeneity.records) == MODEL_IDS


def test_robustness_is_closed_world_and_rank_only() -> None:
    model = presentation.build_formal_presentation(_bundle())
    assert tuple(result.analysis_label for result in model.robustness) == tuple(spec.analysis for spec in formal_results.FROZEN_RUNS)
    assert len(model.robustness) == 9
    s6 = next(result for result in model.robustness if result.analysis_label == "S6-English")
    assert next(record for record in s6.records if record.model_id == "model-04").rank_delta_vs_primary == 1
    assert not hasattr(s6.records[0], "point_score")
    assert next(result for result in model.robustness if result.analysis_label == "S2").score_comparability == "latent_scores_not_comparable_with_primary"
    assert next(result for result in model.robustness if result.analysis_label == "S1").score_comparability == "latent_scores_not_comparable_with_primary"


def test_same_estimator_comparability_is_limited_to_parameterization() -> None:
    model = presentation.build_formal_presentation(_bundle())
    for label in ("Primary", "S3", "S4", "S5-ge10", "S5-ge20", "S5-ge50", "S6-English"):
        result = next(item for item in model.robustness if item.analysis_label == label)
        assert result.score_comparability == "same_estimator_parameterization_only"


def test_s6_heterogeneity_preserves_frozen_boundary() -> None:
    model = presentation.build_formal_presentation(_bundle())
    assert model.heterogeneity.classification == "partially robust / heterogeneous"
    assert model.heterogeneity.causal_interpretation == "NOT SUPPORTED"
    assert model.heterogeneity.top4_set_preserved is True
    assert model.heterogeneity.top4_order_preserved is True
    assert next(record for record in model.heterogeneity.records if record.model_id == "model-04").rank_delta == 1


def test_claim_metadata_and_output_are_immutable() -> None:
    model = presentation.build_formal_presentation(_bundle())
    with pytest.raises(FrozenInstanceError):
        model.primary = ()  # type: ignore[misc]
    with pytest.raises(TypeError):
        model.review_facts.forbidden_claims[0] = "tampered"  # type: ignore[index]
    with pytest.raises(AttributeError):
        model.robustness.append(None)  # type: ignore[attr-defined]
    assert model.claims.historical_population is True
    assert model.claims.current_leaderboard is False
    assert model.claims.capability_claim is False
    assert model.claims.causal_claim is False
    assert model.claims.external_generalization is False


def test_build_is_deterministic_and_does_not_mutate_input() -> None:
    bundle = _bundle()
    first = presentation.build_formal_presentation(bundle)
    second = presentation.build_formal_presentation(bundle)
    assert first == second
    assert bundle.runs[0].point_estimate["model_ids"] == tuple(reversed(MODEL_IDS))


def test_missing_frozen_run_set_is_rejected() -> None:
    bundle = _bundle()
    with pytest.raises(presentation.PresentationModelError, match="closed-world"):
        presentation.build_formal_presentation(FrozenResearchBundle(bundle.runs[:-1], bundle.comparative_review))


def test_unexpected_model_universe_raises_domain_error_before_rank_lookup() -> None:
    bundle = _bundle()
    target = bundle.runs[1]
    point = dict(target.point_estimate)
    storage_ids = list(point["model_ids"])
    storage_ids[0] = "unexpected-model"
    point["model_ids"] = tuple(storage_ids)
    summary = dict(target.bootstrap_summary)
    intervals = dict(summary["score_intervals"])
    rank_summary = dict(summary["rank_summary"])
    intervals["unexpected-model"] = intervals.pop(MODEL_IDS[-1])
    rank_summary["unexpected-model"] = rank_summary.pop(MODEL_IDS[-1])
    summary["score_intervals"] = formal_results._freeze(intervals)
    summary["rank_summary"] = formal_results._freeze(rank_summary)
    replacement = FrozenRunResult(target.spec, target.manifest, formal_results._freeze(point), formal_results._freeze(summary), target.replicate_status, target.bootstrap_scores, target.bootstrap_ranks, target.bootstrap_tie_parameter)
    runs = (bundle.runs[0], replacement) + bundle.runs[2:]
    with pytest.raises(presentation.PresentationModelError, match="model universe"):
        presentation.build_formal_presentation(FrozenResearchBundle(runs, bundle.comparative_review))


@pytest.mark.parametrize("field", ["classification", "interpretation_boundary"])
def test_review_semantic_metadata_must_be_non_empty_strings(field: str) -> None:
    bundle = _bundle()
    review = dict(bundle.comparative_review)
    if field == "classification":
        claims = [dict(item) for item in review["claim_classification"]]
        claims[0]["classification"] = None
        review["claim_classification"] = claims
    else:
        s6 = dict(review["s6_heterogeneity"])
        s6[field] = None
        review["s6_heterogeneity"] = s6
    with pytest.raises(presentation.PresentationModelError, match="non-empty strings"):
        presentation.build_formal_presentation(FrozenResearchBundle(bundle.runs, formal_results._freeze(review)))


@pytest.mark.parametrize("mutation", ["score", "rank", "probability"])
def test_numeric_presentation_bounds_fail_closed(mutation: str) -> None:
    bundle = _bundle()
    primary = bundle.runs[0]
    summary = dict(primary.bootstrap_summary)
    if mutation == "score":
        intervals = dict(summary["score_intervals"])
        intervals[MODEL_IDS[0]] = (1.0, 0.0)
        summary["score_intervals"] = formal_results._freeze(intervals)
    elif mutation == "rank":
        rank_summary = dict(summary["rank_summary"])
        rank_summary[MODEL_IDS[0]] = {"median_rank": 2.0, "lower_rank_quantile": 1.0, "upper_rank_quantile": 1.0, "probability_rank_1": 0.0}
        summary["rank_summary"] = formal_results._freeze(rank_summary)
    else:
        rank_summary = dict(summary["rank_summary"])
        rank_summary[MODEL_IDS[0]] = {"median_rank": 1.0, "lower_rank_quantile": 1.0, "upper_rank_quantile": 1.0, "probability_rank_1": 1.1}
        summary["rank_summary"] = formal_results._freeze(rank_summary)
    replacement = FrozenRunResult(primary.spec, primary.manifest, primary.point_estimate, formal_results._freeze(summary), primary.replicate_status, primary.bootstrap_scores, primary.bootstrap_ranks, primary.bootstrap_tie_parameter)
    with pytest.raises(presentation.PresentationModelError, match="bounds"):
        presentation.build_formal_presentation(FrozenResearchBundle((replacement,) + bundle.runs[1:], bundle.comparative_review))


def test_malformed_e1_vectors_fail_closed() -> None:
    bundle = _bundle()
    primary = bundle.runs[0]
    malformed = dict(primary.point_estimate)
    malformed["derived_rank"] = tuple([1] * 20)
    runs = (FrozenRunResult(primary.spec, primary.manifest, formal_results._freeze(malformed), primary.bootstrap_summary, primary.replicate_status, primary.bootstrap_scores, primary.bootstrap_ranks, primary.bootstrap_tie_parameter),) + bundle.runs[1:]
    with pytest.raises(presentation.PresentationModelError, match="vectors are inconsistent"):
        presentation.build_formal_presentation(FrozenResearchBundle(runs, bundle.comparative_review))
