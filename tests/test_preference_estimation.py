from __future__ import annotations

from dataclasses import replace
import json
import math

import numpy as np
import pandas as pd
import pytest

from src.battle_contract import SourceProvenance, canonicalize_battles
from src.population import BASE_RESEARCH, PopulationResult, apply_population
from src.preference_estimation import (
    EstimationErrorCode,
    PreferenceEstimationError,
    PreferenceEstimatorConfig,
    _negative_log_likelihood,
    _negative_log_likelihood_gradient,
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


def _rows_with_counts(model_a: str, model_b: str, counts: dict[str, int]) -> list[dict[str, object]]:
    return [
        _row(model_a, model_b, winner)
        for winner, count in counts.items()
        for _ in range(count)
    ]


def _renamed(rows: list[dict[str, object]], mapping: dict[str, str]) -> list[dict[str, object]]:
    return [
        _row(mapping[str(row["model_a"])], mapping[str(row["model_b"])], str(row["winner"]))
        for row in rows
    ]


def _davidson_oracle_rows(
    scores: dict[str, float],
    tie_parameter: float, *, total_per_pair: int
) -> list[dict[str, object]]:
    """Expand deterministic integer counts from Davidson probabilities.

    Integer allocation introduces a small, bounded rounding difference from the
    supplied probabilities; oracle tolerances account for that approximation.
    """
    rows: list[dict[str, object]] = []
    model_ids = tuple(scores)
    for left_index, model_a in enumerate(model_ids):
        for model_b in model_ids[left_index + 1 :]:
            pi_a = math.exp(scores[model_a])
            pi_b = math.exp(scores[model_b])
            denominator = pi_a + pi_b + tie_parameter * math.sqrt(pi_a * pi_b)
            probabilities = np.array([pi_a, pi_b, tie_parameter * math.sqrt(pi_a * pi_b)]) / denominator
            raw_counts = probabilities * total_per_pair
            counts = np.floor(raw_counts).astype(int)
            for index in np.argsort(-(raw_counts - counts))[: total_per_pair - int(counts.sum())]:
                counts[index] += 1
            rows.extend(_rows_with_counts(model_a, model_b, dict(zip(("model_a", "model_b", "tie"), counts))))
    return rows


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


def test_davidson_rejects_connected_undirected_but_outcome_separated_data() -> None:
    population = _population(
        [_row("a", "b", "model_a") for _ in range(4)]
        + [_row("b", "c", "tie") for _ in range(4)]
    )

    _assert_error(EstimationErrorCode.SEPARATION, population)


def test_davidson_accepts_outcome_aware_strongly_connected_data() -> None:
    rows = (
        [_row("a", "b", "model_a") for _ in range(4)]
        + [_row("b", "c", "tie") for _ in range(4)]
        + [_row("c", "a", "model_a") for _ in range(4)]
    )
    result = _fit(rows, "davidson")

    assert result.graph_component_count == 1
    assert result.converged


def test_davidson_a_b_swap_preserves_outcome_connected_fit() -> None:
    rows = (
        [_row("a", "b", "model_a") for _ in range(4)]
        + [_row("b", "c", "tie") for _ in range(4)]
        + [_row("c", "a", "model_a") for _ in range(4)]
    )
    original = _fit(rows, "davidson")
    swapped = _fit(_swapped(rows), "davidson")

    assert swapped.model_ids == original.model_ids
    assert swapped.latent_scores == pytest.approx(original.latent_scores, abs=1e-9)


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

    _assert_error(EstimationErrorCode.SELF_COMPARISON, replace(population, eligible=self_comparison))


def test_mixed_self_comparison_is_rejected_without_silent_discard() -> None:
    canonical = canonicalize_battles(
        pd.DataFrame([
            _row("a", "a", "model_a"),
            _row("a", "b", "model_a"),
            _row("b", "a", "model_b"),
        ]),
        provenance=PROVENANCE,
    )
    population = replace(
        _population([_row("a", "a", "model_a"), _row("a", "b", "model_a"), _row("b", "a", "model_b")]),
        eligible=canonical,
    )

    _assert_error(EstimationErrorCode.SELF_COMPARISON, population, "bradley_terry_decisive")


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


def test_config_and_result_identify_coalesced_tie_policy() -> None:
    config = PreferenceEstimatorConfig("davidson_coalesced_ties")
    result = _fit(
        _rows_with_counts("a", "b", {"model_a": 4, "model_b": 3, "tie": 2, "tie (bothbad)": 5}),
        "davidson_coalesced_ties",
    )

    assert config.to_dict()["outcome_policy"] == "all_ties_coalesced"
    assert result.outcome_policy == "all_ties_coalesced"
    assert result.population_outcome_counts["tie_bothbad"] == 5
    assert result.likelihood_outcome_counts["tie"] == 7
    assert result.excluded_outcome_counts == {}


def test_coalescing_does_not_mutate_population_view() -> None:
    population = _population(
        _rows_with_counts("a", "b", {"model_a": 4, "model_b": 3, "tie": 2, "tie (bothbad)": 5})
    )
    before = population.eligible["canonical_outcome"].tolist()
    fit_preference(population, PreferenceEstimatorConfig("davidson_coalesced_ties"))
    assert population.eligible["canonical_outcome"].tolist() == before


def test_primary_davidson_keeps_bothbad_out_of_likelihood() -> None:
    result = _fit(
        _rows_with_counts("a", "b", {"model_a": 4, "model_b": 3, "tie": 2, "tie (bothbad)": 5}),
        "davidson",
    )

    assert result.population_outcome_counts["tie_bothbad"] == 5
    assert result.likelihood_outcome_counts["tie"] == 2
    assert result.excluded_outcome_counts == {"tie_bothbad": 5}


def test_coalesced_davidson_equals_primary_when_no_bothbad() -> None:
    rows = _rows_with_counts("a", "b", {"model_a": 7, "model_b": 4, "tie": 5})
    primary = _fit(rows, "davidson")
    coalesced = _fit(rows, "davidson_coalesced_ties")

    assert coalesced.latent_scores == pytest.approx(primary.latent_scores, abs=1e-10)
    assert coalesced.tie_parameter == pytest.approx(primary.tie_parameter, abs=1e-10)
    assert coalesced.objective == pytest.approx(primary.objective, abs=1e-10)


def test_coalesced_davidson_retains_model_seen_only_in_bothbad() -> None:
    rows = (
        _rows_with_counts("a", "b", {"model_a": 5, "model_b": 4, "tie": 2})
        + _rows_with_counts("a", "c", {"tie (bothbad)": 6})
    )
    population = _population(rows)

    _assert_error(EstimationErrorCode.MODEL_DROPPED_BY_OUTCOME_POLICY, population, "davidson")
    result = fit_preference(population, PreferenceEstimatorConfig("davidson_coalesced_ties"))
    assert result.model_ids == ("a", "b", "c")
    assert result.population_outcome_counts["tie_bothbad"] == 6


def test_coalesced_davidson_invalid_unknown_remains_an_input_error() -> None:
    population = _population(_rows_with_counts("a", "b", {"model_a": 2, "model_b": 2, "tie": 2}))
    invalid = population.eligible.copy()
    invalid.loc[invalid.index[0], "canonical_outcome"] = "invalid_unknown"
    _assert_error(
        EstimationErrorCode.INVALID_OUTCOME,
        replace(population, eligible=invalid),
        "davidson_coalesced_ties",
    )


def test_coalesced_davidson_is_invariant_to_a_b_swapping() -> None:
    rows = _rows_with_counts("a", "b", {"model_a": 6, "model_b": 3, "tie": 4, "tie (bothbad)": 5})
    original = _fit(rows, "davidson_coalesced_ties")
    swapped = _fit(_swapped(rows), "davidson_coalesced_ties")
    assert _score_map(original) == pytest.approx(_score_map(swapped), abs=1e-10)


@pytest.mark.parametrize("estimator", ["bradley_terry_decisive", "davidson", "davidson_coalesced_ties"])
def test_uniform_row_duplication_preserves_estimates_and_scales_objective(estimator: str) -> None:
    rows = (
        _rows_with_counts("a", "b", {"model_a": 8, "model_b": 4, "tie": 3, "tie (bothbad)": 2})
        + _rows_with_counts("b", "c", {"model_a": 7, "model_b": 5, "tie": 4, "tie (bothbad)": 1})
        + _rows_with_counts("c", "a", {"model_a": 6, "model_b": 5, "tie": 3, "tie (bothbad)": 2})
    )
    if estimator == "bradley_terry_decisive":
        rows = [row for row in rows if row["winner"] in {"model_a", "model_b"}]
    base = _fit(rows, estimator)
    duplicated = _fit(rows + rows, estimator)

    assert duplicated.latent_scores == pytest.approx(base.latent_scores, abs=1e-8)
    if base.tie_parameter is not None:
        assert duplicated.tie_parameter == pytest.approx(base.tie_parameter, abs=1e-8)
    assert duplicated.objective == pytest.approx(2 * base.objective, rel=1e-8)


@pytest.mark.parametrize("estimator", ["bradley_terry_decisive", "davidson"])
def test_model_renaming_does_not_change_substantive_scores(estimator: str) -> None:
    rows = (
        _rows_with_counts("a", "b", {"model_a": 8, "model_b": 4, "tie": 3})
        + _rows_with_counts("b", "c", {"model_a": 7, "model_b": 5, "tie": 4})
        + _rows_with_counts("c", "a", {"model_a": 6, "model_b": 5, "tie": 3})
    )
    renamed = _renamed(rows, {"a": "zz", "b": "aa", "c": "mm"})
    original_scores = _score_map(_fit(rows, estimator))
    renamed_scores = _score_map(_fit(renamed, estimator))
    assert renamed_scores["zz"] == pytest.approx(original_scores["a"], abs=3e-6)
    assert renamed_scores["aa"] == pytest.approx(original_scores["b"], abs=3e-6)
    assert renamed_scores["mm"] == pytest.approx(original_scores["c"], abs=3e-6)


def test_aggregate_cell_reordering_is_equivalent_to_expanded_rows() -> None:
    cells = [
        ("a", "b", "model_a", 8), ("a", "b", "model_b", 4), ("a", "b", "tie", 3),
        ("b", "c", "model_a", 7), ("b", "c", "model_b", 5), ("b", "c", "tie", 4),
        ("c", "a", "model_a", 6), ("c", "a", "model_b", 5), ("c", "a", "tie", 3),
    ]
    expanded = [_row(a, b, winner) for a, b, winner, count in cells for _ in range(count)]
    regrouped = [_row(a, b, winner) for a, b, winner, count in reversed(cells) for _ in range(count)]
    left = _fit(expanded, "davidson")
    right = _fit(regrouped, "davidson")
    assert right.latent_scores == pytest.approx(left.latent_scores, abs=1e-10)
    assert right.objective == pytest.approx(left.objective, abs=1e-10)


def test_dense_rank_tolerance_does_not_collapse_clearly_separated_scores() -> None:
    rows = _rows_with_counts("a", "b", {"model_a": 300, "model_b": 100})
    result = _fit(rows, "bradley_terry_decisive")
    assert result.derived_rank == (1, 2)


def test_bt_oracle_recovers_known_two_model_log_odds() -> None:
    rows = _rows_with_counts("a", "b", {"model_a": 300, "model_b": 100})
    result = _fit(rows, "bradley_terry_decisive")
    assert result.latent_scores[0] - result.latent_scores[1] == pytest.approx(math.log(3), abs=1e-6)


def test_bt_oracle_recovers_known_three_model_scores() -> None:
    rows = (
        _rows_with_counts("a", "b", {"model_a": 200, "model_b": 100})
        + _rows_with_counts("b", "c", {"model_a": 200, "model_b": 100})
        + _rows_with_counts("a", "c", {"model_a": 400, "model_b": 100})
    )
    result = _fit(rows, "bradley_terry_decisive")
    scores = _score_map(result)
    assert scores["a"] == pytest.approx(math.log(2), abs=1e-5)
    assert scores["b"] == pytest.approx(0.0, abs=1e-5)
    assert scores["c"] == pytest.approx(-math.log(2), abs=1e-5)


def test_davidson_oracle_recovers_symmetric_scores_and_known_tie_parameter() -> None:
    rows = _rows_with_counts("a", "b", {"model_a": 100, "model_b": 100, "tie": 200})
    result = _fit(rows, "davidson")
    assert result.latent_scores[0] == pytest.approx(result.latent_scores[1], abs=1e-8)
    assert result.tie_parameter == pytest.approx(2.0, abs=1e-6)


def test_davidson_oracle_recovers_three_model_scores_with_integer_rounding() -> None:
    expected = {"a": math.log(2), "b": 0.0, "c": -math.log(2)}
    rows = _davidson_oracle_rows(expected, 1.0, total_per_pair=10_000)
    result = _fit(rows, "davidson")
    scores = _score_map(result)
    for model_id, expected_score in expected.items():
        assert scores[model_id] == pytest.approx(expected_score, abs=0.03)
    assert result.tie_parameter == pytest.approx(1.0, abs=0.03)


def test_coalesced_mode_gradient_matches_finite_difference() -> None:
    parameters = np.array([0.2, -0.1, 0.3])
    kwargs = {
        "estimator_name": "davidson_coalesced_ties",
        "model_a_indices": np.array([0, 1, 0]),
        "model_b_indices": np.array([1, 2, 2]),
        "outcomes": np.array(["model_a_win", "tie", "tie"]),
        "weights": np.array([3.0, 2.0, 4.0]),
        "model_count": 3,
    }
    analytic = _negative_log_likelihood_gradient(parameters, **kwargs)
    numeric = np.zeros_like(parameters)
    for index in range(len(parameters)):
        delta = np.zeros_like(parameters)
        delta[index] = 1e-6
        numeric[index] = (
            _negative_log_likelihood(parameters + delta, **kwargs)
            - _negative_log_likelihood(parameters - delta, **kwargs)
        ) / (2e-6)
    assert analytic == pytest.approx(numeric, abs=1e-6)
