"""Versioned, auditable analysis populations derived from canonical battles."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

import pandas as pd

from src.battle_contract import CanonicalOutcome


POPULATION_SPEC_SCHEMA_VERSION = 2


class ExclusionReason(str, Enum):
    SOURCE_RECORD_INVALID = "SOURCE_RECORD_INVALID"
    INVALID_MODEL_FIELDS = "INVALID_MODEL_FIELDS"
    SAME_MODEL = "SAME_MODEL"
    INVALID_OUTCOME = "INVALID_OUTCOME"
    INVALID_CONVERSATION_A = "INVALID_CONVERSATION_A"
    INVALID_CONVERSATION_B = "INVALID_CONVERSATION_B"
    MISSING_USER_TURN_A = "MISSING_USER_TURN_A"
    MISSING_USER_TURN_B = "MISSING_USER_TURN_B"
    MISSING_ASSISTANT_TURN_A = "MISSING_ASSISTANT_TURN_A"
    MISSING_ASSISTANT_TURN_B = "MISSING_ASSISTANT_TURN_B"
    PROMPT_PAIR_MISMATCH = "PROMPT_PAIR_MISMATCH"
    INVALID_TIMESTAMP = "INVALID_TIMESTAMP"
    MISSING_JUDGE = "MISSING_JUDGE"
    MISSING_LANGUAGE = "MISSING_LANGUAGE"
    INVALID_ANONY_FLAG = "INVALID_ANONY_FLAG"
    NON_ANONYMOUS_BATTLE = "NON_ANONYMOUS_BATTLE"
    OUTCOME_NOT_ALLOWED = "OUTCOME_NOT_ALLOWED"
    EXACT_DUPLICATE_EXCLUDED = "EXACT_DUPLICATE_EXCLUDED"


ALL_CANONICAL_VALID_OUTCOMES = frozenset({
    CanonicalOutcome.MODEL_A_WIN.value,
    CanonicalOutcome.MODEL_B_WIN.value,
    CanonicalOutcome.TIE.value,
    CanonicalOutcome.TIE_BOTHBAD.value,
})
LEGACY_SCORE_OUTCOMES = frozenset({
    CanonicalOutcome.MODEL_A_WIN.value,
    CanonicalOutcome.MODEL_B_WIN.value,
    CanonicalOutcome.TIE.value,
})


@dataclass(frozen=True)
class PopulationSpec:
    """Machine-readable policy for selecting a canonical analysis population."""

    population_id: str
    population_spec_version: int = POPULATION_SPEC_SCHEMA_VERSION
    require_source_record_valid: bool = True
    require_judge: bool = False
    require_language: bool = False
    require_anonymous: bool = False
    allowed_outcomes: frozenset[str] = ALL_CANONICAL_VALID_OUTCOMES
    exclude_exact_duplicates: bool = False
    description: str = ""

    def __post_init__(self) -> None:
        if not self.population_id.strip():
            raise ValueError("population_id must not be empty")
        if self.population_spec_version <= 0:
            raise ValueError("population_spec_version must be positive")
        object.__setattr__(self, "allowed_outcomes", frozenset(self.allowed_outcomes))


@dataclass(frozen=True)
class PopulationResult:
    """Population rows, a one-row-per-battle audit, and aggregate summary."""

    spec: PopulationSpec
    eligible: pd.DataFrame
    audit: pd.DataFrame
    summary: dict[str, Any]


BASE_RESEARCH = PopulationSpec(
    population_id="base_research",
    require_anonymous=True,
    allowed_outcomes=ALL_CANONICAL_VALID_OUTCOMES,
    description="Canonical structurally valid battles, including both tie types.",
)
LEGACY_SCORE = PopulationSpec(
    population_id="legacy_score",
    require_anonymous=True,
    allowed_outcomes=LEGACY_SCORE_OUTCOMES,
    description="Canonical battles supported by the legacy score-rate summary.",
)
JUDGE_CLUSTER_RESEARCH = PopulationSpec(
    population_id="judge_cluster_research",
    require_anonymous=True,
    require_judge=True,
    allowed_outcomes=ALL_CANONICAL_VALID_OUTCOMES,
    description="Base research battles with a source judge-cluster value.",
)
LANGUAGE_RESEARCH = PopulationSpec(
    population_id="language_research",
    require_anonymous=True,
    require_language=True,
    allowed_outcomes=ALL_CANONICAL_VALID_OUTCOMES,
    description="Base research battles with a source language label.",
)


_REQUIRED_COLUMNS = frozenset({
    "battle_id",
    "source_row_index",
    "source_record_valid",
    "model_fields_valid",
    "distinct_models",
    "outcome_valid",
    "canonical_outcome",
    "conversation_a_valid",
    "conversation_b_valid",
    "conversation_a_has_user",
    "conversation_b_has_user",
    "conversation_a_has_assistant",
    "conversation_b_has_assistant",
    "prompt_pair_consistent",
    "timestamp_valid",
    "judge_present",
    "language_present",
    "anony_valid",
    "anonymous_battle",
    "exact_duplicate",
})


def _flag(row: pd.Series, column: str) -> bool:
    value = row[column]
    return False if pd.isna(value) else bool(value)


def _canonical_invalid_reasons(row: pd.Series) -> list[ExclusionReason]:
    if _flag(row, "source_record_valid"):
        return []

    reasons = [ExclusionReason.SOURCE_RECORD_INVALID]
    model_fields_valid = _flag(row, "model_fields_valid")
    if not model_fields_valid:
        reasons.append(ExclusionReason.INVALID_MODEL_FIELDS)
    elif not _flag(row, "distinct_models"):
        reasons.append(ExclusionReason.SAME_MODEL)

    if not _flag(row, "outcome_valid"):
        reasons.append(ExclusionReason.INVALID_OUTCOME)

    conversation_a_valid = _flag(row, "conversation_a_valid")
    conversation_b_valid = _flag(row, "conversation_b_valid")
    if not conversation_a_valid:
        reasons.append(ExclusionReason.INVALID_CONVERSATION_A)
    else:
        if not _flag(row, "conversation_a_has_user"):
            reasons.append(ExclusionReason.MISSING_USER_TURN_A)
        if not _flag(row, "conversation_a_has_assistant"):
            reasons.append(ExclusionReason.MISSING_ASSISTANT_TURN_A)
    if not conversation_b_valid:
        reasons.append(ExclusionReason.INVALID_CONVERSATION_B)
    else:
        if not _flag(row, "conversation_b_has_user"):
            reasons.append(ExclusionReason.MISSING_USER_TURN_B)
        if not _flag(row, "conversation_b_has_assistant"):
            reasons.append(ExclusionReason.MISSING_ASSISTANT_TURN_B)

    if (
        conversation_a_valid
        and conversation_b_valid
        and _flag(row, "conversation_a_has_user")
        and _flag(row, "conversation_b_has_user")
        and not _flag(row, "prompt_pair_consistent")
    ):
        reasons.append(ExclusionReason.PROMPT_PAIR_MISMATCH)

    if not _flag(row, "timestamp_valid"):
        reasons.append(ExclusionReason.INVALID_TIMESTAMP)
    return reasons


def _validate_canonical_columns(canonical_df: pd.DataFrame) -> None:
    missing = sorted(_REQUIRED_COLUMNS.difference(canonical_df.columns))
    if missing:
        raise ValueError(f"canonical dataframe is missing required columns: {missing}")


def apply_population(canonical_df: pd.DataFrame, spec: PopulationSpec) -> PopulationResult:
    """Apply ``spec`` without mutating or reordering a canonical dataframe.

    Every input battle produces exactly one audit row. ``exclusion_reasons`` is
    an ordered tuple of stable codes; reason counts overlap when one battle has
    multiple reasons and therefore do not sum to the excluded-row count.
    """
    _validate_canonical_columns(canonical_df)
    audit_rows: list[dict[str, object]] = []
    eligible_mask: list[bool] = []

    for _, row in canonical_df.iterrows():
        reasons = _canonical_invalid_reasons(row) if spec.require_source_record_valid else []
        if spec.require_judge and not _flag(row, "judge_present"):
            reasons.append(ExclusionReason.MISSING_JUDGE)
        if spec.require_language and not _flag(row, "language_present"):
            reasons.append(ExclusionReason.MISSING_LANGUAGE)
        if spec.require_anonymous:
            if not _flag(row, "anony_valid"):
                reasons.append(ExclusionReason.INVALID_ANONY_FLAG)
            elif not _flag(row, "anonymous_battle"):
                reasons.append(ExclusionReason.NON_ANONYMOUS_BATTLE)
        outcome = row["canonical_outcome"]
        if outcome == CanonicalOutcome.INVALID_UNKNOWN.value or outcome not in spec.allowed_outcomes:
            reasons.append(ExclusionReason.OUTCOME_NOT_ALLOWED)
        if spec.exclude_exact_duplicates and _flag(row, "exact_duplicate"):
            reasons.append(ExclusionReason.EXACT_DUPLICATE_EXCLUDED)

        exclusion_reasons = tuple(reason.value for reason in reasons)
        eligible = not exclusion_reasons
        eligible_mask.append(eligible)
        audit_rows.append({
            "battle_id": row["battle_id"],
            "source_row_index": row["source_row_index"],
            "population_id": spec.population_id,
            "eligible": eligible,
            "exclusion_reasons": exclusion_reasons,
        })

    audit = pd.DataFrame(audit_rows, index=canonical_df.index)
    eligible = canonical_df.loc[eligible_mask].copy()
    reason_counts: dict[str, int] = {}
    for reasons in audit["exclusion_reasons"]:
        for reason in reasons:
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
    input_rows = len(canonical_df)
    eligible_rows = len(eligible)
    summary = {
        "population_id": spec.population_id,
        "population_spec_version": spec.population_spec_version,
        "input_rows": input_rows,
        "eligible_rows": eligible_rows,
        "excluded_rows": input_rows - eligible_rows,
        "eligibility_rate": eligible_rows / input_rows if input_rows else 0.0,
        "exclusion_reason_counts": reason_counts,
    }
    return PopulationResult(spec=spec, eligible=eligible, audit=audit, summary=summary)
