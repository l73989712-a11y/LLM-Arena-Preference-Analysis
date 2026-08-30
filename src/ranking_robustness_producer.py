"""Canonical Phase 5 orchestration from the immutable frozen E1 bundle."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any

from src.formal_results import FROZEN_RUNS, FROZEN_SOURCE, FrozenResearchBundle, load_frozen_formal_research
from src.formal_verifier import (
    EXPECTED_BUNDLE_NAME,
    EXPECTED_BUNDLE_SCHEMA_VERSION,
    EXPECTED_PAYLOAD_INVENTORY_SHA256,
    verify_frozen_bundle,
)
from src.ranking_robustness import (
    FORMAL_TOP_K,
    RANK_EQUALITY_TOLERANCE,
    RankingRobustnessContractError,
    build_artifact_instance_payload,
    build_derivation_spec_payload,
    compute_derivation_spec_id,
    derive_adjacent_rank_reversals,
    derive_cross_specification,
    derive_pairwise_ordering,
    derive_rank_distribution,
    derive_top_k_inclusion,
    extract_rank_intervals,
)
from src.ranking_robustness_artifacts import (
    ArtifactInstanceWriteResult,
    write_ranking_robustness_artifact_instance,
)


class RankingRobustnessProducerError(RankingRobustnessContractError):
    """Raised when the canonical E1-to-E2 producer contract is violated."""


@dataclass(frozen=True)
class RankingRobustnessE2:
    """Complete deterministic E2 inputs assembled from one validated E1 bundle."""

    derivation_payload: Mapping[str, Any]
    artifact_instance_payload: Mapping[str, Any]
    metric_records: Mapping[str, tuple[Mapping[str, Any], ...]]
    run_count: int
    model_count: int
    replicates_per_run: int


def _fail(message: str) -> None:
    raise RankingRobustnessProducerError(message)


def _attach_run_id(run_id: str, records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    attached: list[dict[str, Any]] = []
    for record in records:
        if "run_id" in record:
            _fail("core metric record unexpectedly contains run_id")
        attached.append({"run_id": run_id, **dict(record)})
    return attached


def _validate_run_registry(bundle: FrozenResearchBundle) -> tuple[tuple[Any, ...], tuple[str, ...], tuple[str, ...], int]:
    runs = tuple(bundle.runs)
    expected_ids = tuple(spec.run_id for spec in FROZEN_RUNS)
    actual_ids = tuple(run.spec.run_id for run in runs)
    if len(runs) != 9 or actual_ids != expected_ids:
        _fail("loaded E1 run registry differs from exact FROZEN_RUNS order")
    if len(set(actual_ids)) != len(actual_ids):
        _fail("loaded E1 run registry contains duplicate run IDs")
    if not runs:
        _fail("loaded E1 bundle contains no runs")
    model_ids = tuple(runs[0].point_estimate["model_ids"])
    if len(model_ids) != 20 or len(set(model_ids)) != len(model_ids):
        _fail("frozen E1 model registry must contain 20 unique models")
    for run in runs:
        if tuple(run.point_estimate["model_ids"]) != model_ids or tuple(run.bootstrap_summary["model_ids"]) != model_ids:
            _fail(f"model order differs for frozen run {run.spec.run_id}")
        if run.bootstrap_ranks.shape != (2000, 20) or run.bootstrap_scores.shape != (2000, 20):
            _fail(f"bootstrap matrix shape differs for frozen run {run.spec.run_id}")
        if run.bootstrap_summary["successful_replicates"] != 2000 or run.replicate_status["statuses"] != tuple("SUCCESS" for _ in range(2000)):
            _fail(f"successful replicate gate differs for frozen run {run.spec.run_id}")
    return runs, actual_ids, model_ids, 2000


def _validate_collection(records: Mapping[str, Sequence[Mapping[str, Any]]], run_ids: tuple[str, ...], model_ids: tuple[str, ...]) -> None:
    expected_pairs = {(model_ids[i], model_ids[j]) for i in range(len(model_ids)) for j in range(i + 1, len(model_ids))}
    rank_records = records["rank_distributions"]
    rank_keys = {(r["run_id"], r["model_id"], r["rank"]) for r in rank_records}
    if len(rank_records) != 3600 or len(rank_keys) != 3600 or rank_keys != {(run, model, rank) for run in run_ids for model in model_ids for rank in range(1, 21)}:
        _fail("rank_distributions collection is incomplete or duplicated")
    top_records = records["top_k"]
    top_keys = {(r["run_id"], r["model_id"], r["k"]) for r in top_records}
    if len(top_records) != 540 or len(top_keys) != 540 or top_keys != {(run, model, k) for run in run_ids for model in model_ids for k in FORMAL_TOP_K}:
        _fail("top_k collection is incomplete or duplicated")
    pair_records = records["pairwise_ordering"]
    pair_keys = {(r["run_id"], r["left_model_id"], r["right_model_id"]) for r in pair_records}
    if len(pair_records) != 1710 or len(pair_keys) != 1710 or pair_keys != {(run, left, right) for run in run_ids for left, right in expected_pairs}:
        _fail("pairwise_ordering collection is incomplete or duplicated")
    interval_records = records["rank_intervals"]
    interval_keys = {(r["run_id"], r["model_id"]) for r in interval_records}
    if len(interval_records) != 180 or len(interval_keys) != 180 or interval_keys != {(run, model) for run in run_ids for model in model_ids}:
        _fail("rank_intervals collection is incomplete or duplicated")
    adjacent = records["adjacent_reversals"]
    if len(adjacent) != 19 or [(r["primary_rank_higher"], r["primary_rank_lower"]) for r in adjacent] != [(rank, rank + 1) for rank in range(1, 20)]:
        _fail("adjacent_reversals collection is not the exact primary adjacency")
    cross = records["cross_specification"]
    if len(cross) != 20 or {r["model_id"] for r in cross} != set(model_ids):
        _fail("cross_specification collection is incomplete or duplicated")


def derive_ranking_robustness_e2(
    *,
    producer_git_sha: str,
    bundle: FrozenResearchBundle | None = None,
) -> RankingRobustnessE2:
    """Derive complete E2 records from a validated canonical E1 bundle."""
    if bundle is None:
        bundle = load_frozen_formal_research()
    runs, run_ids, model_ids, replicates = _validate_run_registry(bundle)
    primary_run_id = FROZEN_RUNS[0].run_id
    metrics: dict[str, list[dict[str, Any]]] = {name: [] for name in ("rank_distributions", "top_k", "pairwise_ordering", "rank_intervals", "adjacent_reversals", "cross_specification")}
    point_ranks_by_run: dict[str, Sequence[int]] = {}
    for run in runs:
        run_id = run.spec.run_id
        point_ranks_by_run[run_id] = tuple(run.point_estimate["derived_rank"])
        metrics["rank_distributions"].extend(_attach_run_id(run_id, derive_rank_distribution(model_ids, run.bootstrap_ranks)))
        top_k = _attach_run_id(run_id, derive_top_k_inclusion(model_ids, run.bootstrap_ranks))
        summary = run.bootstrap_summary["rank_summary"]
        for record in top_k:
            if record["k"] == 1 and not math.isclose(record["frequency"], float(summary[record["model_id"]]["probability_rank_1"]), rel_tol=0.0, abs_tol=1e-15):
                _fail(f"top-1 E1 summary mismatch for {run_id}/{record['model_id']}")
        metrics["top_k"].extend(top_k)
        metrics["pairwise_ordering"].extend(_attach_run_id(run_id, derive_pairwise_ordering(model_ids, run.bootstrap_scores)))
        intervals = _attach_run_id(run_id, extract_rank_intervals(model_ids, summary))
        for record in intervals:
            persisted = summary[record["model_id"]]
            for field in ("lower_rank_quantile", "median_rank", "upper_rank_quantile", "probability_rank_1"):
                if record[field] != float(persisted[field]):
                    _fail(f"rank interval E1 summary mismatch for {run_id}/{record['model_id']}")
        metrics["rank_intervals"].extend(intervals)
        if run_id == primary_run_id:
            metrics["adjacent_reversals"] = derive_adjacent_rank_reversals(model_ids, run.point_estimate["derived_rank"], run.bootstrap_ranks)
    metrics["cross_specification"] = derive_cross_specification(run_ids, model_ids, point_ranks_by_run, primary_run_id)
    _validate_collection(metrics, run_ids, model_ids)
    derivation_payload = build_derivation_spec_payload(
        source_snapshot_id=FROZEN_SOURCE.snapshot_id,
        e1_bundle={"bundle_name": EXPECTED_BUNDLE_NAME, "bundle_schema_version": EXPECTED_BUNDLE_SCHEMA_VERSION, "payload_inventory_sha256": EXPECTED_PAYLOAD_INVENTORY_SHA256},
        ordered_run_ids=run_ids,
        primary_run_id=primary_run_id,
        top_k=FORMAL_TOP_K,
        pairwise_ordering_tolerance=RANK_EQUALITY_TOLERANCE,
    )
    artifact_payload = build_artifact_instance_payload(
        derivation_spec_id=compute_derivation_spec_id(derivation_payload),
        producer_git_sha=producer_git_sha,
    )
    return RankingRobustnessE2(derivation_payload, artifact_payload, {name: tuple(values) for name, values in metrics.items()}, len(run_ids), len(model_ids), replicates)


def produce_ranking_robustness_artifact_instance(
    *,
    output_parent: str | Path,
    producer_git_sha: str,
    verifier: Callable[[], Any] = verify_frozen_bundle,
    loader: Callable[[], FrozenResearchBundle] = load_frozen_formal_research,
) -> ArtifactInstanceWriteResult:
    """Verify/load canonical E1, derive complete E2, and write one test-supplied instance."""
    verifier()
    e2 = derive_ranking_robustness_e2(producer_git_sha=producer_git_sha, bundle=loader())
    return write_ranking_robustness_artifact_instance(
        output_parent=output_parent,
        derivation_payload=e2.derivation_payload,
        artifact_instance_payload=e2.artifact_instance_payload,
        metric_records=e2.metric_records,
    )


__all__ = ["RankingRobustnessE2", "RankingRobustnessProducerError", "derive_ranking_robustness_e2", "produce_ranking_robustness_artifact_instance"]
