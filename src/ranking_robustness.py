"""Pure deterministic derivations for Phase 5 ranking robustness evidence.

This module consumes already validated E1 values.  It deliberately does not
load source data, fit estimators, resample bootstrap inputs, or write files.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import json
import math
from numbers import Real
import re
from typing import Any

import numpy as np

from src.preference_bootstrap import _pairwise_stability
from src.preference_estimation import RANK_EQUALITY_TOLERANCE


DERIVATION_CONTRACT_VERSION = 1
METRIC_SCHEMA_VERSION = 1
ARTIFACT_SCHEMA_VERSION = 1
FORMAL_TOP_K = (1, 3, 5)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
_RANK_INTERVAL_FIELDS = (
    "lower_rank_quantile",
    "median_rank",
    "upper_rank_quantile",
    "probability_rank_1",
)


class RankingRobustnessContractError(ValueError):
    """Raised when deterministic Phase 5 inputs violate the accepted contract."""


def _fail(message: str) -> None:
    raise RankingRobustnessContractError(message)


def _model_ids(model_ids: Sequence[str]) -> tuple[str, ...]:
    if isinstance(model_ids, (str, bytes)):
        _fail("model_ids must be an ordered sequence of strings")
    try:
        values = tuple(model_ids)
    except TypeError as exc:
        raise RankingRobustnessContractError("model_ids must be an ordered sequence") from exc
    if not values or any(not isinstance(value, str) or not value.strip() for value in values):
        _fail("model_ids must contain non-empty strings")
    if len(set(values)) != len(values):
        _fail("model_ids must be unique")
    return values


def _run_ids(run_ids: Sequence[str]) -> tuple[str, ...]:
    if isinstance(run_ids, (str, bytes)):
        _fail("run_ids must be an ordered sequence of strings")
    try:
        values = tuple(run_ids)
    except TypeError as exc:
        raise RankingRobustnessContractError("run_ids must be an ordered sequence") from exc
    if not values or any(not isinstance(value, str) or not value.strip() for value in values):
        _fail("run_ids must contain non-empty strings")
    if len(set(values)) != len(values):
        _fail("run_ids must be unique")
    return values


def _numeric_matrix(values: Any, name: str) -> np.ndarray:
    try:
        array = np.asarray(values)
    except (TypeError, ValueError) as exc:
        raise RankingRobustnessContractError(f"{name} must be a numeric matrix") from exc
    if array.ndim != 2:
        _fail(f"{name} must be two-dimensional")
    if array.dtype.kind not in "biuf":
        _fail(f"{name} must contain real numeric values")
    try:
        finite = np.isfinite(array)
    except TypeError as exc:
        raise RankingRobustnessContractError(f"{name} must contain real numeric values") from exc
    if not bool(finite.all()):
        _fail(f"{name} must contain only finite values")
    return array


def _rank_matrix(model_ids: tuple[str, ...], values: Any, name: str) -> np.ndarray:
    array = _numeric_matrix(values, name)
    replicate_count, model_count = array.shape
    if model_count != len(model_ids):
        _fail(f"{name} column count does not match model_ids")
    if replicate_count < 1:
        _fail(f"{name} must contain at least one replicate")
    if not bool(np.equal(array, np.floor(array)).all()):
        _fail(f"{name} must contain integral ranks")
    if bool(((array < 1) | (array > model_count)).any()):
        _fail(f"{name} contains ranks outside 1..M")
    ranks = array.astype(np.int64)
    expected = np.arange(1, model_count + 1, dtype=np.int64)
    if any(not np.array_equal(np.sort(row), expected) for row in ranks):
        _fail(f"each row of {name} must be a 1..M permutation")
    return ranks


def _point_ranks(model_ids: tuple[str, ...], values: Any, name: str) -> np.ndarray:
    try:
        array = np.asarray(values)
    except (TypeError, ValueError) as exc:
        raise RankingRobustnessContractError(f"{name} must be a rank vector") from exc
    if array.ndim != 1 or len(array) != len(model_ids):
        _fail(f"{name} must be a one-dimensional model-length vector")
    return _rank_matrix(model_ids, array.reshape(1, -1), name)[0]


def _score_matrix(model_ids: tuple[str, ...], values: Any) -> np.ndarray:
    array = _numeric_matrix(values, "bootstrap_scores")
    replicate_count, model_count = array.shape
    if model_count != len(model_ids):
        _fail("bootstrap_scores column count does not match model_ids")
    if replicate_count < 1:
        _fail("bootstrap_scores must contain at least one replicate")
    return array.astype(float, copy=False)


def derive_rank_distribution(model_ids: Sequence[str], bootstrap_ranks: Any) -> list[dict[str, Any]]:
    """Return ordered empirical frequency records for every model and rank."""
    ids = _model_ids(model_ids)
    ranks = _rank_matrix(ids, bootstrap_ranks, "bootstrap_ranks")
    successful = int(ranks.shape[0])
    records: list[dict[str, Any]] = []
    for model_index, model_id in enumerate(ids):
        counts = np.bincount(ranks[:, model_index], minlength=len(ids) + 1)
        for rank in range(1, len(ids) + 1):
            count = int(counts[rank])
            records.append(
                {
                    "model_id": model_id,
                    "rank": rank,
                    "count": count,
                    "successful_replicates": successful,
                    "frequency": float(count / successful),
                }
            )
    return records


def derive_top_k_inclusion(model_ids: Sequence[str], bootstrap_ranks: Any) -> list[dict[str, Any]]:
    """Return empirical inclusion frequencies for the formal top-k values."""
    ids = _model_ids(model_ids)
    ranks = _rank_matrix(ids, bootstrap_ranks, "bootstrap_ranks")
    if len(ids) < max(FORMAL_TOP_K):
        _fail("model set is too small for the formal top-k contract")
    successful = int(ranks.shape[0])
    records: list[dict[str, Any]] = []
    for model_index, model_id in enumerate(ids):
        values = ranks[:, model_index]
        for k in FORMAL_TOP_K:
            included = int(np.count_nonzero(values <= k))
            records.append(
                {
                    "model_id": model_id,
                    "k": k,
                    "included_count": included,
                    "successful_replicates": successful,
                    "frequency": float(included / successful),
                }
            )
    return records


def _pairwise_counts(scores: np.ndarray, model_ids: tuple[str, ...]) -> list[tuple[str, str, int, int, int]]:
    """Count score orderings using the frozen E1 tolerance semantics."""
    successful = int(scores.shape[0])
    records: list[tuple[str, str, int, int, int]] = []
    for left_index, left in enumerate(model_ids):
        for right_index in range(left_index + 1, len(model_ids)):
            right = model_ids[right_index]
            difference = scores[:, left_index] - scores[:, right_index]
            gt = int(np.count_nonzero(difference > RANK_EQUALITY_TOLERANCE))
            eq = int(np.count_nonzero(np.abs(difference) <= RANK_EQUALITY_TOLERANCE))
            lt = int(np.count_nonzero(difference < -RANK_EQUALITY_TOLERANCE))
            if gt + eq + lt != successful:
                _fail("pairwise score outcomes do not partition replicates")
            records.append((left, right, gt, eq, lt))
    return records


def derive_pairwise_ordering(model_ids: Sequence[str], bootstrap_scores: Any) -> list[dict[str, Any]]:
    """Return score-based pairwise stability with exact E1 cross-checking."""
    ids = _model_ids(model_ids)
    scores = _score_matrix(ids, bootstrap_scores)
    authority = _pairwise_stability(scores, ids)
    successful = int(scores.shape[0])
    records: list[dict[str, Any]] = []
    for left, right, gt, eq, lt in _pairwise_counts(scores, ids):
        key = f"{left}|{right}"
        expected = authority.get(key)
        if expected is None:
            _fail(f"existing E1 pairwise authority is missing {key}")
        counts = {"gt_frequency": gt / successful, "eq_frequency": eq / successful, "lt_frequency": lt / successful}
        for name, value in counts.items():
            if not math.isclose(float(value), float(expected[name]), rel_tol=0.0, abs_tol=1e-15):
                _fail(f"local pairwise counts disagree with E1 authority for {key}")
        records.append(
            {
                "left_model_id": left,
                "right_model_id": right,
                "gt_count": gt,
                "eq_count": eq,
                "lt_count": lt,
                "successful_replicates": successful,
                "gt_frequency": float(expected["gt_frequency"]),
                "eq_frequency": float(expected["eq_frequency"]),
                "lt_frequency": float(expected["lt_frequency"]),
            }
        )
    return records


def extract_rank_intervals(model_ids: Sequence[str], rank_summary: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Validate and return the persisted E1 rank-summary fields in model order."""
    ids = _model_ids(model_ids)
    if not isinstance(rank_summary, Mapping) or tuple(rank_summary) != ids:
        _fail("rank_summary model coverage/order does not match model_ids")
    records: list[dict[str, Any]] = []
    for model_index, model_id in enumerate(ids):
        value = rank_summary[model_id]
        if not isinstance(value, Mapping) or set(value) != set(_RANK_INTERVAL_FIELDS):
            _fail(f"rank_summary fields are invalid for {model_id}")
        parsed: dict[str, float] = {}
        for field in _RANK_INTERVAL_FIELDS:
            item = value[field]
            if isinstance(item, bool) or not isinstance(item, Real) or not math.isfinite(float(item)):
                _fail(f"rank_summary {field} is non-finite for {model_id}")
            parsed[field] = float(item)
        if not 1 <= parsed["lower_rank_quantile"] <= parsed["median_rank"] <= parsed["upper_rank_quantile"] <= len(ids):
            _fail(f"rank_summary interval is outside valid rank bounds for {model_id}")
        if not 0 <= parsed["probability_rank_1"] <= 1:
            _fail(f"rank_summary probability_rank_1 is outside [0,1] for {model_id}")
        records.append({"model_id": model_id, **{field: parsed[field] for field in _RANK_INTERVAL_FIELDS}})
    return records


def derive_adjacent_rank_reversals(
    model_ids: Sequence[str],
    primary_point_ranks: Any,
    primary_bootstrap_ranks: Any,
) -> list[dict[str, Any]]:
    """Return support/reversal frequencies for the primary 1..M adjacencies."""
    ids = _model_ids(model_ids)
    point = _point_ranks(ids, primary_point_ranks, "primary_point_ranks")
    ranks = _rank_matrix(ids, primary_bootstrap_ranks, "primary_bootstrap_ranks")
    index_by_model = {model_id: index for index, model_id in enumerate(ids)}
    model_by_rank = {int(rank): model_id for model_id, rank in zip(ids, point)}
    successful = int(ranks.shape[0])
    records: list[dict[str, Any]] = []
    for rank in range(1, len(ids)):
        higher = model_by_rank[rank]
        lower = model_by_rank[rank + 1]
        higher_values = ranks[:, index_by_model[higher]]
        lower_values = ranks[:, index_by_model[lower]]
        support = int(np.count_nonzero(higher_values < lower_values))
        reversal = int(np.count_nonzero(lower_values < higher_values))
        if support + reversal != successful:
            _fail("adjacent bootstrap ranks are not strict pairwise orderings")
        records.append(
            {
                "primary_rank_higher": rank,
                "primary_rank_lower": rank + 1,
                "higher_model_id": higher,
                "lower_model_id": lower,
                "support_count": support,
                "reversal_count": reversal,
                "successful_replicates": successful,
                "support_frequency": float(support / successful),
                "reversal_frequency": float(reversal / successful),
            }
        )
    return records


def derive_cross_specification(
    run_ids: Sequence[str],
    model_ids: Sequence[str],
    point_ranks_by_run: Mapping[str, Sequence[int]],
    primary_run_id: str,
) -> list[dict[str, Any]]:
    """Return descriptive ordinal rank movement across the named E1 runs."""
    runs = _run_ids(run_ids)
    ids = _model_ids(model_ids)
    if not isinstance(point_ranks_by_run, Mapping) or tuple(point_ranks_by_run) != runs:
        _fail("point_ranks_by_run coverage/order does not match run_ids")
    if primary_run_id not in runs:
        _fail("primary_run_id is missing from run_ids")
    ranks_by_run = {run_id: _point_ranks(ids, point_ranks_by_run[run_id], f"point_ranks[{run_id}]") for run_id in runs}
    primary = ranks_by_run[primary_run_id]
    records: list[dict[str, Any]] = []
    for model_index, model_id in enumerate(ids):
        primary_rank = int(primary[model_index])
        rank_by_run = {run_id: int(ranks_by_run[run_id][model_index]) for run_id in runs}
        shifts = {run_id: rank_by_run[run_id] - primary_rank for run_id in runs}
        observed = tuple(rank_by_run.values())
        records.append(
            {
                "model_id": model_id,
                "primary_rank": primary_rank,
                "rank_by_run": rank_by_run,
                "primary_relative_shift_by_run": shifts,
                "minimum_observed_rank": min(observed),
                "maximum_observed_rank": max(observed),
                "maximum_absolute_rank_shift": max(abs(value) for value in shifts.values()),
                "top_1_specification_count": sum(value <= 1 for value in observed),
                "top_3_specification_count": sum(value <= 3 for value in observed),
                "top_5_specification_count": sum(value <= 5 for value in observed),
                "specification_count": len(runs),
            }
        )
    return records


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, np.generic):
        return _jsonable(value.item())
    if isinstance(value, bool) or isinstance(value, int) or isinstance(value, str) or value is None:
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            _fail("canonical JSON does not permit non-finite values")
        return value
    _fail(f"unsupported canonical JSON value: {type(value).__name__}")


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize an E2 identity value deterministically without a newline."""
    try:
        canonical = _jsonable(value)
        return json.dumps(
            canonical,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        if isinstance(exc, RankingRobustnessContractError):
            raise
        raise RankingRobustnessContractError(f"unable to serialize canonical JSON: {exc}") from exc


def _sha(value: Any, name: str, pattern: re.Pattern[str]) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        _fail(f"{name} must be a lowercase hexadecimal Git identity")
    return value


def build_derivation_spec_payload(
    *,
    source_snapshot_id: str,
    e1_bundle: Mapping[str, Any],
    ordered_run_ids: Sequence[str],
    primary_run_id: str,
    top_k: Sequence[int] = FORMAL_TOP_K,
    pairwise_ordering_tolerance: float = RANK_EQUALITY_TOLERANCE,
) -> dict[str, Any]:
    """Build the exact semantic E2 derivation identity payload."""
    source_id = _sha(source_snapshot_id, "source_snapshot_id", _SHA256_RE)
    if not isinstance(e1_bundle, Mapping) or set(e1_bundle) != {"bundle_name", "bundle_schema_version", "payload_inventory_sha256"}:
        _fail("e1_bundle fields are invalid")
    if not isinstance(e1_bundle["bundle_name"], str) or not e1_bundle["bundle_name"].strip():
        _fail("e1 bundle_name must be non-empty")
    if isinstance(e1_bundle["bundle_schema_version"], bool) or e1_bundle["bundle_schema_version"] != 1:
        _fail("e1 bundle_schema_version must be 1")
    payload_inventory = _sha(e1_bundle["payload_inventory_sha256"], "payload_inventory_sha256", _SHA256_RE)
    runs = _run_ids(ordered_run_ids)
    for run_id in runs:
        _sha(run_id, "run_id", _SHA256_RE)
    _sha(primary_run_id, "primary_run_id", _SHA256_RE)
    if primary_run_id not in runs:
        _fail("primary_run_id is missing from ordered_run_ids")
    if tuple(top_k) != FORMAL_TOP_K:
        _fail("formal top-k must equal (1, 3, 5)")
    if isinstance(pairwise_ordering_tolerance, bool) or not isinstance(pairwise_ordering_tolerance, Real) or float(pairwise_ordering_tolerance) != RANK_EQUALITY_TOLERANCE:
        _fail("pairwise_ordering_tolerance differs from the frozen E1 tolerance")
    return {
        "derivation_contract_version": DERIVATION_CONTRACT_VERSION,
        "metric_schema_version": METRIC_SCHEMA_VERSION,
        "source_snapshot_id": source_id,
        "e1_bundle": {
            "bundle_name": e1_bundle["bundle_name"],
            "bundle_schema_version": 1,
            "payload_inventory_sha256": payload_inventory,
        },
        "ordered_run_ids": list(runs),
        "primary_run_id": primary_run_id,
        "top_k": list(FORMAL_TOP_K),
        "pairwise_ordering_tolerance": float(pairwise_ordering_tolerance),
    }


def compute_derivation_spec_id(payload: Mapping[str, Any]) -> str:
    """Hash a semantic derivation payload, independent of producer identity."""
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def build_artifact_instance_payload(
    *,
    derivation_spec_id: str,
    producer_git_sha: str,
    artifact_schema_version: int = ARTIFACT_SCHEMA_VERSION,
) -> dict[str, Any]:
    """Build the non-circular identity payload for one E2 artifact instance."""
    derivation_id = _sha(derivation_spec_id, "derivation_spec_id", _SHA256_RE)
    producer_id = _sha(producer_git_sha, "producer_git_sha", _SHA1_RE)
    if isinstance(artifact_schema_version, bool) or artifact_schema_version != ARTIFACT_SCHEMA_VERSION:
        _fail("artifact_schema_version must be 1")
    return {
        "derivation_spec_id": derivation_id,
        "producer_git_sha": producer_id,
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
    }


def compute_artifact_instance_id(payload: Mapping[str, Any]) -> str:
    """Hash an artifact-instance payload without reading repository state."""
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


__all__ = [
    "ARTIFACT_SCHEMA_VERSION",
    "DERIVATION_CONTRACT_VERSION",
    "FORMAL_TOP_K",
    "METRIC_SCHEMA_VERSION",
    "RankingRobustnessContractError",
    "build_artifact_instance_payload",
    "build_derivation_spec_payload",
    "canonical_json_bytes",
    "compute_artifact_instance_id",
    "compute_derivation_spec_id",
    "derive_adjacent_rank_reversals",
    "derive_cross_specification",
    "derive_pairwise_ordering",
    "derive_rank_distribution",
    "derive_top_k_inclusion",
    "extract_rank_intervals",
]
