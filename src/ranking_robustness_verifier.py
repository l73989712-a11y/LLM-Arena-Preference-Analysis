"""Independent verification of deterministic Phase 5 E2 artifact instances."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any

from src.formal_results import FROZEN_RUNS, FROZEN_SOURCE, FrozenResultsError, load_frozen_formal_research
from src.formal_verifier import (
    EXPECTED_BUNDLE_NAME,
    EXPECTED_BUNDLE_SCHEMA_VERSION,
    EXPECTED_PAYLOAD_INVENTORY_SHA256,
    FrozenBundleVerificationError,
    verify_frozen_bundle,
)
from src.ranking_robustness import (
    ARTIFACT_SCHEMA_VERSION,
    DERIVATION_CONTRACT_VERSION,
    FORMAL_TOP_K,
    METRIC_SCHEMA_VERSION,
    RANK_EQUALITY_TOLERANCE,
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
from src.ranking_robustness_artifacts import FORMAL_ARTIFACT_FILENAMES, METRIC_FILES


FORMAL_PRODUCER_GIT_SHA = "766fd10a0a22c1266a70b11c1581e8f607f10c07"
FORMAL_DERIVATION_SPEC_ID = "dc03cc925d2a85dc023542fc21f703abbb966dd4df5da36974c8ea061ece0be4"
FORMAL_ARTIFACT_INSTANCE_ID = "82239159eecc2067b7b89f9e13b9cf34d36497b8fdd7105e6babbcc2668e9a1e"

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
_MANIFEST_FIELDS = frozenset(
    {
        "artifact_schema_version",
        "derivation_contract_version",
        "metric_schema_version",
        "derivation_spec_id",
        "artifact_instance_id",
        "producer_git_sha",
        "source_snapshot_id",
        "e1_bundle",
        "ordered_run_ids",
        "primary_run_id",
        "top_k",
        "pairwise_ordering_tolerance",
        "e2_payload_inventory_sha256",
        "artifacts",
    }
)
_ENVELOPE_FIELDS = frozenset(
    {"artifact_schema_version", "metric_schema_version", "derivation_spec_id", "artifact_instance_id", "metric", "records"}
)
_PAYLOAD_FILENAMES = tuple(sorted(filename for _, filename in METRIC_FILES))


class RankingRobustnessVerificationError(ValueError):
    """Raised when an E2 instance is missing, malformed, tampered, or unauthorized."""


@dataclass(frozen=True)
class RankingRobustnessVerificationResult:
    artifact_instance_id: str
    derivation_spec_id: str
    producer_git_sha: str
    e2_payload_inventory_sha256: str
    artifact_count: int
    run_count: int
    model_count: int


def _fail(message: str) -> None:
    raise RankingRobustnessVerificationError(message)


def _strict_equal(expected: Any, actual: Any) -> bool:
    """Compare JSON values without bool/int or int/float coercion."""
    if type(expected) is not type(actual):
        return False
    if isinstance(expected, dict):
        return set(expected) == set(actual) and all(_strict_equal(expected[key], actual[key]) for key in expected)
    if isinstance(expected, list):
        return len(expected) == len(actual) and all(_strict_equal(left, right) for left, right in zip(expected, actual))
    return expected == actual


def _ordinary_root(value: str | Path) -> Path:
    try:
        requested = Path(os.path.abspath(os.fspath(Path(value).expanduser())))
    except (OSError, TypeError, ValueError) as exc:
        raise RankingRobustnessVerificationError(f"invalid artifact path: {exc}") from exc
    if requested.is_symlink() or not requested.is_dir():
        _fail("artifact instance root must be an ordinary directory")
    try:
        resolved = requested.resolve(strict=False)
    except OSError as exc:
        raise RankingRobustnessVerificationError(f"unable to normalize artifact path: {exc}") from exc
    if resolved != requested:
        _fail("artifact instance root must be an ordinary directory")
    return requested


def _read_canonical_json(path: Path) -> dict[str, Any]:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise RankingRobustnessVerificationError(f"unable to read {path.name}: {exc}") from exc
    if b"\r\n" in data or not data.endswith(b"\n") or data.endswith(b"\n\n"):
        _fail(f"{path.name} does not have exactly one final LF")
    body = data[:-1]
    if body.rstrip() != body:
        _fail(f"{path.name} has trailing whitespace")
    try:
        value = json.loads(body.decode("utf-8"), parse_constant=lambda value: _fail(f"{path.name} contains non-finite JSON constant {value}"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise RankingRobustnessVerificationError(f"{path.name} is not valid UTF-8 JSON: {exc}") from exc
    if not isinstance(value, dict):
        _fail(f"{path.name} must contain a JSON object")
    try:
        expected = canonical_json_bytes(value) + b"\n"
    except Exception as exc:
        if isinstance(exc, RankingRobustnessVerificationError):
            raise
        raise RankingRobustnessVerificationError(f"{path.name} is not canonically serializable: {exc}") from exc
    if data != expected:
        _fail(f"{path.name} is not canonical JSON")
    return value


def _frozen_payload() -> tuple[dict[str, Any], str, dict[str, Any], str]:
    derivation = build_derivation_spec_payload(
        source_snapshot_id=FROZEN_SOURCE.snapshot_id,
        e1_bundle={
            "bundle_name": EXPECTED_BUNDLE_NAME,
            "bundle_schema_version": EXPECTED_BUNDLE_SCHEMA_VERSION,
            "payload_inventory_sha256": EXPECTED_PAYLOAD_INVENTORY_SHA256,
        },
        ordered_run_ids=tuple(spec.run_id for spec in FROZEN_RUNS),
        primary_run_id=FROZEN_RUNS[0].run_id,
        top_k=FORMAL_TOP_K,
        pairwise_ordering_tolerance=RANK_EQUALITY_TOLERANCE,
    )
    derivation_id = compute_derivation_spec_id(derivation)
    instance = build_artifact_instance_payload(
        derivation_spec_id=derivation_id,
        producer_git_sha=FORMAL_PRODUCER_GIT_SHA,
        artifact_schema_version=ARTIFACT_SCHEMA_VERSION,
    )
    instance_id = compute_artifact_instance_id(instance)
    return derivation, derivation_id, instance, instance_id


def _attach_run_id(run_id: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"run_id": run_id, **dict(record)} for record in records]


def _expected_records(bundle: Any, ordered_run_ids: tuple[str, ...], model_ids: tuple[str, ...]) -> dict[str, list[dict[str, Any]]]:
    records: dict[str, list[dict[str, Any]]] = {name: [] for name, _ in METRIC_FILES}
    point_ranks: dict[str, tuple[int, ...]] = {}
    for run in bundle.runs:
        run_id = run.spec.run_id
        point_ranks[run_id] = tuple(run.point_estimate["derived_rank"])
        records["rank_distributions"].extend(_attach_run_id(run_id, derive_rank_distribution(model_ids, run.bootstrap_ranks)))
        records["top_k"].extend(_attach_run_id(run_id, derive_top_k_inclusion(model_ids, run.bootstrap_ranks)))
        records["pairwise_ordering"].extend(_attach_run_id(run_id, derive_pairwise_ordering(model_ids, run.bootstrap_scores)))
        records["rank_intervals"].extend(_attach_run_id(run_id, extract_rank_intervals(model_ids, run.bootstrap_summary["rank_summary"])))
    primary = bundle.runs[0]
    records["adjacent_reversals"] = derive_adjacent_rank_reversals(model_ids, primary.point_estimate["derived_rank"], primary.bootstrap_ranks)
    records["cross_specification"] = derive_cross_specification(
        ordered_run_ids,
        model_ids,
        point_ranks,
        ordered_run_ids[0],
    )
    return records


def _verify_manifest(manifest: Mapping[str, Any], derivation: Mapping[str, Any], derivation_id: str, instance: Mapping[str, Any], instance_id: str) -> None:
    if set(manifest) != _MANIFEST_FIELDS:
        _fail("manifest has an unexpected field set")
    expected = {
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "derivation_contract_version": DERIVATION_CONTRACT_VERSION,
        "metric_schema_version": METRIC_SCHEMA_VERSION,
        "derivation_spec_id": derivation_id,
        "artifact_instance_id": instance_id,
        "producer_git_sha": FORMAL_PRODUCER_GIT_SHA,
        "source_snapshot_id": FROZEN_SOURCE.snapshot_id,
        "e1_bundle": derivation["e1_bundle"],
        "ordered_run_ids": derivation["ordered_run_ids"],
        "primary_run_id": derivation["primary_run_id"],
        "top_k": list(FORMAL_TOP_K),
        "pairwise_ordering_tolerance": RANK_EQUALITY_TOLERANCE,
    }
    for key, value in expected.items():
        if not _strict_equal(value, manifest[key]):
            _fail(f"manifest field {key} differs from frozen authority")
    if not _strict_equal(manifest["derivation_spec_id"], compute_derivation_spec_id(derivation)):
        _fail("manifest derivation_spec_id does not match recomputed identity")
    if not _strict_equal(manifest["artifact_instance_id"], compute_artifact_instance_id(instance)):
        _fail("manifest artifact_instance_id does not match recomputed identity")
    if not _SHA256_RE.fullmatch(manifest["derivation_spec_id"]) or not _SHA256_RE.fullmatch(manifest["artifact_instance_id"]):
        _fail("manifest identities are not lowercase SHA-256 values")
    if not _SHA1_RE.fullmatch(manifest["producer_git_sha"]):
        _fail("manifest producer_git_sha is not a lowercase Git SHA-1")


def _verify_inventory(root: Path, manifest: Mapping[str, Any]) -> str:
    declared = manifest["artifacts"]
    if not isinstance(declared, list) or len(declared) != len(_PAYLOAD_FILENAMES) or any(not isinstance(entry, dict) for entry in declared):
        _fail("manifest payload inventory does not contain the exact six sorted metric files")
    if [entry.get("path") for entry in declared] != list(_PAYLOAD_FILENAMES):
        _fail("manifest payload inventory does not contain the exact six sorted metric files")
    actual: list[dict[str, Any]] = []
    for entry in declared:
        if not isinstance(entry, dict) or set(entry) != {"path", "size_bytes", "sha256"}:
            _fail("manifest payload inventory record is malformed")
        path_name = entry["path"]
        if not isinstance(path_name, str) or path_name not in _PAYLOAD_FILENAMES or not isinstance(entry["size_bytes"], int) or isinstance(entry["size_bytes"], bool) or entry["size_bytes"] < 0 or not isinstance(entry["sha256"], str) or _SHA256_RE.fullmatch(entry["sha256"]) is None:
            _fail("manifest payload inventory record has invalid identity fields")
        data = (root / path_name).read_bytes()
        observed = {"path": path_name, "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        if observed != entry:
            _fail(f"payload inventory mismatch for {path_name}")
        actual.append(observed)
    return hashlib.sha256(canonical_json_bytes(actual)).hexdigest()


def _verify_metrics(documents: Mapping[str, dict[str, Any]], expected: Mapping[str, list[dict[str, Any]]], derivation_id: str, instance_id: str) -> None:
    for metric_name, filename in METRIC_FILES:
        document = documents[filename]
        if set(document) != _ENVELOPE_FIELDS:
            _fail(f"{filename} envelope has an unexpected field set")
        if not _strict_equal(document["artifact_schema_version"], ARTIFACT_SCHEMA_VERSION) or not _strict_equal(document["metric_schema_version"], METRIC_SCHEMA_VERSION) or not _strict_equal(document["derivation_spec_id"], derivation_id) or not _strict_equal(document["artifact_instance_id"], instance_id) or not _strict_equal(document["metric"], metric_name) or not isinstance(document["records"], list):
            _fail(f"{filename} envelope identity/schema differs from frozen authority")
        if not _strict_equal(document["records"], expected[metric_name]):
            _fail(f"{filename} records differ from independently recomputed E2")


def verify_ranking_robustness_artifact(
    artifact_instance_root: str | Path,
    *,
    _verifier: Callable[[], Any] | None = None,
    _loader: Callable[[], Any] | None = None,
) -> RankingRobustnessVerificationResult:
    """Verify one complete E2 instance against immutable frozen E1 evidence."""
    root = _ordinary_root(artifact_instance_root)
    children = list(root.iterdir())
    if any(path.is_symlink() or path.is_dir() or not path.is_file() for path in children):
        _fail("artifact instance contains a non-ordinary entry")
    if {path.name for path in children} != set(FORMAL_ARTIFACT_FILENAMES):
        _fail("artifact instance must contain exactly the seven formal files")
    documents = {path.name: _read_canonical_json(path) for path in children}
    manifest = documents["manifest.json"]
    derivation, derivation_id, instance, instance_id = _frozen_payload()
    if derivation_id != FORMAL_DERIVATION_SPEC_ID or instance_id != FORMAL_ARTIFACT_INSTANCE_ID:
        _fail("repository frozen identity constants are inconsistent")
    _verify_manifest(manifest, derivation, derivation_id, instance, instance_id)
    inventory_hash = _verify_inventory(root, manifest)
    if manifest["e2_payload_inventory_sha256"] != inventory_hash:
        _fail("manifest e2_payload_inventory_sha256 does not match recomputed inventory")
    verifier = verify_frozen_bundle if _verifier is None else _verifier
    loader = load_frozen_formal_research if _loader is None else _loader
    try:
        verifier()
    except FrozenBundleVerificationError as exc:
        raise RankingRobustnessVerificationError(f"frozen E1 verification failed: {exc}") from exc
    try:
        bundle = loader()
    except FrozenResultsError as exc:
        raise RankingRobustnessVerificationError(f"frozen E1 loading failed: {exc}") from exc
    ordered_run_ids = tuple(spec.run_id for spec in FROZEN_RUNS)
    if tuple(run.spec.run_id for run in bundle.runs) != ordered_run_ids or len(bundle.runs) != 9:
        _fail("loaded E1 run registry differs from FROZEN_RUNS")
    model_ids = tuple(bundle.runs[0].point_estimate["model_ids"])
    if len(model_ids) != 20 or len(set(model_ids)) != 20:
        _fail("loaded E1 model registry is not the frozen 20-model universe")
    expected = _expected_records(bundle, ordered_run_ids, model_ids)
    expected_counts = {"rank_distributions": 3600, "top_k": 540, "pairwise_ordering": 1710, "rank_intervals": 180, "adjacent_reversals": 19, "cross_specification": 20}
    if any(len(expected[name]) != count for name, count in expected_counts.items()):
        _fail("independently recomputed E2 collection count differs from frozen contract")
    _verify_metrics(documents, expected, derivation_id, instance_id)
    return RankingRobustnessVerificationResult(instance_id, derivation_id, FORMAL_PRODUCER_GIT_SHA, inventory_hash, 7, 9, 20)


__all__ = ["FORMAL_ARTIFACT_INSTANCE_ID", "FORMAL_DERIVATION_SPEC_ID", "FORMAL_PRODUCER_GIT_SHA", "RankingRobustnessVerificationError", "RankingRobustnessVerificationResult", "verify_ranking_robustness_artifact"]
