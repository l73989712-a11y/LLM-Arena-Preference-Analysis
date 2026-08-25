"""Deterministic, manifest-addressable views derived from ``base_research``.

The historical base population remains governed by population spec schema v2.
Sensitivity views have their own schema and are applied only to the already
eligible base population.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from src.population import (
    ALL_CANONICAL_VALID_OUTCOMES,
    BASE_RESEARCH,
    PopulationResult,
    PopulationSpec,
)


POPULATION_VIEW_SCHEMA_VERSION = 1
BASE_POPULATION_ID = BASE_RESEARCH.population_id
BASE_POPULATION_SPEC_VERSION = BASE_RESEARCH.population_spec_version

S4_POPULATION_ID = "base_research_no_repeated_qid"
S5_GE10_POPULATION_ID = "base_research_pair_support_ge10"
S5_GE20_POPULATION_ID = "base_research_pair_support_ge20"
S5_GE50_POPULATION_ID = "base_research_pair_support_ge50"
S6_ENGLISH_POPULATION_ID = "base_research_language_en"


@dataclass(frozen=True)
class PopulationViewSpec:
    """Stable definition of one single-axis derived population view."""

    population_id: str
    view_type: str
    parameters: dict[str, Any]
    population_view_schema_version: int = POPULATION_VIEW_SCHEMA_VERSION
    base_population_id: str = BASE_POPULATION_ID
    base_population_spec_version: int = BASE_POPULATION_SPEC_VERSION

    def __post_init__(self) -> None:
        if not self.population_id.strip():
            raise ValueError("population_id must not be empty")
        if self.population_view_schema_version != POPULATION_VIEW_SCHEMA_VERSION:
            raise ValueError("unsupported population view schema version")
        if self.base_population_id != BASE_POPULATION_ID:
            raise ValueError("population views must derive from base_research")
        if self.base_population_spec_version != BASE_POPULATION_SPEC_VERSION:
            raise ValueError("population views require base_research spec v2")
        if not self.view_type.strip():
            raise ValueError("view_type must not be empty")
        object.__setattr__(self, "parameters", dict(self.parameters))

    def to_dict(self) -> dict[str, Any]:
        return {
            "population_id": self.population_id,
            "population_view_schema_version": self.population_view_schema_version,
            "base_population": {
                "population_id": self.base_population_id,
                "population_spec_version": self.base_population_spec_version,
            },
            "view": {
                "view_type": self.view_type,
                **dict(self.parameters),
            },
        }


@dataclass(frozen=True)
class PopulationViewResult:
    """Effective population plus provenance for a derived view."""

    spec: PopulationViewSpec
    population: PopulationResult
    support_audit: dict[str, Any] | None = None


def _view(
    population_id: str,
    view_type: str,
    parameters: dict[str, Any],
) -> PopulationViewSpec:
    return PopulationViewSpec(population_id, view_type, parameters)


S4_REPEATED_QID = _view(
    S4_POPULATION_ID,
    "exclude_repeated_question_groups",
    {
        "question_id_field": "question_id_raw",
        "missing_policy": "retain_not_grouped",
        "group_policy": "exclude_all_rows_when_count_gt_1",
    },
)
S5_PAIR_SUPPORT_GE10 = _view(
    S5_GE10_POPULATION_ID,
    "unordered_pair_support_threshold",
    {
        "pair_definition": "canonical_unordered_model_pair",
        "support_population": BASE_POPULATION_ID,
        "support_measure": "eligible_battle_count",
        "support_count_stage": "before_estimator_outcome_filter",
        "threshold_operator": ">=",
        "threshold": 10,
    },
)
S5_PAIR_SUPPORT_GE20 = _view(
    S5_GE20_POPULATION_ID,
    "unordered_pair_support_threshold",
    {
        "pair_definition": "canonical_unordered_model_pair",
        "support_population": BASE_POPULATION_ID,
        "support_measure": "eligible_battle_count",
        "support_count_stage": "before_estimator_outcome_filter",
        "threshold_operator": ">=",
        "threshold": 20,
    },
)
S5_PAIR_SUPPORT_GE50 = _view(
    S5_GE50_POPULATION_ID,
    "unordered_pair_support_threshold",
    {
        "pair_definition": "canonical_unordered_model_pair",
        "support_population": BASE_POPULATION_ID,
        "support_measure": "eligible_battle_count",
        "support_count_stage": "before_estimator_outcome_filter",
        "threshold_operator": ">=",
        "threshold": 50,
    },
)
S6_LANGUAGE_ENGLISH = _view(
    S6_ENGLISH_POPULATION_ID,
    "language_exact_match",
    {
        "language_field": "language_canonical",
        "language_value": "English",
    },
)


POPULATION_VIEWS: dict[str, PopulationViewSpec] = {
    spec.population_id: spec
    for spec in (
        S4_REPEATED_QID,
        S5_PAIR_SUPPORT_GE10,
        S5_PAIR_SUPPORT_GE20,
        S5_PAIR_SUPPORT_GE50,
        S6_LANGUAGE_ENGLISH,
    )
}


def population_view_for_id(population_id: str) -> PopulationViewSpec:
    """Return a registered view or raise a stable ``KeyError``."""
    try:
        return POPULATION_VIEWS[population_id]
    except KeyError as exc:
        raise KeyError(f"unknown population view: {population_id}") from exc


def derived_population_spec(view: PopulationViewSpec) -> PopulationSpec:
    """Create the effective spec consumed by estimator/bootstrap code."""
    return PopulationSpec(
        population_id=view.population_id,
        population_spec_version=POPULATION_VIEW_SCHEMA_VERSION,
        require_source_record_valid=False,
        allowed_outcomes=ALL_CANONICAL_VALID_OUTCOMES,
        description=f"Derived population view: {view.view_type}",
    )


def _nonblank(value: object) -> bool:
    if pd.isna(value):
        return False
    return bool(str(value).strip())


def _pair_key(row: pd.Series) -> tuple[str, str]:
    return tuple(sorted((str(row["model_a_id"]), str(row["model_b_id"]))))


def pair_support_audit(base_population: PopulationResult) -> dict[str, Any]:
    """Return aggregate outcome-blind support information for a base view."""
    frame = base_population.eligible
    if not {"model_a_id", "model_b_id"}.issubset(frame.columns):
        raise ValueError("base population is missing canonical model columns")
    counts = frame.apply(_pair_key, axis=1).value_counts()
    return {
        "eligible_rows": int(len(frame)),
        "qualifying_pair_count": int(len(counts)),
        "model_count": int(len(set(frame["model_a_id"]).union(frame["model_b_id"]))),
    }


def _apply_repeated_qid(frame: pd.DataFrame) -> tuple[pd.Series, dict[str, Any]]:
    if "question_id_raw" not in frame.columns:
        raise ValueError("base population is missing question_id_raw")
    valid = frame["question_id_raw"].map(_nonblank)
    # ``question_id_raw`` is already a canonical scalar identity. Whitespace
    # trimming is only for blank detection and must not alter that identity.
    counts = frame.loc[valid, "question_id_raw"].value_counts(dropna=False)
    repeated = set(counts[counts > 1].index)
    excluded = valid & frame["question_id_raw"].isin(repeated)
    return ~excluded, {
        "repeated_group_count": int(len(repeated)),
        "rows_excluded": int(excluded.sum()),
        "max_group_size": int(counts.max()) if len(counts) else 0,
    }


def _apply_pair_support(frame: pd.DataFrame, threshold: int) -> tuple[pd.Series, dict[str, Any]]:
    if threshold <= 0:
        raise ValueError("pair support threshold must be positive")
    pair_keys = frame.apply(_pair_key, axis=1)
    counts = pair_keys.value_counts()
    qualifying = set(counts[counts >= threshold].index)
    mask = pair_keys.isin(qualifying)
    return mask, {
        "threshold": threshold,
        "qualifying_pair_count": int(len(qualifying)),
        "excluded_pair_count": int(len(counts) - len(qualifying)),
    }


def apply_population_view(
    base_population: PopulationResult,
    view: PopulationViewSpec,
) -> PopulationViewResult:
    """Apply one registered view to BASE_RESEARCH-eligible rows only."""
    if base_population.spec.population_id != BASE_POPULATION_ID:
        raise ValueError("population view input must be base_research")
    if base_population.spec.population_spec_version != BASE_POPULATION_SPEC_VERSION:
        raise ValueError("population view input must use base_research spec v2")
    registered = population_view_for_id(view.population_id)
    if view.to_dict() != registered.to_dict():
        raise ValueError("population view does not match its registered definition")

    frame = base_population.eligible
    support_audit: dict[str, Any] | None = None
    if view.view_type == "exclude_repeated_question_groups":
        mask, support_audit = _apply_repeated_qid(frame)
    elif view.view_type == "unordered_pair_support_threshold":
        threshold = int(view.parameters["threshold"])
        mask, support_audit = _apply_pair_support(frame, threshold)
        support_audit["eligible_rows"] = int(len(frame))
        support_audit["model_count"] = int(len(set(frame["model_a_id"]).union(frame["model_b_id"])))
    elif view.view_type == "language_exact_match":
        field = view.parameters["language_field"]
        if field not in frame.columns:
            raise ValueError(f"base population is missing {field}")
        mask = frame[field].eq(view.parameters["language_value"])
        support_audit = {
            "eligible_rows": int(mask.sum()),
            "model_count": int(len(set(frame.loc[mask, "model_a_id"]).union(frame.loc[mask, "model_b_id"]))),
        }
    else:
        raise ValueError(f"unsupported population view type: {view.view_type}")

    effective_spec = derived_population_spec(view)
    effective = frame.loc[mask].copy()
    audit = base_population.audit.copy()
    audit["view_population_id"] = view.population_id
    audit["view_eligible"] = False
    audit.loc[effective.index, "view_eligible"] = True
    audit["view_exclusion_reason"] = ""
    audit.loc[~audit["view_eligible"], "view_exclusion_reason"] = view.view_type
    summary = {
        "population_id": view.population_id,
        "population_spec_version": POPULATION_VIEW_SCHEMA_VERSION,
        "population_view_schema_version": POPULATION_VIEW_SCHEMA_VERSION,
        "base_population_id": BASE_POPULATION_ID,
        "base_population_spec_version": BASE_POPULATION_SPEC_VERSION,
        "input_rows": int(len(frame)),
        "eligible_rows": int(len(effective)),
        "excluded_rows": int(len(frame) - len(effective)),
        "eligibility_rate": len(effective) / len(frame) if len(frame) else 0.0,
        "view": view.to_dict()["view"],
    }
    return PopulationViewResult(
        spec=view,
        population=PopulationResult(spec=effective_spec, eligible=effective, audit=audit, summary=summary),
        support_audit=support_audit,
    )
