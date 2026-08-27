"""Canonical read-only verification of the published frozen formal bundle."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

from src.formal_results import (
    DEFAULT_FROZEN_ARTIFACT_ROOT,
    FROZEN_REVIEW,
    FROZEN_RUNS,
    FROZEN_SOURCE,
    FrozenResultsError,
    load_frozen_formal_research,
)
from src.formal_run import ARTIFACT_FILES


EXPECTED_BUNDLE_NAME = "formal-research-v1"
EXPECTED_BUNDLE_SCHEMA_VERSION = 1
EXPECTED_PAYLOAD_FILE_COUNT = 73
EXPECTED_PAYLOAD_TOTAL_BYTES = 3_626_761
EXPECTED_PAYLOAD_INVENTORY_SHA256 = "392066c7a23408e97f0f2bcd3e2a530b167e596c9b382d999d959ba49abb7eb6"

_MANIFEST_KEYS = frozenset(
    {
        "bundle_name",
        "bundle_schema_version",
        "expected_analysis_inventory",
        "files",
        "payload_file_count",
        "payload_inventory_canonicalization",
        "payload_inventory_sha256",
        "payload_root",
        "payload_total_bytes",
        "producing_repository_identity",
        "source_identity",
    }
)
_MANIFEST_FILE_KEYS = frozenset(
    {"relative_path", "artifact_role", "run_id", "analysis_label", "byte_size", "sha256"}
)
_ROLE_BY_NAME = {
    "artifact_manifest.json": "run_artifact_manifest",
    "manifest.json": "run_provenance_manifest",
    "point_estimate.json": "point_estimate",
    "bootstrap_summary.json": "bootstrap_summary",
    "bootstrap_scores.npz": "bootstrap_score_replicates",
    "bootstrap_ranks.npz": "bootstrap_rank_replicates",
    "bootstrap_tie_parameter.npz": "bootstrap_tie_parameter_replicates",
    "replicate_status.json": "replicate_status",
}
_EXPECTED_CANONICALIZATION = {
    "algorithm": "sha256",
    "encoding": "UTF-8",
    "hashed_fields": ["relative_path", "artifact_role", "run_id", "analysis_label", "byte_size", "sha256"],
    "json": "sorted keys, compact separators, ensure_ascii=true",
    "ordering": "ascending relative_path",
}
_EXPECTED_PRODUCING_REPOSITORY_IDENTITY = {
    "repository": "https://github.com/l73989712-a11y/LLM-Arena-Preference-Analysis",
    "formal_evidence_status": "Phase 2 frozen evidence consumed by Phase 3 presentation/report/explorer",
    "frozen_run_git_shas": None,
}


@dataclass(frozen=True)
class VerificationResult:
    """Small immutable summary of one successful bundle verification."""

    bundle_name: str
    payload_file_count: int
    payload_total_bytes: int
    payload_inventory_sha256: str
    source_snapshot_id: str
    verified_run_count: int
    comparative_review_verified: bool
    semantic_validation_passed: bool


class FrozenBundleVerificationError(ValueError):
    """An expected, fail-closed frozen-bundle verification failure."""

    def __init__(self, stage: str, reason: str) -> None:
        self.stage = stage
        self.reason = reason
        super().__init__(f"{stage}: {reason}")


def _fail(stage: str, reason: str) -> None:
    raise FrozenBundleVerificationError(stage, reason)


def _strict_equal(expected: Any, actual: Any) -> bool:
    """Compare JSON values without Python's bool/int equality coercion."""
    if type(expected) is not type(actual):
        return False
    if isinstance(expected, dict):
        return set(expected) == set(actual) and all(_strict_equal(expected[key], actual[key]) for key in expected)
    if isinstance(expected, list):
        return len(expected) == len(actual) and all(_strict_equal(left, right) for left, right in zip(expected, actual))
    return expected == actual


def _no_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_bytes().decode("utf-8"),
            object_pairs_hook=_no_duplicate_pairs,
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"non-standard JSON constant: {value}")),
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        _fail(label, f"malformed JSON: {exc}")
    if not isinstance(value, dict):
        _fail(label, "expected a JSON object")
    return value


def _ordinary_file(path: Path, label: str) -> None:
    try:
        if path.is_symlink() or not path.is_file() or path.resolve() != path:
            _fail("structure", f"{label} is not an ordinary file")
    except OSError as exc:
        _fail("structure", f"unable to inspect {label}: {exc}")


def _ordinary_directory(path: Path, label: str) -> None:
    try:
        if path.is_symlink() or not path.is_dir() or path.resolve() != path:
            _fail("structure", f"{label} is not an ordinary directory")
    except OSError as exc:
        _fail("structure", f"unable to inspect {label}: {exc}")


def _source_identity() -> dict[str, Any]:
    return {
        "canonical_schema_version": FROZEN_SOURCE.canonical_schema_version,
        "dataset": FROZEN_SOURCE.dataset,
        "parquet_file": FROZEN_SOURCE.file,
        "revision": FROZEN_SOURCE.revision,
        "source_file_sha256": FROZEN_SOURCE.file_sha256,
        "source_snapshot_id": FROZEN_SOURCE.snapshot_id,
        "split": FROZEN_SOURCE.split,
    }


def _analysis_inventory() -> list[dict[str, Any]]:
    return [
        {
            "analysis": spec.analysis,
            "git_sha": spec.git_commit,
            "population_id": spec.population_id,
            "run_id": spec.run_id,
            "valid": True,
        }
        for spec in FROZEN_RUNS
    ]


def _producing_repository_identity() -> dict[str, Any]:
    return {
        **_EXPECTED_PRODUCING_REPOSITORY_IDENTITY,
        "frozen_run_git_shas": sorted({spec.git_commit for spec in FROZEN_RUNS}),
    }


def _expected_payload_paths() -> set[str]:
    paths = {
        f"{spec.run_id}/{name}"
        for spec in FROZEN_RUNS
        for name in ARTIFACT_FILES
    }
    paths.add(FROZEN_REVIEW.relative_path)
    return paths


def _enumerate_payload(payload_root: Path) -> list[Path]:
    expected_dirs = {spec.run_id for spec in FROZEN_RUNS} | {"comparative_review"}
    actual: list[Path] = []
    for current, directories, files in os.walk(payload_root, topdown=True, followlinks=False):
        current_path = Path(current)
        relative_dir = current_path.relative_to(payload_root).as_posix() if current_path != payload_root else ""
        for name in list(directories):
            directory = current_path / name
            relative = f"{relative_dir}/{name}" if relative_dir else name
            if directory.is_symlink():
                _fail("payload_inventory", f"symlink directory: {relative}")
            if relative not in expected_dirs:
                _fail("payload_inventory", f"unexpected payload directory: {relative}")
        for name in files:
            path = current_path / name
            relative = f"{relative_dir}/{name}" if relative_dir else name
            if path.is_symlink() or not path.is_file() or path.resolve() != path:
                _fail("payload_inventory", f"non-ordinary payload file: {relative}")
            actual.append(path)
    return actual


def _inventory_entry(path: Path, payload_root: Path, run_by_id: Mapping[str, Any]) -> dict[str, Any]:
    relative = path.relative_to(payload_root).as_posix()
    data = path.read_bytes()
    parts = relative.split("/", 1)
    if relative == FROZEN_REVIEW.relative_path:
        analysis_label = None
        run_id = None
        role = "comparative_review"
    elif len(parts) == 2 and parts[0] in run_by_id and parts[1] in _ROLE_BY_NAME:
        spec = run_by_id[parts[0]]
        analysis_label = spec.analysis
        run_id = spec.run_id
        role = _ROLE_BY_NAME[parts[1]]
    else:
        _fail("payload_inventory", f"unexpected payload path: {relative}")
    return {
        "analysis_label": analysis_label,
        "artifact_role": role,
        "byte_size": len(data),
        "relative_path": relative,
        "run_id": run_id,
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def _verify_manifest_and_payload(bundle_root: Path, payload_root: Path) -> None:
    manifest = _read_json(bundle_root / "bundle_manifest.json", "bundle_manifest")
    if set(manifest) != set(_MANIFEST_KEYS):
        _fail("bundle_manifest", "keys do not match the frozen schema")
    if not _strict_equal(EXPECTED_BUNDLE_NAME, manifest["bundle_name"]):
        _fail("bundle_manifest", "bundle name differs from the frozen anchor")
    if not _strict_equal(EXPECTED_BUNDLE_SCHEMA_VERSION, manifest["bundle_schema_version"]):
        _fail("bundle_manifest", "bundle schema version differs from the frozen anchor")
    if not _strict_equal("payload", manifest["payload_root"]):
        _fail("bundle_manifest", "payload root differs from the frozen layout")
    if not _strict_equal(EXPECTED_PAYLOAD_FILE_COUNT, manifest["payload_file_count"]):
        _fail("bundle_manifest", "payload file count differs from the frozen anchor")
    if not _strict_equal(EXPECTED_PAYLOAD_TOTAL_BYTES, manifest["payload_total_bytes"]):
        _fail("bundle_manifest", "payload byte count differs from the frozen anchor")
    if not _strict_equal(EXPECTED_PAYLOAD_INVENTORY_SHA256, manifest["payload_inventory_sha256"]):
        _fail("bundle_manifest", "payload inventory digest differs from the frozen anchor")
    if not _strict_equal(_source_identity(), manifest["source_identity"]):
        _fail("bundle_manifest", "source identity differs from the frozen anchor")
    if not _strict_equal(_analysis_inventory(), manifest["expected_analysis_inventory"]):
        _fail("bundle_manifest", "analysis inventory differs from the frozen registry")
    if not _strict_equal(_EXPECTED_CANONICALIZATION, manifest["payload_inventory_canonicalization"]):
        _fail("bundle_manifest", "inventory canonicalization differs from the frozen contract")
    if not _strict_equal(_producing_repository_identity(), manifest["producing_repository_identity"]):
        _fail("bundle_manifest", "producing repository identity differs from the frozen contract")

    run_by_id = {spec.run_id: spec for spec in FROZEN_RUNS}
    actual_paths = _enumerate_payload(payload_root)
    actual_entries = sorted((_inventory_entry(path, payload_root, run_by_id) for path in actual_paths), key=lambda item: item["relative_path"])
    declared = manifest["files"]
    if not isinstance(declared, list) or len(declared) != EXPECTED_PAYLOAD_FILE_COUNT:
        _fail("payload_inventory", "manifest file inventory is not exactly 73 entries")
    for entry in declared:
        if not isinstance(entry, dict) or set(entry) != set(_MANIFEST_FILE_KEYS):
            _fail("payload_inventory", "manifest file entry is malformed")
        if not isinstance(entry["relative_path"], str) or not isinstance(entry["byte_size"], int) or isinstance(entry["byte_size"], bool) or not isinstance(entry["sha256"], str):
            _fail("payload_inventory", "manifest file entry has invalid types")
    if declared != actual_entries:
        _fail("payload_inventory", "payload paths, sizes, or SHA-256 values differ from the manifest")
    if {entry["relative_path"] for entry in actual_entries} != _expected_payload_paths():
        _fail("payload_inventory", "payload closed-world path set differs from the frozen registry")
    canonical = json.dumps(declared, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if hashlib.sha256(canonical).hexdigest() != EXPECTED_PAYLOAD_INVENTORY_SHA256:
        _fail("payload_inventory", "recomputed payload inventory digest differs from the frozen anchor")


def verify_frozen_bundle(bundle_root: str | Path | None = None) -> VerificationResult:
    """Verify the public bundle without writes, network access, or inference."""
    requested_root = DEFAULT_FROZEN_ARTIFACT_ROOT.parent if bundle_root is None else Path(bundle_root)
    if not requested_root.is_absolute():
        requested_root = Path(os.path.abspath(requested_root))
    _ordinary_directory(requested_root, "bundle root")
    root = requested_root.resolve()
    _ordinary_file(root / "NOTICE.md", "NOTICE.md")
    _ordinary_file(root / "bundle_manifest.json", "bundle_manifest.json")
    payload_root = root / "payload"
    _ordinary_directory(payload_root, "payload root")
    _verify_manifest_and_payload(root, payload_root)
    try:
        bundle = load_frozen_formal_research(payload_root)
    except FrozenResultsError as exc:
        _fail("semantic_validation", str(exc))
    if len(bundle.runs) != len(FROZEN_RUNS) or len(bundle.comparative_review.get("artifact_inventory", ())) != len(FROZEN_RUNS):
        _fail("consumption", "complete FrozenResearchBundle inventory is incomplete")
    return VerificationResult(
        bundle_name=EXPECTED_BUNDLE_NAME,
        payload_file_count=EXPECTED_PAYLOAD_FILE_COUNT,
        payload_total_bytes=EXPECTED_PAYLOAD_TOTAL_BYTES,
        payload_inventory_sha256=EXPECTED_PAYLOAD_INVENTORY_SHA256,
        source_snapshot_id=FROZEN_SOURCE.snapshot_id,
        verified_run_count=len(bundle.runs),
        comparative_review_verified=True,
        semantic_validation_passed=True,
    )
