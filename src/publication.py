"""Deterministic in-memory Phase 6 publication model.

This module is deliberately limited to semantic models and pure serializers.
Filesystem publication, manifests, payload inventories, and instance identity
belong to the later artifact-writer task.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_EVEN
import hashlib
import json
import math
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from src.formal_figures import (
    FormalPublicationPackage,
    HeterogeneityFigureSpec,
    PrimaryFigureSpec,
    RankUncertaintyFigureSpec,
    RobustnessFigureSpec,
    build_formal_publication_package,
)
from src.formal_presentation import FormalPresentationModel, build_formal_presentation
from src.formal_results import FROZEN_RUNS, FROZEN_SOURCE, FrozenResearchBundle, load_frozen_formal_research


PUBLICATION_SCHEMA_VERSION = 1
PUBLICATION_CONTRACT_VERSION = 1
PRIMARY_RUN_ID = FROZEN_RUNS[0].run_id
S6_RUN_ID = next(spec.run_id for spec in FROZEN_RUNS if spec.analysis == "S6-English")
SECTION_IDS = (
    "overview", "research-question", "data-population", "method", "primary-result",
    "uncertainty", "robustness", "heterogeneity", "limitations", "methods-provenance",
)
TABLE_IDS = ("primary-results", "robustness-ranks", "english-subgroup-ranks", "provenance")
FIGURE_ROLES = ("primary_preference", "rank_uncertainty", "robustness_ranks", "s6_heterogeneity")
TRANSFORM_IDS = (
    "identity.v1", "select.primary_top3.v1", "select.primary_rows.v1",
    "select.robustness_rows.v1", "select.s6_rows.v1", "order.primary_rank.v1",
    "order.analysis_then_primary_rank.v1", "order.provenance_fields.v1",
    "project.table_columns.v1", "figure.accepted_spec.v1",
)
DISPLAY_FORMAT_IDS = ("integer.v1", "decimal6_half_even.v1", "sha256.v1", "label.v1", "markdown_text.v1")
CLAIM_IDS = (
    "provenance.e0_identity", "provenance.e1_identity", "provenance.e2_identity",
    "primary.top_three", "primary.score_uncertainty", "primary.rank_uncertainty",
    "robustness.point_ranks", "s6.rank_comparison",
)
CLAIM_KINDS = ("provenance", "quantitative")
ACCEPTED_MODEL_IDS = (
    "RWKV-4-Raven-14B", "alpaca-13b", "chatglm-6b", "claude-instant-v1", "claude-v1",
    "dolly-v2-12b", "fastchat-t5-3b", "gpt-3.5-turbo", "gpt-4", "gpt4all-13b-snoozy",
    "guanaco-33b", "koala-13b", "llama-13b", "mpt-7b-chat", "oasst-pythia-12b",
    "palm-2", "stablelm-tuned-alpha-7b", "vicuna-13b", "vicuna-7b", "wizardlm-13b",
)
AGGREGATION_TRANSFORMS: tuple[str, ...] = ()
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_RUN_ID = re.compile(r"^[0-9a-f]{64}$")
_FORBIDDEN_REPORT_TERMS = ("current leaderboard", "objective capability", "universally preferred", "best model")
_FORBIDDEN_E3 = re.compile(r"\be3\b", re.IGNORECASE)
_ACCEPTED_RUN_IDS = frozenset(spec.run_id for spec in FROZEN_RUNS)
_ACCEPTED_PROVENANCE_FIELDS = ("source_dataset", "source_revision", "source_snapshot_id", "source_file_sha256", "bundle_name", "e1_payload_inventory_sha256", "primary_run_id", "s6_run_id", "artifact_instance_id", "derivation_spec_id", "e2_payload_inventory_sha256")
_TABLE_SCHEMA = {
    "primary-results": (("point_rank", "Point rank", "integer", "integer.v1"), ("model_id", "Model", "string", "label.v1"), ("point_score", "Point score", "number", "decimal6_half_even.v1"), ("score_ci_low", "Score CI low", "number", "decimal6_half_even.v1"), ("score_ci_high", "Score CI high", "number", "decimal6_half_even.v1"), ("rank_median", "Rank median", "number", "decimal6_half_even.v1"), ("rank_ci_low", "Rank CI low", "number", "decimal6_half_even.v1"), ("rank_ci_high", "Rank CI high", "number", "decimal6_half_even.v1"), ("probability_rank_1", "P(rank=1)", "number", "decimal6_half_even.v1")),
    "robustness-ranks": (("analysis_label", "Analysis", "string", "label.v1"), ("primary_rank", "Primary rank", "integer", "integer.v1"), ("model_id", "Model", "string", "label.v1"), ("point_rank", "Point rank", "integer", "integer.v1")),
    "english-subgroup-ranks": (("primary_rank", "Primary rank", "integer", "integer.v1"), ("model_id", "Model", "string", "label.v1"), ("s6_rank", "English rank", "integer", "integer.v1")),
    "provenance": (("field", "Field", "string", "label.v1"), ("value", "Value", "string", "markdown_text.v1")),
}
_CLAIM_SEMANTICS = {
    "provenance.e0_identity": ("provenance", "E0"), "provenance.e1_identity": ("provenance", "E1"), "provenance.e2_identity": ("provenance", "E2"),
    "primary.top_three": ("quantitative", "E1"), "primary.score_uncertainty": ("quantitative", "E1"), "primary.rank_uncertainty": ("quantitative", "E1"),
    "robustness.point_ranks": ("quantitative", "E2"), "s6.rank_comparison": ("quantitative", "E1"),
}


class PublicationError(ValueError):
    """Raised when frozen inputs cannot satisfy the publication core schema."""


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(k): _freeze(v) for k, v in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(v) for v in value)
    if isinstance(value, tuple):
        return tuple(_freeze(v) for v in value)
    return value


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(v) for v in value]
    if isinstance(value, Decimal):
        return str(value)
    return value


def canonical_json_bytes(value: Any) -> bytes:
    """Return sorted, compact UTF-8 JSON with exactly one final LF."""
    try:
        text = json.dumps(_plain(value), ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise PublicationError(f"canonical JSON serialization failed: {exc}") from exc
    return text.encode("utf-8") + b"\n"


def _require_sha(value: Any, name: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise PublicationError(f"{name} must be a lowercase SHA-256")
    return value


def _require_run_id(value: Any, name: str = "run_id") -> str:
    if not isinstance(value, str) or _RUN_ID.fullmatch(value) is None:
        raise PublicationError(f"{name} must be a lowercase 64-character run identity")
    return value


def _require_finite(value: Any, name: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or (isinstance(value, float) and not math.isfinite(value)):
        raise PublicationError(f"{name} must be a finite numeric value")
    return value


@dataclass(frozen=True)
class PublicationSpec:
    publication_schema_version: int
    publication_contract_version: int
    source_e0_identity: Mapping[str, Any]
    source_e1_identity: Mapping[str, Any]
    source_e2_identity: Mapping[str, Any]
    section_ids: tuple[str, ...]
    table_ids: tuple[str, ...]
    figure_roles: tuple[str, ...]
    transform_ids: tuple[str, ...]
    display_format_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.publication_schema_version != PUBLICATION_SCHEMA_VERSION or self.publication_contract_version != PUBLICATION_CONTRACT_VERSION:
            raise PublicationError("unsupported publication version")
        if tuple(self.section_ids) != SECTION_IDS or tuple(self.table_ids) != TABLE_IDS or tuple(self.figure_roles) != FIGURE_ROLES:
            raise PublicationError("publication specification order is not canonical")
        if tuple(self.transform_ids) != TRANSFORM_IDS or tuple(self.display_format_ids) != DISPLAY_FORMAT_IDS:
            raise PublicationError("publication registries are not canonical")
        object.__setattr__(self, "section_ids", tuple(self.section_ids))
        object.__setattr__(self, "table_ids", tuple(self.table_ids))
        object.__setattr__(self, "figure_roles", tuple(self.figure_roles))
        object.__setattr__(self, "transform_ids", tuple(self.transform_ids))
        object.__setattr__(self, "display_format_ids", tuple(self.display_format_ids))
        for identity in (self.source_e0_identity, self.source_e1_identity, self.source_e2_identity):
            if not isinstance(identity, Mapping):
                raise PublicationError("source identities must be mappings")
        object.__setattr__(self, "source_e0_identity", _freeze(self.source_e0_identity))
        object.__setattr__(self, "source_e1_identity", _freeze(self.source_e1_identity))
        object.__setattr__(self, "source_e2_identity", _freeze(self.source_e2_identity))

    def to_dict(self) -> dict[str, Any]:
        return {
            "publication_schema_version": self.publication_schema_version,
            "publication_contract_version": self.publication_contract_version,
            "source_e0_identity": _plain(self.source_e0_identity),
            "source_e1_identity": _plain(self.source_e1_identity),
            "source_e2_identity": _plain(self.source_e2_identity),
            "section_ids": list(self.section_ids),
            "table_ids": list(self.table_ids),
            "figure_roles": list(self.figure_roles),
            "transform_ids": list(self.transform_ids),
            "display_format_ids": list(self.display_format_ids),
        }

    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_dict())

    @property
    def publication_spec_id(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()


@dataclass(frozen=True)
class SourcePointer:
    authority: str
    object: str
    run_id: str | None = None
    document: str | None = None
    record_key: str | None = None
    record_value: str | None = None
    field: str | None = None
    metric: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"authority": self.authority, "object": self.object}
        for key in ("run_id", "document", "record_key", "record_value", "field", "metric"):
            value = getattr(self, key)
            if value is not None:
                data[key] = value
        return data

    def __post_init__(self) -> None:
        if self.authority not in {"E0", "E1", "E2"}:
            raise PublicationError("source pointer authority must be E0, E1, or E2")
        if self.authority == "E0":
            if self.object != "source_identity" or self.field not in {"dataset", "revision", "source_file_sha256", "source_snapshot_id", "row_count", "model_count"} or any(getattr(self, k) is not None for k in ("run_id", "document", "record_key", "record_value", "metric")):
                raise PublicationError("invalid E0 source pointer")
        elif self.authority == "E1":
            if self.object == "bundle_identity":
                if any(getattr(self, k) is not None for k in ("run_id", "document", "record_key", "record_value", "metric")) or self.field not in {"bundle_name", "payload_inventory_sha256", "primary_run_id", "s6_run_id"}:
                    raise PublicationError("invalid E1 bundle identity pointer")
                return
            if self.object != "run_result" or self.run_id not in _ACCEPTED_RUN_IDS or self.document not in {"manifest", "point_estimate", "bootstrap_summary"} or not self.field or self.metric is not None:
                raise PublicationError("invalid E1 source pointer")
            if (self.record_key is None) != (self.record_value is None) or (self.record_key is not None and (self.record_key != "model_id" or self.record_value not in ACCEPTED_MODEL_IDS)):
                raise PublicationError("E1 record selectors must be paired model_id selectors")
            if self.document == "manifest" and self.field not in {"run_id", "population_id", "source_snapshot_id"}:
                raise PublicationError("unsupported E1 manifest field")
            if self.document == "manifest" and self.record_key is not None:
                raise PublicationError("E1 manifest pointers cannot select a model record")
            if self.document == "point_estimate" and self.field not in {"model_ids", "derived_rank", "latent_scores"}:
                raise PublicationError("unsupported E1 point-estimate field")
            if self.document == "point_estimate" and self.record_key is not None and self.field == "model_ids":
                raise PublicationError("model_ids is a whole collection")
            if self.document == "bootstrap_summary" and self.field not in {"score_intervals", "rank_summary"}:
                raise PublicationError("unsupported E1 summary field")
        else:
            if self.object == "artifact_identity":
                if any(getattr(self, k) is not None for k in ("run_id", "document", "record_key", "record_value", "metric")) or self.field not in {"artifact_instance_id", "derivation_spec_id", "payload_inventory_sha256"}:
                    raise PublicationError("invalid E2 artifact identity pointer")
                return
            if self.object != "metric" or self.metric != "cross_specification" or self.field not in {"record_set", "rank_by_run", "primary_rank", "maximum_absolute_rank_shift", "minimum_observed_rank", "maximum_observed_rank"}:
                raise PublicationError("invalid E2 source pointer")
            if self.field == "record_set":
                if self.record_key is not None or self.record_value is not None:
                    raise PublicationError("E2 record-set pointer cannot have a record selector")
            elif self.record_key != "model_id" or self.record_value not in ACCEPTED_MODEL_IDS:
                raise PublicationError("E2 selectors must use paired model_id selectors")


@dataclass(frozen=True)
class ColumnSpec:
    column_id: str
    label: str
    value_type: str
    display_format_id: str

    def __post_init__(self) -> None:
        if self.display_format_id not in DISPLAY_FORMAT_IDS or self.value_type not in {"integer", "number", "string"} or not self.column_id or not self.label:
            raise PublicationError("invalid column specification")

    def to_dict(self) -> dict[str, str]:
        return {"column_id": self.column_id, "label": self.label, "value_type": self.value_type, "display_format_id": self.display_format_id}


@dataclass(frozen=True)
class TableRow:
    row_id: str
    values: Mapping[str, Any]
    claim_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.row_id or not isinstance(self.values, Mapping) or any(claim not in CLAIM_IDS for claim in self.claim_ids):
            raise PublicationError("invalid table row")
        object.__setattr__(self, "values", _freeze(self.values))
        object.__setattr__(self, "claim_ids", tuple(self.claim_ids))

    def to_dict(self) -> dict[str, Any]:
        return {"row_id": self.row_id, "values": _plain(self.values), "claim_ids": list(self.claim_ids)}


@dataclass(frozen=True)
class TableModel:
    table_id: str
    title: str
    columns: tuple[ColumnSpec, ...]
    rows: tuple[TableRow, ...]

    def __post_init__(self) -> None:
        if self.table_id not in TABLE_IDS or not isinstance(self.columns, tuple) or not isinstance(self.rows, tuple):
            raise PublicationError("invalid table model")
        expected = _TABLE_SCHEMA[self.table_id]
        actual = tuple((c.column_id, c.label, c.value_type, c.display_format_id) for c in self.columns)
        if actual != expected:
            raise PublicationError("table columns do not match the canonical schema")
        ids = tuple(column.column_id for column in self.columns)
        if len(set(ids)) != len(ids) or any(set(row.values) != set(ids) for row in self.rows):
            raise PublicationError("table row keys do not match declared columns")

    def to_dict(self) -> dict[str, Any]:
        return {"table_id": self.table_id, "title": self.title, "columns": [c.to_dict() for c in self.columns], "rows": [r.to_dict() for r in self.rows]}


@dataclass(frozen=True)
class Claim:
    claim_id: str
    claim_kind: str
    source_authority: str
    source_pointers: tuple[SourcePointer, ...]
    transform_chain: tuple[str, ...]
    scientific_values: tuple[Any, ...]
    render_bindings: tuple[Mapping[str, Any], ...]

    def __post_init__(self) -> None:
        if self.claim_id not in CLAIM_IDS or self.claim_kind not in CLAIM_KINDS or self.source_authority not in {"E0", "E1", "E2"} or _CLAIM_SEMANTICS.get(self.claim_id) != (self.claim_kind, self.source_authority):
            raise PublicationError("invalid claim identity")
        if not self.source_pointers:
            raise PublicationError("claims require at least one source pointer")
        if any(pointer.authority != self.source_authority for pointer in self.source_pointers):
            raise PublicationError("claim authority does not match source pointers")
        if any(transform not in TRANSFORM_IDS for transform in self.transform_chain):
            raise PublicationError("claim transform chain contains an unknown or display transform")
        if self.claim_kind == "provenance" and self.source_authority not in {"E0", "E1", "E2"}:
            raise PublicationError("invalid provenance authority")
        object.__setattr__(self, "source_pointers", tuple(self.source_pointers))
        object.__setattr__(self, "transform_chain", tuple(self.transform_chain))
        object.__setattr__(self, "scientific_values", _freeze(self.scientific_values))
        object.__setattr__(self, "render_bindings", _freeze(self.render_bindings))
        for binding in self.render_bindings:
            _validate_binding(binding, self.claim_id)

    def to_dict(self) -> dict[str, Any]:
        return {"claim_id": self.claim_id, "claim_kind": self.claim_kind, "source_authority": self.source_authority, "source_pointers": [p.to_dict() for p in self.source_pointers], "transform_chain": list(self.transform_chain), "scientific_values": _plain(self.scientific_values), "render_bindings": [_plain(v) for v in self.render_bindings]}


def _validate_binding(binding: Mapping[str, Any], claim_id: str | None = None) -> None:
    if not isinstance(binding, Mapping) or binding.get("kind") not in {"table_cell", "report_claim", "figure_semantic"}:
        raise PublicationError("unknown render-binding kind")
    kind = binding["kind"]
    if kind == "table_cell":
        required = {"output_path", "kind", "table_id", "row_id", "column_id", "expected_value"}
        if set(binding) != required or binding["output_path"] != "tables.json" or binding["table_id"] not in TABLE_IDS:
            raise PublicationError("invalid table-cell binding")
    elif kind == "report_claim":
        common = {"output_path", "kind", "section_id", "anchor_id", "display_format_id", "expected_text_anchor"}
        if binding["output_path"] != "report.md" or binding.get("section_id") not in SECTION_IDS or binding.get("display_format_id") not in DISPLAY_FORMAT_IDS:
            raise PublicationError("invalid report binding")
        if claim_id is not None and (binding.get("anchor_id") != f"publication-claim:{claim_id}" or binding.get("expected_text_anchor") != f"<!-- publication-claim:{claim_id} -->"):
            raise PublicationError("report binding anchor does not identify its claim")
        if "expected_text" in binding:
            if set(binding) != common | {"expected_text"} or not isinstance(binding["expected_text"], str):
                raise PublicationError("invalid text-backed report binding")
        elif "table_id" in binding:
            if set(binding) != common | {"table_id", "table_sha256"} or binding["table_id"] not in TABLE_IDS or _SHA256.fullmatch(str(binding["table_sha256"])) is None:
                raise PublicationError("invalid table-backed report binding")
        else:
            raise PublicationError("report binding lacks content binding")
    else:
        required = {"output_path", "kind", "figure_role", "transform_id", "phase3_spec_type", "source_claim_ids"}
        role = binding.get("figure_role")
        if set(binding) != required or role not in FIGURE_ROLES or binding.get("output_path") != f"figures/{role}.png" or binding.get("transform_id") != "figure.accepted_spec.v1" or not isinstance(binding.get("source_claim_ids"), (list, tuple)) or any(claim not in CLAIM_IDS for claim in binding.get("source_claim_ids", ())):
            raise PublicationError("invalid figure binding")


@dataclass(frozen=True)
class PublicationModel:
    specification: PublicationSpec
    claims: tuple[Claim, ...]
    tables: tuple[TableModel, ...]
    report_markdown: str
    traceability: Mapping[str, Any]
    figures: Mapping[str, Any]
    presentation: FormalPresentationModel

    def __post_init__(self) -> None:
        if tuple(claim.claim_id for claim in self.claims) != CLAIM_IDS or tuple(table.table_id for table in self.tables) != TABLE_IDS:
            raise PublicationError("publication model registry is not canonical")
        object.__setattr__(self, "claims", tuple(self.claims))
        object.__setattr__(self, "tables", tuple(self.tables))
        object.__setattr__(self, "traceability", _freeze(self.traceability))
        object.__setattr__(self, "figures", _freeze(self.figures))
        validate_publication_model_consistency(self)

    def tables_payload(self) -> dict[str, Any]:
        return {"publication_schema_version": PUBLICATION_SCHEMA_VERSION, "publication_spec_id": self.specification.publication_spec_id, "tables": [table.to_dict() for table in self.tables]}

    def traceability_payload(self) -> dict[str, Any]:
        return _plain(self.traceability)


def validate_publication_model_consistency(model: PublicationModel) -> None:
    """Validate producer-side agreement between every in-memory surface."""
    if tuple(claim.claim_id for claim in model.claims) != CLAIM_IDS or tuple(table.table_id for table in model.tables) != TABLE_IDS:
        raise PublicationError("publication claim/table registry mismatch")
    expected_counts = {"primary-results": 20, "robustness-ranks": 180, "english-subgroup-ranks": 20, "provenance": 11}
    for table in model.tables:
        if len(table.rows) != expected_counts[table.table_id]:
            raise PublicationError(f"non-canonical row count for {table.table_id}")
    primary_table = next(t for t in model.tables if t.table_id == "primary-results")
    if tuple(row.values.get("point_rank") for row in primary_table.rows) != tuple(range(1, 21)) or tuple(row.row_id for row in primary_table.rows) != tuple(f"model:{row.values['model_id']}" for row in primary_table.rows) or {row.values.get("model_id") for row in primary_table.rows} != set(ACCEPTED_MODEL_IDS):
        raise PublicationError("primary table row identity/order is not canonical")
    robustness_table = next(t for t in model.tables if t.table_id == "robustness-ranks")
    analysis_order = ("Primary", "S1", "S2", "S3", "S4", "S5-ge10", "S5-ge20", "S5-ge50", "S6-English")
    if tuple(row.values.get("analysis_label") for row in robustness_table.rows) != tuple(label for label in analysis_order for _ in range(20)) or any(tuple(row.values.get("primary_rank") for row in robustness_table.rows[i * 20:(i + 1) * 20]) != tuple(range(1, 21)) for i in range(9)) or any(row.row_id != f"{row.values['analysis_label']}:model:{row.values['model_id']}" for row in robustness_table.rows) or any({row.values.get("model_id") for row in robustness_table.rows[i * 20:(i + 1) * 20]} != set(ACCEPTED_MODEL_IDS) for i in range(9)):
        raise PublicationError("robustness table row identity/order is not canonical")
    s6_table = next(t for t in model.tables if t.table_id == "english-subgroup-ranks")
    if tuple(row.values.get("primary_rank") for row in s6_table.rows) != tuple(range(1, 21)) or tuple(row.row_id for row in s6_table.rows) != tuple(f"model:{row.values['model_id']}" for row in s6_table.rows) or {row.values.get("model_id") for row in s6_table.rows} != set(ACCEPTED_MODEL_IDS):
        raise PublicationError("S6 table row identity/order is not canonical")
    provenance_table = next(t for t in model.tables if t.table_id == "provenance")
    if tuple(row.values.get("field") for row in provenance_table.rows) != _ACCEPTED_PROVENANCE_FIELDS or tuple(row.row_id for row in provenance_table.rows) != tuple(f"field:{field}" for field in _ACCEPTED_PROVENANCE_FIELDS):
        raise PublicationError("provenance table row identity/order is not canonical")
    expected_membership = {"primary-results": {"primary.top_three", "primary.score_uncertainty", "primary.rank_uncertainty"}, "robustness-ranks": {"robustness.point_ranks"}, "english-subgroup-ranks": {"s6.rank_comparison"}}
    for table_id, required in expected_membership.items():
        table = table_map = next(t for t in model.tables if t.table_id == table_id)
        for row in table.rows:
            actual = set(row.claim_ids)
            if table_id == "primary-results" and row.values["point_rank"] > 3:
                required_row = required - {"primary.top_three"}
            else:
                required_row = required
            if actual != required_row:
                raise PublicationError(f"row claim membership is not canonical for {table_id}")
    for row in provenance_table.rows:
        authority_claim = "provenance.e0_identity" if row.values["field"] in _ACCEPTED_PROVENANCE_FIELDS[:4] else "provenance.e1_identity" if row.values["field"] in _ACCEPTED_PROVENANCE_FIELDS[4:8] else "provenance.e2_identity"
        if row.claim_ids != (authority_claim,):
            raise PublicationError("provenance row claim membership is not canonical")
    if set(model.traceability) != {"publication_schema_version", "publication_spec_id", "claims", "figure_bindings"} or model.traceability.get("publication_schema_version") != PUBLICATION_SCHEMA_VERSION or model.traceability.get("publication_spec_id") != model.specification.publication_spec_id:
        raise PublicationError("traceability top-level identity/schema mismatch")
    trace_entries = model.traceability.get("claims", ())
    if not isinstance(trace_entries, (tuple, list)) or len(trace_entries) != len(CLAIM_IDS) or any(not isinstance(item, Mapping) for item in trace_entries):
        raise PublicationError("traceability claim list is not canonical")
    trace_claims = {item.get("claim_id"): item for item in trace_entries}
    if len(trace_claims) != len(CLAIM_IDS) or tuple(item.get("claim_id") for item in trace_entries) != CLAIM_IDS:
        raise PublicationError("traceability claim registry mismatch")
    table_map = {table.table_id: table for table in model.tables}
    claim_sections = {
        "primary.top_three": "primary-result",
        "primary.score_uncertainty": "uncertainty",
        "primary.rank_uncertainty": "uncertainty",
        "robustness.point_ranks": "robustness",
        "s6.rank_comparison": "heterogeneity",
        "provenance.e0_identity": "methods-provenance",
        "provenance.e1_identity": "methods-provenance",
        "provenance.e2_identity": "methods-provenance",
    }
    for claim in model.claims:
        entry = trace_claims.get(claim.claim_id)
        if entry is None or entry.get("claim_kind") != claim.claim_kind or entry.get("source_authority") != claim.source_authority:
            raise PublicationError(f"traceability metadata mismatch for {claim.claim_id}")
        expected_semantics = claim.to_dict()
        for field in ("claim_id", "claim_kind", "source_authority", "source_pointers", "transform_chain", "scientific_values"):
            if _plain(entry.get(field)) != _plain(expected_semantics[field]):
                raise PublicationError(f"traceability semantic mismatch for {claim.claim_id}")
        for binding in entry.get("render_bindings", ()):
            _validate_binding(binding, claim.claim_id)
        expected_cells = [canonical_json_bytes(binding) for binding in claim.render_bindings if binding.get("kind") == "table_cell"]
        actual_cells = [canonical_json_bytes(binding) for binding in entry.get("render_bindings", ()) if isinstance(binding, Mapping) and binding.get("kind") == "table_cell"]
        if actual_cells != expected_cells:
            raise PublicationError(f"traceability table coverage mismatch for {claim.claim_id}")
        report_bindings = [binding for binding in entry.get("render_bindings", ()) if isinstance(binding, Mapping) and binding.get("kind") == "report_claim"]
        if len(report_bindings) != 1 or len(entry.get("render_bindings", ())) != len(actual_cells) + 1 or any(binding.get("kind") not in {"table_cell", "report_claim"} for binding in entry.get("render_bindings", ())):
            raise PublicationError(f"claim render-binding surface is not canonical for {claim.claim_id}")
        if report_bindings[0].get("section_id") != claim_sections[claim.claim_id]:
            raise PublicationError(f"report section mapping is not canonical for {claim.claim_id}")
        for raw_binding in entry.get("render_bindings", ()):
            if not isinstance(raw_binding, Mapping) or raw_binding.get("kind") != "table_cell":
                continue
            table = table_map.get(raw_binding.get("table_id"))
            row = next((row for row in table.rows if row.row_id == raw_binding.get("row_id")), None) if table else None
            if row is None or row.values.get(raw_binding.get("column_id")) != raw_binding.get("expected_value"):
                raise PublicationError(f"traceability table value mismatch for {claim.claim_id}")
    for claim_id, entry in trace_claims.items():
        for binding in entry.get("render_bindings", ()):
            if not isinstance(binding, Mapping) or binding.get("kind") != "report_claim":
                continue
            section_text = _report_section(model.report_markdown, binding["section_id"])
            if binding.get("anchor_id") not in section_text or binding.get("expected_text_anchor") not in section_text:
                raise PublicationError(f"missing report anchor for {claim_id}")
            if "expected_text" in binding and binding["expected_text"] not in section_text:
                raise PublicationError(f"report text mismatch for {claim_id}")
            if "table_sha256" in binding:
                table = table_map.get(binding.get("table_id"))
                if table is None or hashlib.sha256(_markdown_table(table).encode("utf-8")).hexdigest() != binding["table_sha256"] or _markdown_table(table) not in section_text:
                    raise PublicationError(f"report table hash mismatch for {claim_id}")
    if model.specification.canonical_bytes() != build_publication_spec().canonical_bytes():
        raise PublicationError("publication model does not use the accepted publication specification")
    figure_types = {"primary_preference":"PrimaryFigureSpec", "rank_uncertainty":"RankUncertaintyFigureSpec", "robustness_ranks":"RobustnessFigureSpec", "s6_heterogeneity":"HeterogeneityFigureSpec"}
    figure_entries = model.traceability.get("figure_bindings", ())
    if not isinstance(figure_entries, (tuple, list)) or len(figure_entries) != len(FIGURE_ROLES) or any(not isinstance(item, Mapping) for item in figure_entries):
        raise PublicationError("figure traceability list is not canonical")
    figure_bindings = {item.get("figure_role"): item for item in figure_entries}
    if len(figure_bindings) != len(FIGURE_ROLES) or tuple(item.get("figure_role") for item in figure_entries) != FIGURE_ROLES:
        raise PublicationError("figure traceability registry mismatch")
    figure_specs = {"primary_preference": PrimaryFigureSpec, "rank_uncertainty": RankUncertaintyFigureSpec, "robustness_ranks": RobustnessFigureSpec, "s6_heterogeneity": HeterogeneityFigureSpec}
    figure_claims = {"primary_preference":["primary.top_three", "primary.score_uncertainty"], "rank_uncertainty":["primary.rank_uncertainty"], "robustness_ranks":["robustness.point_ranks"], "s6_heterogeneity":["s6.rank_comparison"]}
    expected_package = build_formal_publication_package(model.presentation)
    expected_figure_objects = {"primary_preference": expected_package.primary_figure, "rank_uncertainty": expected_package.rank_uncertainty_figure, "robustness_ranks": expected_package.robustness_figure, "s6_heterogeneity": expected_package.heterogeneity_figure}
    for role in FIGURE_ROLES:
        binding = figure_bindings[role]
        _validate_binding(binding)
        if binding.get("phase3_spec_type") != figure_types[role] or tuple(binding.get("source_claim_ids", ())) != tuple(figure_claims[role]) or not isinstance(model.figures, Mapping) or set(model.figures) != set(FIGURE_ROLES) or not isinstance(model.figures.get(role), figure_specs[role]) or model.figures.get(role) != expected_figure_objects[role]:
            raise PublicationError(f"figure binding mismatch for {role}")
    if _FORBIDDEN_E3.search(model.report_markdown) or any(term in model.report_markdown.lower() for term in _FORBIDDEN_REPORT_TERMS):
        raise PublicationError("report contains forbidden interpretation wording")


def _source_identities(e2_manifest: Mapping[str, Any] | None = None) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    e0 = {"dataset": FROZEN_SOURCE.dataset, "revision": FROZEN_SOURCE.revision, "source_file_sha256": FROZEN_SOURCE.file_sha256, "source_snapshot_id": FROZEN_SOURCE.snapshot_id, "split": FROZEN_SOURCE.split, "row_count": 33000, "model_count": 20}
    e1 = {"bundle_name": "formal-research-v1", "bundle_schema_version": 1, "payload_inventory_sha256": "392066c7a23408e97f0f2bcd3e2a530b167e596c9b382d999d959ba49abb7eb6", "primary_run_id": PRIMARY_RUN_ID, "s6_run_id": S6_RUN_ID, "formal_run_count": 9}
    e2 = {"artifact_instance_id": "82239159eecc2067b7b89f9e13b9cf34d36497b8fdd7105e6babbcc2668e9a1e", "derivation_spec_id": "dc03cc925d2a85dc023542fc21f703abbb966dd4df5da36974c8ea061ece0be4", "payload_inventory_sha256": "a6a872a6737b5fd7e8d9836ff34ee895d5e99784bca4b5ef1ccb839f7f88857f"}
    return e0, e1, e2


def build_publication_spec() -> PublicationSpec:
    e0, e1, e2 = _source_identities()
    return PublicationSpec(PUBLICATION_SCHEMA_VERSION, PUBLICATION_CONTRACT_VERSION, MappingProxyType(e0), MappingProxyType(e1), MappingProxyType(e2), SECTION_IDS, TABLE_IDS, FIGURE_ROLES, TRANSFORM_IDS, DISPLAY_FORMAT_IDS)


def _columns(table_id: str) -> tuple[ColumnSpec, ...]:
    if table_id == "primary-results":
        fields = (("point_rank", "Point rank", "integer", "integer.v1"), ("model_id", "Model", "string", "label.v1"), ("point_score", "Point score", "number", "decimal6_half_even.v1"), ("score_ci_low", "Score CI low", "number", "decimal6_half_even.v1"), ("score_ci_high", "Score CI high", "number", "decimal6_half_even.v1"), ("rank_median", "Rank median", "number", "decimal6_half_even.v1"), ("rank_ci_low", "Rank CI low", "number", "decimal6_half_even.v1"), ("rank_ci_high", "Rank CI high", "number", "decimal6_half_even.v1"), ("probability_rank_1", "P(rank=1)", "number", "decimal6_half_even.v1"))
    elif table_id == "robustness-ranks":
        fields = (("analysis_label", "Analysis", "string", "label.v1"), ("primary_rank", "Primary rank", "integer", "integer.v1"), ("model_id", "Model", "string", "label.v1"), ("point_rank", "Point rank", "integer", "integer.v1"))
    elif table_id == "english-subgroup-ranks":
        fields = (("primary_rank", "Primary rank", "integer", "integer.v1"), ("model_id", "Model", "string", "label.v1"), ("s6_rank", "English rank", "integer", "integer.v1"))
    else:
        fields = (("field", "Field", "string", "label.v1"), ("value", "Value", "string", "markdown_text.v1"))
    return tuple(ColumnSpec(*field) for field in fields)


E2_INSTANCE_ID = "82239159eecc2067b7b89f9e13b9cf34d36497b8fdd7105e6babbcc2668e9a1e"
E2_DERIVATION_SPEC_ID = "dc03cc925d2a85dc023542fc21f703abbb966dd4df5da36974c8ea061ece0be4"
E2_PAYLOAD_INVENTORY_SHA256 = "a6a872a6737b5fd7e8d9836ff34ee895d5e99784bca4b5ef1ccb839f7f88857f"
E2_CROSS_SPEC_SHA256 = "0dbe9efe03aca8fc323197831190a50d573f20624f5651abe601a06394a0bcfe"
E2_CROSS_SPEC_SIZE = 31111


def _cross_specification(path: str | Path | None = None) -> tuple[Mapping[str, Any], ...]:
    default_path = Path(__file__).resolve().parents[1] / "artifacts" / "phase-5" / E2_INSTANCE_ID / "cross_specification.json"
    path = Path(path) if path is not None else default_path
    try:
        if path == default_path:
            manifest = json.loads((path.parent / "manifest.json").read_text(encoding="utf-8"))
            entries = {item.get("path"): item for item in manifest.get("artifacts", [])}
            entry = entries.get("cross_specification.json")
            if manifest.get("artifact_instance_id") != E2_INSTANCE_ID or manifest.get("derivation_spec_id") != E2_DERIVATION_SPEC_ID or manifest.get("e2_payload_inventory_sha256") != E2_PAYLOAD_INVENTORY_SHA256 or not isinstance(entry, Mapping) or entry.get("size_bytes") != E2_CROSS_SPEC_SIZE or entry.get("sha256") != E2_CROSS_SPEC_SHA256:
                raise PublicationError("accepted E2 manifest does not bind cross_specification")
        data = path.read_bytes()
        if len(data) != E2_CROSS_SPEC_SIZE or hashlib.sha256(data).hexdigest() != E2_CROSS_SPEC_SHA256:
            raise PublicationError("E2 cross_specification bytes do not match accepted payload identity")
        payload = json.loads(data.decode("utf-8"))
    except (OSError, ValueError) as exc:
        raise PublicationError(f"accepted E2 cross_specification cannot be read: {exc}") from exc
    if payload.get("artifact_instance_id") != E2_INSTANCE_ID or payload.get("derivation_spec_id") != E2_DERIVATION_SPEC_ID or payload.get("metric") != "cross_specification":
        raise PublicationError("E2 cross_specification identity mismatch")
    records = payload.get("records")
    if not isinstance(records, list) or len(records) != 20:
        raise PublicationError("E2 cross_specification record set is not canonical")
    return tuple(records)


def _table_models(presentation: FormalPresentationModel, cross: Sequence[Mapping[str, Any]]) -> tuple[TableModel, ...]:
    package = build_formal_publication_package(presentation)
    primary = tuple(TableRow(f"model:{row.model_id}", {"point_rank": row.point_rank, "model_id": row.model_id, "point_score": row.point_score, "score_ci_low": row.score_ci_low, "score_ci_high": row.score_ci_high, "rank_median": row.rank_median, "rank_ci_low": row.rank_ci_low, "rank_ci_high": row.rank_ci_high, "probability_rank_1": row.probability_rank_1}, (("primary.top_three",) if row.point_rank <= 3 else ()) + ("primary.score_uncertainty", "primary.rank_uncertainty")) for row in package.primary_table)
    analysis_order = ("Primary", "S1", "S2", "S3", "S4", "S5-ge10", "S5-ge20", "S5-ge50", "S6-English")
    robustness_rows = []
    for analysis in analysis_order:
        run_id = next(spec.run_id for spec in FROZEN_RUNS if spec.analysis == analysis)
        for record in sorted(cross, key=lambda item: int(item["primary_rank"])):
            robustness_rows.append(TableRow(f"{analysis}:model:{record['model_id']}", {"analysis_label": analysis, "primary_rank": int(record["primary_rank"]), "model_id": str(record["model_id"]), "point_rank": int(record["rank_by_run"][run_id])}, ("robustness.point_ranks",)))
    s6_rows = tuple(TableRow(f"model:{row.model_id}", {"primary_rank": row.primary_rank, "model_id": row.model_id, "s6_rank": row.english_rank}, ("s6.rank_comparison",)) for row in package.heterogeneity_table)
    provenance_values = (("source_dataset", FROZEN_SOURCE.dataset, "provenance.e0_identity"), ("source_revision", FROZEN_SOURCE.revision, "provenance.e0_identity"), ("source_snapshot_id", FROZEN_SOURCE.snapshot_id, "provenance.e0_identity"), ("source_file_sha256", FROZEN_SOURCE.file_sha256, "provenance.e0_identity"), ("bundle_name", "formal-research-v1", "provenance.e1_identity"), ("e1_payload_inventory_sha256", "392066c7a23408e97f0f2bcd3e2a530b167e596c9b382d999d959ba49abb7eb6", "provenance.e1_identity"), ("primary_run_id", PRIMARY_RUN_ID, "provenance.e1_identity"), ("s6_run_id", S6_RUN_ID, "provenance.e1_identity"), ("artifact_instance_id", E2_INSTANCE_ID, "provenance.e2_identity"), ("derivation_spec_id", E2_DERIVATION_SPEC_ID, "provenance.e2_identity"), ("e2_payload_inventory_sha256", E2_PAYLOAD_INVENTORY_SHA256, "provenance.e2_identity"))
    provenance = tuple(TableRow(f"field:{field}", {"field": field, "value": value}, (claim_id,)) for field, value, claim_id in provenance_values)
    return (TableModel("primary-results", "Primary estimated historical Arena preference and frozen uncertainty", _columns("primary-results"), primary), TableModel("robustness-ranks", "Frozen rank comparison across accepted analyses", _columns("robustness-ranks"), tuple(robustness_rows)), TableModel("english-subgroup-ranks", "Primary and English-subgroup rank movement", _columns("english-subgroup-ranks"), s6_rows), TableModel("provenance", "Frozen source and formal analysis provenance", _columns("provenance"), provenance))


def _display(value: Any, format_id: str) -> str:
    if format_id == "integer.v1":
        if isinstance(value, bool) or not isinstance(value, int):
            raise PublicationError("integer formatter received a non-integer")
        return str(value)
    if format_id == "decimal6_half_even.v1":
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise PublicationError("decimal formatter received a non-finite value")
        return format(Decimal(str(value)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_EVEN), "f")
    if format_id in {"sha256.v1", "label.v1", "markdown_text.v1"}:
        return str(value)
    raise PublicationError(f"unknown display format: {format_id}")


def _markdown_table(table: TableModel) -> str:
    lines = [f"### {table.title}", "", "| " + " | ".join(c.label for c in table.columns) + " |", "| " + " | ".join("---" for _ in table.columns) + " |"]
    for row in table.rows:
        lines.append("| " + " | ".join(_display(row.values[c.column_id], c.display_format_id).replace("|", "\\|") for c in table.columns) + " |")
    return "\n".join(lines) + "\n"


def _top_three_text(table: TableModel) -> str:
    return "The first three Primary point ranks are " + ", ".join(f"{r.values['model_id']} (point rank {_display(r.values['point_rank'], 'integer.v1')})" for r in table.rows[:3]) + "."


def _report_section(report: str, section_id: str) -> str:
    """Return one canonical section bounded by its fixed publication markers."""
    if not isinstance(report, str) or section_id not in SECTION_IDS:
        raise PublicationError("invalid report section selector")
    marker = f"<!-- publication-section:{section_id} -->"
    start = report.find(marker)
    if start < 0:
        raise PublicationError(f"missing report section: {section_id}")
    end = len(report)
    for later_id in SECTION_IDS:
        later_marker = f"<!-- publication-section:{later_id} -->"
        if later_marker == marker:
            continue
        position = report.find(later_marker, start + len(marker))
        if position >= 0:
            end = min(end, position)
    return report[start:end]


def _report(tables: Sequence[TableModel], claims: Sequence[Claim]) -> str:
    lookup = {table.table_id: table for table in tables}
    top = lookup["primary-results"].rows[:3]
    lines = ["# Frozen Historical Arena Preference Report", ""]
    paragraphs = {
        "overview": "This report presents estimated preference under the frozen historical Arena population.",
        "research-question": "The question is how model preferences are estimated in that frozen population, with frozen uncertainty and rank robustness.",
        "data-population": "The source and population are historical and frozen; this report is not a current system comparison.",
        "method": "The report consumes accepted frozen E1 results and E2 ranking-robustness records. It does not fit an estimator or calculate new intervals.",
        "primary-result": _top_three_text(lookup["primary-results"]),
        "uncertainty": "Frozen score and rank uncertainty values are retained in the Primary table.",
        "robustness": "Point-rank records are compared across the accepted analyses; latent scores are not compared across estimator parameterizations.",
        "heterogeneity": "The English subgroup comparison preserves the accepted historical-population boundary and does not support causal interpretation.",
        "limitations": "The evidence concerns one frozen historical population and does not establish current quality, causality, or external generalization.",
        "methods-provenance": "The provenance table records the frozen source and formal-run identities.",
    }
    headings = {"overview":"1. Overview", "research-question":"2. Research Question", "data-population":"3. Data & Frozen Population", "method":"4. Method", "primary-result":"5. Primary Result", "uncertainty":"6. Uncertainty", "robustness":"7. Robustness", "heterogeneity":"8. Heterogeneity", "limitations":"9. Limitations", "methods-provenance":"10. Methods & Provenance"}
    table_for = {"primary-result":"primary-results", "uncertainty":"primary-results", "robustness":"robustness-ranks", "heterogeneity":"english-subgroup-ranks", "methods-provenance":"provenance"}
    for section in SECTION_IDS:
        lines.extend([f"<!-- publication-section:{section} -->", f"## {headings[section]}", "", paragraphs[section], ""])
        claim_id = {"primary-result":"primary.top_three", "uncertainty":"primary.score_uncertainty", "robustness":"robustness.point_ranks", "heterogeneity":"s6.rank_comparison"}.get(section)
        if claim_id:
            lines.extend([f"<!-- publication-claim:{claim_id} -->", ""])
            if section == "uncertainty":
                lines.extend(["<!-- publication-claim:primary.rank_uncertainty -->", ""])
        if section == "methods-provenance":
            lines.extend(["<!-- publication-claim:provenance.e0_identity -->", "", "<!-- publication-claim:provenance.e1_identity -->", "", "<!-- publication-claim:provenance.e2_identity -->", ""])
        table_id = table_for.get(section)
        if table_id:
            table = lookup[table_id]
            lines.extend(_markdown_table(table).rstrip("\n").split("\n"))
            lines.append("")
    result = "\n".join(lines).rstrip() + "\n"
    lowered = result.lower()
    if any(term in lowered for term in _FORBIDDEN_REPORT_TERMS):
        raise PublicationError("report contains forbidden interpretation wording")
    return result


def _claims(presentation: FormalPresentationModel, tables: Sequence[TableModel], spec: PublicationSpec) -> tuple[Claim, ...]:
    primary = next(t for t in tables if t.table_id == "primary-results")
    robustness = next(t for t in tables if t.table_id == "robustness-ranks")
    s6 = next(t for t in tables if t.table_id == "english-subgroup-ranks")
    provenance = next(t for t in tables if t.table_id == "provenance")
    pointers = lambda field: (SourcePointer("E1", "run_result", PRIMARY_RUN_ID, "point_estimate", field=field),)
    def bindings(table_id: str, rows: Sequence[TableRow], columns: Sequence[str]) -> tuple[Mapping[str, Any], ...]:
        return tuple({"output_path":"tables.json", "kind":"table_cell", "table_id":table_id, "row_id":row.row_id, "column_id":column, "expected_value":row.values[column]} for row in rows for column in columns)
    top_values = tuple({"model_id": row.values["model_id"], "point_rank": row.values["point_rank"]} for row in primary.rows[:3])
    score_values = tuple({"model_id": row.values["model_id"], "point_score": row.values["point_score"], "score_ci_low": row.values["score_ci_low"], "score_ci_high": row.values["score_ci_high"]} for row in primary.rows)
    rank_values = tuple({"model_id": row.values["model_id"], "point_rank": row.values["point_rank"], "rank_median": row.values["rank_median"], "rank_ci_low": row.values["rank_ci_low"], "rank_ci_high": row.values["rank_ci_high"], "probability_rank_1": row.values["probability_rank_1"]} for row in primary.rows)
    robustness_values = tuple({"analysis_label": row.values["analysis_label"], "model_id": row.values["model_id"], "primary_rank": row.values["primary_rank"], "point_rank": row.values["point_rank"]} for row in robustness.rows)
    s6_values = tuple({"model_id": row.values["model_id"], "primary_rank": row.values["primary_rank"], "s6_rank": row.values["s6_rank"]} for row in s6.rows)
    e0_rows = provenance.rows[:4]
    e1_rows = provenance.rows[4:8]
    e2_rows = provenance.rows[8:]
    claims = (
        Claim("provenance.e0_identity", "provenance", "E0", (SourcePointer("E0", "source_identity", field="dataset"), SourcePointer("E0", "source_identity", field="revision"), SourcePointer("E0", "source_identity", field="source_snapshot_id"), SourcePointer("E0", "source_identity", field="source_file_sha256")), ("identity.v1",), tuple(row.values["value"] for row in e0_rows), bindings("provenance", e0_rows, ("field", "value"))),
        Claim("provenance.e1_identity", "provenance", "E1", (SourcePointer("E1", "bundle_identity", field="bundle_name"), SourcePointer("E1", "bundle_identity", field="payload_inventory_sha256"), SourcePointer("E1", "bundle_identity", field="primary_run_id"), SourcePointer("E1", "bundle_identity", field="s6_run_id")), ("identity.v1",), tuple(row.values["value"] for row in e1_rows), bindings("provenance", e1_rows, ("field", "value"))),
        Claim("provenance.e2_identity", "provenance", "E2", (SourcePointer("E2", "artifact_identity", field="artifact_instance_id"), SourcePointer("E2", "artifact_identity", field="derivation_spec_id"), SourcePointer("E2", "artifact_identity", field="payload_inventory_sha256")), ("identity.v1",), tuple(row.values["value"] for row in e2_rows), bindings("provenance", e2_rows, ("field", "value"))),
        Claim("primary.top_three", "quantitative", "E1", pointers("derived_rank"), ("select.primary_top3.v1", "order.primary_rank.v1"), top_values, bindings("primary-results", primary.rows[:3], ("point_rank", "model_id"))),
        Claim("primary.score_uncertainty", "quantitative", "E1", (SourcePointer("E1", "run_result", PRIMARY_RUN_ID, "point_estimate", field="latent_scores"), SourcePointer("E1", "run_result", PRIMARY_RUN_ID, "bootstrap_summary", field="score_intervals")), ("select.primary_rows.v1", "project.table_columns.v1"), score_values, bindings("primary-results", primary.rows, ("model_id", "point_score", "score_ci_low", "score_ci_high"))),
        Claim("primary.rank_uncertainty", "quantitative", "E1", (SourcePointer("E1", "run_result", PRIMARY_RUN_ID, "point_estimate", field="derived_rank"), SourcePointer("E1", "run_result", PRIMARY_RUN_ID, "bootstrap_summary", field="rank_summary")), ("select.primary_rows.v1", "project.table_columns.v1"), rank_values, bindings("primary-results", primary.rows, ("model_id", "point_rank", "rank_median", "rank_ci_low", "rank_ci_high", "probability_rank_1"))),
        Claim("robustness.point_ranks", "quantitative", "E2", (SourcePointer("E2", "metric", field="record_set", metric="cross_specification"),), ("select.robustness_rows.v1", "order.analysis_then_primary_rank.v1", "project.table_columns.v1"), robustness_values, bindings("robustness-ranks", robustness.rows, ("analysis_label", "primary_rank", "model_id", "point_rank"))),
        Claim("s6.rank_comparison", "quantitative", "E1", (SourcePointer("E1", "run_result", PRIMARY_RUN_ID, "point_estimate", field="derived_rank"), SourcePointer("E1", "run_result", S6_RUN_ID, "point_estimate", field="derived_rank")), ("select.s6_rows.v1", "order.primary_rank.v1", "project.table_columns.v1"), s6_values, bindings("english-subgroup-ranks", s6.rows, ("primary_rank", "model_id", "s6_rank"))),
    )
    return claims


def _traceability(claims: Sequence[Claim], spec: PublicationSpec, model_tables: Sequence[TableModel]) -> dict[str, Any]:
    items = []
    for claim in claims:
        bindings = list(claim.render_bindings)
        if claim.claim_id in {"primary.top_three", "primary.score_uncertainty", "primary.rank_uncertainty", "robustness.point_ranks", "s6.rank_comparison", "provenance.e0_identity", "provenance.e1_identity", "provenance.e2_identity"}:
            section = {"primary.top_three":"primary-result", "primary.score_uncertainty":"uncertainty", "primary.rank_uncertainty":"uncertainty", "robustness.point_ranks":"robustness", "s6.rank_comparison":"heterogeneity", "provenance.e0_identity":"methods-provenance", "provenance.e1_identity":"methods-provenance", "provenance.e2_identity":"methods-provenance"}[claim.claim_id]
            report_binding: dict[str, Any] = {"output_path":"report.md", "kind":"report_claim", "section_id":section, "anchor_id":f"publication-claim:{claim.claim_id}", "display_format_id":"markdown_text.v1", "expected_text_anchor":f"<!-- publication-claim:{claim.claim_id} -->"}
            if claim.claim_id == "primary.top_three":
                table = next(t for t in model_tables if t.table_id == "primary-results")
                report_binding["expected_text"] = _top_three_text(table)
            else:
                table_id = {"primary.score_uncertainty":"primary-results", "primary.rank_uncertainty":"primary-results", "robustness.point_ranks":"robustness-ranks", "s6.rank_comparison":"english-subgroup-ranks", "provenance.e0_identity":"provenance", "provenance.e1_identity":"provenance", "provenance.e2_identity":"provenance"}[claim.claim_id]
                table = next(t for t in model_tables if t.table_id == table_id)
                report_binding["table_id"] = table_id
                report_binding["table_sha256"] = hashlib.sha256(_markdown_table(table).encode("utf-8")).hexdigest()
            bindings.append(report_binding)
        items.append({"claim_id": claim.claim_id, "claim_kind": claim.claim_kind, "source_authority": claim.source_authority, "source_pointers":[p.to_dict() for p in claim.source_pointers], "transform_chain":list(claim.transform_chain), "scientific_values":_plain(claim.scientific_values), "render_bindings":_plain(bindings)})
    figure_types = {"primary_preference":"PrimaryFigureSpec", "rank_uncertainty":"RankUncertaintyFigureSpec", "robustness_ranks":"RobustnessFigureSpec", "s6_heterogeneity":"HeterogeneityFigureSpec"}
    figure_claims = {"primary_preference":["primary.top_three", "primary.score_uncertainty"], "rank_uncertainty":["primary.rank_uncertainty"], "robustness_ranks":["robustness.point_ranks"], "s6_heterogeneity":["s6.rank_comparison"]}
    return {"publication_schema_version": PUBLICATION_SCHEMA_VERSION, "publication_spec_id": spec.publication_spec_id, "claims": items, "figure_bindings":[{"output_path":f"figures/{role}.png", "kind":"figure_semantic", "figure_role":role, "transform_id":"figure.accepted_spec.v1", "phase3_spec_type":figure_types[role], "source_claim_ids":figure_claims[role]} for role in FIGURE_ROLES]}


def build_publication_model(bundle: FrozenResearchBundle | None = None) -> PublicationModel:
    """Build the complete deterministic model without writing publication files."""
    if bundle is None:
        bundle = load_frozen_formal_research()
    presentation = build_formal_presentation(bundle)
    package = build_formal_publication_package(presentation)
    spec = build_publication_spec()
    tables = _table_models(presentation, _cross_specification())
    claims = _claims(presentation, tables, spec)
    report = _report(tables, claims)
    traceability = _traceability(claims, spec, tables)
    figures = MappingProxyType({"primary_preference": package.primary_figure, "rank_uncertainty": package.rank_uncertainty_figure, "robustness_ranks": package.robustness_figure, "s6_heterogeneity": package.heterogeneity_figure})
    return PublicationModel(spec, claims, tables, report, traceability, figures, presentation)


def serialize_publication_spec(spec: PublicationSpec) -> bytes:
    return spec.canonical_bytes()


def serialize_tables(model: PublicationModel) -> bytes:
    validate_publication_model_consistency(model)
    return canonical_json_bytes(model.tables_payload())


def serialize_traceability(model: PublicationModel) -> bytes:
    validate_publication_model_consistency(model)
    return canonical_json_bytes(model.traceability_payload())


def render_report_markdown(model: PublicationModel) -> str:
    if not isinstance(model, PublicationModel):
        raise TypeError("render_report_markdown expects PublicationModel")
    validate_publication_model_consistency(model)
    return model.report_markdown


__all__ = [
    "AGGREGATION_TRANSFORMS", "Claim", "ColumnSpec", "DISPLAY_FORMAT_IDS", "FIGURE_ROLES", "PRIMARY_RUN_ID", "PublicationError", "PublicationModel", "PublicationSpec", "PUBLICATION_CONTRACT_VERSION", "PUBLICATION_SCHEMA_VERSION", "S6_RUN_ID", "SECTION_IDS", "SourcePointer", "TABLE_IDS", "TRANSFORM_IDS", "TableModel", "TableRow", "build_publication_model", "build_publication_spec", "canonical_json_bytes", "render_report_markdown", "serialize_publication_spec", "serialize_tables", "serialize_traceability", "validate_publication_model_consistency",
]
