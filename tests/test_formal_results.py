from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from types import MappingProxyType

import numpy as np
import pytest

import src.formal_results as formal_results
from src.battle_contract import SourceProvenance
from src.formal_results import FrozenReviewSpec, FrozenResultsError, FrozenRunSpec
from src.population import BASE_RESEARCH
from src.run_manifest import create_run_manifest


def _json_write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")), encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, FrozenRunSpec]:
    root = tmp_path / "research"
    source = SourceProvenance(
        source_dataset=formal_results.FROZEN_SOURCE.dataset,
        source_revision=formal_results.FROZEN_SOURCE.revision,
        source_split=formal_results.FROZEN_SOURCE.split,
        source_file=formal_results.FROZEN_SOURCE.file,
        source_file_sha256=formal_results.FROZEN_SOURCE.file_sha256,
    )
    seed = 7
    population_view = {
        "view_type": "synthetic_fixture_view",
        "nested": {"label": "a"},
    }
    draft = FrozenRunSpec("Fixture", "0" * 64, "0" * 64, 0, seed, "b" * 40, "base_research", 2, "davidson", "ordinary_tie_only", "judge_cluster", population_view)
    manifest = create_run_manifest(
        source_provenance=source,
        population_spec=BASE_RESEARCH,
        git_commit=draft.git_commit,
        git_branch="main",
        analysis_config=formal_results._expected_analysis_config(draft),
        environment={"python_version": "3.12.0", "package_versions": {"numpy": "1", "pandas": "1", "scipy": "1"}},
    )
    spec = FrozenRunSpec(draft.analysis, manifest.run_id, "", 0, draft.seed, draft.git_commit, draft.population_id, draft.population_spec_version, draft.estimator, draft.outcome_policy, draft.resampling_unit)
    run_dir = root / spec.run_id
    run_dir.mkdir(parents=True)
    model_ids = ["a", "b"]
    point = {
        "converged": True, "derived_rank": [1, 2], "estimator_config": manifest.analysis_config["estimator"], "estimator_model_count": 2,
        "estimator_name": "davidson", "estimator_version": 1, "excluded_outcome_counts": {"tie_bothbad": 0}, "graph_component_count": 1,
        "graph_edge_count": 1, "graph_node_count": 2, "identifiability_constraint": "sum_to_zero", "iterations": 3,
        "latent_scores": [0.5, -0.5], "likelihood_battle_count": 10, "likelihood_outcome_counts": {"model_a_win": 6, "model_b_win": 2, "tie": 2},
        "model_ids": model_ids, "objective": 1.0, "optimizer_name": "L-BFGS-B", "outcome_policy": "ordinary_tie_only",
        "population_eligible_battle_count": 10, "population_id": "base_research", "population_model_count": 2,
        "population_outcome_counts": {"model_a_win": 6, "model_b_win": 2, "tie": 2, "tie_bothbad": 0}, "population_spec_version": 2,
        "tie_parameter": 0.5, "warnings": [],
    }
    statuses = ["SUCCESS"] * 2000
    summary = {
        "artifact_schema_version": 1, "attempted_replicates": 2000, "failed_replicates": 0, "failure_counts": {},
        "formal_ci_valid": True, "formal_replicate_target_met": True, "matrix_shapes": {"bootstrap_scores.npz": [2000, 2], "bootstrap_ranks.npz": [2000, 2], "bootstrap_tie_parameter.npz": [2000]},
        "model_ids": model_ids, "pairwise_stability": {"a|b": {"eq_frequency": 0.0, "gt_frequency": 1.0, "lt_frequency": 0.0}},
        "rank_summary": {m: {"lower_rank_quantile": float(i), "median_rank": float(i), "probability_rank_1": 1.0 if i == 1 else 0.0, "upper_rank_quantile": float(i)} for i, m in enumerate(model_ids, 1)},
        "replicate_status": statuses, "run_id": spec.run_id, "score_intervals": {"a": [0.1, 0.9], "b": [-0.9, -0.1]},
        "successful_replicates": 2000, "tie_parameter_interval": [0.2, 0.8], "warnings": [],
    }
    _json_write(run_dir / "manifest.json", manifest.to_dict())
    _json_write(run_dir / "point_estimate.json", point)
    _json_write(run_dir / "bootstrap_summary.json", summary)
    _json_write(run_dir / "replicate_status.json", {"run_id": spec.run_id, "statuses": statuses})
    scores = np.tile(np.array([[0.5, -0.5]], dtype=np.float64), (2000, 1))
    ranks = np.tile(np.array([[1.0, 2.0]], dtype=np.float64), (2000, 1))
    ties = np.full(2000, 0.5, dtype=np.float64)
    for name, key, value in (("bootstrap_scores.npz", "scores", scores), ("bootstrap_ranks.npz", "ranks", ranks), ("bootstrap_tie_parameter.npz", "tie_parameter", ties)):
        with (run_dir / name).open("wb") as stream:
            np.savez(stream, **{key: value})
    files = {name: {"sha256": _sha256(run_dir / name), "size_bytes": (run_dir / name).stat().st_size} for name in ("manifest.json", "point_estimate.json", "bootstrap_summary.json", "bootstrap_scores.npz", "bootstrap_ranks.npz", "bootstrap_tie_parameter.npz", "replicate_status.json")}
    _json_write(run_dir / "artifact_manifest.json", {"artifact_schema_version": 1, "run_id": spec.run_id, "files": files})
    spec = FrozenRunSpec("Fixture", manifest.run_id, _sha256(run_dir / "artifact_manifest.json"), (run_dir / "artifact_manifest.json").stat().st_size, seed, draft.git_commit, "base_research", 2, "davidson", "ordinary_tie_only", "judge_cluster", formal_results._freeze_value(population_view))
    review_dir = root / "comparative_review"
    review_dir.mkdir()
    review_path = review_dir / "review.json"
    _json_write(review_path, {"review_schema_version": 1, "review_type": "read_only_comparative_review", "artifact_inventory": [{"run_id": spec.run_id}]})
    monkeypatch.setattr(formal_results, "FROZEN_SOURCE", formal_results.FROZEN_SOURCE)
    monkeypatch.setattr(formal_results, "FROZEN_RUNS", (spec,))
    monkeypatch.setattr(formal_results, "FROZEN_RUN_REGISTRY", MappingProxyType({spec.run_id: spec}))
    monkeypatch.setattr(formal_results, "FROZEN_REVIEW", FrozenReviewSpec("comparative_review/review.json", review_path.stat().st_size, _sha256(review_path)))
    return root, spec


def test_valid_bundle_loads_and_normalizes_ranks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, spec = _fixture(tmp_path, monkeypatch)
    bundle = formal_results.load_frozen_formal_research(root)
    assert len(bundle.runs) == 1
    assert bundle.runs[0].spec == spec
    assert bundle.runs[0].bootstrap_ranks.dtype == np.int64
    assert bundle.runs[0].bootstrap_ranks.flags.writeable is False
    for array in (bundle.runs[0].bootstrap_scores, bundle.runs[0].bootstrap_ranks, bundle.runs[0].bootstrap_tie_parameter):
        with pytest.raises(ValueError):
            array.setflags(write=True)
    assert bundle.comparative_review["review_type"] == "read_only_comparative_review"
    with pytest.raises(TypeError):
        bundle.runs[0].manifest["run_id"] = "tampered"  # type: ignore[index]
    with pytest.raises(TypeError):
        bundle.runs[0].spec.population_view["view_type"] = "tampered"  # type: ignore[index]
    with pytest.raises(TypeError):
        bundle.runs[0].spec.population_view["nested"]["label"] = "tampered"  # type: ignore[index]


def test_unknown_run_is_closed_world_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fixture(tmp_path, monkeypatch)
    with pytest.raises(FrozenResultsError, match="unknown frozen run_id"):
        formal_results.load_frozen_formal_run("c" * 64, tmp_path / "research")


def test_missing_frozen_run_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, spec = _fixture(tmp_path, monkeypatch)
    for path in (root / spec.run_id).iterdir():
        path.unlink()
    (root / spec.run_id).rmdir()
    with pytest.raises(FrozenResultsError, match="missing"):
        formal_results.load_frozen_formal_research(root)


def test_external_artifact_manifest_digest_rejects_tampering(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, spec = _fixture(tmp_path, monkeypatch)
    path = root / spec.run_id / "artifact_manifest.json"
    path.write_text(path.read_text(encoding="utf-8") + " ", encoding="utf-8")
    with pytest.raises(FrozenResultsError, match="artifact_manifest.json identity mismatch"):
        formal_results.load_frozen_formal_research(root)


def test_self_consistent_rebuilt_artifact_manifest_is_still_not_frozen(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, spec = _fixture(tmp_path, monkeypatch)
    run_dir = root / spec.run_id
    artifact_path = run_dir / "artifact_manifest.json"
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    point_path = run_dir / "point_estimate.json"
    point = json.loads(point_path.read_text(encoding="utf-8"))
    point["tampered_note"] = "reconstructed"
    _json_write(point_path, point)
    artifact["files"]["point_estimate.json"] = {"sha256": _sha256(point_path), "size_bytes": point_path.stat().st_size}
    artifact_path.write_text(json.dumps(artifact, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    from src.formal_run import verify_research_artifacts
    assert verify_research_artifacts(run_dir).ok is True
    with pytest.raises(FrozenResultsError, match="artifact_manifest.json identity mismatch"):
        formal_results.load_frozen_formal_research(root)


def test_registry_semantics_reject_after_transitive_hashes_are_rebuilt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, spec = _fixture(tmp_path, monkeypatch)
    manifest_path = root / spec.run_id / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["git_branch"] = "tampered-branch"
    _json_write(manifest_path, manifest)
    artifact_path = root / spec.run_id / "artifact_manifest.json"
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    artifact["files"]["manifest.json"] = {"sha256": _sha256(manifest_path), "size_bytes": manifest_path.stat().st_size}
    _json_write(artifact_path, artifact)
    updated = FrozenRunSpec(spec.analysis, spec.run_id, _sha256(artifact_path), artifact_path.stat().st_size, spec.seed, spec.git_commit, spec.population_id, spec.population_spec_version, spec.estimator, spec.outcome_policy, spec.resampling_unit)
    monkeypatch.setattr(formal_results, "FROZEN_RUNS", (updated,))
    monkeypatch.setattr(formal_results, "FROZEN_RUN_REGISTRY", MappingProxyType({updated.run_id: updated}))
    assert formal_results.verify_research_artifacts(root / spec.run_id).ok is True
    with pytest.raises(FrozenResultsError, match="manifest E1 field git_branch"):
        formal_results.load_frozen_formal_research(root)


@pytest.mark.parametrize("target", ["point_estimate.json", "bootstrap_scores.npz"])
def test_parser_uses_verified_byte_snapshot_when_path_changes_after_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: str) -> None:
    root, spec = _fixture(tmp_path, monkeypatch)
    original_snapshot = formal_results._read_snapshot
    monkeypatch.setattr(formal_results, "verify_research_artifacts", lambda _directory: None)

    def read_then_replace(path: Path, label: str) -> bytes:
        data = original_snapshot(path, label)
        if path.name == target:
            path.write_bytes(b"tampered after verified read")
        return data

    monkeypatch.setattr(formal_results, "_read_snapshot", read_then_replace)
    loaded = formal_results.load_frozen_formal_run(spec.run_id, root)
    assert loaded.spec.run_id == spec.run_id


def test_review_parser_uses_verified_byte_snapshot_when_path_changes_after_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, spec = _fixture(tmp_path, monkeypatch)
    original_snapshot = formal_results._read_snapshot
    review_path = root / "comparative_review" / "review.json"

    def read_then_replace(path: Path, label: str) -> bytes:
        data = original_snapshot(path, label)
        if path == review_path:
            path.write_bytes(b"tampered after verified read")
        return data

    monkeypatch.setattr(formal_results, "_read_snapshot", read_then_replace)
    monkeypatch.setattr(formal_results, "verify_research_artifacts", lambda _directory: None)
    bundle = formal_results.load_frozen_formal_research(root)
    assert bundle.comparative_review["review_type"] == "read_only_comparative_review"
    assert bundle.comparative_review["artifact_inventory"][0]["run_id"] == spec.run_id


def test_comparative_review_directory_symlink_escape_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, _ = _fixture(tmp_path, monkeypatch)
    review_dir = root / "comparative_review"
    outside = tmp_path / "outside-review"
    outside.mkdir()
    (outside / "review.json").write_bytes((review_dir / "review.json").read_bytes())
    (review_dir / "review.json").unlink()
    review_dir.rmdir()
    try:
        os.symlink(outside, review_dir, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"directory symlink unavailable: {exc}")
    with pytest.raises(FrozenResultsError, match="comparative review path"):
        formal_results.load_frozen_formal_research(root)


@pytest.mark.parametrize("field", ["source_snapshot_id", "git_commit", "seed"])
def test_non_frozen_identity_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str) -> None:
    root, spec = _fixture(tmp_path, monkeypatch)
    manifest_path = root / spec.run_id / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if field == "seed":
        manifest["analysis_config"]["bootstrap"]["seed"] = 8
    else:
        manifest[field] = "c" * (64 if field == "source_snapshot_id" else 40)
    _json_write(manifest_path, manifest)
    with pytest.raises(FrozenResultsError):
        formal_results.load_frozen_formal_research(root)


def test_malformed_json_and_unexpected_file_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, spec = _fixture(tmp_path, monkeypatch)
    (root / spec.run_id / "point_estimate.json").write_text("{", encoding="utf-8")
    with pytest.raises(FrozenResultsError):
        formal_results.load_frozen_formal_research(root)
    root, spec = _fixture(tmp_path / "second", monkeypatch)
    (root / spec.run_id / "unexpected.txt").write_text("x", encoding="utf-8")
    with pytest.raises(FrozenResultsError):
        formal_results.load_frozen_formal_research(root)


@pytest.mark.parametrize("name, key, value", [
    ("bootstrap_scores.npz", "scores", np.zeros((1, 2), dtype=np.float64)),
    ("bootstrap_ranks.npz", "wrong", np.zeros((2000, 2), dtype=np.float64)),
    ("bootstrap_ranks.npz", "ranks", np.zeros((2000, 2), dtype=np.int64)),
])
def test_npz_schema_and_dtype_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str, key: str, value: np.ndarray) -> None:
    root, spec = _fixture(tmp_path, monkeypatch)
    with (root / spec.run_id / name).open("wb") as stream:
        np.savez(stream, **{key: value})
    with pytest.raises(FrozenResultsError):
        formal_results.load_frozen_formal_research(root)


def test_invalid_rank_semantics_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, spec = _fixture(tmp_path, monkeypatch)
    bad = np.tile(np.array([[1.0, 1.0]], dtype=np.float64), (2000, 1))
    with (root / spec.run_id / "bootstrap_ranks.npz").open("wb") as stream:
        np.savez(stream, ranks=bad)
    with pytest.raises(FrozenResultsError):
        formal_results.load_frozen_formal_research(root)


def test_review_hash_and_run_inventory_are_verified(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, _ = _fixture(tmp_path, monkeypatch)
    review_path = root / "comparative_review" / "review.json"
    review_path.write_text(review_path.read_text(encoding="utf-8").replace('"artifact_inventory"', '"extra_run": "d" * 64, "artifact_inventory"'), encoding="utf-8")
    with pytest.raises(FrozenResultsError, match="comparative review digest"):
        formal_results.load_frozen_formal_research(root)


def test_loader_does_not_call_execution_paths_or_write_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, _ = _fixture(tmp_path, monkeypatch)
    before = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    import src.data_io as data_io
    import src.formal_run as formal_run
    import src.preference_bootstrap as bootstrap
    import src.preference_estimation as estimation
    for module, name in ((formal_run, "execute_formal_run"), (data_io, "download_chatbot_arena"), (bootstrap, "run_bootstrap"), (estimation, "fit_preference")):
        monkeypatch.setattr(module, name, lambda *args, **kwargs: pytest.fail(f"execution path called: {name}"))
    formal_results.load_frozen_formal_research(root)
    after = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    assert before == after
