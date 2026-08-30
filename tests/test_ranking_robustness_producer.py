from __future__ import annotations

from dataclasses import replace
from collections import Counter
import json
import math
from pathlib import Path

import pytest

from src.formal_results import FROZEN_RUNS, FrozenResearchBundle, load_frozen_formal_research
from src.ranking_robustness import RankingRobustnessContractError
import src.ranking_robustness_producer as producer
from src.ranking_robustness_producer import (
    RankingRobustnessProducerError,
    derive_ranking_robustness_e2,
    produce_ranking_robustness_artifact_instance,
)


def test_verifier_failure_prevents_loading_and_output(tmp_path: Path) -> None:
    called = False

    def fail_verifier() -> None:
        raise RuntimeError("E1 verification failed")

    def loader():
        nonlocal called
        called = True
        raise AssertionError("loader must not run")

    with pytest.raises(RuntimeError, match="E1 verification failed"):
        produce_ranking_robustness_artifact_instance(
            output_parent=tmp_path,
            producer_git_sha="a" * 40,
            verifier=fail_verifier,
            loader=loader,
        )
    assert not called
    assert not list(tmp_path.iterdir())


def test_registry_order_mismatch_fails_closed() -> None:
    bundle = load_frozen_formal_research()
    bad = replace(bundle, runs=tuple(reversed(bundle.runs)))
    with pytest.raises(RankingRobustnessProducerError, match="run registry"):
        derive_ranking_robustness_e2(producer_git_sha="a" * 40, bundle=bad)


def test_missing_frozen_run_fails_closed() -> None:
    bundle = load_frozen_formal_research()
    bad = replace(bundle, runs=bundle.runs[:-1])
    with pytest.raises(RankingRobustnessProducerError, match="run registry"):
        derive_ranking_robustness_e2(producer_git_sha="a" * 40, bundle=bad)


def test_model_order_drift_fails_closed() -> None:
    bundle = load_frozen_formal_research()
    first = bundle.runs[0]
    point = dict(first.point_estimate)
    model_ids = list(point["model_ids"])
    model_ids.reverse()
    point["model_ids"] = model_ids
    bad_first = replace(first, point_estimate=point)
    bad = replace(bundle, runs=(bad_first, *bundle.runs[1:]))
    with pytest.raises(RankingRobustnessProducerError, match="model order"):
        derive_ranking_robustness_e2(producer_git_sha="a" * 40, bundle=bad)


def test_malformed_primary_point_ranks_fail_closed() -> None:
    bundle = load_frozen_formal_research()
    first = bundle.runs[0]
    point = dict(first.point_estimate)
    malformed = list(point["derived_rank"])
    malformed[1] = malformed[0]
    point["derived_rank"] = malformed
    bad_first = replace(first, point_estimate=point)
    bad = replace(bundle, runs=(bad_first, *bundle.runs[1:]))
    with pytest.raises((RankingRobustnessProducerError, RankingRobustnessContractError)):
        derive_ranking_robustness_e2(producer_git_sha="a" * 40, bundle=bad)


def test_duplicate_formal_record_guard_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    bundle = load_frozen_formal_research()
    original = producer.derive_rank_distribution

    def duplicate(model_ids, bootstrap_ranks):
        records = original(model_ids, bootstrap_ranks)
        return [*records, records[-1]]

    monkeypatch.setattr(producer, "derive_rank_distribution", duplicate)
    with pytest.raises(RankingRobustnessProducerError, match="rank_distributions"):
        derive_ranking_robustness_e2(producer_git_sha="a" * 40, bundle=bundle)


def test_writer_failure_propagates_after_derivation(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    bundle = load_frozen_formal_research()

    def fail_writer(**_kwargs):
        raise RuntimeError("writer sentinel failure")

    monkeypatch.setattr(producer, "write_ranking_robustness_artifact_instance", fail_writer)
    with pytest.raises(RuntimeError, match="writer sentinel failure"):
        produce_ranking_robustness_artifact_instance(
            output_parent=tmp_path,
            producer_git_sha="a" * 40,
            verifier=lambda: None,
            loader=lambda: bundle,
        )
    assert not list(tmp_path.iterdir())


def test_real_frozen_e1_produces_complete_deterministic_instances(tmp_path: Path) -> None:
    first = produce_ranking_robustness_artifact_instance(
        output_parent=tmp_path / "first",
        producer_git_sha="a" * 40,
    )
    second = produce_ranking_robustness_artifact_instance(
        output_parent=tmp_path / "second",
        producer_git_sha="a" * 40,
    )
    assert first.derivation_spec_id == second.derivation_spec_id
    assert first.artifact_instance_id == second.artifact_instance_id
    assert first.e2_payload_inventory_sha256 == second.e2_payload_inventory_sha256
    filenames = (
        "rank_distributions.json",
        "top_k.json",
        "pairwise_ordering.json",
        "rank_intervals.json",
        "adjacent_reversals.json",
        "cross_specification.json",
        "manifest.json",
    )
    for filename in filenames:
        assert (first.instance_path / filename).read_bytes() == (second.instance_path / filename).read_bytes()

    documents = {
        filename: json.loads((first.instance_path / filename).read_text(encoding="utf-8"))
        for filename in filenames
    }
    run_ids = tuple(spec.run_id for spec in FROZEN_RUNS)
    by_metric = {document["metric"]: document for document in documents.values() if document.get("metric")}
    assert len(by_metric["rank_distributions"]["records"]) == 3600
    assert len(by_metric["top_k"]["records"]) == 540
    assert len(by_metric["pairwise_ordering"]["records"]) == 1710
    assert len(by_metric["rank_intervals"]["records"]) == 180
    assert len(by_metric["adjacent_reversals"]["records"]) == 19
    assert len(by_metric["cross_specification"]["records"]) == 20
    for metric in ("rank_distributions", "top_k", "pairwise_ordering", "rank_intervals"):
        observed = {record["run_id"] for record in by_metric[metric]["records"]}
        assert observed == set(run_ids)
    assert set(by_metric["cross_specification"]["records"][0]["rank_by_run"]) == set(run_ids)
    in_memory = derive_ranking_robustness_e2(producer_git_sha="a" * 40, bundle=load_frozen_formal_research())
    assert in_memory.run_count == 9
    assert in_memory.model_count == 20
    assert in_memory.replicates_per_run == 2000
    assert in_memory.derivation_payload["primary_run_id"] == FROZEN_RUNS[0].run_id == "9c1fd5abbe8681db45b535e5368c806caad8d8297914c7b86a598112900f2689"
    from src.ranking_robustness import compute_derivation_spec_id

    assert compute_derivation_spec_id(in_memory.derivation_payload) == "dc03cc925d2a85dc023542fc21f703abbb966dd4df5da36974c8ea061ece0be4"
    assert tuple(in_memory.metric_records["cross_specification"][0]["rank_by_run"].keys()) == run_ids
    assert all(record["specification_count"] == 9 for record in in_memory.metric_records["cross_specification"])
    assert all(tuple(record["rank_by_run"].keys()) == run_ids for record in in_memory.metric_records["cross_specification"])
    assert all(tuple(record["primary_relative_shift_by_run"].keys()) == run_ids for record in in_memory.metric_records["cross_specification"])
    top_by_run = {(record["run_id"], record["model_id"]): record for record in in_memory.metric_records["top_k"] if record["k"] == 1}
    bundle = load_frozen_formal_research()
    for run in bundle.runs:
        expected = run.bootstrap_summary["rank_summary"]
        assert {key[1] for key in top_by_run if key[0] == run.spec.run_id} == set(expected)
        for model_id, summary in expected.items():
            assert math.isclose(top_by_run[(run.spec.run_id, model_id)]["frequency"], float(summary["probability_rank_1"]), rel_tol=0.0, abs_tol=1e-15)
    pair_counts = Counter(record["run_id"] for record in in_memory.metric_records["pairwise_ordering"])
    assert pair_counts == Counter({run_id: 190 for run_id in run_ids})
    for run_id in run_ids:
        pairs = {(record["left_model_id"], record["right_model_id"]) for record in in_memory.metric_records["pairwise_ordering"] if record["run_id"] == run_id}
        assert len(pairs) == 190
    assert [record["primary_rank"] for record in by_metric["cross_specification"]["records"] if record["model_id"] == "gpt-4"][0] == 1
    top_three = [record["model_id"] for record in sorted(by_metric["cross_specification"]["records"], key=lambda record: record["primary_rank"])[:3]]
    assert top_three == ["gpt-4", "claude-v1", "claude-instant-v1"]
    assert not (Path.cwd() / "artifacts" / "phase-5").exists()
