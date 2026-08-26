"""Read-only consumption of the frozen Phase 2 formal evidence bundle."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import io
import json
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any, Mapping

import numpy as np

from src.formal_run import verify_research_artifacts
from src.run_manifest import RunManifest


class FrozenResultsError(ValueError):
    """Raised when an artifact is not an accepted frozen Phase 2 input."""


@dataclass(frozen=True)
class FrozenSourceSpec:
    dataset: str
    revision: str
    split: str
    file: str
    file_sha256: str
    snapshot_id: str
    canonical_schema_version: int = 2


@dataclass(frozen=True)
class FrozenRunSpec:
    analysis: str
    run_id: str
    artifact_manifest_sha256: str
    artifact_manifest_size: int
    seed: int
    git_commit: str
    population_id: str
    population_spec_version: int
    estimator: str
    outcome_policy: str
    resampling_unit: str
    population_view: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class FrozenReviewSpec:
    relative_path: str
    byte_size: int
    sha256: str
    schema_version: int = 1
    review_type: str = "read_only_comparative_review"


@dataclass(frozen=True)
class FrozenRunResult:
    """Immutable parsed representation of one verified frozen run."""

    spec: FrozenRunSpec
    manifest: Mapping[str, Any]
    point_estimate: Mapping[str, Any]
    bootstrap_summary: Mapping[str, Any]
    replicate_status: Mapping[str, Any]
    bootstrap_scores: np.ndarray
    bootstrap_ranks: np.ndarray
    bootstrap_tie_parameter: np.ndarray


@dataclass(frozen=True)
class FrozenResearchBundle:
    """The closed-world nine-run bundle plus its separate review artifact."""

    runs: tuple[FrozenRunResult, ...]
    comparative_review: Mapping[str, Any]


FROZEN_SOURCE = FrozenSourceSpec(
    dataset="lmsys/chatbot_arena_conversations",
    revision="1b6335d42a1d2c7e34870c905d03ab964f7f2bd8",
    split="train",
    file="data/train-00000-of-00001-cced8514c7ed782a.parquet",
    file_sha256="3726a6352e9bfc34e206460646f6e5e99bb837751966a671ddd30c7f64e5b06e",
    snapshot_id="2f8937a5f46ea4c3ed4ac7d59a5e51a6b3fb9bae79918b1050c6420b34ce1fa4",
)


def _freeze_value(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({str(key): _freeze_value(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze_value(item) for item in value)
    return value


def _run(
    analysis: str,
    run_id: str,
    artifact_manifest_sha256: str,
    seed: int,
    git_commit: str,
    population_id: str,
    population_spec_version: int,
    estimator: str,
    outcome_policy: str,
    resampling_unit: str,
    population_view: Mapping[str, Any] | None = None,
    artifact_manifest_size: int = 955,
) -> FrozenRunSpec:
    return FrozenRunSpec(
        analysis=analysis,
        run_id=run_id,
        artifact_manifest_sha256=artifact_manifest_sha256,
        artifact_manifest_size=artifact_manifest_size,
        seed=seed,
        git_commit=git_commit,
        population_id=population_id,
        population_spec_version=population_spec_version,
        estimator=estimator,
        outcome_policy=outcome_policy,
        resampling_unit=resampling_unit,
        population_view=_freeze_value(population_view) if population_view is not None else None,
    )


FROZEN_RUNS: tuple[FrozenRunSpec, ...] = (
    _run("Primary", "9c1fd5abbe8681db45b535e5368c806caad8d8297914c7b86a598112900f2689", "d5ac78a510cfabffc7b72b17b033771e8e7664eca3946061b42f8bf3442f4748", 15832207067816131242, "2dad21a4816931b0dddf4ae77282ffde1c713512", "base_research", 2, "davidson", "ordinary_tie_only", "judge_cluster"),
    _run("S1", "fa59994fb1f9de6a093162858bda584f6241c4a42314f0b027e57e2ff04d33e7", "eba2b6019be6b9b592d0a6433f17f469127723cb2d32a82679d0f5a38741119d", 15918316334149081368, "2d268c753478bc695b4f516fd70c738460c683b9", "base_research", 2, "davidson_coalesced_ties", "all_ties_coalesced", "judge_cluster"),
    _run("S2", "3babe007af583d3f8a6b4e25731828a77dd6e91d1f1110c618f82aee531d49d3", "412ac1a37074279f446c1d1a3ccbdb6f5d5aaf099254e52e71aa70e93a14ef47", 17623742310410676408, "2d268c753478bc695b4f516fd70c738460c683b9", "base_research", 2, "bradley_terry_decisive", "decisive_only", "judge_cluster", artifact_manifest_size=953),
    _run("S3", "3c62408ca810a5aaa34a3c237333156b8f62ebeb7e1d94f4316264f898b3e2cf", "b7fcf100ccf88fbe33f54314e7b1639791663473138bb05f4493b2970e0707fb", 2232815072757272902, "2d268c753478bc695b4f516fd70c738460c683b9", "base_research", 2, "davidson", "ordinary_tie_only", "battle_row"),
    _run("S4", "33b992df5e34b50d69218931bbcbadeee9db8658bd0b697d785cc909e3bb7d1f", "a923b1a8d856a0d11df35d41e42aa988a257000a5cb91d0cf384e7aca82cf9ee", 10795549338136829013, "241a6db67686def7a777c00704d997e281eab1a9", "base_research_no_repeated_qid", 1, "davidson", "ordinary_tie_only", "judge_cluster", {"group_policy": "exclude_all_rows_when_count_gt_1", "missing_policy": "retain_not_grouped", "question_id_field": "question_id_raw", "view_type": "exclude_repeated_question_groups"}),
    _run("S5-ge10", "60c314ba7c6453b8227db0be16a73963df0bda1e8321cd1085ae698549d6a466", "386bcee5ab5014419f7ef988890e13148c144cb7261f6e48ea8072401fbb9ded", 22049035408235882, "241a6db67686def7a777c00704d997e281eab1a9", "base_research_pair_support_ge10", 1, "davidson", "ordinary_tie_only", "judge_cluster", {"pair_definition": "canonical_unordered_model_pair", "support_count_stage": "before_estimator_outcome_filter", "support_measure": "eligible_battle_count", "support_population": "base_research", "threshold": 10, "threshold_operator": ">=", "view_type": "unordered_pair_support_threshold"}),
    _run("S5-ge20", "29a6ad3a3e401210de5a0ac1ad915e92d86bdcd6d954223dbb73fcf2e6f5ab7f", "5f8c6bd0111f64fa1498e654bfd4ac25d01b011370d00918e475c5ef6c016853", 5611320067224646494, "241a6db67686def7a777c00704d997e281eab1a9", "base_research_pair_support_ge20", 1, "davidson", "ordinary_tie_only", "judge_cluster", {"pair_definition": "canonical_unordered_model_pair", "support_count_stage": "before_estimator_outcome_filter", "support_measure": "eligible_battle_count", "support_population": "base_research", "threshold": 20, "threshold_operator": ">=", "view_type": "unordered_pair_support_threshold"}),
    _run("S5-ge50", "da1dbcf8f4a55403f1df8e8cd4ada2b903b93431486ce337849f116f2aadc7e2", "e123551f9f203893618deb5270f949ce96b9755a1f7f807c442f71af146e702f", 6822823098261160380, "241a6db67686def7a777c00704d997e281eab1a9", "base_research_pair_support_ge50", 1, "davidson", "ordinary_tie_only", "judge_cluster", {"pair_definition": "canonical_unordered_model_pair", "support_count_stage": "before_estimator_outcome_filter", "support_measure": "eligible_battle_count", "support_population": "base_research", "threshold": 50, "threshold_operator": ">=", "view_type": "unordered_pair_support_threshold"}),
    _run("S6-English", "8dba0d09c93abafe6c448a3ddb8ee22671792208e85b378f5c1b2328ee52624d", "ebe4d56606c075d61fcba37b81c928735d809e6e381a1220f622162cc9949623", 3148167322047722507, "241a6db67686def7a777c00704d997e281eab1a9", "base_research_language_en", 1, "davidson", "ordinary_tie_only", "judge_cluster", {"language_field": "language_canonical", "language_value": "English", "view_type": "language_exact_match"}),
)
FROZEN_RUN_REGISTRY: Mapping[str, FrozenRunSpec] = MappingProxyType({spec.run_id: spec for spec in FROZEN_RUNS})
FROZEN_REVIEW = FrozenReviewSpec(
    relative_path="comparative_review/review.json",
    byte_size=89996,
    sha256="452192dabbb8e8ad428a023ab8bb78052688965473a2736c5be352d021f26ffa",
)

_MANIFEST_KEYS = frozenset({"analysis_config", "canonical_schema_version", "created_by", "git_branch", "git_commit", "manifest_schema_version", "package_versions", "population_id", "population_spec_version", "python_version", "run_id", "source_dataset", "source_file", "source_file_sha256", "source_revision", "source_snapshot_id", "source_split"})
_POINT_KEYS = frozenset({"converged", "derived_rank", "estimator_config", "estimator_model_count", "estimator_name", "estimator_version", "excluded_outcome_counts", "graph_component_count", "graph_edge_count", "graph_node_count", "identifiability_constraint", "iterations", "latent_scores", "likelihood_battle_count", "likelihood_outcome_counts", "model_ids", "objective", "optimizer_name", "outcome_policy", "population_eligible_battle_count", "population_id", "population_model_count", "population_outcome_counts", "population_spec_version", "tie_parameter", "warnings"})
_SUMMARY_KEYS = frozenset({"artifact_schema_version", "attempted_replicates", "failed_replicates", "failure_counts", "formal_ci_valid", "formal_replicate_target_met", "matrix_shapes", "model_ids", "pairwise_stability", "rank_summary", "replicate_status", "run_id", "score_intervals", "successful_replicates", "tie_parameter_interval", "warnings"})
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant: {value}")


def _no_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _read_json_bytes(data: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=_no_duplicate_pairs, parse_constant=_reject_constant)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise FrozenResultsError(f"{label} is not valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise FrozenResultsError(f"{label} must contain a JSON object")
    return value


def _exact_keys(value: Mapping[str, Any], expected: frozenset[str], label: str) -> None:
    if set(value) != set(expected):
        raise FrozenResultsError(f"{label} keys do not match schema")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _freeze(value: Any) -> Any:
    """Recursively freeze parsed JSON so the E1 bundle stays read-only."""
    return _freeze_value(value)


def _read_snapshot(path: Path, label: str) -> bytes:
    """Read one ordinary file once; all trust checks consume these bytes."""
    if path.is_symlink() or not path.is_file():
        raise FrozenResultsError(f"{label} is missing or is not an ordinary file")
    try:
        return path.read_bytes()
    except (OSError, IOError) as exc:
        raise FrozenResultsError(f"unable to read {label}: {exc}") from exc


def _verify_snapshot(data: bytes, expected_size: int, expected_sha256: str, label: str) -> None:
    if len(data) != expected_size or hashlib.sha256(data).hexdigest() != expected_sha256:
        raise FrozenResultsError(f"{label} digest or size mismatch")


def _expected_analysis_config(spec: FrozenRunSpec) -> dict[str, Any]:
    estimator = {
        "estimator": spec.estimator,
        "estimator_version": 1,
        "identifiability": "sum_to_zero",
        "max_iterations": 1000,
        "optimizer": "L-BFGS-B",
        "outcome_policy": spec.outcome_policy,
        "regularization": None,
        "tolerance": 1e-09,
    }
    config: dict[str, Any] = {
        "bootstrap": {
            "bit_generator": "PCG64",
            "ci_method": "percentile",
            "confidence_level": 0.95,
            "estimator": estimator.copy(),
            "failure_policy": "fixed_attempts_zero_failure_formal_gate",
            "replicate_count": 2000,
            "resampling_unit": spec.resampling_unit,
            "seed": spec.seed,
        },
        "estimator": estimator,
        "formal_run": {"artifact_schema_version": 1, "execution_mode": "formal", "require_published": True},
    }
    if spec.population_view is not None:
        config["population_view"] = {
            "base_population": {"population_id": "base_research", "population_spec_version": 2},
            "population_id": spec.population_id,
            "population_view_schema_version": 1,
            "view": spec.population_view,
        }
    return config


def _validate_manifest(manifest: dict[str, Any], spec: FrozenRunSpec) -> None:
    _exact_keys(manifest, _MANIFEST_KEYS, "manifest.json")
    try:
        RunManifest.from_dict(manifest)
    except (KeyError, TypeError, ValueError) as exc:
        raise FrozenResultsError(f"manifest identity validation failed: {exc}") from exc
    for key in ("created_by", "git_branch", "git_commit", "python_version", "run_id", "source_dataset", "source_file", "source_file_sha256", "source_revision", "source_snapshot_id", "source_split", "population_id"):
        if not isinstance(manifest[key], str):
            raise FrozenResultsError(f"manifest field {key} must be a string")
    if manifest["manifest_schema_version"] != 1 or manifest["canonical_schema_version"] != FROZEN_SOURCE.canonical_schema_version:
        raise FrozenResultsError("manifest schema version is not frozen")
    expected_source = {"source_dataset": FROZEN_SOURCE.dataset, "source_revision": FROZEN_SOURCE.revision, "source_split": FROZEN_SOURCE.split, "source_file": FROZEN_SOURCE.file, "source_file_sha256": FROZEN_SOURCE.file_sha256, "source_snapshot_id": FROZEN_SOURCE.snapshot_id}
    for key, expected in expected_source.items():
        if manifest[key] != expected:
            raise FrozenResultsError(f"manifest E0 field {key} differs from frozen source")
    expected = {"run_id": spec.run_id, "git_branch": "main", "git_commit": spec.git_commit, "population_id": spec.population_id, "population_spec_version": spec.population_spec_version, "analysis_config": _expected_analysis_config(spec)}
    for key, value in expected.items():
        if manifest[key] != value:
            raise FrozenResultsError(f"manifest E1 field {key} differs from frozen registry")


def _validate_artifact_manifest(data: bytes, spec: FrozenRunSpec) -> dict[str, Any]:
    if len(data) != spec.artifact_manifest_size or hashlib.sha256(data).hexdigest() != spec.artifact_manifest_sha256:
        raise FrozenResultsError(f"artifact_manifest.json identity mismatch for {spec.analysis}")
    artifact = _read_json_bytes(data, "artifact_manifest.json")
    _exact_keys(artifact, frozenset({"artifact_schema_version", "files", "run_id"}), "artifact_manifest.json")
    if artifact["artifact_schema_version"] != 1 or artifact["run_id"] != spec.run_id or not isinstance(artifact["files"], dict):
        raise FrozenResultsError("artifact manifest identity/schema mismatch")
    expected_files = {"manifest.json", "point_estimate.json", "bootstrap_summary.json", "bootstrap_scores.npz", "bootstrap_ranks.npz", "bootstrap_tie_parameter.npz", "replicate_status.json"}
    if set(artifact["files"]) != expected_files:
        raise FrozenResultsError("artifact manifest file set mismatch")
    for name, record in artifact["files"].items():
        if not isinstance(record, dict) or set(record) != {"sha256", "size_bytes"} or not isinstance(record["size_bytes"], int) or record["size_bytes"] < 0 or not isinstance(record["sha256"], str) or not _SHA_RE.fullmatch(record["sha256"]):
            raise FrozenResultsError(f"artifact record is malformed: {name}")
    return artifact


def _validate_point(point: dict[str, Any], manifest: dict[str, Any], summary: dict[str, Any], spec: FrozenRunSpec) -> tuple[str, ...]:
    _exact_keys(point, _POINT_KEYS, "point_estimate.json")
    if point["population_id"] != spec.population_id or point["population_spec_version"] != spec.population_spec_version or point["estimator_config"] != manifest["analysis_config"]["estimator"] or point["estimator_name"] != spec.estimator or point["estimator_version"] != 1 or point["outcome_policy"] != spec.outcome_policy:
        raise FrozenResultsError("point estimate identity differs from frozen manifest")
    model_ids = point["model_ids"]
    if not isinstance(model_ids, list) or not model_ids or any(not isinstance(item, str) or not item for item in model_ids) or len(set(model_ids)) != len(model_ids):
        raise FrozenResultsError("point model_ids are invalid")
    n = len(model_ids)
    ranks = point["derived_rank"]
    scores = point["latent_scores"]
    if not isinstance(ranks, list) or len(ranks) != n or any(isinstance(x, bool) or not isinstance(x, int) for x in ranks) or set(ranks) != set(range(1, n + 1)):
        raise FrozenResultsError("point derived_rank is not a 1..N permutation")
    if not isinstance(scores, list) or len(scores) != n or any(isinstance(x, bool) or not isinstance(x, (int, float)) or not np.isfinite(x) for x in scores):
        raise FrozenResultsError("point latent_scores are invalid")
    if point["tie_parameter"] is not None and (isinstance(point["tie_parameter"], bool) or not isinstance(point["tie_parameter"], (int, float)) or not np.isfinite(point["tie_parameter"])):
        raise FrozenResultsError("point tie_parameter is invalid")
    if point["estimator_model_count"] != n or point["population_model_count"] != n or point["model_ids"] != summary["model_ids"]:
        raise FrozenResultsError("point and summary model universes differ")
    return tuple(model_ids)


def _validate_summary(summary: dict[str, Any], status: dict[str, Any], model_ids: tuple[str, ...], spec: FrozenRunSpec) -> None:
    _exact_keys(summary, _SUMMARY_KEYS, "bootstrap_summary.json")
    if summary["run_id"] != spec.run_id or summary["model_ids"] != list(model_ids) or summary["attempted_replicates"] != 2000 or summary["successful_replicates"] != 2000 or summary["failed_replicates"] != 0 or summary["formal_replicate_target_met"] is not True or summary["formal_ci_valid"] is not True or summary["failure_counts"] != {}:
        raise FrozenResultsError("bootstrap summary does not satisfy frozen formal semantics")
    if status.get("run_id") != spec.run_id or status.get("statuses") != summary["replicate_status"] or not isinstance(status.get("statuses"), list) or len(status["statuses"]) != 2000 or any(item != "SUCCESS" for item in status["statuses"]):
        raise FrozenResultsError("replicate status is inconsistent with the frozen formal gate")
    shapes = summary["matrix_shapes"]
    expected_shapes = {"bootstrap_scores.npz": [2000, len(model_ids)], "bootstrap_ranks.npz": [2000, len(model_ids)], "bootstrap_tie_parameter.npz": [2000]}
    if shapes != expected_shapes:
        raise FrozenResultsError("summary matrix shapes are not frozen")
    for key in ("score_intervals", "rank_summary", "pairwise_stability"):
        if not isinstance(summary[key], dict):
            raise FrozenResultsError(f"summary field {key} must be an object")
    if set(summary["score_intervals"]) != set(model_ids) or set(summary["rank_summary"]) != set(model_ids):
        raise FrozenResultsError("summary model keys are incomplete")
    if spec.estimator == "bradley_terry_decisive":
        if summary["tie_parameter_interval"] is not None:
            raise FrozenResultsError("Bradley-Terry tie interval must be null")
    elif not isinstance(summary["tie_parameter_interval"], list) or len(summary["tie_parameter_interval"]) != 2 or any(not isinstance(x, (int, float)) or not np.isfinite(x) for x in summary["tie_parameter_interval"]):
        raise FrozenResultsError("tie parameter interval is invalid")


def _read_npz(data: bytes, key: str, shape: tuple[int, ...], label: str) -> np.ndarray:
    try:
        with np.load(io.BytesIO(data), allow_pickle=False) as archive:
            if set(archive.files) != {key}:
                raise FrozenResultsError(f"{label} keys do not match frozen schema")
            array = np.asarray(archive[key])
    except (OSError, ValueError, KeyError) as exc:
        if isinstance(exc, FrozenResultsError):
            raise
        raise FrozenResultsError(f"{label} is not a valid NPZ: {exc}") from exc
    if array.shape != shape or array.dtype != np.dtype("float64"):
        raise FrozenResultsError(f"{label} shape or dtype differs from frozen schema")
    return array.copy()


def _immutable_array(array: np.ndarray) -> np.ndarray:
    """Use immutable bytes as the ndarray backing store."""
    immutable = bytes(array.tobytes(order="C"))
    return np.frombuffer(immutable, dtype=array.dtype, count=array.size).reshape(array.shape)


def _validate_arrays(scores: np.ndarray, ranks: np.ndarray, ties: np.ndarray, model_count: int, spec: FrozenRunSpec) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if not np.isfinite(scores).all() or (spec.estimator != "bradley_terry_decisive" and not np.isfinite(ties).all()) or (spec.estimator == "bradley_terry_decisive" and not np.isnan(ties).all()):
        raise FrozenResultsError("bootstrap arrays contain invalid finite values")
    if not np.isfinite(ranks).all() or not np.equal(ranks, np.floor(ranks)).all():
        raise FrozenResultsError("bootstrap ranks are not integral finite values")
    rank_int = ranks.astype(np.int64)
    expected = set(range(1, model_count + 1))
    if any(set(row.tolist()) != expected for row in rank_int):
        raise FrozenResultsError("each bootstrap rank replicate must be a 1..N permutation")
    scores = _immutable_array(scores)
    rank_int = _immutable_array(rank_int)
    ties = _immutable_array(ties)
    return scores, rank_int, ties


def load_frozen_formal_run(run_id: str, artifact_root: str | Path = "outputs/research") -> FrozenRunResult:
    """Load one run from the closed frozen registry without discovery or writes."""
    spec = FROZEN_RUN_REGISTRY.get(run_id)
    if spec is None:
        raise FrozenResultsError(f"unknown frozen run_id: {run_id}")
    root = Path(artifact_root).resolve()
    directory = (root / spec.run_id).resolve()
    if directory.parent != root or directory.name != spec.run_id or not directory.is_dir():
        raise FrozenResultsError(f"frozen run directory is missing or outside artifact root: {spec.run_id}")
    artifact_manifest_data = _read_snapshot(directory / "artifact_manifest.json", "artifact_manifest.json")
    artifact_manifest = _validate_artifact_manifest(artifact_manifest_data, spec)
    snapshots: dict[str, bytes] = {"artifact_manifest.json": artifact_manifest_data}
    for name, record in artifact_manifest["files"].items():
        path = directory / name
        if path.resolve().parent != directory or path.resolve() != path or path.is_symlink():
            raise FrozenResultsError(f"artifact path escapes run directory: {name}")
        data = _read_snapshot(path, name)
        _verify_snapshot(data, record["size_bytes"], record["sha256"], name)
        snapshots[name] = data
    try:
        verify_research_artifacts(directory)
    except Exception as exc:
        raise FrozenResultsError(f"existing artifact verifier rejected {spec.analysis}: {exc}") from exc
    manifest = _read_json_bytes(snapshots["manifest.json"], "manifest.json")
    point = _read_json_bytes(snapshots["point_estimate.json"], "point_estimate.json")
    summary = _read_json_bytes(snapshots["bootstrap_summary.json"], "bootstrap_summary.json")
    status = _read_json_bytes(snapshots["replicate_status.json"], "replicate_status.json")
    _validate_manifest(manifest, spec)
    model_ids = _validate_point(point, manifest, summary, spec)
    _validate_summary(summary, status, model_ids, spec)
    scores = _read_npz(snapshots["bootstrap_scores.npz"], "scores", (2000, len(model_ids)), "bootstrap_scores.npz")
    ranks = _read_npz(snapshots["bootstrap_ranks.npz"], "ranks", (2000, len(model_ids)), "bootstrap_ranks.npz")
    ties = _read_npz(snapshots["bootstrap_tie_parameter.npz"], "tie_parameter", (2000,), "bootstrap_tie_parameter.npz")
    scores, ranks, ties = _validate_arrays(scores, ranks, ties, len(model_ids), spec)
    return FrozenRunResult(spec, _freeze(manifest), _freeze(point), _freeze(summary), _freeze(status), scores, ranks, ties)


def _load_review(root: Path, run_ids: set[str]) -> Mapping[str, Any]:
    path = root / FROZEN_REVIEW.relative_path
    review_dir = root / "comparative_review"
    if root not in review_dir.resolve().parents or review_dir.is_symlink() or not review_dir.is_dir() or path.is_symlink() or not path.is_file() or path.resolve() != review_dir.resolve() / "review.json":
        raise FrozenResultsError("comparative review path is missing or outside artifact root")
    data = _read_snapshot(path, "comparative review")
    _verify_snapshot(data, FROZEN_REVIEW.byte_size, FROZEN_REVIEW.sha256, "comparative review")
    review = _read_json_bytes(data, "comparative review")
    if review.get("review_schema_version") != FROZEN_REVIEW.schema_version or review.get("review_type") != FROZEN_REVIEW.review_type:
        raise FrozenResultsError("comparative review schema/type mismatch")
    inventory = review.get("artifact_inventory")
    if not isinstance(inventory, list) or len(inventory) != len(run_ids):
        raise FrozenResultsError("comparative review run inventory is incomplete")
    referenced = {item.get("run_id") for item in inventory if isinstance(item, dict)}
    if referenced != run_ids:
        raise FrozenResultsError("comparative review references unknown or missing runs")
    return _freeze(review)


def load_frozen_formal_research(artifact_root: str | Path = "outputs/research") -> FrozenResearchBundle:
    """Load exactly the nine frozen runs and their separate review artifact."""
    root = Path(artifact_root).resolve()
    if not root.is_dir():
        raise FrozenResultsError(f"artifact root does not exist: {root}")
    runs = tuple(load_frozen_formal_run(spec.run_id, root) for spec in FROZEN_RUNS)
    review = _load_review(root, {spec.run_id for spec in FROZEN_RUNS})
    return FrozenResearchBundle(runs=runs, comparative_review=review)
