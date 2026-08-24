from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.battle_contract import SourceProvenance, canonicalize_battles
from src.formal_run import (
    FormalRunConfig,
    FormalRunError,
    FormalRunErrorCode,
    _write_deterministic_npz,
    execute_formal_run,
    preflight_formal_run,
    verify_research_artifacts,
)
from src.population import BASE_RESEARCH, apply_population
from src.preference_bootstrap import BootstrapConfig
from src.preference_estimation import PreferenceEstimatorConfig


PROVENANCE = SourceProvenance(
    source_dataset="synthetic/formal-run",
    source_revision="v1",
    source_split="train",
    source_file="synthetic.parquet",
)
GIT_STATE = {
    "branch": "main",
    "head": "a" * 40,
    "origin_main": "a" * 40,
    "status": "",
}


def _rows() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    conversation = [
        {"role": "user", "content": "prompt"},
        {"role": "assistant", "content": "response"},
    ]
    for judge in ("j1", "j2", "j3"):
        rows.extend(
            [
                {"model_a": "a", "model_b": "b", "winner": "model_a", "judge": judge},
                {"model_a": "b", "model_b": "c", "winner": "tie", "judge": judge},
                {"model_a": "c", "model_b": "a", "winner": "model_a", "judge": judge},
            ]
        )
    for row in rows:
        row.update(
            {
                "conversation_a": conversation,
                "conversation_b": conversation,
                "tstamp": 0,
                "language": "English",
                "anony": True,
            }
        )
    return pd.DataFrame(rows)


def _config(source: Path, artifact_root: Path, *, mode: str = "development", count: int = 4) -> FormalRunConfig:
    provenance = replace(PROVENANCE, source_file_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
    estimator = PreferenceEstimatorConfig("davidson")
    bootstrap = BootstrapConfig(
        resampling_unit="judge_cluster",
        replicate_count=count,
        seed=19,
        estimator_config=estimator,
    )
    return FormalRunConfig(
        source_provenance=provenance,
        population_id=BASE_RESEARCH.population_id,
        estimator_config=estimator,
        bootstrap_config=bootstrap,
        artifact_root=artifact_root,
        execution_mode=mode,
        git_commit=GIT_STATE["head"],
        git_branch="main",
    )


def _run(tmp_path: Path, *, count: int = 4) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    source = tmp_path / "synthetic.parquet"
    source.write_bytes(b"synthetic source")
    config = _config(source, tmp_path / "outputs" / "research", count=count)
    return execute_formal_run(
        source,
        config,
        repo_root=tmp_path,
        git_state=GIT_STATE,
        loader=lambda _path: _rows(),
    )


def test_development_run_writes_and_verifies_complete_artifacts(tmp_path: Path) -> None:
    run_dir = _run(tmp_path)
    verification = verify_research_artifacts(run_dir)
    assert verification.ok is True
    assert set(verification.files_checked) == {
        "bootstrap_ranks.npz",
        "bootstrap_scores.npz",
        "bootstrap_summary.json",
        "bootstrap_tie_parameter.npz",
        "manifest.json",
        "point_estimate.json",
        "replicate_status.json",
    }
    summary = json.loads((run_dir / "bootstrap_summary.json").read_text(encoding="utf-8"))
    assert summary["attempted_replicates"] == 4
    assert summary["formal_ci_valid"] is False
    payload = "\n".join(path.read_text(encoding="utf-8") for path in run_dir.glob("*.json"))
    assert "judge_cluster_id" not in payload
    assert "prompt_text" not in payload
    assert "response_a_text" not in payload
    assert "response_b_text" not in payload


def test_deterministic_npz_bytes_are_stable(tmp_path: Path) -> None:
    arrays = {"scores": np.arange(6, dtype=float).reshape(2, 3)}
    first = tmp_path / "first.npz"
    second = tmp_path / "second.npz"
    _write_deterministic_npz(first, arrays)
    _write_deterministic_npz(second, arrays)
    assert hashlib.sha256(first.read_bytes()).digest() == hashlib.sha256(second.read_bytes()).digest()


def test_same_development_spec_has_same_run_and_artifact_bytes(tmp_path: Path) -> None:
    first = _run(tmp_path / "first")
    second = _run(tmp_path / "second")
    assert first.name == second.name
    for name in (
        "manifest.json",
        "point_estimate.json",
        "bootstrap_summary.json",
        "bootstrap_scores.npz",
        "bootstrap_ranks.npz",
        "bootstrap_tie_parameter.npz",
        "replicate_status.json",
        "artifact_manifest.json",
    ):
        assert (first / name).read_bytes() == (second / name).read_bytes()


def test_tampered_json_fails_hash_verification(tmp_path: Path) -> None:
    run_dir = _run(tmp_path)
    path = run_dir / "bootstrap_summary.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["failed_replicates"] = 1
    path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    with pytest.raises(FormalRunError) as caught:
        verify_research_artifacts(run_dir)
    assert caught.value.code == FormalRunErrorCode.ARTIFACT_HASH_MISMATCH


def test_tampered_matrix_fails_hash_verification(tmp_path: Path) -> None:
    run_dir = _run(tmp_path)
    with (run_dir / "bootstrap_scores.npz").open("ab") as stream:
        stream.write(b"tamper")
    with pytest.raises(FormalRunError) as caught:
        verify_research_artifacts(run_dir)
    assert caught.value.code == FormalRunErrorCode.ARTIFACT_HASH_MISMATCH


def test_wrong_artifact_manifest_run_id_fails_consistency(tmp_path: Path) -> None:
    run_dir = _run(tmp_path)
    path = run_dir / "artifact_manifest.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["run_id"] = "0" * 64
    path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    with pytest.raises(FormalRunError) as caught:
        verify_research_artifacts(run_dir)
    assert caught.value.code == FormalRunErrorCode.ARTIFACT_CONSISTENCY_ERROR


def test_matrix_shape_mismatch_fails_consistency(tmp_path: Path) -> None:
    run_dir = _run(tmp_path)
    summary_path = run_dir / "bootstrap_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["matrix_shapes"]["bootstrap_scores.npz"] = [999, 3]
    summary_path.write_text(json.dumps(summary, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    artifact_path = run_dir / "artifact_manifest.json"
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    artifact["files"]["bootstrap_summary.json"] = {
        "sha256": hashlib.sha256(summary_path.read_bytes()).hexdigest(),
        "size_bytes": summary_path.stat().st_size,
    }
    artifact_path.write_text(json.dumps(artifact, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    with pytest.raises(FormalRunError) as caught:
        verify_research_artifacts(run_dir)
    assert caught.value.code == FormalRunErrorCode.ARTIFACT_CONSISTENCY_ERROR


def test_preflight_rejects_formal_missing_target_and_source_before_loading(tmp_path: Path) -> None:
    source = tmp_path / "synthetic.parquet"
    source.write_bytes(b"synthetic source")
    development = _config(source, tmp_path / "outputs" / "research")
    with pytest.raises(FormalRunError) as caught:
        FormalRunConfig(
            **{**development.__dict__, "execution_mode": "formal", "bootstrap_config": replace(development.bootstrap_config, replicate_count=1999)}
        )
    assert caught.value.code == FormalRunErrorCode.INVALID_FORMAL_CONFIG

    wrong_source = replace(development.source_provenance, source_file_sha256="0" * 64)
    wrong_config = replace(development, source_provenance=wrong_source)
    with pytest.raises(FormalRunError) as caught:
        preflight_formal_run(source, wrong_config, git_state=GIT_STATE, repo_root=tmp_path)
    assert caught.value.code == FormalRunErrorCode.SOURCE_SHA_MISMATCH


@pytest.mark.parametrize(
    ("field", "code"),
    [
        ("head", FormalRunErrorCode.GIT_SHA_MISMATCH),
        ("status", FormalRunErrorCode.DIRTY_WORKTREE),
        ("origin_main", FormalRunErrorCode.UNPUBLISHED_GIT_SHA),
    ],
)
def test_preflight_git_publication_gates(tmp_path: Path, field: str, code: FormalRunErrorCode) -> None:
    source = tmp_path / "synthetic.parquet"
    source.write_bytes(b"synthetic source")
    config = _config(source, tmp_path / "outputs" / "research")
    state = dict(GIT_STATE)
    state[field] = "dirty" if field == "status" else "b" * 40
    with pytest.raises(FormalRunError) as caught:
        preflight_formal_run(source, config, git_state=state, repo_root=tmp_path)
    assert caught.value.code == code


def test_unknown_population_and_existing_run_are_rejected(tmp_path: Path) -> None:
    source = tmp_path / "synthetic.parquet"
    source.write_bytes(b"synthetic source")
    config = _config(source, tmp_path / "outputs" / "research")
    unknown = replace(config, population_id="not-a-population")
    with pytest.raises(FormalRunError) as caught:
        preflight_formal_run(source, unknown, git_state=GIT_STATE, repo_root=tmp_path)
    assert caught.value.code == FormalRunErrorCode.UNKNOWN_POPULATION

    first = _run(tmp_path / "first")
    second_source = tmp_path / "second" / "synthetic.parquet"
    second_source.parent.mkdir()
    second_source.write_bytes(b"synthetic source")
    second_config = _config(second_source, first.parent)
    with pytest.raises(FormalRunError) as caught:
        preflight_formal_run(second_source, second_config, git_state=GIT_STATE, repo_root=tmp_path)
    assert caught.value.code == FormalRunErrorCode.RUN_ALREADY_EXISTS


def test_formal_seed_and_replicate_requirements_are_explicit(tmp_path: Path) -> None:
    source = tmp_path / "synthetic.parquet"
    source.write_bytes(b"synthetic source")
    config = _config(source, tmp_path / "outputs" / "research", mode="formal", count=2000)
    assert config.bootstrap_config.seed == 19
    assert config.bootstrap_config.to_dict()["seed"] == 19
    with pytest.raises(ValueError):
        BootstrapConfig(resampling_unit="judge_cluster", replicate_count=2000, seed=None)  # type: ignore[arg-type]


def test_manifest_contains_one_authoritative_bootstrap_seed(tmp_path: Path) -> None:
    source = tmp_path / "synthetic.parquet"
    source.write_bytes(b"synthetic source")
    config = _config(source, tmp_path / "outputs" / "research")
    result = preflight_formal_run(source, config, git_state=GIT_STATE, repo_root=tmp_path)
    assert result.manifest is not None
    analysis = result.manifest.analysis_config
    assert analysis["bootstrap"]["seed"] == config.bootstrap_config.seed
    assert "seed" not in analysis["formal_run"]


def test_incomplete_temporary_directory_is_not_accepted(tmp_path: Path) -> None:
    run_dir = tmp_path / "outputs" / "research" / ".tmp-incomplete"
    run_dir.mkdir(parents=True)
    (run_dir / "manifest.json").write_text("{}", encoding="utf-8")
    with pytest.raises(FormalRunError) as caught:
        verify_research_artifacts(run_dir)
    assert caught.value.code == FormalRunErrorCode.MANIFEST_INVALID
