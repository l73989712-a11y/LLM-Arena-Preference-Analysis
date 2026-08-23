from __future__ import annotations

from dataclasses import replace
import json

import numpy as np
import pandas as pd
import pytest

from src.battle_contract import SourceProvenance, canonicalize_battles
from src.population import BASE_RESEARCH, PopulationResult, apply_population
from src.preference_estimation import (
    EstimationErrorCode,
    PreferenceEstimationError,
    PreferenceEstimatorConfig,
    fit_preference,
)


PROVENANCE = SourceProvenance(source_dataset="synthetic/preference", source_revision="v1")


def _conversation() -> list[dict[str, str]]:
    return [
        {"role": "user", "content": "prompt"},
        {"role": "assistant", "content": "response"},
    ]


def _row(model_a: str, model_b: str, winner: str) -> dict[str, object]:
    return {
        "model_a": model_a,
        "model_b": model_b,
        "winner": winner,
        "conversation_a": _conversation(),
        "conversation_b": _conversation(),
        "tstamp": 0,
        "judge": "synthetic-judge",
        "language": "English",
        "anony": True,
    }


def _population(rows: list[dict[str, object]]) -> PopulationResult:
    canonical = canonicalize_battles(pd.DataFrame(rows), provenance=PROVENANCE)
    return apply_population(canonical, BASE_RESEARCH)


def _fit(rows: list[dict[str, object]], estimator: str) -> object:
    return fit_preference(_population(rows), PreferenceEstimatorConfig(estimator))


def _score_map(result: object) -> dict[str, float]:
    return dict(zip(result.model_ids, result.latent_scores))


def _swapped(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    mapping = {"model_a": "model_b", "model_b": "model_a", "tie": "tie", "tie (bothbad)": "tie (bothbad)"}
    swapped = []
    for row in rows:
        winner = str(row["winner"])
        winner = mapping[winner]
        swapped.append(_row(str(row["model_b"]), str(row["model_a"]), winner))
    return swapped


def _assert_error(code: EstimationErrorCode, population: PopulationResult, estimator: str = "davidson") -> None:
    with pytest.raises(PreferenceEstimationError) as caught:
        fit_preference(population, PreferenceEstimatorConfig(estimator))
    assert caught.value.code == code


def test_decisive_bradley_terry_orders_two_models_and_uses_sum_to_zero() -> None:
    rows = [_row("a", "b", "model_a") for _ in range(12)] + [_row("a", "b", "model_b") for _ in range(4)]
    result = _fit(rows, "bradley_terry_decisive")
    scores = _score_map(result)

    assert scores["a"] > scores["b"]
    assert sum(result.latent_scores) == pytest.approx(0.0, abs=1e-12)
    assert result.tie_parameter is None
    assert result.derived_rank == (1, 2)


def test_decisive_bradley_terry_balanced_data_has_equal_dense_rank() -> None:
    rows = [_row("a", "b", "model_a") for _ in range(8)] + [_row("a", "b", "model_b") for _ in range(8)]
    result = _fit(rows, "bradley_terry_decisive")

    assert result.latent_scores[0] == pytest.approx(result.latent_scores[1], abs=1e-10)
    assert result.derived_rank == (1, 1)


def test_estimator_is_invariant_to_a_b_label_swapping() -> None:
    rows = [_row("a", "b", "model_a") for _ in range(9)] + [_row("a", "b", "model_b") for _ in range(3)]
    original = _fit(rows, "bradley_terry_decisive")
    swapped = _fit(_swapped(rows), "bradley_terry_decisive")

    assert _score_map(original) == pytest.approx(_score_map(swapped), abs=1e-10)


def test_estimator_is_invariant_to_row_order_and_model_order_is_lexical() -> None:
    rows = (
        [_row("c", "a", "model_b") for _ in range(3)]
        + [_row("a", "b", "model_a") for _ in range(8)]
        + [_row("b", "c", "model_a") for _ in range(6)]
        + [_row("b", "a", "model_a") for _ in range(2)]
        + [_row("c", "b", "model_a") for _ in range(2)]
        + [_row("a", "c", "model_a")]
    )
    original_population = _population(rows)
    shuffled_population = replace(
        original_population,
        eligible=original_population.eligible.sample(frac=1, random_state=7),
    )
    original = fit_preference(original_population, PreferenceEstimatorConfig("bradley_terry_decisive"))
    shuffled = fit_preference(shuffled_population, PreferenceEstimatorConfig("bradley_terry_decisive"))

    assert original.model_ids == ("a", "b", "c")
    assert shuffled.model_ids == original.model_ids
    assert shuffled.latent_scores == pytest.approx(original.latent_scores, abs=1e-10)


def test_decisive_bradley_terry_orders_a_transitive_three_model_example() -> None:
    rows = (
        [_row("a", "b", "model_a") for _ in range(12)]
        + [_row("a", "b", "model_b") for _ in range(2)]
        + [_row("b", "c", "model_a") for _ in range(12)]
        + [_row("b", "c", "model_b") for _ in range(2)]
        + [_row("a", "c", "model_a") for _ in range(12)]
        + [_row("a", "c", "model_b")]
    )
    scores = _score_map(_fit(rows, "bradley_terry_decisive"))

    assert scores["a"] > scores["b"] > scores["c"]


def test_davidson_symmetric_ties_are_finite_and_keep_models_equal() -> None:
    rows = (
        [_row("a", "b", "model_a") for _ in range(5)]
        + [_row("a", "b", "model_b") for _ in range(5)]
        + [_row("a", "b", "tie") for _ in range(20)]
    )
    result = _fit(rows, "davidson")

    assert result.latent_scores[0] == pytest.approx(result.latent_scores[1], abs=1e-10)
    assert result.tie_parameter is not None and result.tie_parameter > 0
    assert result.derived_rank == (1, 1)


def test_davidson_reports_a_positive_tie_propensity() -> None:
    rows = (
        [_row("a", "b", "model_a") for _ in range(5)]
        + [_row("a", "b", "model_b") for _ in range(5)]
        + [_row("a", "b", "tie") for _ in range(30)]
    )
    result = _fit(rows, "davidson")

    assert result.tie_parameter is not None and np.isfinite(result.tie_parameter)
    assert result.tie_parameter > 1


def test_davidson_excludes_bothbad_without_turning_it_into_an_ordinary_tie() -> None:
    rows = [_row("a", "b", "model_a") for _ in range(5)] + [_row("a", "b", "model_b") for _ in range(3)]
    rows += [_row("a", "b", "tie") for _ in range(4)] + [_row("a", "b", "tie (bothbad)") for _ in range(7)]
    result = _fit(rows, "davidson")

    assert result.likelihood_battle_count == 12
    assert result.outcome_policy == "ordinary_tie_only"
    assert result.likelihood_outcome_counts["tie"] == 4
    assert result.excluded_outcome_counts == {"tie_bothbad": 7}


def test_decisive_bradley_terry_excludes_both_tie_categories() -> None:
    rows = [_row("a", "b", "model_a") for _ in range(5)] + [_row("a", "b", "model_b") for _ in range(3)]
    rows += [_row("a", "b", "tie") for _ in range(4)] + [_row("a", "b", "tie (bothbad)") for _ in range(7)]
    result = _fit(rows, "bradley_terry_decisive")

    assert result.likelihood_battle_count == 8
    assert result.outcome_policy == "decisive_only"
    assert result.excluded_outcome_counts == {"tie": 4, "tie_bothbad": 7}


def test_decisive_bradley_terry_rejects_separation_instead_of_returning_a_boundary_fit() -> None:
    population = _population([_row("a", "b", "model_a") for _ in range(4)])

    _assert_error(EstimationErrorCode.SEPARATION, population, "bradley_terry_decisive")


@pytest.mark.parametrize("winner", ["model_a", "tie"])
def test_davidson_rejects_an_unidentifiable_tie_parameter(winner: str) -> None:
    population = _population([_row("a", "b", winner) for _ in range(4)])

    _assert_error(EstimationErrorCode.UNIDENTIFIABLE_TIE_PARAMETER, population)


def test_invalid_unknown_is_a_stable_input_error() -> None:
    population = _population([_row("a", "b", "model_a")])
    invalid = population.eligible.copy()
    invalid.loc[invalid.index[0], "canonical_outcome"] = "invalid_unknown"

    _assert_error(EstimationErrorCode.INVALID_OUTCOME, replace(population, eligible=invalid))


def test_disconnected_estimator_graph_is_rejected() -> None:
    population = _population([
        _row("a", "b", "model_a"),
        _row("a", "b", "model_b"),
        _row("c", "d", "model_a"),
        _row("c", "d", "model_b"),
    ])

    _assert_error(EstimationErrorCode.DISCONNECTED_GRAPH, population, "bradley_terry_decisive")


def test_zero_likelihood_rows_are_rejected() -> None:
    _assert_error(
        EstimationErrorCode.ZERO_LIKELIHOOD_ROWS,
        _population([_row("a", "b", "tie (bothbad)")]),
    )


def test_one_model_self_comparison_is_rejected() -> None:
    population = _population([_row("a", "b", "model_a")])
    self_comparison = population.eligible.copy()
    self_comparison["model_b_id"] = "a"

    _assert_error(EstimationErrorCode.INSUFFICIENT_MODELS, replace(population, eligible=self_comparison))


def test_model_dropped_by_outcome_policy_is_rejected() -> None:
    population = _population([
        _row("a", "b", "model_a"),
        _row("a", "b", "model_b"),
        _row("a", "c", "tie (bothbad)"),
    ])

    _assert_error(EstimationErrorCode.MODEL_DROPPED_BY_OUTCOME_POLICY, population, "bradley_terry_decisive")


def test_repeated_battle_ids_and_rows_are_not_deduplicated() -> None:
    population = _population([
        _row("a", "b", "model_a"),
        _row("a", "b", "model_b"),
    ])
    resampled = replace(population, eligible=pd.concat([population.eligible, population.eligible]))
    result = fit_preference(resampled, PreferenceEstimatorConfig("bradley_terry_decisive"))

    assert result.likelihood_battle_count == 4
    assert result.population_eligible_battle_count == 4


def test_estimator_config_is_json_compatible_for_run_manifest_analysis_config() -> None:
    config = PreferenceEstimatorConfig("davidson", max_iterations=250, tolerance=1e-8)

    assert json.loads(json.dumps(config.to_dict())) == {
        "estimator": "davidson",
        "estimator_version": 1,
        "outcome_policy": "ordinary_tie_only",
        "identifiability": "sum_to_zero",
        "optimizer": "L-BFGS-B",
        "regularization": None,
        "max_iterations": 250,
        "tolerance": 1e-8,
    }
