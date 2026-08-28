from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import src.ranking_robustness_artifacts as artifacts
from src.ranking_robustness import (
    FORMAL_TOP_K,
    RankingRobustnessContractError,
    build_artifact_instance_payload,
    build_derivation_spec_payload,
    compute_artifact_instance_id,
    compute_derivation_spec_id,
)
from src.ranking_robustness_artifacts import (
    FORMAL_ARTIFACT_FILENAMES,
    METRIC_FILES,
    ArtifactFileRecord,
    RankingRobustnessArtifactError,
    build_payload_inventory,
    compute_payload_inventory_sha256,
    write_ranking_robustness_artifact_instance,
)


def _derivation_payload() -> dict[str, object]:
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


def _instance_payload(derivation_payload: dict[str, object] | None = None) -> dict[str, object]:
    payload = derivation_payload or _derivation_payload()
    return build_artifact_instance_payload(
        derivation_spec_id=compute_derivation_spec_id(payload),
        producer_git_sha="e" * 40,
    )


def _records() -> dict[str, list[dict[str, object]]]:
    runs = ["c" * 64, "d" * 64]
    return {
        "rank_distributions": [{"run_id": runs[0], "model_id": "alpha", "rank": 1, "count": 1, "successful_replicates": 2, "frequency": 0.5}],
        "top_k": [{"run_id": runs[0], "model_id": "alpha", "k": 1, "included_count": 1, "successful_replicates": 2, "frequency": 0.5}],
        "pairwise_ordering": [{"run_id": runs[0], "left_model_id": "alpha", "right_model_id": "beta", "gt_count": 1, "eq_count": 0, "lt_count": 1, "successful_replicates": 2, "gt_frequency": 0.5, "eq_frequency": 0.0, "lt_frequency": 0.5}],
        "rank_intervals": [{"run_id": runs[0], "model_id": "alpha", "lower_rank_quantile": 1.0, "median_rank": 1.0, "upper_rank_quantile": 2.0, "probability_rank_1": 0.5}],
        "adjacent_reversals": [{"primary_rank_higher": 1, "primary_rank_lower": 2, "higher_model_id": "alpha", "lower_model_id": "beta", "support_count": 1, "reversal_count": 1, "successful_replicates": 2, "support_frequency": 0.5, "reversal_frequency": 0.5}],
        "cross_specification": [{"model_id": "alpha", "primary_rank": 1, "rank_by_run": {runs[0]: 1, runs[1]: 2}, "primary_relative_shift_by_run": {runs[0]: 0, runs[1]: 1}, "minimum_observed_rank": 1, "maximum_observed_rank": 2, "maximum_absolute_rank_shift": 1, "top_1_specification_count": 1, "top_3_specification_count": 2, "top_5_specification_count": 2, "specification_count": 2}],
    }


def _write(parent: Path, *, derivation_payload=None, instance_payload=None, metric_records=None):
    return write_ranking_robustness_artifact_instance(
        output_parent=parent,
        derivation_payload=derivation_payload or _derivation_payload(),
        artifact_instance_payload=instance_payload or _instance_payload(derivation_payload),
        metric_records=metric_records or _records(),
    )


def test_writer_produces_exact_seven_file_layout_and_manifest(tmp_path: Path) -> None:
    result = _write(tmp_path)
    files = sorted(path.name for path in result.instance_path.iterdir())
    assert files == sorted(FORMAL_ARTIFACT_FILENAMES)
    manifest = json.loads((result.instance_path / "manifest.json").read_text(encoding="utf-8"))
    assert set(manifest) == {
        "artifact_schema_version", "derivation_contract_version", "metric_schema_version",
        "derivation_spec_id", "artifact_instance_id", "producer_git_sha",
        "source_snapshot_id", "e1_bundle", "ordered_run_ids", "primary_run_id",
        "top_k", "pairwise_ordering_tolerance", "e2_payload_inventory_sha256", "artifacts",
    }
    assert manifest["artifact_schema_version"] == 1
    assert manifest["top_k"] == list(FORMAL_TOP_K)
    assert "comparative_review" not in json.dumps(manifest)
    assert len(manifest["artifacts"]) == 6
    assert "manifest.json" not in {record["path"] for record in manifest["artifacts"]}


def test_same_identity_produces_byte_identical_payload_and_manifest(tmp_path: Path) -> None:
    first = _write(tmp_path / "first")
    second = _write(tmp_path / "second")
    assert first.artifact_instance_id == second.artifact_instance_id
    assert first.e2_payload_inventory_sha256 == second.e2_payload_inventory_sha256
    for filename in FORMAL_ARTIFACT_FILENAMES:
        assert (first.instance_path / filename).read_bytes() == (second.instance_path / filename).read_bytes()
    assert all((first.instance_path / filename).read_bytes().count(b"\r\n") == 0 for filename in FORMAL_ARTIFACT_FILENAMES)
    assert all((first.instance_path / filename).read_bytes().endswith(b"\n") for filename in FORMAL_ARTIFACT_FILENAMES)
    assert all(not (first.instance_path / filename).read_bytes().endswith(b"\n\n") for filename in FORMAL_ARTIFACT_FILENAMES)


def test_json_bytes_are_utf8_ascii_escaped_and_sorted(tmp_path: Path) -> None:
    records = _records()
    records["top_k"][0]["model_id"] = "模型"
    result = _write(tmp_path, metric_records=records)
    raw = (result.instance_path / "top_k.json").read_bytes()
    assert raw.decode("utf-8").encode("utf-8") == raw
    assert b"\\u6a21\\u578b" in raw
    expected = json.dumps(
        json.loads(raw), ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8") + b"\n"
    assert raw == expected


def test_authorized_second_run_id_is_preserved_for_sampling_records(tmp_path: Path) -> None:
    records = _records()
    second_run = _derivation_payload()["ordered_run_ids"][1]
    for metric in ("rank_distributions", "top_k", "pairwise_ordering", "rank_intervals"):
        records[metric][0]["run_id"] = second_run
    result = _write(tmp_path, metric_records=records)
    for metric, filename in METRIC_FILES:
        if metric in {"rank_distributions", "top_k", "pairwise_ordering", "rank_intervals"}:
            document = json.loads((result.instance_path / filename).read_text(encoding="utf-8"))
            assert document["records"][0]["run_id"] == second_run


@pytest.mark.parametrize("metric", ["rank_distributions", "top_k", "pairwise_ordering", "rank_intervals"])
def test_sampling_record_requires_run_id(tmp_path: Path, metric: str) -> None:
    records = _records()
    records[metric][0].pop("run_id")
    with pytest.raises(RankingRobustnessArtifactError, match="fields"):
        _write(tmp_path / metric, metric_records=records)


@pytest.mark.parametrize("run_id", ["f" * 64, "A" * 64, "short", "g" * 64])
def test_sampling_record_rejects_unknown_or_malformed_run_id(tmp_path: Path, run_id: str) -> None:
    records = _records()
    records["top_k"][0]["run_id"] = run_id
    with pytest.raises(RankingRobustnessArtifactError, match="run_id"):
        _write(tmp_path / "bad-run", metric_records=records)


def test_inventory_is_sorted_excludes_manifest_and_detects_byte_change() -> None:
    payload = {filename: filename.encode("utf-8") for filename in FORMAL_ARTIFACT_FILENAMES if filename != "manifest.json"}
    records = build_payload_inventory(payload)
    assert [record.path for record in records] == sorted(payload)
    assert all(record.size_bytes == len(payload[record.path]) for record in records)
    assert all(record.sha256 == hashlib.sha256(payload[record.path]).hexdigest() for record in records)
    assert {record.path for record in records} == {filename for _, filename in METRIC_FILES}
    assert len(records) == 6
    first_hash = compute_payload_inventory_sha256(records)
    changed = dict(payload)
    changed["top_k.json"] = b"changed"
    assert compute_payload_inventory_sha256(build_payload_inventory(changed)) != first_hash
    assert compute_payload_inventory_sha256(records) == hashlib.sha256(
        artifacts.canonical_json_bytes([record.to_dict() for record in records])
    ).hexdigest()


def test_collision_fails_closed_and_preserves_first_instance(tmp_path: Path) -> None:
    first = _write(tmp_path)
    before = {filename: (first.instance_path / filename).read_bytes() for filename in FORMAL_ARTIFACT_FILENAMES}
    with pytest.raises(RankingRobustnessArtifactError, match="already exists"):
        _write(tmp_path)
    assert {filename: (first.instance_path / filename).read_bytes() for filename in FORMAL_ARTIFACT_FILENAMES} == before


def test_partial_publication_failure_leaves_no_final_instance(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    original_replace = artifacts.os.replace

    def fail_replace(source: str, destination: str) -> None:
        raise OSError("controlled publication failure")

    monkeypatch.setattr(artifacts.os, "replace", fail_replace)
    with pytest.raises(RankingRobustnessArtifactError, match="unable to publish"):
        _write(tmp_path)
    instance_id = compute_artifact_instance_id(_instance_payload())
    assert not (tmp_path / instance_id).exists()
    assert not list(tmp_path.glob(".tmp-*"))
    monkeypatch.setattr(artifacts.os, "replace", original_replace)


def test_concurrent_publication_failure_preserves_other_writer_instance(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    instance_id = compute_artifact_instance_id(_instance_payload())

    def race_replace(source: str, destination: str) -> None:
        final_dir = Path(destination)
        final_dir.mkdir()
        (final_dir / "sentinel").write_bytes(b"published-by-other-writer")
        raise OSError("destination appeared")

    monkeypatch.setattr(artifacts.os, "replace", race_replace)
    with pytest.raises(RankingRobustnessArtifactError, match="unable to publish"):
        _write(tmp_path)
    assert (tmp_path / instance_id / "sentinel").read_bytes() == b"published-by-other-writer"
    assert not list(tmp_path.glob(".tmp-*"))


def test_identity_and_metric_set_mismatches_fail_at_writer_boundary(tmp_path: Path) -> None:
    derivation = _derivation_payload()
    other_derivation = {**derivation, "ordered_run_ids": ["f" * 64, "d" * 64]}
    with pytest.raises(RankingRobustnessArtifactError, match="different derivation"):
        _write(tmp_path / "mismatch", derivation_payload=derivation, instance_payload=_instance_payload(other_derivation))
    missing = _records()
    missing.pop("top_k")
    with pytest.raises(RankingRobustnessArtifactError, match="exactly"):
        _write(tmp_path / "missing", metric_records=missing)
    extra = _records()
    extra["unexpected"] = []
    with pytest.raises(RankingRobustnessArtifactError, match="exactly"):
        _write(tmp_path / "extra", metric_records=extra)
    bad_schema = {**_instance_payload(), "artifact_schema_version": 2}
    with pytest.raises(RankingRobustnessArtifactError, match="schema"):
        _write(tmp_path / "schema", instance_payload=bad_schema)


def test_json_safety_rejects_nonfinite_metric_records(tmp_path: Path) -> None:
    records = _records()
    records["top_k"][0]["frequency"] = float("nan")
    with pytest.raises(RankingRobustnessArtifactError, match="JSON-safe|non-finite"):
        _write(tmp_path, metric_records=records)


@pytest.mark.parametrize(
    ("metric", "mutate"),
    [
        ("rank_distributions", lambda record: record.pop("rank")),
        ("top_k", lambda record: record.update(included_count=2)),
        ("pairwise_ordering", lambda record: record.update(right_model_id="alpha")),
        ("rank_intervals", lambda record: record.update(upper_rank_quantile=0.5)),
        ("adjacent_reversals", lambda record: record.update(primary_rank_lower=3)),
        ("cross_specification", lambda record: record.update(primary_relative_shift_by_run={"bad": 0})),
        ("cross_specification", lambda record: record.update(minimum_observed_rank=1.0)),
    ],
)
def test_each_formal_metric_schema_rejects_malformed_record(tmp_path: Path, metric: str, mutate) -> None:
    records = _records()
    mutate(records[metric][0])
    with pytest.raises(RankingRobustnessArtifactError):
        _write(tmp_path / metric, metric_records=records)


def test_malformed_producer_sha_fails_at_writer_boundary(tmp_path: Path) -> None:
    bad_instance = {**_instance_payload(), "producer_git_sha": "NOT-A-SHA"}
    with pytest.raises(RankingRobustnessArtifactError, match="producer_git_sha"):
        _write(tmp_path, instance_payload=bad_instance)


def test_metric_envelope_has_fixed_identity_and_no_writer_recomputation(tmp_path: Path) -> None:
    derivation = _derivation_payload()
    instance = _instance_payload(derivation)
    result = _write(tmp_path, derivation_payload=derivation, instance_payload=instance)
    document = json.loads((result.instance_path / "top_k.json").read_text(encoding="utf-8"))
    assert set(document) == {
        "artifact_schema_version", "metric_schema_version", "derivation_spec_id",
        "artifact_instance_id", "metric", "records",
    }
    assert document["metric"] == "top_k"
    assert document["derivation_spec_id"] == compute_derivation_spec_id(derivation)
    assert document["artifact_instance_id"] == compute_artifact_instance_id(instance)
