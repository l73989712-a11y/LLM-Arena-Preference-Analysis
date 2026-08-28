"""Deterministic structured-artifact writing for Phase 5 E2 evidence.

The metric calculations remain in :mod:`src.ranking_robustness`.  This module
only validates already-derived records, serializes them, and writes one
collision-safe artifact instance.  It never loads E1 or discovers Git state.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import math
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any
from numbers import Real

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
)


METRIC_FILES = (
    ("rank_distributions", "rank_distributions.json"),
    ("top_k", "top_k.json"),
    ("pairwise_ordering", "pairwise_ordering.json"),
    ("rank_intervals", "rank_intervals.json"),
    ("adjacent_reversals", "adjacent_reversals.json"),
    ("cross_specification", "cross_specification.json"),
)
FORMAL_ARTIFACT_FILENAMES = tuple(filename for _, filename in METRIC_FILES) + ("manifest.json",)
_METRIC_NAMES = frozenset(name for name, _ in METRIC_FILES)


class RankingRobustnessArtifactError(RankingRobustnessContractError):
    """Raised when E2 artifact inputs or output lifecycle violate the contract."""


@dataclass(frozen=True)
class ArtifactFileRecord:
    """Identity of one written non-manifest E2 payload file."""

    path: str
    size_bytes: int
    sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {"path": self.path, "size_bytes": self.size_bytes, "sha256": self.sha256}


@dataclass(frozen=True)
class ArtifactInstanceWriteResult:
    """Immutable summary of one successfully published artifact instance."""

    artifact_instance_id: str
    derivation_spec_id: str
    instance_path: Path
    e2_payload_inventory_sha256: str
    artifacts: tuple[ArtifactFileRecord, ...]


def _artifact_error(message: str) -> None:
    raise RankingRobustnessArtifactError(message)


def _artifact_json_bytes(value: Any) -> bytes:
    """Return formal artifact JSON bytes with exactly one LF terminator."""
    try:
        return canonical_json_bytes(value) + b"\n"
    except RankingRobustnessContractError as exc:
        raise RankingRobustnessArtifactError(str(exc)) from exc


def _validate_identity_payloads(
    derivation_payload: Mapping[str, Any],
    artifact_instance_payload: Mapping[str, Any],
) -> tuple[str, str, dict[str, Any], dict[str, Any]]:
    if not isinstance(derivation_payload, Mapping):
        _artifact_error("derivation_payload must be a mapping")
    if not isinstance(artifact_instance_payload, Mapping):
        _artifact_error("artifact_instance_payload must be a mapping")
    required_derivation = {
        "derivation_contract_version",
        "metric_schema_version",
        "source_snapshot_id",
        "e1_bundle",
        "ordered_run_ids",
        "primary_run_id",
        "top_k",
        "pairwise_ordering_tolerance",
    }
    if set(derivation_payload) != required_derivation:
        _artifact_error("derivation_payload fields do not match the accepted identity schema")
    try:
        normalized_derivation = build_derivation_spec_payload(
            source_snapshot_id=derivation_payload["source_snapshot_id"],
            e1_bundle=derivation_payload["e1_bundle"],
            ordered_run_ids=derivation_payload["ordered_run_ids"],
            primary_run_id=derivation_payload["primary_run_id"],
            top_k=derivation_payload["top_k"],
            pairwise_ordering_tolerance=derivation_payload["pairwise_ordering_tolerance"],
        )
    except (KeyError, TypeError, RankingRobustnessContractError) as exc:
        raise RankingRobustnessArtifactError(f"invalid derivation payload: {exc}") from exc
    if dict(derivation_payload) != normalized_derivation:
        _artifact_error("derivation_payload is not normalized to the accepted identity schema")
    derivation_id = compute_derivation_spec_id(normalized_derivation)

    required_instance = {"derivation_spec_id", "producer_git_sha", "artifact_schema_version"}
    if set(artifact_instance_payload) != required_instance:
        _artifact_error("artifact_instance_payload fields do not match the accepted identity schema")
    try:
        normalized_instance = build_artifact_instance_payload(
            derivation_spec_id=artifact_instance_payload["derivation_spec_id"],
            producer_git_sha=artifact_instance_payload["producer_git_sha"],
            artifact_schema_version=artifact_instance_payload["artifact_schema_version"],
        )
    except (KeyError, TypeError, RankingRobustnessContractError) as exc:
        raise RankingRobustnessArtifactError(f"invalid artifact-instance payload: {exc}") from exc
    if dict(artifact_instance_payload) != normalized_instance:
        _artifact_error("artifact_instance_payload is not normalized to the accepted identity schema")
    if normalized_instance["derivation_spec_id"] != derivation_id:
        _artifact_error("artifact-instance payload references a different derivation specification")
    instance_id = compute_artifact_instance_id(normalized_instance)
    return derivation_id, instance_id, normalized_derivation, normalized_instance


def _is_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _require_fields(record: Mapping[str, Any], fields: tuple[str, ...], metric_name: str, index: int) -> None:
    if set(record) != set(fields):
        _artifact_error(f"record {index} for {metric_name} has invalid fields")


def _frequency(value: Any, count: int, denominator: int, metric_name: str, index: int, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(float(value)):
        _artifact_error(f"record {index} for {metric_name} has invalid {field}")
    result = float(value)
    expected = count / denominator
    if not 0.0 <= result <= 1.0 or not math.isclose(result, expected, rel_tol=1e-12, abs_tol=1e-15):
        _artifact_error(f"record {index} for {metric_name} has inconsistent {field}")
    return result


def _validate_metric_record(metric_name: str, record: Mapping[str, Any], index: int, ordered_run_ids: Sequence[str], primary_run_id: str) -> dict[str, Any]:
    if metric_name == "rank_distributions":
        fields = ("model_id", "rank", "count", "successful_replicates", "frequency")
        _require_fields(record, fields, metric_name, index)
        if not isinstance(record["model_id"], str) or not record["model_id"]:
            _artifact_error(f"record {index} for {metric_name} has invalid model_id")
        if not _is_integer(record["rank"]) or record["rank"] <= 0:
            _artifact_error(f"record {index} for {metric_name} has invalid rank")
        if not _is_integer(record["count"]) or record["count"] < 0:
            _artifact_error(f"record {index} for {metric_name} has invalid count")
        if not _is_integer(record["successful_replicates"]) or record["successful_replicates"] <= 0:
            _artifact_error(f"record {index} for {metric_name} has invalid successful_replicates")
        if record["count"] > record["successful_replicates"]:
            _artifact_error(f"record {index} for {metric_name} has count above denominator")
        frequency = _frequency(record["frequency"], record["count"], record["successful_replicates"], metric_name, index, "frequency")
        return {"model_id": record["model_id"], "rank": record["rank"], "count": record["count"], "successful_replicates": record["successful_replicates"], "frequency": frequency}

    if metric_name == "top_k":
        fields = ("model_id", "k", "included_count", "successful_replicates", "frequency")
        _require_fields(record, fields, metric_name, index)
        if not isinstance(record["model_id"], str) or not record["model_id"]:
            _artifact_error(f"record {index} for {metric_name} has invalid model_id")
        if not _is_integer(record["k"]) or record["k"] not in FORMAL_TOP_K:
            _artifact_error(f"record {index} for {metric_name} has invalid k")
        if not _is_integer(record["included_count"]) or record["included_count"] < 0:
            _artifact_error(f"record {index} for {metric_name} has invalid included_count")
        if not _is_integer(record["successful_replicates"]) or record["successful_replicates"] <= 0:
            _artifact_error(f"record {index} for {metric_name} has invalid successful_replicates")
        if record["included_count"] > record["successful_replicates"]:
            _artifact_error(f"record {index} for {metric_name} has included_count above denominator")
        frequency = _frequency(record["frequency"], record["included_count"], record["successful_replicates"], metric_name, index, "frequency")
        return {"model_id": record["model_id"], "k": record["k"], "included_count": record["included_count"], "successful_replicates": record["successful_replicates"], "frequency": frequency}

    if metric_name == "pairwise_ordering":
        fields = ("left_model_id", "right_model_id", "gt_count", "eq_count", "lt_count", "successful_replicates", "gt_frequency", "eq_frequency", "lt_frequency")
        _require_fields(record, fields, metric_name, index)
        left, right = record["left_model_id"], record["right_model_id"]
        if not isinstance(left, str) or not left or not isinstance(right, str) or not right or left == right:
            _artifact_error(f"record {index} for {metric_name} has invalid model IDs")
        counts = [record[field] for field in ("gt_count", "eq_count", "lt_count")]
        if any(not _is_integer(value) or value < 0 for value in counts):
            _artifact_error(f"record {index} for {metric_name} has invalid counts")
        denominator = record["successful_replicates"]
        if not _is_integer(denominator) or denominator <= 0 or sum(counts) != denominator:
            _artifact_error(f"record {index} for {metric_name} has inconsistent counts")
        frequencies = {field: _frequency(record[field], record[count_field], denominator, metric_name, index, field) for field, count_field in (("gt_frequency", "gt_count"), ("eq_frequency", "eq_count"), ("lt_frequency", "lt_count"))}
        return {**{field: record[field] for field in fields[:6]}, **frequencies}

    if metric_name == "rank_intervals":
        fields = ("model_id", "lower_rank_quantile", "median_rank", "upper_rank_quantile", "probability_rank_1")
        _require_fields(record, fields, metric_name, index)
        if not isinstance(record["model_id"], str) or not record["model_id"]:
            _artifact_error(f"record {index} for {metric_name} has invalid model_id")
        values = [record[field] for field in fields[1:]]
        if any(isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(float(value)) for value in values):
            _artifact_error(f"record {index} for {metric_name} has non-finite values")
        lower, median, upper, probability = map(float, values)
        if lower < 1 or not lower <= median <= upper or not 0 <= probability <= 1:
            _artifact_error(f"record {index} for {metric_name} has invalid interval")
        return {"model_id": record["model_id"], "lower_rank_quantile": lower, "median_rank": median, "upper_rank_quantile": upper, "probability_rank_1": probability}

    if metric_name == "adjacent_reversals":
        fields = ("primary_rank_higher", "primary_rank_lower", "higher_model_id", "lower_model_id", "support_count", "reversal_count", "successful_replicates", "support_frequency", "reversal_frequency")
        _require_fields(record, fields, metric_name, index)
        if not _is_integer(record["primary_rank_higher"]) or record["primary_rank_higher"] <= 0 or not _is_integer(record["primary_rank_lower"]) or record["primary_rank_lower"] != record["primary_rank_higher"] + 1:
            _artifact_error(f"record {index} for {metric_name} has invalid primary ranks")
        higher, lower = record["higher_model_id"], record["lower_model_id"]
        if not isinstance(higher, str) or not higher or not isinstance(lower, str) or not lower or higher == lower:
            _artifact_error(f"record {index} for {metric_name} has invalid model IDs")
        support, reversal, denominator = (record[field] for field in ("support_count", "reversal_count", "successful_replicates"))
        if any(not _is_integer(value) or value < 0 for value in (support, reversal)) or not _is_integer(denominator) or denominator <= 0 or support + reversal != denominator:
            _artifact_error(f"record {index} for {metric_name} has inconsistent counts")
        return {**{field: record[field] for field in fields[:7]}, "support_frequency": _frequency(record["support_frequency"], support, denominator, metric_name, index, "support_frequency"), "reversal_frequency": _frequency(record["reversal_frequency"], reversal, denominator, metric_name, index, "reversal_frequency")}

    if metric_name == "cross_specification":
        fields = ("model_id", "primary_rank", "rank_by_run", "primary_relative_shift_by_run", "minimum_observed_rank", "maximum_observed_rank", "maximum_absolute_rank_shift", "top_1_specification_count", "top_3_specification_count", "top_5_specification_count", "specification_count")
        _require_fields(record, fields, metric_name, index)
        if not isinstance(record["model_id"], str) or not record["model_id"] or not _is_integer(record["primary_rank"]) or record["primary_rank"] <= 0:
            _artifact_error(f"record {index} for {metric_name} has invalid model/rank")
        rank_by_run, shifts = record["rank_by_run"], record["primary_relative_shift_by_run"]
        if not isinstance(rank_by_run, Mapping) or not isinstance(shifts, Mapping) or list(rank_by_run) != list(ordered_run_ids) or list(shifts) != list(ordered_run_ids):
            _artifact_error(f"record {index} for {metric_name} has invalid run mappings")
        if primary_run_id not in rank_by_run or rank_by_run[primary_run_id] != record["primary_rank"] or shifts[primary_run_id] != 0:
            _artifact_error(f"record {index} for {metric_name} has invalid primary mapping")
        if any(not _is_integer(rank) or rank <= 0 for rank in rank_by_run.values()) or any(not _is_integer(shift) for shift in shifts.values()):
            _artifact_error(f"record {index} for {metric_name} has non-integral run values")
        if any(shifts[run_id] != rank_by_run[run_id] - record["primary_rank"] for run_id in ordered_run_ids):
            _artifact_error(f"record {index} for {metric_name} has inconsistent shifts")
        ranks = list(rank_by_run.values())
        summary_values = (record["minimum_observed_rank"], record["maximum_observed_rank"], record["maximum_absolute_rank_shift"])
        if any(not _is_integer(value) for value in summary_values):
            _artifact_error(f"record {index} for {metric_name} has non-integral rank summaries")
        if record["minimum_observed_rank"] != min(ranks) or record["maximum_observed_rank"] != max(ranks) or record["maximum_absolute_rank_shift"] != max(abs(value) for value in shifts.values()):
            _artifact_error(f"record {index} for {metric_name} has inconsistent rank movement")
        count = record["specification_count"]
        if not _is_integer(count) or count != len(ordered_run_ids):
            _artifact_error(f"record {index} for {metric_name} has invalid specification_count")
        top_counts = (record["top_1_specification_count"], record["top_3_specification_count"], record["top_5_specification_count"])
        if any(not _is_integer(value) or not 0 <= value <= count for value in top_counts):
            _artifact_error(f"record {index} for {metric_name} has invalid top-k counts")
        expected_top = tuple(sum(rank <= k for rank in ranks) for k in FORMAL_TOP_K)
        if top_counts != expected_top:
            _artifact_error(f"record {index} for {metric_name} has inconsistent top-k counts")
        return {**{field: record[field] for field in fields[:2]}, "rank_by_run": dict(rank_by_run), "primary_relative_shift_by_run": dict(shifts), **{field: record[field] for field in fields[4:]}}

    _artifact_error(f"unsupported metric {metric_name}")


def _metric_records(metric_records: Mapping[str, Sequence[Mapping[str, Any]]], ordered_run_ids: Sequence[str], primary_run_id: str) -> dict[str, list[Mapping[str, Any]]]:
    if not isinstance(metric_records, Mapping) or set(metric_records) != _METRIC_NAMES:
        _artifact_error("metric_records must contain exactly the six formal metrics")
    normalized: dict[str, list[Mapping[str, Any]]] = {}
    for metric_name, _filename in METRIC_FILES:
        records = metric_records[metric_name]
        if isinstance(records, (str, bytes)) or not isinstance(records, Sequence):
            _artifact_error(f"records for {metric_name} must be a sequence")
        copied: list[Mapping[str, Any]] = []
        for index, record in enumerate(records):
            if not isinstance(record, Mapping):
                _artifact_error(f"record {index} for {metric_name} must be a mapping")
            try:
                canonical_json_bytes(record)
            except RankingRobustnessContractError as exc:
                raise RankingRobustnessArtifactError(f"record {index} for {metric_name} is not JSON-safe: {exc}") from exc
            copied.append(_validate_metric_record(metric_name, record, index, ordered_run_ids, primary_run_id))
        normalized[metric_name] = copied
    return normalized


def _metric_documents(
    derivation_id: str,
    instance_id: str,
    metric_records: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, bytes]:
    documents: dict[str, bytes] = {}
    for metric_name, filename in METRIC_FILES:
        document = {
            "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
            "metric_schema_version": METRIC_SCHEMA_VERSION,
            "derivation_spec_id": derivation_id,
            "artifact_instance_id": instance_id,
            "metric": metric_name,
            "records": list(metric_records[metric_name]),
        }
        documents[filename] = _artifact_json_bytes(document)
    return documents


def build_payload_inventory(file_bytes: Mapping[str, bytes]) -> tuple[ArtifactFileRecord, ...]:
    """Build sorted identities for exactly the six non-manifest payload files."""
    if not isinstance(file_bytes, Mapping) or set(file_bytes) != set(FORMAL_ARTIFACT_FILENAMES) - {"manifest.json"}:
        _artifact_error("payload inventory requires exactly the six metric filenames")
    records: list[ArtifactFileRecord] = []
    for path in sorted(file_bytes):
        if not isinstance(path, str) or Path(path).name != path or "/" in path or "\\" in path or path == "manifest.json":
            _artifact_error("payload inventory paths must be direct POSIX filenames")
        data = file_bytes[path]
        if not isinstance(data, bytes):
            _artifact_error("payload inventory values must be bytes")
        records.append(ArtifactFileRecord(path, len(data), hashlib.sha256(data).hexdigest()))
    return tuple(records)


def compute_payload_inventory_sha256(records: Sequence[ArtifactFileRecord]) -> str:
    """Hash the canonical sorted non-manifest inventory representation."""
    if not isinstance(records, Sequence) or isinstance(records, (str, bytes)):
        _artifact_error("inventory records must be a sequence")
    if not all(isinstance(record, ArtifactFileRecord) for record in records):
        _artifact_error("inventory records must be ArtifactFileRecord values")
    dictionaries = [record.to_dict() for record in records]
    paths = [record.path for record in records]
    expected_paths = sorted(set(filename for _, filename in METRIC_FILES))
    if paths != expected_paths or len(set(paths)) != 6:
        _artifact_error("payload inventory must contain six unique sorted records")
    for record in records:
        if not _is_integer(record.size_bytes) or record.size_bytes < 0 or not isinstance(record.sha256, str) or len(record.sha256) != 64 or record.sha256 != record.sha256.lower() or any(char not in "0123456789abcdef" for char in record.sha256):
            _artifact_error("inventory record has invalid size or SHA-256")
    try:
        payload = canonical_json_bytes(dictionaries)
    except RankingRobustnessContractError as exc:
        raise RankingRobustnessArtifactError(str(exc)) from exc
    return hashlib.sha256(payload).hexdigest()


def _manifest_bytes(
    derivation_payload: Mapping[str, Any],
    artifact_instance_payload: Mapping[str, Any],
    inventory: Sequence[ArtifactFileRecord],
) -> tuple[bytes, str]:
    inventory_hash = compute_payload_inventory_sha256(inventory)
    manifest = {
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "derivation_contract_version": DERIVATION_CONTRACT_VERSION,
        "metric_schema_version": METRIC_SCHEMA_VERSION,
        "derivation_spec_id": derivation_payload["derivation_spec_id"] if "derivation_spec_id" in derivation_payload else compute_derivation_spec_id(derivation_payload),
        "artifact_instance_id": compute_artifact_instance_id(artifact_instance_payload),
        "producer_git_sha": artifact_instance_payload["producer_git_sha"],
        "source_snapshot_id": derivation_payload["source_snapshot_id"],
        "e1_bundle": derivation_payload["e1_bundle"],
        "ordered_run_ids": derivation_payload["ordered_run_ids"],
        "primary_run_id": derivation_payload["primary_run_id"],
        "top_k": list(FORMAL_TOP_K),
        "pairwise_ordering_tolerance": derivation_payload["pairwise_ordering_tolerance"],
        "e2_payload_inventory_sha256": inventory_hash,
        "artifacts": [record.to_dict() for record in inventory],
    }
    return _artifact_json_bytes(manifest), inventory_hash


def write_ranking_robustness_artifact_instance(
    *,
    output_parent: str | Path,
    derivation_payload: Mapping[str, Any],
    artifact_instance_payload: Mapping[str, Any],
    metric_records: Mapping[str, Sequence[Mapping[str, Any]]],
) -> ArtifactInstanceWriteResult:
    """Write one complete E2 instance beneath ``output_parent``.

    All bytes and identities are prepared before filesystem publication.  An
    existing instance directory is never overwritten, merged, or reused.
    """
    derivation_id, instance_id, normalized_derivation, normalized_instance = _validate_identity_payloads(
        derivation_payload, artifact_instance_payload
    )
    normalized_records = _metric_records(metric_records, normalized_derivation["ordered_run_ids"], normalized_derivation["primary_run_id"])
    documents = _metric_documents(derivation_id, instance_id, normalized_records)
    inventory = build_payload_inventory(documents)
    manifest_bytes, inventory_hash = _manifest_bytes(normalized_derivation, normalized_instance, inventory)
    all_bytes = {**documents, "manifest.json": manifest_bytes}

    parent = Path(output_parent).expanduser().resolve()
    if parent.exists() and not parent.is_dir():
        _artifact_error("output_parent must be a directory")
    parent.mkdir(parents=True, exist_ok=True)
    final_dir = parent / instance_id
    if final_dir.exists():
        _artifact_error("artifact instance directory already exists")

    temporary_dir: Path | None = None
    try:
        temporary_dir = Path(tempfile.mkdtemp(prefix=f".tmp-{instance_id}-", dir=str(parent)))
        for filename in FORMAL_ARTIFACT_FILENAMES:
            (temporary_dir / filename).write_bytes(all_bytes[filename])
        if final_dir.exists():
            _artifact_error("artifact instance directory appeared before publication")
        os.replace(str(temporary_dir), str(final_dir))
        temporary_dir = None
    except RankingRobustnessArtifactError:
        if temporary_dir is not None and temporary_dir.exists():
            shutil.rmtree(temporary_dir)
        raise
    except (OSError, TypeError, ValueError) as exc:
        if temporary_dir is not None and temporary_dir.exists():
            shutil.rmtree(temporary_dir)
        raise RankingRobustnessArtifactError(f"unable to publish artifact instance: {exc}") from exc

    return ArtifactInstanceWriteResult(
        artifact_instance_id=instance_id,
        derivation_spec_id=derivation_id,
        instance_path=final_dir,
        e2_payload_inventory_sha256=inventory_hash,
        artifacts=inventory,
    )


__all__ = [
    "ArtifactFileRecord",
    "ArtifactInstanceWriteResult",
    "FORMAL_ARTIFACT_FILENAMES",
    "METRIC_FILES",
    "RankingRobustnessArtifactError",
    "build_payload_inventory",
    "compute_payload_inventory_sha256",
    "write_ranking_robustness_artifact_instance",
]
