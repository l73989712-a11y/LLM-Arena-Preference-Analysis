"""Formal research-run gates and deterministic artifact orchestration.

This layer prepares and verifies runs. It does not choose statistical
semantics, seeds, or populations and is intentionally separate from the
estimator and bootstrap implementations.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import zipfile
from typing import Any

import numpy as np
import pandas as pd

from src.battle_contract import (
    CANONICAL_BATTLE_SCHEMA_VERSION,
    SourceProvenance,
    canonicalize_battles,
)
from src.population import (
    BASE_RESEARCH,
    JUDGE_CLUSTER_RESEARCH,
    LANGUAGE_RESEARCH,
    LEGACY_SCORE,
    POPULATION_SPEC_SCHEMA_VERSION,
    PopulationSpec,
    apply_population,
)
from src.population_views import (
    POPULATION_VIEW_SCHEMA_VERSION,
    PopulationViewSpec,
    apply_population_view,
    derived_population_spec,
    population_view_for_id,
)
from src.preference_bootstrap import (
    BootstrapConfig,
    BootstrapResult,
    FORMAL_REPLICATE_TARGET,
    run_bootstrap,
)
from src.preference_estimation import PreferenceEstimationResult, PreferenceEstimatorConfig, fit_preference
from src.run_manifest import (
    RunManifest,
    capture_environment,
    create_run_manifest,
)


RESEARCH_ARTIFACT_SCHEMA_VERSION = 1
ARTIFACT_FILES = (
    "manifest.json",
    "point_estimate.json",
    "bootstrap_summary.json",
    "bootstrap_scores.npz",
    "bootstrap_ranks.npz",
    "bootstrap_tie_parameter.npz",
    "replicate_status.json",
    "artifact_manifest.json",
)
class FormalRunErrorCode(str, Enum):
    INVALID_FORMAL_CONFIG = "INVALID_FORMAL_CONFIG"
    SOURCE_SHA_MISMATCH = "SOURCE_SHA_MISMATCH"
    GIT_SHA_MISMATCH = "GIT_SHA_MISMATCH"
    DIRTY_WORKTREE = "DIRTY_WORKTREE"
    UNPUBLISHED_GIT_SHA = "UNPUBLISHED_GIT_SHA"
    UNKNOWN_POPULATION = "UNKNOWN_POPULATION"
    RUN_ALREADY_EXISTS = "RUN_ALREADY_EXISTS"
    TEMP_RUN_ALREADY_EXISTS = "TEMP_RUN_ALREADY_EXISTS"
    MANIFEST_INVALID = "MANIFEST_INVALID"
    ARTIFACT_WRITE_FAILED = "ARTIFACT_WRITE_FAILED"
    ARTIFACT_HASH_MISMATCH = "ARTIFACT_HASH_MISMATCH"
    ARTIFACT_CONSISTENCY_ERROR = "ARTIFACT_CONSISTENCY_ERROR"


class FormalRunError(RuntimeError):
    def __init__(self, code: FormalRunErrorCode, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code.value}: {message}")


@dataclass(frozen=True)
class FormalRunConfig:
    source_provenance: SourceProvenance
    population_id: str
    estimator_config: PreferenceEstimatorConfig
    bootstrap_config: BootstrapConfig
    artifact_root: str | Path
    execution_mode: str
    git_commit: str
    git_branch: str = "main"
    require_published: bool = True
    created_by: str = "formal-research-runner"
    population_view: PopulationViewSpec | None = None

    def __post_init__(self) -> None:
        if self.execution_mode not in {"preflight", "development", "formal"}:
            raise FormalRunError(FormalRunErrorCode.INVALID_FORMAL_CONFIG, "unsupported execution_mode")
        if not self.population_id.strip():
            raise FormalRunError(FormalRunErrorCode.INVALID_FORMAL_CONFIG, "population_id must not be empty")
        if self.population_view is not None and self.population_view.population_id != self.population_id:
            raise FormalRunError(FormalRunErrorCode.INVALID_FORMAL_CONFIG, "population view id differs from population_id")
        if not self.git_commit.strip() or not self.git_branch.strip():
            raise FormalRunError(FormalRunErrorCode.INVALID_FORMAL_CONFIG, "Git identity is required")
        if self.bootstrap_config.estimator_config != self.estimator_config:
            raise FormalRunError(FormalRunErrorCode.INVALID_FORMAL_CONFIG, "estimator config differs from bootstrap config")
        if self.execution_mode == "formal":
            if self.bootstrap_config.replicate_count < FORMAL_REPLICATE_TARGET:
                raise FormalRunError(FormalRunErrorCode.INVALID_FORMAL_CONFIG, "formal mode requires at least 2,000 attempts")
            if not isinstance(self.bootstrap_config.seed, int) or isinstance(self.bootstrap_config.seed, bool):
                raise FormalRunError(FormalRunErrorCode.INVALID_FORMAL_CONFIG, "formal mode requires an explicit integer seed")
            if not self.require_published:
                raise FormalRunError(FormalRunErrorCode.INVALID_FORMAL_CONFIG, "formal mode requires publication verification")
        if not str(self.artifact_root).strip():
            raise FormalRunError(FormalRunErrorCode.INVALID_FORMAL_CONFIG, "artifact_root must not be empty")

    def analysis_config(self) -> dict[str, Any]:
        config = {
            "estimator": self.estimator_config.to_dict(),
            "bootstrap": self.bootstrap_config.to_dict(),
            "formal_run": {
                "execution_mode": self.execution_mode,
                "artifact_schema_version": RESEARCH_ARTIFACT_SCHEMA_VERSION,
                "require_published": self.require_published,
            },
        }
        if self.population_view is not None:
            config["population_view"] = self.population_view.to_dict()
        return config


@dataclass(frozen=True)
class PreflightResult:
    ok: bool
    checks: dict[str, str]
    manifest: RunManifest | None


@dataclass(frozen=True)
class ArtifactVerification:
    ok: bool
    run_id: str
    files_checked: tuple[str, ...]


_POPULATIONS: dict[str, PopulationSpec] = {
    spec.population_id: spec for spec in (BASE_RESEARCH, LEGACY_SCORE, JUDGE_CLUSTER_RESEARCH, LANGUAGE_RESEARCH)
}


def _error(code: FormalRunErrorCode, message: str) -> None:
    raise FormalRunError(code, message)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(_jsonable(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _jsonable(value: Any) -> Any:
    """Convert numpy scalars and nested containers without exposing raw rows."""
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _write_json(path: Path, value: Any) -> None:
    path.write_bytes(_json_bytes(value))


def _deterministic_npy(value: np.ndarray) -> bytes:
    stream = io.BytesIO()
    np.save(stream, np.asarray(value), allow_pickle=False)
    return stream.getvalue()


def _write_deterministic_npz(path: Path, arrays: Mapping[str, np.ndarray]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(arrays):
            info = zipfile.ZipInfo(f"{name}.npy", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 0
            info.external_attr = 0o600 << 16
            archive.writestr(info, _deterministic_npy(np.asarray(arrays[name])))


def _read_git_state(repo_root: Path) -> dict[str, str]:
    def git(*args: str, missing: str = "") -> str:
        result = subprocess.run(["git", *args], cwd=repo_root, capture_output=True, text=True)
        if result.returncode != 0:
            return missing
        return result.stdout.strip()

    return {
        "branch": git("branch", "--show-current"),
        "head": git("rev-parse", "HEAD"),
        "origin_main": git("rev-parse", "--verify", "origin/main"),
        "status": git("status", "--porcelain", "--untracked-files=all"),
    }


def _population_spec(population_id: str) -> PopulationSpec:
    spec = _POPULATIONS.get(population_id)
    if spec is None:
        _error(FormalRunErrorCode.UNKNOWN_POPULATION, f"unknown population: {population_id}")
    return spec


def _population_view(config: FormalRunConfig) -> PopulationViewSpec | None:
    if config.population_view is not None:
        try:
            registered = population_view_for_id(config.population_id)
        except KeyError:
            _error(FormalRunErrorCode.UNKNOWN_POPULATION, f"unknown population view: {config.population_id}")
        if config.population_view.to_dict() != registered.to_dict():
            _error(FormalRunErrorCode.INVALID_FORMAL_CONFIG, "population view does not match registry")
        return config.population_view
    if config.population_id in {
        "base_research_no_repeated_qid",
        "base_research_pair_support_ge10",
        "base_research_pair_support_ge20",
        "base_research_pair_support_ge50",
        "base_research_language_en",
    }:
        _error(FormalRunErrorCode.UNKNOWN_POPULATION, "sensitivity population requires a population_view definition")
    return None


def _effective_population_spec(config: FormalRunConfig) -> PopulationSpec:
    view = _population_view(config)
    if view is not None:
        return derived_population_spec(view)
    return _population_spec(config.population_id)


def _manifest(config: FormalRunConfig, *, environment: Mapping[str, Any] | None = None) -> RunManifest:
    return create_run_manifest(
        source_provenance=config.source_provenance,
        population_spec=_effective_population_spec(config),
        git_commit=config.git_commit,
        git_branch=config.git_branch,
        analysis_config=config.analysis_config(),
        created_by=config.created_by,
        environment=environment or capture_environment(("numpy", "pandas", "scipy")),
    )


def _check_source(path: Path, provenance: SourceProvenance) -> None:
    if not path.is_file():
        _error(FormalRunErrorCode.SOURCE_SHA_MISMATCH, "source file does not exist")
    expected = provenance.source_file_sha256
    if not expected or _sha256(path) != expected:
        _error(FormalRunErrorCode.SOURCE_SHA_MISMATCH, "source SHA-256 does not match formal provenance")
    if provenance.source_file and path.name != Path(provenance.source_file).name:
        _error(FormalRunErrorCode.SOURCE_SHA_MISMATCH, "source filename does not match formal provenance")


def preflight_formal_run(
    source_path: str | Path,
    config: FormalRunConfig,
    *,
    repo_root: str | Path = ".",
    git_state: Mapping[str, str] | None = None,
) -> PreflightResult:
    """Run all static formal gates without canonicalizing or fitting data."""
    source = Path(source_path).resolve()
    root = Path(repo_root).resolve()
    state = dict(git_state or _read_git_state(root))
    checks: dict[str, str] = {}
    _check_source(source, config.source_provenance)
    checks["source_sha"] = "PASS"
    if state.get("branch") != config.git_branch or state.get("head") != config.git_commit:
        _error(FormalRunErrorCode.GIT_SHA_MISMATCH, "current Git branch or HEAD does not match formal config")
    checks["git_identity"] = "PASS"
    if state.get("status", ""):
        _error(FormalRunErrorCode.DIRTY_WORKTREE, "tracked or untracked worktree changes are present")
    checks["worktree"] = "PASS"
    if config.require_published and state.get("origin_main") != config.git_commit:
        _error(FormalRunErrorCode.UNPUBLISHED_GIT_SHA, "origin/main does not contain the formal Git SHA")
    checks["publication"] = "PASS"
    spec = _effective_population_spec(config)
    expected_population_version = (
        POPULATION_VIEW_SCHEMA_VERSION if config.population_view is not None else POPULATION_SPEC_SCHEMA_VERSION
    )
    if spec.population_spec_version != expected_population_version:
        _error(FormalRunErrorCode.UNKNOWN_POPULATION, "population schema version mismatch")
    checks["population"] = "PASS"
    if CANONICAL_BATTLE_SCHEMA_VERSION <= 0:
        _error(FormalRunErrorCode.MANIFEST_INVALID, "invalid canonical schema version")
    checks["canonical_schema"] = "PASS"
    environment = capture_environment(("numpy", "pandas", "scipy"))
    package_versions = environment.get("package_versions", {})
    missing_packages = [name for name in ("numpy", "pandas", "scipy") if not package_versions.get(name)]
    if missing_packages:
        _error(FormalRunErrorCode.MANIFEST_INVALID, f"required packages unavailable: {missing_packages}")
    checks["environment"] = "PASS"
    artifact_root = Path(config.artifact_root).resolve()
    artifact_root.mkdir(parents=True, exist_ok=True)
    manifest = _manifest(config, environment=environment)
    try:
        RunManifest.from_json(manifest.to_json())
    except (KeyError, TypeError, ValueError) as exc:
        _error(FormalRunErrorCode.MANIFEST_INVALID, str(exc))
    final_dir = artifact_root / manifest.run_id
    if final_dir.exists():
        _error(FormalRunErrorCode.RUN_ALREADY_EXISTS, "final run directory already exists")
    temp_dir = artifact_root / f".tmp-{manifest.run_id}"
    if temp_dir.exists():
        _error(FormalRunErrorCode.TEMP_RUN_ALREADY_EXISTS, "temporary run directory already exists")
    checks["artifact_root"] = "PASS"
    checks["manifest"] = "PASS"
    return PreflightResult(ok=True, checks=checks, manifest=manifest)


def _point_payload(result: PreferenceEstimationResult) -> dict[str, Any]:
    return {
        "estimator_name": result.estimator_name,
        "estimator_version": result.estimator_version,
        "estimator_config": result.estimator_config,
        "outcome_policy": result.outcome_policy,
        "population_id": result.population_id,
        "population_spec_version": result.population_spec_version,
        "model_ids": list(result.model_ids),
        "latent_scores": list(result.latent_scores),
        "derived_rank": list(result.derived_rank),
        "identifiability_constraint": result.identifiability_constraint,
        "population_eligible_battle_count": result.population_eligible_battle_count,
        "likelihood_battle_count": result.likelihood_battle_count,
        "population_outcome_counts": result.population_outcome_counts,
        "likelihood_outcome_counts": result.likelihood_outcome_counts,
        "excluded_outcome_counts": result.excluded_outcome_counts,
        "population_model_count": result.population_model_count,
        "estimator_model_count": result.estimator_model_count,
        "graph_node_count": result.graph_node_count,
        "graph_edge_count": result.graph_edge_count,
        "graph_component_count": result.graph_component_count,
        "converged": result.converged,
        "optimizer_name": result.optimizer_name,
        "iterations": result.iterations,
        "objective": result.objective,
        "tie_parameter": result.tie_parameter,
        "warnings": list(result.warnings),
    }


def _bootstrap_summary(result: BootstrapResult) -> dict[str, Any]:
    return {
        "artifact_schema_version": RESEARCH_ARTIFACT_SCHEMA_VERSION,
        "run_id": None,
        "model_ids": list(result.model_ids),
        "attempted_replicates": result.attempted_replicates,
        "successful_replicates": result.successful_replicates,
        "failed_replicates": result.failed_replicates,
        "formal_replicate_target_met": result.formal_replicate_target_met,
        "formal_ci_valid": result.formal_ci_valid,
        "failure_counts": result.failure_counts,
        "replicate_status": list(result.replicate_status),
        "score_intervals": result.score_intervals,
        "rank_summary": result.rank_summary,
        "pairwise_stability": result.pairwise_stability,
        "tie_parameter_interval": result.tie_parameter_interval,
        "warnings": list(result.warnings),
        "matrix_shapes": {
            "bootstrap_scores.npz": list(result.score_replicates.shape),
            "bootstrap_ranks.npz": list(result.rank_replicates.shape),
            "bootstrap_tie_parameter.npz": list(result.tie_parameter_replicates.shape),
        },
    }


def _artifact_files(directory: Path) -> dict[str, dict[str, Any]]:
    return {
        name: {"sha256": _sha256(directory / name), "size_bytes": (directory / name).stat().st_size}
        for name in ARTIFACT_FILES
        if name != "artifact_manifest.json"
    }


def _validate_result_consistency(manifest: RunManifest, point: PreferenceEstimationResult, bootstrap: BootstrapResult) -> None:
    estimator_config = manifest.analysis_config.get("estimator")
    if not isinstance(estimator_config, Mapping):
        _error(FormalRunErrorCode.ARTIFACT_CONSISTENCY_ERROR, "manifest estimator config is invalid")
    if point.population_id != manifest.population_id:
        _error(FormalRunErrorCode.ARTIFACT_CONSISTENCY_ERROR, "point population differs from manifest")
    if point.population_spec_version != manifest.population_spec_version:
        _error(FormalRunErrorCode.ARTIFACT_CONSISTENCY_ERROR, "point population spec version differs from manifest")
    if point.estimator_config != estimator_config:
        _error(FormalRunErrorCode.ARTIFACT_CONSISTENCY_ERROR, "point estimator config differs from manifest")
    if point.estimator_name != estimator_config.get("estimator") or point.estimator_version != estimator_config.get("estimator_version"):
        _error(FormalRunErrorCode.ARTIFACT_CONSISTENCY_ERROR, "point estimator identity differs from manifest")
    if tuple(point.model_ids) != tuple(bootstrap.model_ids):
        _error(FormalRunErrorCode.ARTIFACT_CONSISTENCY_ERROR, "point and bootstrap model universes differ")
    if bootstrap.attempted_replicates != bootstrap.bootstrap_config.replicate_count:
        _error(FormalRunErrorCode.ARTIFACT_CONSISTENCY_ERROR, "attempt count mismatch")
    if len(bootstrap.replicate_status) != bootstrap.attempted_replicates:
        _error(FormalRunErrorCode.ARTIFACT_CONSISTENCY_ERROR, "replicate status length mismatch")
    shapes = (bootstrap.score_replicates.shape, bootstrap.rank_replicates.shape, bootstrap.tie_parameter_replicates.shape)
    expected = ((bootstrap.attempted_replicates, len(bootstrap.model_ids)), (bootstrap.attempted_replicates, len(bootstrap.model_ids)), (bootstrap.attempted_replicates,))
    if shapes != expected:
        _error(FormalRunErrorCode.ARTIFACT_CONSISTENCY_ERROR, "bootstrap matrix shape mismatch")


def write_research_artifacts(
    directory: str | Path,
    manifest: RunManifest,
    point: PreferenceEstimationResult,
    bootstrap: BootstrapResult,
) -> Path:
    """Write a complete run atomically and verify it before finalization."""
    final_dir = Path(directory).resolve()
    if final_dir.name != manifest.run_id or final_dir.name in {"", ".", ".."}:
        _error(FormalRunErrorCode.ARTIFACT_WRITE_FAILED, "artifact directory must be the manifest run_id")
    root = final_dir.parent
    root.mkdir(parents=True, exist_ok=True)
    if final_dir.exists():
        _error(FormalRunErrorCode.RUN_ALREADY_EXISTS, "final run directory already exists")
    temp_dir = root / f".tmp-{manifest.run_id}"
    if temp_dir.exists():
        _error(FormalRunErrorCode.TEMP_RUN_ALREADY_EXISTS, "temporary run directory already exists")
    temp_created = False
    try:
        try:
            temp_dir.mkdir(parents=False)
            temp_created = True
        except FileExistsError:
            _error(FormalRunErrorCode.TEMP_RUN_ALREADY_EXISTS, "temporary run directory already exists")
        _validate_result_consistency(manifest, point, bootstrap)
        _write_json(temp_dir / "manifest.json", manifest.to_dict())
        _write_json(temp_dir / "point_estimate.json", _point_payload(point))
        summary = _bootstrap_summary(bootstrap)
        summary["run_id"] = manifest.run_id
        _write_json(temp_dir / "bootstrap_summary.json", summary)
        _write_deterministic_npz(temp_dir / "bootstrap_scores.npz", {"scores": bootstrap.score_replicates})
        _write_deterministic_npz(temp_dir / "bootstrap_ranks.npz", {"ranks": bootstrap.rank_replicates})
        _write_deterministic_npz(temp_dir / "bootstrap_tie_parameter.npz", {"tie_parameter": bootstrap.tie_parameter_replicates})
        _write_json(temp_dir / "replicate_status.json", {"run_id": manifest.run_id, "statuses": list(bootstrap.replicate_status)})
        _write_json(temp_dir / "artifact_manifest.json", {
            "artifact_schema_version": RESEARCH_ARTIFACT_SCHEMA_VERSION,
            "run_id": manifest.run_id,
            "files": _artifact_files(temp_dir),
        })
        verify_research_artifacts(temp_dir, allow_temporary=True)
        os.replace(temp_dir, final_dir)
        try:
            verify_research_artifacts(final_dir)
        except FormalRunError:
            if final_dir.exists():
                shutil.rmtree(final_dir)
            raise
        return final_dir
    except FormalRunError:
        if temp_created and temp_dir.exists():
            shutil.rmtree(temp_dir)
        raise
    except Exception as exc:
        if temp_created and temp_dir.exists():
            shutil.rmtree(temp_dir)
        _error(FormalRunErrorCode.ARTIFACT_WRITE_FAILED, str(exc))


def verify_research_artifacts(run_dir: str | Path, *, allow_temporary: bool = False) -> ArtifactVerification:
    directory = Path(run_dir).resolve()
    manifest_path = directory / "manifest.json"
    artifact_path = directory / "artifact_manifest.json"
    if not directory.is_dir() or not manifest_path.is_file() or not artifact_path.is_file():
        _error(FormalRunErrorCode.MANIFEST_INVALID, "run directory is incomplete")
    try:
        manifest = RunManifest.from_json(manifest_path.read_text(encoding="utf-8"))
        artifact_manifest = json.loads(artifact_path.read_text(encoding="utf-8"))
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        _error(FormalRunErrorCode.MANIFEST_INVALID, str(exc))
    if artifact_manifest.get("artifact_schema_version") != RESEARCH_ARTIFACT_SCHEMA_VERSION:
        _error(FormalRunErrorCode.ARTIFACT_CONSISTENCY_ERROR, "unsupported artifact schema version")
    if artifact_manifest.get("run_id") != manifest.run_id:
        _error(FormalRunErrorCode.ARTIFACT_CONSISTENCY_ERROR, "artifact manifest run_id mismatch")
    valid_names = {manifest.run_id}
    if allow_temporary:
        valid_names.add(f".tmp-{manifest.run_id}")
    if directory.name not in valid_names:
        _error(FormalRunErrorCode.ARTIFACT_CONSISTENCY_ERROR, "run directory name does not match manifest run_id")
    files = artifact_manifest.get("files")
    if not isinstance(files, Mapping):
        _error(FormalRunErrorCode.ARTIFACT_CONSISTENCY_ERROR, "artifact file manifest is invalid")
    if set(files or {}) != set(ARTIFACT_FILES) - {"artifact_manifest.json"}:
        _error(FormalRunErrorCode.ARTIFACT_CONSISTENCY_ERROR, "artifact file set mismatch")
    actual_files = {path.name for path in directory.iterdir() if path.is_file()}
    if actual_files != set(ARTIFACT_FILES):
        _error(FormalRunErrorCode.ARTIFACT_CONSISTENCY_ERROR, "run directory contains unexpected or missing files")
    for name, record in files.items():
        path = directory / name
        if not path.is_file() or path.stat().st_size != record.get("size_bytes") or _sha256(path) != record.get("sha256"):
            _error(FormalRunErrorCode.ARTIFACT_HASH_MISMATCH, f"artifact hash mismatch: {name}")
    summary = json.loads((directory / "bootstrap_summary.json").read_text(encoding="utf-8"))
    point_payload = json.loads((directory / "point_estimate.json").read_text(encoding="utf-8"))
    status_payload = json.loads((directory / "replicate_status.json").read_text(encoding="utf-8"))
    if summary.get("run_id") != manifest.run_id:
        _error(FormalRunErrorCode.ARTIFACT_CONSISTENCY_ERROR, "bootstrap summary run_id mismatch")
    estimator_config = manifest.analysis_config.get("estimator")
    if not isinstance(estimator_config, Mapping):
        _error(FormalRunErrorCode.ARTIFACT_CONSISTENCY_ERROR, "manifest estimator config is invalid")
    if point_payload.get("population_id") != manifest.population_id:
        _error(FormalRunErrorCode.ARTIFACT_CONSISTENCY_ERROR, "point population differs from manifest")
    if point_payload.get("population_spec_version") != manifest.population_spec_version:
        _error(FormalRunErrorCode.ARTIFACT_CONSISTENCY_ERROR, "point population spec version differs from manifest")
    if point_payload.get("estimator_config") != estimator_config:
        _error(FormalRunErrorCode.ARTIFACT_CONSISTENCY_ERROR, "point estimator config differs from manifest")
    if (
        point_payload.get("estimator_name") != estimator_config.get("estimator")
        or point_payload.get("estimator_version") != estimator_config.get("estimator_version")
    ):
        _error(FormalRunErrorCode.ARTIFACT_CONSISTENCY_ERROR, "point estimator identity differs from manifest")
    if point_payload.get("model_ids") != summary.get("model_ids"):
        _error(FormalRunErrorCode.ARTIFACT_CONSISTENCY_ERROR, "point and bootstrap model universes differ")
    if status_payload.get("run_id") != manifest.run_id or status_payload.get("statuses") != summary.get("replicate_status"):
        _error(FormalRunErrorCode.ARTIFACT_CONSISTENCY_ERROR, "replicate status artifact differs from summary")
    if summary.get("attempted_replicates") != len(summary.get("replicate_status", [])):
        _error(FormalRunErrorCode.ARTIFACT_CONSISTENCY_ERROR, "summary status length mismatch")
    expected_formal = (
        summary.get("attempted_replicates", 0) >= FORMAL_REPLICATE_TARGET
        and summary.get("failed_replicates") == 0
    )
    if summary.get("formal_ci_valid") != expected_formal:
        _error(FormalRunErrorCode.ARTIFACT_CONSISTENCY_ERROR, "formal CI gate does not match summary")
    configured_attempts = manifest.analysis_config.get("bootstrap", {}).get("replicate_count")
    if configured_attempts != summary.get("attempted_replicates"):
        _error(FormalRunErrorCode.ARTIFACT_CONSISTENCY_ERROR, "summary attempt count differs from manifest config")
    with np.load(directory / "bootstrap_scores.npz") as scores, np.load(directory / "bootstrap_ranks.npz") as ranks, np.load(directory / "bootstrap_tie_parameter.npz") as ties:
        shapes = {
            "bootstrap_scores.npz": list(scores["scores"].shape),
            "bootstrap_ranks.npz": list(ranks["ranks"].shape),
            "bootstrap_tie_parameter.npz": list(ties["tie_parameter"].shape),
        }
    if shapes != summary.get("matrix_shapes"):
        _error(FormalRunErrorCode.ARTIFACT_CONSISTENCY_ERROR, "matrix shape does not match summary")
    attempted_replicates = summary.get("attempted_replicates")
    model_count = len(summary.get("model_ids", []))
    expected_shapes = {
        "bootstrap_scores.npz": [attempted_replicates, model_count],
        "bootstrap_ranks.npz": [attempted_replicates, model_count],
        "bootstrap_tie_parameter.npz": [attempted_replicates],
    }
    if shapes != expected_shapes:
        _error(FormalRunErrorCode.ARTIFACT_CONSISTENCY_ERROR, "matrix shape does not match bootstrap identity")
    return ArtifactVerification(ok=True, run_id=manifest.run_id, files_checked=tuple(sorted(files)))


def execute_formal_run(
    source_path: str | Path,
    config: FormalRunConfig,
    *,
    repo_root: str | Path = ".",
    git_state: Mapping[str, str] | None = None,
    loader: Callable[[Path], pd.DataFrame] | None = None,
) -> Path:
    """Execute a configured run; formal mode is gated but never implicit."""
    preflight = preflight_formal_run(source_path, config, repo_root=repo_root, git_state=git_state)
    if config.execution_mode == "preflight":
        _error(FormalRunErrorCode.INVALID_FORMAL_CONFIG, "preflight mode cannot execute analysis")
    source = Path(source_path).resolve()
    raw = (loader or pd.read_parquet)(source)
    canonical = canonicalize_battles(raw, provenance=config.source_provenance)
    view = _population_view(config)
    base_spec = BASE_RESEARCH if view is not None else _population_spec(config.population_id)
    population = apply_population(canonical, base_spec)
    if view is not None:
        population = apply_population_view(population, view).population
    expected_population_version = POPULATION_VIEW_SCHEMA_VERSION if view is not None else POPULATION_SPEC_SCHEMA_VERSION
    if population.spec.population_spec_version != expected_population_version:
        _error(FormalRunErrorCode.UNKNOWN_POPULATION, "population schema version mismatch")
    point = fit_preference(population, config.estimator_config)
    bootstrap = run_bootstrap(population, config.bootstrap_config)
    return write_research_artifacts(Path(config.artifact_root).resolve() / preflight.manifest.run_id, preflight.manifest, point, bootstrap)
