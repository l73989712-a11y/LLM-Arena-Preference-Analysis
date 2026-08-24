from __future__ import annotations

from dataclasses import replace
import json

import numpy as np
import pandas as pd
import pytest

import src.preference_bootstrap as bootstrap_module
from src.battle_contract import SourceProvenance, canonicalize_battles
from src.population import BASE_RESEARCH, PopulationResult, apply_population
from src.preference_estimation import PreferenceEstimatorConfig
from src.preference_bootstrap import (
    BootstrapConfig,
    BootstrapErrorCode,
    PreferenceBootstrapError,
    _formal_ci_valid,
    _cluster_plan,
    _pairwise_stability,
    _percentile_interval,
    _rank_summary,
    _resample_cluster_rows,
    _resample_rows,
    run_bootstrap,
)
from src.preference_estimation import fit_preference


PROVENANCE = SourceProvenance(source_dataset="synthetic/bootstrap", source_revision="v1")


def _row(model_a: str, model_b: str, winner: str, judge: str) -> dict[str, object]:
    conversation = [
        {"role": "user", "content": "prompt"},
        {"role": "assistant", "content": "response"},
    ]
    return {
        "model_a": model_a,
        "model_b": model_b,
        "winner": winner,
        "conversation_a": conversation,
        "conversation_b": conversation,
        "tstamp": 0,
        "judge": judge,
        "language": "English",
        "anony": True,
    }


def _population(rows: list[dict[str, object]]) -> PopulationResult:
    canonical = canonicalize_battles(pd.DataFrame(rows), provenance=PROVENANCE)
    return apply_population(canonical, BASE_RESEARCH)


def _clustered_davidson_population() -> PopulationResult:
    rows: list[dict[str, object]] = []
    for judge in ("judge-a", "judge-b", "judge-c"):
        rows.extend([
            _row("a", "b", "model_a", judge),
            _row("a", "b", "model_a", judge),
            _row("a", "b", "model_b", judge),
            _row("a", "b", "tie", judge),
        ])
    return _population(rows)


def _clustered_bt_population() -> PopulationResult:
    rows: list[dict[str, object]] = []
    for judge in ("judge-a", "judge-b", "judge-c"):
        rows.extend([
            _row("a", "b", "model_a", judge),
            _row("a", "b", "model_b", judge),
        ])
    return _population(rows)


def test_bootstrap_config_is_frozen_and_manifest_compatible() -> None:
    config = BootstrapConfig(
        resampling_unit="judge_cluster",
        replicate_count=20,
        seed=17,
        estimator_config=PreferenceEstimatorConfig("davidson"),
    )

    assert config.formal_replicate_target_met is False
    payload = config.to_dict()
    assert json.loads(json.dumps(payload)) == payload
    assert payload["bit_generator"] == "PCG64"
    assert payload["failure_policy"] == "fixed_attempts_zero_failure_formal_gate"


def test_cluster_resampling_preserves_whole_cluster_multiplicity() -> None:
    population = _clustered_davidson_population()
    frame = population.eligible.sort_values("battle_id").reset_index(drop=True)
    sampled = _resample_cluster_rows(frame, np.random.Generator(np.random.PCG64(3)))
    original_counts = frame.groupby("judge_cluster_id").size().to_dict()
    sampled_counts = sampled.groupby("judge_cluster_id").size().to_dict()

    assert set(sampled_counts).issubset(original_counts)
    for cluster, count in sampled_counts.items():
        assert count % original_counts[cluster] == 0


def test_cluster_plan_partitions_each_source_row_once_in_sorted_cluster_order() -> None:
    population = _clustered_davidson_population()
    frame = population.eligible.sort_values("battle_id").reset_index(drop=True)
    cluster_ids, row_positions = _cluster_plan(frame)

    assert cluster_ids == tuple(sorted(cluster_ids))
    flattened = np.concatenate(row_positions)
    assert sorted(flattened.tolist()) == list(range(len(frame)))
    assert all(np.all(np.diff(positions) > 0) for positions in row_positions)


def test_index_plan_matches_reference_cluster_draw_and_multiplicity() -> None:
    population = _clustered_davidson_population()
    frame = population.eligible.sort_values("battle_id").reset_index(drop=True)
    cluster_ids, row_positions = _cluster_plan(frame)
    seed = 31
    optimized = bootstrap_module._resample_cluster_rows_from_plan(
        frame,
        cluster_ids,
        row_positions,
        np.random.Generator(np.random.PCG64(seed)),
    )

    keys = frame["judge_cluster_id"].map(str)
    reference_ids = tuple(sorted(keys.unique()))
    draw_indices = np.random.Generator(np.random.PCG64(seed)).integers(
        0, len(reference_ids), size=len(reference_ids)
    )
    reference = pd.concat(
        [frame.loc[keys.eq(reference_ids[int(index)])] for index in draw_indices],
        ignore_index=True,
    )

    assert optimized[["battle_id", "model_a_id", "model_b_id", "canonical_outcome"]].reset_index(drop=True).equals(
        reference[["battle_id", "model_a_id", "model_b_id", "canonical_outcome"]].reset_index(drop=True)
    )
    source_counts = frame.groupby("judge_cluster_id").size().to_dict()
    sampled_counts = optimized.groupby("judge_cluster_id").size().to_dict()
    for cluster, count in sampled_counts.items():
        assert count % source_counts[cluster] == 0


def test_narrow_estimator_view_is_equivalent_for_all_point_modes() -> None:
    population = _clustered_davidson_population()
    narrow = population.eligible[["battle_id", "model_a_id", "model_b_id", "canonical_outcome"]].copy()
    narrow_population = replace(population, eligible=narrow)

    for estimator_name in ("davidson", "davidson_coalesced_ties", "bradley_terry_decisive"):
        config = PreferenceEstimatorConfig(estimator_name)
        full = fit_preference(population, config)
        reduced = fit_preference(narrow_population, config)
        assert reduced.model_ids == full.model_ids
        assert reduced.latent_scores == pytest.approx(full.latent_scores)
        assert reduced.derived_rank == full.derived_rank
        if full.tie_parameter is None:
            assert reduced.tie_parameter is None
        else:
            assert reduced.tie_parameter == pytest.approx(full.tie_parameter)
        assert reduced.objective == pytest.approx(full.objective)
        assert reduced.population_outcome_counts == full.population_outcome_counts


def test_narrow_cluster_population_has_same_bootstrap_outputs() -> None:
    population = _clustered_davidson_population()
    narrow = population.eligible[
        ["battle_id", "model_a_id", "model_b_id", "canonical_outcome", "judge_cluster_id"]
    ].copy()
    config = BootstrapConfig("judge_cluster", 4, seed=37)
    full = run_bootstrap(population, config)
    reduced = run_bootstrap(replace(population, eligible=narrow), config)

    assert full.replicate_status == reduced.replicate_status
    assert np.array_equal(full.score_replicates, reduced.score_replicates, equal_nan=True)
    assert np.array_equal(full.rank_replicates, reduced.rank_replicates, equal_nan=True)
    assert np.array_equal(full.tie_parameter_replicates, reduced.tie_parameter_replicates, equal_nan=True)
    assert full.point_estimate.population_outcome_counts == reduced.point_estimate.population_outcome_counts


def test_cluster_bootstrap_same_seed_is_deterministic() -> None:
    population = _clustered_davidson_population()
    config = BootstrapConfig("judge_cluster", 8, seed=11)
    first = run_bootstrap(population, config)
    second = run_bootstrap(population, config)

    assert np.array_equal(first.score_replicates, second.score_replicates, equal_nan=True)
    assert np.array_equal(first.rank_replicates, second.rank_replicates, equal_nan=True)
    assert first.replicate_status == second.replicate_status


def test_cluster_bootstrap_rejects_missing_judge_cluster_without_row_fallback() -> None:
    population = _clustered_davidson_population()
    missing = replace(population, eligible=population.eligible.drop(columns="judge_cluster_id"))
    with pytest.raises(PreferenceBootstrapError) as caught:
        run_bootstrap(missing, BootstrapConfig("judge_cluster", 3, seed=1))
    assert caught.value.code == BootstrapErrorCode.MISSING_JUDGE_CLUSTER


def test_cluster_bootstrap_is_invariant_to_input_row_order() -> None:
    population = _clustered_davidson_population()
    shuffled = replace(population, eligible=population.eligible.sample(frac=1, random_state=23))
    config = BootstrapConfig("judge_cluster", 8, seed=11)
    first = run_bootstrap(population, config)
    second = run_bootstrap(shuffled, config)

    assert np.array_equal(first.score_replicates, second.score_replicates, equal_nan=True)
    assert first.replicate_status == second.replicate_status


def test_row_bootstrap_draws_exactly_n_rows_and_allows_repeated_battle_ids() -> None:
    population = _clustered_bt_population()
    frame = population.eligible.sort_values("battle_id").reset_index(drop=True)
    sampled = _resample_rows(frame, np.random.Generator(np.random.PCG64(7)))

    assert len(sampled) == len(frame)
    assert sampled["battle_id"].duplicated().any()


def test_row_bootstrap_same_seed_is_deterministic() -> None:
    population = _clustered_bt_population()
    config = BootstrapConfig("battle_row", 8, seed=19, estimator_config=PreferenceEstimatorConfig("bradley_terry_decisive"))
    first = run_bootstrap(population, config)
    second = run_bootstrap(population, config)

    assert np.array_equal(first.score_replicates, second.score_replicates, equal_nan=True)
    assert first.replicate_status == second.replicate_status


def test_model_absent_is_recorded_without_redraw() -> None:
    rows = [
        _row("a", "b", "model_a", "core"),
        _row("a", "b", "model_b", "core"),
        _row("a", "c", "model_a", "rare"),
        _row("a", "c", "model_b", "rare"),
    ]
    population = _population(rows)
    config = BootstrapConfig("judge_cluster", 6, seed=0, estimator_config=PreferenceEstimatorConfig("bradley_terry_decisive"))
    result = run_bootstrap(population, config)

    assert result.attempted_replicates == 6
    assert result.failed_replicates > 0
    assert result.failure_counts[BootstrapErrorCode.MODEL_ABSENT.value] > 0
    assert result.formal_ci_valid is False
    failed_rows = np.isnan(result.score_replicates).all(axis=1)
    assert failed_rows.sum() == result.failed_replicates


def test_estimator_failure_code_is_preserved_and_not_redrawn(monkeypatch: pytest.MonkeyPatch) -> None:
    population = _clustered_bt_population()

    def always_one_direction(frame: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
        return frame.iloc[[0] * len(frame)].reset_index(drop=True).copy()

    monkeypatch.setattr(bootstrap_module, "_resample_rows", always_one_direction)
    config = BootstrapConfig("battle_row", 4, seed=1, estimator_config=PreferenceEstimatorConfig("bradley_terry_decisive"))
    result = run_bootstrap(population, config)

    assert result.attempted_replicates == 4
    assert result.successful_replicates == 0
    assert result.failure_counts["SEPARATION"] == 4
    assert result.replicate_status == ("SEPARATION",) * 4


def test_formal_gate_requires_2000_attempts_and_zero_failures() -> None:
    config = BootstrapConfig("battle_row", 20, seed=1)
    assert _formal_ci_valid(config, 0) is False
    assert _formal_ci_valid(replace(config, replicate_count=2000), 1) is False
    assert _formal_ci_valid(replace(config, replicate_count=2000), 0) is True


def test_successful_development_run_has_diagnostic_interval_but_is_not_formal() -> None:
    result = run_bootstrap(_clustered_davidson_population(), BootstrapConfig("judge_cluster", 6, seed=7))
    assert result.failed_replicates == 0
    assert result.score_intervals is not None
    assert result.formal_replicate_target_met is False
    assert result.formal_ci_valid is False


def test_percentile_interval_uses_linear_quantiles() -> None:
    values = np.arange(40.0).reshape(20, 2)
    interval = _percentile_interval(values[:, 0], 0.95)
    expected = tuple(np.quantile(values[:, 0], [0.025, 0.975], method="linear"))
    assert interval == pytest.approx(expected)


def test_rank_summary_reports_quantiles_and_tied_rank_one_frequency() -> None:
    ranks = np.array([
        [1, 1, 3],
        [1, 2, 2],
        [2, 1, 2],
        [2, 2, 1],
    ], dtype=float)
    summary = _rank_summary(ranks, ("a", "b", "c"), 0.95)

    assert summary["a"]["probability_rank_1"] == pytest.approx(0.5)
    assert summary["b"]["probability_rank_1"] == pytest.approx(0.5)
    assert summary["c"]["probability_rank_1"] == pytest.approx(0.25)
    assert summary["a"]["median_rank"] == pytest.approx(1.5)


def test_pairwise_stability_frequencies_sum_to_one_and_respect_tolerance() -> None:
    scores = np.array([
        [1.0, 1.0, 0.0],
        [1.0 + 0.5e-10, 1.0, 0.0],
        [0.0, 1.0, 1.0],
    ])
    stability = _pairwise_stability(scores, ("a", "b", "c"))

    assert stability["a|b"]["eq_frequency"] == pytest.approx(2 / 3)
    assert sum(stability["a|b"].values()) == pytest.approx(1.0)
    assert sum(stability["a|c"].values()) == pytest.approx(1.0)


def test_davidson_tie_parameter_summary_is_finite_and_bt_has_none() -> None:
    davidson = run_bootstrap(
        _clustered_davidson_population(),
        BootstrapConfig("judge_cluster", 6, seed=5),
    )
    bt = run_bootstrap(
        _clustered_bt_population(),
        BootstrapConfig("judge_cluster", 6, seed=5, estimator_config=PreferenceEstimatorConfig("bradley_terry_decisive")),
    )

    assert np.isfinite(davidson.tie_parameter_replicates).all()
    assert davidson.tie_parameter_interval is not None
    assert np.isnan(bt.tie_parameter_replicates).all()
    assert bt.tie_parameter_interval is None


def test_bootstrap_result_keeps_battle_identity_and_does_not_mutate_population() -> None:
    population = _clustered_davidson_population()
    before = population.eligible["battle_id"].tolist()
    result = run_bootstrap(population, BootstrapConfig("judge_cluster", 3, seed=2))

    assert population.eligible["battle_id"].tolist() == before
    assert result.score_replicates.shape == (3, len(result.model_ids))
    assert result.rank_replicates.shape == (3, len(result.model_ids))
