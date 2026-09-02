"""Independent verification of persisted Phase 6 publication bundles.

This module intentionally duplicates the bounded publication schema.  It reads
persisted bytes and frozen authorities directly; producer construction and
writer functions are not used as correctness oracles.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_EVEN
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
from typing import Any, Mapping

from src.formal_results import FROZEN_RUNS, FROZEN_SOURCE, FrozenResultsError, load_frozen_formal_research
from src.formal_verifier import FrozenBundleVerificationError, verify_frozen_bundle
from src.ranking_robustness_verifier import RankingRobustnessVerificationError, verify_ranking_robustness_artifact


PUBLICATION_SCHEMA_VERSION = 1
PUBLICATION_CONTRACT_VERSION = 1
SECTION_IDS = (
    "overview", "research-question", "data-population", "method", "primary-result",
    "uncertainty", "robustness", "heterogeneity", "limitations", "methods-provenance",
)
TABLE_IDS = ("primary-results", "robustness-ranks", "english-subgroup-ranks", "provenance")
FIGURE_ROLES = ("primary_preference", "rank_uncertainty", "robustness_ranks", "s6_heterogeneity")
ANALYSIS_ORDER = ("Primary", "S1", "S2", "S3", "S4", "S5-ge10", "S5-ge20", "S5-ge50", "S6-English")
CLAIM_IDS = (
    "provenance.e0_identity", "provenance.e1_identity", "provenance.e2_identity",
    "primary.top_three", "primary.score_uncertainty", "primary.rank_uncertainty",
    "robustness.point_ranks", "s6.rank_comparison",
)
TRANSFORM_IDS = (
    "identity.v1", "select.primary_top3.v1", "select.primary_rows.v1", "select.robustness_rows.v1",
    "select.s6_rows.v1", "order.primary_rank.v1", "order.analysis_then_primary_rank.v1",
    "order.provenance_fields.v1", "project.table_columns.v1", "figure.accepted_spec.v1",
)
DISPLAY_FORMAT_IDS = ("integer.v1", "decimal6_half_even.v1", "sha256.v1", "label.v1", "markdown_text.v1")
MODEL_IDS = (
    "RWKV-4-Raven-14B", "alpaca-13b", "chatglm-6b", "claude-instant-v1", "claude-v1",
    "dolly-v2-12b", "fastchat-t5-3b", "gpt-3.5-turbo", "gpt-4", "gpt4all-13b-snoozy",
    "guanaco-33b", "koala-13b", "llama-13b", "mpt-7b-chat", "oasst-pythia-12b",
    "palm-2", "stablelm-tuned-alpha-7b", "vicuna-13b", "vicuna-7b", "wizardlm-13b",
)
PROVENANCE_FIELDS = (
    "source_dataset", "source_revision", "source_snapshot_id", "source_file_sha256",
    "bundle_name", "e1_payload_inventory_sha256", "primary_run_id", "s6_run_id",
    "artifact_instance_id", "derivation_spec_id", "e2_payload_inventory_sha256",
)
TABLE_SCHEMAS = {
    "primary-results": (
        ("point_rank", "Point rank", "integer", "integer.v1"), ("model_id", "Model", "string", "label.v1"),
        ("point_score", "Point score", "number", "decimal6_half_even.v1"), ("score_ci_low", "Score CI low", "number", "decimal6_half_even.v1"),
        ("score_ci_high", "Score CI high", "number", "decimal6_half_even.v1"), ("rank_median", "Rank median", "number", "decimal6_half_even.v1"),
        ("rank_ci_low", "Rank CI low", "number", "decimal6_half_even.v1"), ("rank_ci_high", "Rank CI high", "number", "decimal6_half_even.v1"),
        ("probability_rank_1", "P(rank=1)", "number", "decimal6_half_even.v1"),
    ),
    "robustness-ranks": (("analysis_label", "Analysis", "string", "label.v1"), ("primary_rank", "Primary rank", "integer", "integer.v1"), ("model_id", "Model", "string", "label.v1"), ("point_rank", "Point rank", "integer", "integer.v1")),
    "english-subgroup-ranks": (("primary_rank", "Primary rank", "integer", "integer.v1"), ("model_id", "Model", "string", "label.v1"), ("s6_rank", "English rank", "integer", "integer.v1")),
    "provenance": (("field", "Field", "string", "label.v1"), ("value", "Value", "string", "markdown_text.v1")),
}
TABLE_TITLES = {
    "primary-results": "Primary estimated historical Arena preference and frozen uncertainty",
    "robustness-ranks": "Frozen rank comparison across accepted analyses",
    "english-subgroup-ranks": "Primary and English-subgroup rank movement",
    "provenance": "Frozen source and formal analysis provenance",
}
NON_MANIFEST_PATHS = (
    "report.md", "tables.json", "traceability.json",
    "figures/primary_preference.png", "figures/rank_uncertainty.png",
    "figures/robustness_ranks.png", "figures/s6_heterogeneity.png",
)
ALL_PATHS = ("manifest.json",) + NON_MANIFEST_PATHS
E2_INSTANCE_ID = "82239159eecc2067b7b89f9e13b9cf34d36497b8fdd7105e6babbcc2668e9a1e"
E2_DERIVATION_SPEC_ID = "dc03cc925d2a85dc023542fc21f703abbb966dd4df5da36974c8ea061ece0be4"
E2_INVENTORY_SHA = "a6a872a6737b5fd7e8d9836ff34ee895d5e99784bca4b5ef1ccb839f7f88857f"
E2_CROSS_SIZE = 31111
E2_CROSS_SHA = "0dbe9efe03aca8fc323197831190a50d573f20624f5651abe601a06394a0bcfe"
E1_INVENTORY_SHA = "392066c7a23408e97f0f2bcd3e2a530b167e596c9b382d999d959ba49abb7eb6"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
FORBIDDEN_TERMS = ("current leaderboard", "objective capability", "universally preferred", "best model", "causes better performance")
FORBIDDEN_E3 = re.compile(r"\be3\b", re.IGNORECASE)
REQUIRED_INTERPRETATION = {
    "data-population": "The source and population are historical and frozen; this report is not a current system comparison.",
    "method": "The report consumes accepted frozen E1 results and E2 ranking-robustness records. It does not fit an estimator or calculate new intervals.",
    "heterogeneity": "The English subgroup comparison preserves the accepted historical-population boundary and does not support causal interpretation.",
    "limitations": "The evidence concerns one frozen historical population and does not establish current quality, causality, or external generalization.",
}
FORBIDDEN_AFFIRMATIVE_DRIFT = (
    "establishes current model quality",
    "establish current model quality",
    "supports a causal interpretation",
    "support a causal interpretation",
    "establishes causality",
    "establish causality",
    "proves causality",
    "prove causality",
    "objective model capability",
    "current-model superiority",
    "current model superiority",
)


class PublicationVerificationError(ValueError):
    """Raised when a persisted publication bundle fails closed verification."""

    def __init__(self, stage: str, reason: str) -> None:
        self.stage = stage
        self.reason = reason
        super().__init__(f"{stage}: {reason}")


@dataclass(frozen=True)
class PublicationVerificationResult:
    publication_instance_id: str
    publication_spec_id: str
    producer_git_sha: str
    payload_inventory_sha256: str
    bundle_path: Path


def _fail(stage: str, reason: str) -> None:
    raise PublicationVerificationError(stage, reason)


def _strict_equal(expected: Any, actual: Any) -> bool:
    if type(expected) is not type(actual):
        return False
    if isinstance(expected, dict):
        return set(expected) == set(actual) and all(_strict_equal(expected[key], actual[key]) for key in expected)
    if isinstance(expected, list):
        return len(expected) == len(actual) and all(_strict_equal(a, b) for a, b in zip(expected, actual))
    return expected == actual


def _canonical_json_bytes(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8") + b"\n"
    except (TypeError, ValueError) as exc:
        raise PublicationVerificationError("json", f"canonical serialization failed: {exc}") from exc


def _no_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant: {value}")


def _is_reparse(path: Path) -> bool:
    if path.is_symlink():
        return True
    junction = getattr(path, "is_junction", None)
    if callable(junction):
        try:
            if junction():
                return True
        except OSError:
            return True
    try:
        attrs = os.lstat(path).st_file_attributes
    except FileNotFoundError:
        return False
    except AttributeError:
        return False
    except OSError:
        return True
    return bool(attrs & 0x40000000)


def _root(value: str | Path) -> Path:
    try:
        requested = Path(os.path.abspath(os.fspath(Path(value).expanduser())))
    except (OSError, TypeError, ValueError) as exc:
        raise PublicationVerificationError("filesystem", f"invalid bundle path: {exc}") from exc
    if _is_reparse(requested) or not requested.is_dir():
        _fail("filesystem", "bundle root must be an ordinary directory")
    try:
        if requested.resolve(strict=False) != requested:
            _fail("filesystem", "bundle root must not resolve through a link or reparse point")
    except OSError as exc:
        raise PublicationVerificationError("filesystem", f"unable to normalize bundle path: {exc}") from exc
    return requested


def _closed_world(root: Path) -> None:
    if _is_reparse(root):
        _fail("filesystem", "bundle root is a reparse point")
    actual: set[str] = set()
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        if _is_reparse(path):
            _fail("filesystem", f"reparse entry is forbidden: {relative}")
        if path.is_dir():
            if relative != "figures":
                _fail("filesystem", f"unexpected directory: {relative}")
        elif path.is_file():
            if Path(relative).is_absolute() or "\\" in relative or any(part in {".", ".."} for part in Path(relative).parts):
                _fail("filesystem", f"unsafe relative path: {relative}")
            actual.add(relative)
        else:
            _fail("filesystem", f"non-regular entry: {relative}")
    if actual != set(ALL_PATHS):
        _fail("filesystem", f"bundle file set mismatch: {sorted(actual)}")


def _read_json(root: Path, name: str) -> tuple[dict[str, Any], bytes]:
    path = root / name
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise PublicationVerificationError("json", f"unable to read {name}: {exc}") from exc
    if b"\r" in raw or not raw.endswith(b"\n") or raw.endswith(b"\n\n"):
        _fail("json", f"{name} must use exactly one final LF")
    try:
        value = json.loads(raw[:-1].decode("utf-8"), object_pairs_hook=_no_duplicate_pairs, parse_constant=_reject_constant)
    except (UnicodeError, ValueError, json.JSONDecodeError) as exc:
        raise PublicationVerificationError("json", f"{name} is invalid canonical JSON: {exc}") from exc
    if not isinstance(value, dict) or raw != _canonical_json_bytes(value):
        _fail("json", f"{name} is not canonical JSON")
    return value, raw


def _expected_spec() -> dict[str, Any]:
    return {
        "publication_schema_version": 1,
        "publication_contract_version": 1,
        "source_e0_identity": {
            "dataset": FROZEN_SOURCE.dataset, "revision": FROZEN_SOURCE.revision,
            "source_file_sha256": FROZEN_SOURCE.file_sha256, "source_snapshot_id": FROZEN_SOURCE.snapshot_id,
            "split": FROZEN_SOURCE.split, "row_count": 33000, "model_count": 20,
        },
        "source_e1_identity": {
            "bundle_name": "formal-research-v1", "bundle_schema_version": 1,
            "payload_inventory_sha256": E1_INVENTORY_SHA, "primary_run_id": FROZEN_RUNS[0].run_id,
            "s6_run_id": next(run.run_id for run in FROZEN_RUNS if run.analysis == "S6-English"), "formal_run_count": 9,
        },
        "source_e2_identity": {
            "artifact_instance_id": E2_INSTANCE_ID, "derivation_spec_id": E2_DERIVATION_SPEC_ID,
            "payload_inventory_sha256": E2_INVENTORY_SHA,
        },
        "section_ids": list(SECTION_IDS), "table_ids": list(TABLE_IDS), "figure_roles": list(FIGURE_ROLES),
        "transform_ids": list(TRANSFORM_IDS), "display_format_ids": list(DISPLAY_FORMAT_IDS),
    }


def _verify_authorities() -> Any:
    try:
        verify_frozen_bundle()
    except Exception as exc:
        _fail("authorities", f"E1 verifier failed: {exc}")
    e2_root = Path(__file__).resolve().parents[1] / "artifacts" / "phase-5" / E2_INSTANCE_ID
    try:
        verify_ranking_robustness_artifact(e2_root)
    except Exception as exc:
        _fail("authorities", f"E2 verifier failed: {exc}")
    try:
        return load_frozen_formal_research()
    except (FrozenResultsError, OSError, ValueError) as exc:
        _fail("authorities", f"unable to load frozen E1 values: {exc}")


def _verify_manifest(manifest: Mapping[str, Any], expected_spec: Mapping[str, Any]) -> None:
    expected_keys = {"publication_schema_version", "publication_contract_version", "publication_spec_id", "publication_spec", "producer_git_sha", "publication_instance_id", "payload_inventory_sha256", "source_e0_identity", "source_e1_identity", "source_e2_identity", "non_manifest_payload_inventory"}
    if set(manifest) != expected_keys:
        _fail("manifest", "manifest key set is not canonical")
    if manifest["publication_schema_version"] != 1 or manifest["publication_contract_version"] != 1:
        _fail("manifest", "publication versions are not frozen")
    if not isinstance(manifest["publication_spec"], dict) or not _strict_equal(expected_spec, manifest["publication_spec"]):
        _fail("manifest", "embedded publication specification differs from verifier-owned accepted spec")
    spec_id = hashlib.sha256(_canonical_json_bytes(expected_spec)).hexdigest()
    if spec_id != "62503b0a94b7658c6c0b48b8b9d9b7e43df2e963039b999d9a87a2af760ba400" or manifest["publication_spec_id"] != spec_id:
        _fail("manifest", "publication_spec_id does not match accepted specification")
    if not isinstance(manifest["producer_git_sha"], str) or SHA1_RE.fullmatch(manifest["producer_git_sha"]) is None:
        _fail("manifest", "producer_git_sha is not a lowercase 40-character Git identity")
    for key in ("publication_instance_id", "payload_inventory_sha256"):
        if not isinstance(manifest[key], str) or SHA256_RE.fullmatch(manifest[key]) is None:
            _fail("manifest", f"{key} is not a lowercase SHA-256")
    for key in ("source_e0_identity", "source_e1_identity", "source_e2_identity"):
        if not _strict_equal(manifest[key], expected_spec[key]):
            _fail("manifest", f"{key} differs from accepted authority")


def _inventory(root: Path) -> tuple[dict[str, Any], ...]:
    entries = []
    for relative in sorted(NON_MANIFEST_PATHS):
        data = (root / relative).read_bytes()
        entries.append({"path": relative, "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    return tuple(entries)


def _markdown_display(value: Any, fmt: str) -> str:
    if fmt == "integer.v1":
        if isinstance(value, bool) or not isinstance(value, int):
            _fail("report", "integer display value has invalid type")
        return str(value)
    if fmt == "decimal6_half_even.v1":
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            _fail("report", "decimal display value is not finite")
        return format(Decimal(str(value)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_EVEN), "f")
    if fmt in {"label.v1", "markdown_text.v1", "sha256.v1"}:
        return str(value)
    _fail("report", f"unknown display format: {fmt}")


def _markdown_table(table: Mapping[str, Any]) -> str:
    lines = [f"### {table['title']}", "", "| " + " | ".join(c["label"] for c in table["columns"]) + " |", "| " + " | ".join("---" for _ in table["columns"]) + " |"]
    for row in table["rows"]:
        lines.append("| " + " | ".join(_markdown_display(row["values"][column["column_id"]], column["display_format_id"]).replace("|", "\\|") for column in table["columns"]) + " |")
    return "\n".join(lines) + "\n"


def _table_expected(bundle: Any, cross: Mapping[str, Any]) -> list[dict[str, Any]]:
    primary_run = bundle.runs[0]
    point = primary_run.point_estimate
    summary = primary_run.bootstrap_summary
    model_ids = tuple(point["model_ids"])
    order = sorted(range(len(model_ids)), key=lambda index: point["derived_rank"][index])
    primary_rows = []
    for index in order:
        model_id = model_ids[index]
        rank_values = summary["rank_summary"][model_id]
        interval = summary["score_intervals"][model_id]
        values = {"point_rank": point["derived_rank"][index], "model_id": model_id, "point_score": float(point["latent_scores"][index]), "score_ci_low": float(interval[0]), "score_ci_high": float(interval[1]), "rank_median": float(rank_values["median_rank"]), "rank_ci_low": float(rank_values["lower_rank_quantile"]), "rank_ci_high": float(rank_values["upper_rank_quantile"]), "probability_rank_1": float(rank_values["probability_rank_1"])}
        claims = ["primary.score_uncertainty", "primary.rank_uncertainty"]
        if values["point_rank"] <= 3:
            claims.insert(0, "primary.top_three")
        primary_rows.append({"row_id": f"model:{model_id}", "values": values, "claim_ids": claims})
    robustness_rows = []
    cross_records = sorted(cross["records"], key=lambda item: int(item["primary_rank"]))
    by_analysis = {run.analysis: run.run_id for run in FROZEN_RUNS}
    for analysis in ANALYSIS_ORDER:
        run_id = by_analysis[analysis]
        for record in cross_records:
            values = {"analysis_label": analysis, "primary_rank": int(record["primary_rank"]), "model_id": str(record["model_id"]), "point_rank": int(record["rank_by_run"][run_id])}
            robustness_rows.append({"row_id": f"{analysis}:model:{record['model_id']}", "values": values, "claim_ids": ["robustness.point_ranks"]})
    s6_run = next(run for run in bundle.runs if run.spec.analysis == "S6-English")
    primary_by_model = dict(zip(model_ids, point["derived_rank"]))
    english_by_model = dict(zip(s6_run.point_estimate["model_ids"], s6_run.point_estimate["derived_rank"]))
    s6_rows = [{"row_id": f"model:{model_id}", "values": {"primary_rank": int(primary_by_model[model_id]), "model_id": model_id, "s6_rank": int(english_by_model[model_id])}, "claim_ids": ["s6.rank_comparison"]} for model_id in sorted(model_ids, key=lambda item: primary_by_model[item])]
    e0 = _expected_spec()["source_e0_identity"]
    e1 = _expected_spec()["source_e1_identity"]
    e2 = _expected_spec()["source_e2_identity"]
    provenance_values = (e0["dataset"], e0["revision"], e0["source_snapshot_id"], e0["source_file_sha256"], e1["bundle_name"], e1["payload_inventory_sha256"], e1["primary_run_id"], e1["s6_run_id"], e2["artifact_instance_id"], e2["derivation_spec_id"], e2["payload_inventory_sha256"])
    provenance_claims = (["provenance.e0_identity"] * 4) + (["provenance.e1_identity"] * 4) + (["provenance.e2_identity"] * 3)
    provenance_rows = [{"row_id": f"field:{field}", "values": {"field": field, "value": value}, "claim_ids": [claim]} for field, value, claim in zip(PROVENANCE_FIELDS, provenance_values, provenance_claims)]
    def table(table_id: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
        return {"table_id": table_id, "title": TABLE_TITLES[table_id], "columns": [{"column_id": c[0], "label": c[1], "value_type": c[2], "display_format_id": c[3]} for c in TABLE_SCHEMAS[table_id]], "rows": rows}
    return [table("primary-results", primary_rows), table("robustness-ranks", robustness_rows), table("english-subgroup-ranks", s6_rows), table("provenance", provenance_rows)]


def _pointer(authority: str, obj: str, **fields: Any) -> dict[str, Any]:
    value = {"authority": authority, "object": obj}
    value.update(fields)
    return value


def _expected_claims(tables: list[dict[str, Any]], cross: Mapping[str, Any]) -> list[dict[str, Any]]:
    primary, robustness, s6, provenance = tables
    def cells(table: Mapping[str, Any], columns: tuple[str, ...], rows: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        selected = table["rows"] if rows is None else rows
        return [{"output_path": "tables.json", "kind": "table_cell", "table_id": table["table_id"], "row_id": row["row_id"], "column_id": column, "expected_value": row["values"][column]} for row in selected for column in columns]
    def report(claim_id: str, section: str, table: Mapping[str, Any] | None = None, text: str | None = None) -> dict[str, Any]:
        binding = {"output_path": "report.md", "kind": "report_claim", "section_id": section, "anchor_id": f"publication-claim:{claim_id}", "display_format_id": "markdown_text.v1", "expected_text_anchor": f"<!-- publication-claim:{claim_id} -->"}
        if text is not None:
            binding["expected_text"] = text
        else:
            binding["table_id"] = table["table_id"]
            binding["table_sha256"] = hashlib.sha256(_markdown_table(table).encode("utf-8")).hexdigest()
        return binding
    top_rows = primary["rows"][:3]
    top_text = "The first three Primary point ranks are " + ", ".join(f"{r['values']['model_id']} (point rank {r['values']['point_rank']})" for r in top_rows) + "."
    primary_id = FROZEN_RUNS[0].run_id
    s6_id = next(run.run_id for run in FROZEN_RUNS if run.analysis == "S6-English")
    claims = [
        {"claim_id": "provenance.e0_identity", "claim_kind": "provenance", "source_authority": "E0", "source_pointers": [_pointer("E0", "source_identity", field=f) for f in ("dataset", "revision", "source_snapshot_id", "source_file_sha256")], "transform_chain": ["identity.v1"], "scientific_values": [r["values"]["value"] for r in provenance["rows"][:4]], "render_bindings": cells(provenance, ("field", "value"), provenance["rows"][:4]) + [report("provenance.e0_identity", "methods-provenance", provenance)]},
        {"claim_id": "provenance.e1_identity", "claim_kind": "provenance", "source_authority": "E1", "source_pointers": [_pointer("E1", "bundle_identity", field=f) for f in ("bundle_name", "payload_inventory_sha256", "primary_run_id", "s6_run_id")], "transform_chain": ["identity.v1"], "scientific_values": [r["values"]["value"] for r in provenance["rows"][4:8]], "render_bindings": cells(provenance, ("field", "value"), provenance["rows"][4:8]) + [report("provenance.e1_identity", "methods-provenance", provenance)]},
        {"claim_id": "provenance.e2_identity", "claim_kind": "provenance", "source_authority": "E2", "source_pointers": [_pointer("E2", "artifact_identity", field=f) for f in ("artifact_instance_id", "derivation_spec_id", "payload_inventory_sha256")], "transform_chain": ["identity.v1"], "scientific_values": [r["values"]["value"] for r in provenance["rows"][8:]], "render_bindings": cells(provenance, ("field", "value"), provenance["rows"][8:]) + [report("provenance.e2_identity", "methods-provenance", provenance)]},
        {"claim_id": "primary.top_three", "claim_kind": "quantitative", "source_authority": "E1", "source_pointers": [_pointer("E1", "run_result", run_id=primary_id, document="point_estimate", field="derived_rank")], "transform_chain": ["select.primary_top3.v1", "order.primary_rank.v1"], "scientific_values": [{"model_id": r["values"]["model_id"], "point_rank": r["values"]["point_rank"]} for r in top_rows], "render_bindings": cells(primary, ("point_rank", "model_id"), top_rows) + [report("primary.top_three", "primary-result", text=top_text)]},
        {"claim_id": "primary.score_uncertainty", "claim_kind": "quantitative", "source_authority": "E1", "source_pointers": [_pointer("E1", "run_result", run_id=primary_id, document="point_estimate", field="latent_scores"), _pointer("E1", "run_result", run_id=primary_id, document="bootstrap_summary", field="score_intervals")], "transform_chain": ["select.primary_rows.v1", "project.table_columns.v1"], "scientific_values": [{"model_id": r["values"]["model_id"], "point_score": r["values"]["point_score"], "score_ci_low": r["values"]["score_ci_low"], "score_ci_high": r["values"]["score_ci_high"]} for r in primary["rows"]], "render_bindings": cells(primary, ("model_id", "point_score", "score_ci_low", "score_ci_high")) + [report("primary.score_uncertainty", "uncertainty", primary)]},
        {"claim_id": "primary.rank_uncertainty", "claim_kind": "quantitative", "source_authority": "E1", "source_pointers": [_pointer("E1", "run_result", run_id=primary_id, document="point_estimate", field="derived_rank"), _pointer("E1", "run_result", run_id=primary_id, document="bootstrap_summary", field="rank_summary")], "transform_chain": ["select.primary_rows.v1", "project.table_columns.v1"], "scientific_values": [{"model_id": r["values"]["model_id"], "point_rank": r["values"]["point_rank"], "rank_median": r["values"]["rank_median"], "rank_ci_low": r["values"]["rank_ci_low"], "rank_ci_high": r["values"]["rank_ci_high"], "probability_rank_1": r["values"]["probability_rank_1"]} for r in primary["rows"]], "render_bindings": cells(primary, ("model_id", "point_rank", "rank_median", "rank_ci_low", "rank_ci_high", "probability_rank_1")) + [report("primary.rank_uncertainty", "uncertainty", primary)]},
        {"claim_id": "robustness.point_ranks", "claim_kind": "quantitative", "source_authority": "E2", "source_pointers": [_pointer("E2", "metric", metric="cross_specification", field="record_set")], "transform_chain": ["select.robustness_rows.v1", "order.analysis_then_primary_rank.v1", "project.table_columns.v1"], "scientific_values": [{"analysis_label": r["values"]["analysis_label"], "model_id": r["values"]["model_id"], "primary_rank": r["values"]["primary_rank"], "point_rank": r["values"]["point_rank"]} for r in robustness["rows"]], "render_bindings": cells(robustness, ("analysis_label", "primary_rank", "model_id", "point_rank")) + [report("robustness.point_ranks", "robustness", robustness)]},
        {"claim_id": "s6.rank_comparison", "claim_kind": "quantitative", "source_authority": "E1", "source_pointers": [_pointer("E1", "run_result", run_id=primary_id, document="point_estimate", field="derived_rank"), _pointer("E1", "run_result", run_id=s6_id, document="point_estimate", field="derived_rank")], "transform_chain": ["select.s6_rows.v1", "order.primary_rank.v1", "project.table_columns.v1"], "scientific_values": [{"model_id": r["values"]["model_id"], "primary_rank": r["values"]["primary_rank"], "s6_rank": r["values"]["s6_rank"]} for r in s6["rows"]], "render_bindings": cells(s6, ("primary_rank", "model_id", "s6_rank")) + [report("s6.rank_comparison", "heterogeneity", s6)]},
    ]
    return claims


def _report_section(report: str, section_id: str) -> str:
    marker = f"<!-- publication-section:{section_id} -->"
    start = report.find(marker)
    if start < 0:
        _fail("report", f"missing section {section_id}")
    positions = [report.find(f"<!-- publication-section:{other} -->", start + len(marker)) for other in SECTION_IDS if other != section_id]
    end = min((pos for pos in positions if pos >= 0), default=len(report))
    return report[start:end]


def _verify_tables(tables_doc: Mapping[str, Any], expected: list[dict[str, Any]], spec_id: str) -> None:
    if set(tables_doc) != {"publication_schema_version", "publication_spec_id", "tables"} or tables_doc["publication_schema_version"] != 1 or tables_doc["publication_spec_id"] != spec_id:
        _fail("tables", "top-level schema or identity mismatch")
    if not isinstance(tables_doc["tables"], list) or len(tables_doc["tables"]) != 4 or [t.get("table_id") for t in tables_doc["tables"]] != list(TABLE_IDS):
        _fail("tables", "table registry is not canonical")
    if not _strict_equal(tables_doc["tables"], expected):
        _fail("tables", "table values/schema/order differ from frozen authorities")


def _verify_traceability(trace: Mapping[str, Any], expected_claims: list[dict[str, Any]], spec_id: str, tables: list[dict[str, Any]], report: str) -> None:
    if set(trace) != {"publication_schema_version", "publication_spec_id", "claims", "figure_bindings"} or trace["publication_schema_version"] != 1 or trace["publication_spec_id"] != spec_id:
        _fail("traceability", "top-level schema or identity mismatch")
    if not _strict_equal(trace.get("claims"), expected_claims):
        _fail("traceability", "claims do not match independently reconstructed values/bindings")
    figure_claims = {"primary_preference": ["primary.top_three", "primary.score_uncertainty"], "rank_uncertainty": ["primary.rank_uncertainty"], "robustness_ranks": ["robustness.point_ranks"], "s6_heterogeneity": ["s6.rank_comparison"]}
    figure_types = {"primary_preference": "PrimaryFigureSpec", "rank_uncertainty": "RankUncertaintyFigureSpec", "robustness_ranks": "RobustnessFigureSpec", "s6_heterogeneity": "HeterogeneityFigureSpec"}
    expected_figures = [{"output_path": f"figures/{role}.png", "kind": "figure_semantic", "figure_role": role, "transform_id": "figure.accepted_spec.v1", "phase3_spec_type": figure_types[role], "source_claim_ids": figure_claims[role]} for role in FIGURE_ROLES]
    if not _strict_equal(trace.get("figure_bindings"), expected_figures):
        _fail("figures", "figure semantic registry differs from accepted Phase 3 mapping")
    if report.count("<!-- publication-claim:") != 8:
        _fail("report", "report does not contain exactly eight claim anchors")
    for claim in expected_claims:
        for binding in claim["render_bindings"]:
            if binding["kind"] == "report_claim":
                section = _report_section(report, binding["section_id"])
                if binding["expected_text_anchor"] not in section or binding["anchor_id"] not in section:
                    _fail("report", f"claim anchor is outside declared section: {claim['claim_id']}")
                if "expected_text" in binding and binding["expected_text"] not in section:
                    _fail("report", f"claim text is not rendered: {claim['claim_id']}")
                if "table_id" in binding:
                    table = next(t for t in tables if t["table_id"] == binding["table_id"])
                    rendered = _markdown_table(table)
                    if hashlib.sha256(rendered.encode("utf-8")).hexdigest() != binding["table_sha256"] or rendered not in section:
                        _fail("report", f"canonical table is not rendered in its declared section: {claim['claim_id']}")


def verify_publication_bundle(path: str | Path) -> PublicationVerificationResult:
    root = _root(path)
    _closed_world(root)
    manifest, manifest_raw = _read_json(root, "manifest.json")
    expected_spec = _expected_spec()
    _verify_manifest(manifest, expected_spec)
    # Authority checks are deliberately separate from publication payload parsing.
    bundle = _verify_authorities()
    e2_path = Path(__file__).resolve().parents[1] / "artifacts" / "phase-5" / E2_INSTANCE_ID / "cross_specification.json"
    cross_raw = e2_path.read_bytes()
    if len(cross_raw) != E2_CROSS_SIZE or hashlib.sha256(cross_raw).hexdigest() != E2_CROSS_SHA:
        _fail("authorities", "accepted E2 cross_specification bytes do not match frozen identity")
    try:
        cross = json.loads(cross_raw.decode("utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise PublicationVerificationError("authorities", f"E2 cross_specification is invalid: {exc}") from exc
    if cross.get("artifact_instance_id") != E2_INSTANCE_ID or cross.get("derivation_spec_id") != E2_DERIVATION_SPEC_ID or cross.get("metric") != "cross_specification" or not isinstance(cross.get("records"), list):
        _fail("authorities", "E2 cross_specification identity/schema mismatch")
    tables_doc, _ = _read_json(root, "tables.json")
    trace_doc, _ = _read_json(root, "traceability.json")
    expected_tables = _table_expected(bundle, cross)
    _verify_tables(tables_doc, expected_tables, manifest["publication_spec_id"])
    report_raw = (root / "report.md").read_bytes()
    if b"\r" in report_raw or not report_raw.endswith(b"\n") or report_raw.endswith(b"\n\n"):
        _fail("report", "report.md must be UTF-8 text with exactly one final LF")
    try:
        report = report_raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PublicationVerificationError("report", f"report.md is not UTF-8: {exc}") from exc
    if not report.startswith("# Frozen Historical Arena Preference Report\n") or "estimated preference under the frozen historical Arena population" not in report:
        _fail("report", "historical report title or interpretation boundary is missing")
    lowered_report = report.casefold()
    if FORBIDDEN_E3.search(report) or any(term in lowered_report for term in FORBIDDEN_TERMS):
        _fail("report", "forbidden interpretation or E3 wording is present")
    section_positions = []
    for section_id in SECTION_IDS:
        marker = f"<!-- publication-section:{section_id} -->"
        position = report.find(marker)
        if report.count(marker) != 1 or position < 0:
            _fail("report", "section anchors are missing or duplicated")
        section_positions.append(position)
    if section_positions != sorted(section_positions):
        _fail("report", "report sections are out of canonical order")
    for section_id, required_text in REQUIRED_INTERPRETATION.items():
        if required_text not in _report_section(report, section_id):
            _fail("report", f"interpretation boundary is missing from {section_id}")
    if any(term in lowered_report for term in FORBIDDEN_AFFIRMATIVE_DRIFT):
        _fail("report", "affirmative current-quality or causal interpretation drift is present")
    expected_claims = _expected_claims(expected_tables, cross)
    _verify_traceability(trace_doc, expected_claims, manifest["publication_spec_id"], expected_tables, report)
    inventory = _inventory(root)
    if manifest.get("non_manifest_payload_inventory") != list(inventory):
        _fail("inventory", "manifest inventory differs from actual payload bytes")
    inventory_hash = hashlib.sha256(_canonical_json_bytes(list(inventory))).hexdigest()
    if manifest["payload_inventory_sha256"] != inventory_hash:
        _fail("inventory", "payload_inventory_sha256 does not match actual payload bytes")
    instance_preimage = {"publication_schema_version": 1, "publication_spec_id": manifest["publication_spec_id"], "producer_git_sha": manifest["producer_git_sha"], "payload_inventory_sha256": inventory_hash}
    instance_id = hashlib.sha256(_canonical_json_bytes(instance_preimage)).hexdigest()
    if manifest["publication_instance_id"] != instance_id or root.name != instance_id:
        _fail("identity", "publication_instance_id or bundle directory name is not canonical")
    return PublicationVerificationResult(instance_id, manifest["publication_spec_id"], manifest["producer_git_sha"], inventory_hash, root)


__all__ = ["PublicationVerificationError", "PublicationVerificationResult", "verify_publication_bundle"]
