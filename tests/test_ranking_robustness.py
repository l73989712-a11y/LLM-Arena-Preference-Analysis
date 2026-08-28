from __future__ import annotations

import hashlib

import numpy as np
import pytest

from src.preference_bootstrap import _pairwise_stability
from src.preference_estimation import RANK_EQUALITY_TOLERANCE
from src.ranking_robustness import (
    ARTIFACT_SCHEMA_VERSION,
    DERIVATION_CONTRACT_VERSION,
    FORMAL_TOP_K,
    METRIC_SCHEMA_VERSION,
    RankingRobustnessContractError,
    build_artifact_instance_payload,
    build_derivation_spec_payload,
    canonical_json_bytes,
    compute_artifact_instance_id,
    compute_derivation_spec_id,
    derive_adjacent_rank_reversals,
    derive_cross_specification,
    derive_pairwise_ordering,
    derive_rank_distribution,
    derive_top_k_inclusion,
    extract_rank_intervals,
)


MODELS = ("alpha", "beta", "gamma", "delta", "epsilon")
RANKS = np.array(
    [
        [1, 2, 3, 4, 5],
        [2, 1, 3, 5, 4],
        [3, 2, 1, 4, 5],
    ],
    dtype=np.int64,
)


def test_rank_distribution_is_ordered_and_exact() -> None:
    records = derive_rank_distribution(MODELS, RANKS)
    assert len(records) == 25
    assert records[:3] == [
        {"model_id": "alpha", "rank": 1, "count": 1, "successful_replicates": 3, "frequency": 1 / 3},
        {"model_id": "alpha", "rank": 2, "count": 1, "successful_replicates": 3, "frequency": 1 / 3},
        {"model_id": "alpha", "rank": 3, "count": 1, "successful_replicates": 3, "frequency": 1 / 3},
    ]
    for model in MODELS:
        assert sum(item["frequency"] for item in records if item["model_id"] == model) == pytest.approx(1.0)


def test_rank_validation_rejects_duplicates_and_shape() -> None:
    invalid = RANKS.copy()
    invalid[0, 1] = invalid[0, 0]
    with pytest.raises(RankingRobustnessContractError, match="permutation"):
        derive_rank_distribution(MODELS, invalid)
    with pytest.raises(RankingRobustnessContractError, match="column count"):
        derive_rank_distribution(MODELS[:-1], RANKS)
    with pytest.raises(RankingRobustnessContractError, match="unique"):
        derive_rank_distribution(("alpha", "alpha"), np.array([[1, 1]]))


def test_top_k_is_bound_to_formal_values() -> None:
    records = derive_top_k_inclusion(MODELS, RANKS)
    assert [item["k"] for item in records[:3]] == list(FORMAL_TOP_K)
    alpha = {item["k"]: item for item in records if item["model_id"] == "alpha"}
    assert alpha[1]["included_count"] == 1
    assert alpha[3]["included_count"] == 3
    assert alpha[5]["included_count"] == 3
    with pytest.raises(RankingRobustnessContractError, match="too small"):
        derive_top_k_inclusion(("a", "b"), np.array([[1, 2]]))


def test_pairwise_uses_score_authority_and_tolerance() -> None:
    scores = np.array(
        [
            [0.0, -2 * RANK_EQUALITY_TOLERANCE, 1.0],
            [0.0, -RANK_EQUALITY_TOLERANCE, -1.0],
            [0.0, 0.0, 1.0],
            [0.0, RANK_EQUALITY_TOLERANCE, -1.0],
            [0.0, 2 * RANK_EQUALITY_TOLERANCE, 1.0],
        ],
        dtype=float,
    )
    ids = ("a", "b", "c")
    records = derive_pairwise_ordering(ids, scores)
    first = records[0]
    assert (first["gt_count"], first["eq_count"], first["lt_count"]) == (1, 3, 1)
    assert first["successful_replicates"] == 5
    authority = _pairwise_stability(scores, ids)
    assert first["gt_frequency"] == authority["a|b"]["gt_frequency"]
    assert first["eq_frequency"] == authority["a|b"]["eq_frequency"]
    assert first["lt_frequency"] == authority["a|b"]["lt_frequency"]
    assert all(item["gt_count"] + item["eq_count"] + item["lt_count"] == 5 for item in records)


def test_pairwise_rejects_nonfinite_scores() -> None:
    scores = np.zeros((2, 2), dtype=float)
    scores[0, 0] = np.nan
    with pytest.raises(RankingRobustnessContractError, match="finite"):
        derive_pairwise_ordering(("a", "b"), scores)


def test_rank_intervals_preserve_e1_fields() -> None:
    summary = {
        model: {
            "lower_rank_quantile": float(index),
            "median_rank": float(index),
            "upper_rank_quantile": float(index),
            "probability_rank_1": 1.0 if index == 1 else 0.0,
        }
        for index, model in enumerate(MODELS, 1)
    }
    records = extract_rank_intervals(MODELS, summary)
    assert [item["model_id"] for item in records] == list(MODELS)
    assert list(records[0]) == [
        "model_id",
        "lower_rank_quantile",
        "median_rank",
        "upper_rank_quantile",
        "probability_rank_1",
    ]
    assert records[0]["probability_rank_1"] == 1.0
    bad = dict(summary)
    bad["alpha"] = {**summary["alpha"], "probability_rank_1": 1.1}
    with pytest.raises(RankingRobustnessContractError, match=r"\[0,1\]"):
        extract_rank_intervals(MODELS, bad)
    bad["alpha"] = {**summary["alpha"], "median_rank": float("nan")}
    with pytest.raises(RankingRobustnessContractError, match="non-finite"):
        extract_rank_intervals(MODELS, bad)


def test_rank_validation_rejects_non_integral_and_nonfinite_values() -> None:
    non_integral = RANKS.astype(float)
    non_integral[0, 0] = 1.5
    with pytest.raises(RankingRobustnessContractError, match="integral"):
        derive_rank_distribution(MODELS, non_integral)
    non_finite = RANKS.astype(float)
    non_finite[0, 0] = np.nan
    with pytest.raises(RankingRobustnessContractError, match="finite"):
        derive_rank_distribution(MODELS, non_finite)


def test_adjacent_reversals_use_primary_ranks_only() -> None:
    ids = ("a", "b", "c")
    point = [1, 2, 3]
    bootstrap = np.array([[1, 2, 3], [2, 1, 3], [1, 3, 2]], dtype=int)
    records = derive_adjacent_rank_reversals(ids, point, bootstrap)
    assert [(r["higher_model_id"], r["lower_model_id"]) for r in records] == [("a", "b"), ("b", "c")]
    assert (records[0]["support_count"], records[0]["reversal_count"]) == (2, 1)
    assert (records[1]["support_count"], records[1]["reversal_count"]) == (2, 1)
    with pytest.raises(RankingRobustnessContractError, match="permutation"):
        derive_adjacent_rank_reversals(ids, [1, 1, 3], bootstrap)


def test_cross_specification_is_ordinal_and_ordered() -> None:
    runs = ("run-a", "run-b", "run-c")
    point_ranks = {
        "run-a": [1, 2, 3, 4, 5],
        "run-b": [2, 1, 3, 5, 4],
        "run-c": [1, 3, 2, 4, 5],
    }
    records = derive_cross_specification(runs, MODELS, point_ranks, "run-a")
    alpha = records[0]
    assert alpha["primary_relative_shift_by_run"] == {"run-a": 0, "run-b": 1, "run-c": 0}
    assert alpha["maximum_absolute_rank_shift"] == 1
    assert alpha["top_1_specification_count"] == 2
    assert alpha["specification_count"] == 3
    with pytest.raises(RankingRobustnessContractError, match="order"):
        derive_cross_specification(runs, MODELS, {"run-b": point_ranks["run-b"], "run-a": point_ranks["run-a"], "run-c": point_ranks["run-c"]}, "run-a")


def _identity_payload() -> dict[str, object]:
    return build_derivation_spec_payload(
        source_snapshot_id="a" * 64,
        e1_bundle={
            "bundle_name": "formal-research-v1",
            "bundle_schema_version": 1,
            "payload_inventory_sha256": "b" * 64,
        },
        ordered_run_ids=["c" * 64, "d" * 64],
        primary_run_id="c" * 64,
    )


def test_identity_payload_and_hash_are_order_sensitive_only_where_required() -> None:
    payload = _identity_payload()
    assert set(payload) == {
        "derivation_contract_version", "metric_schema_version", "source_snapshot_id", "e1_bundle",
        "ordered_run_ids", "primary_run_id", "top_k", "pairwise_ordering_tolerance",
    }
    reordered = {"primary_run_id": payload["primary_run_id"], **{key: payload[key] for key in payload if key != "primary_run_id"}}
    assert compute_derivation_spec_id(payload) == compute_derivation_spec_id(reordered)
    reversed_runs = {**payload, "ordered_run_ids": list(reversed(payload["ordered_run_ids"]))}
    assert compute_derivation_spec_id(payload) != compute_derivation_spec_id(reversed_runs)
    assert payload["top_k"] == [1, 3, 5]
    assert payload["pairwise_ordering_tolerance"] == RANK_EQUALITY_TOLERANCE
    assert "comparative_review" not in canonical_json_bytes(payload).decode("utf-8")
    assert DERIVATION_CONTRACT_VERSION == METRIC_SCHEMA_VERSION == ARTIFACT_SCHEMA_VERSION == 1


def test_identity_payload_rejects_wrong_top_k_tolerance_and_primary() -> None:
    payload = _identity_payload()
    with pytest.raises(RankingRobustnessContractError, match="top-k"):
        build_derivation_spec_payload(
            source_snapshot_id=payload["source_snapshot_id"],
            e1_bundle=payload["e1_bundle"],
            ordered_run_ids=payload["ordered_run_ids"],
            primary_run_id=payload["primary_run_id"],
            top_k=(1, 3, 4),
        )
    with pytest.raises(RankingRobustnessContractError, match="tolerance"):
        build_derivation_spec_payload(
            source_snapshot_id=payload["source_snapshot_id"],
            e1_bundle=payload["e1_bundle"],
            ordered_run_ids=payload["ordered_run_ids"],
            primary_run_id=payload["primary_run_id"],
            pairwise_ordering_tolerance=RANK_EQUALITY_TOLERANCE * 2,
        )
    with pytest.raises(RankingRobustnessContractError, match="missing"):
        build_derivation_spec_payload(
            source_snapshot_id=payload["source_snapshot_id"],
            e1_bundle=payload["e1_bundle"],
            ordered_run_ids=payload["ordered_run_ids"],
            primary_run_id="e" * 64,
        )


def test_artifact_identity_is_non_circular_and_producer_sensitive() -> None:
    derivation_id = compute_derivation_spec_id(_identity_payload())
    first = build_artifact_instance_payload(derivation_spec_id=derivation_id, producer_git_sha="e" * 40)
    second = build_artifact_instance_payload(derivation_spec_id=derivation_id, producer_git_sha="f" * 40)
    assert compute_artifact_instance_id(first) != compute_artifact_instance_id(second)
    assert first["derivation_spec_id"] == second["derivation_spec_id"] == derivation_id
    with pytest.raises(RankingRobustnessContractError, match="Git identity"):
        build_artifact_instance_payload(derivation_spec_id=derivation_id, producer_git_sha="E" * 40)
    with pytest.raises(RankingRobustnessContractError, match="schema"):
        build_artifact_instance_payload(derivation_spec_id=derivation_id, producer_git_sha="e" * 40, artifact_schema_version=2)


def test_canonical_json_rejects_nonfinite_values() -> None:
    with pytest.raises(RankingRobustnessContractError, match="non-finite"):
        canonical_json_bytes({"value": float("nan")})
