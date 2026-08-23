from __future__ import annotations

from dataclasses import replace

import pandas as pd

from src.analysis import build_model_statistics
from src.battle_contract import SourceProvenance, canonicalize_battles
from src.population import (
    BASE_RESEARCH,
    JUDGE_CLUSTER_RESEARCH,
    LANGUAGE_RESEARCH,
    LEGACY_SCORE,
    POPULATION_SPEC_SCHEMA_VERSION,
    ExclusionReason,
    apply_population,
)


PROVENANCE = SourceProvenance(source_dataset="synthetic/population", source_revision="v1")


def _conversation(prompt: str = "prompt", response: str = "response") -> list[dict[str, str]]:
    return [
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": response},
    ]


def _row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "model_a": "model-a",
        "model_b": "model-b",
        "winner": "model_a",
        "conversation_a": _conversation(),
        "conversation_b": _conversation(),
        "tstamp": 0,
        "judge": "synthetic-cluster",
        "language": "English",
        "anony": True,
    }
    row.update(overrides)
    return row


def _canonical(rows: list[dict[str, object]], index: list[int] | None = None) -> pd.DataFrame:
    return canonicalize_battles(pd.DataFrame(rows, index=index), provenance=PROVENANCE)


def test_base_research_accepts_a_valid_canonical_battle() -> None:
    result = apply_population(_canonical([_row()]), BASE_RESEARCH)

    assert len(result.eligible) == 1
    assert result.audit.loc[0, "eligible"]
    assert result.audit.loc[0, "exclusion_reasons"] == ()


def test_named_populations_have_stable_ids_and_spec_versions() -> None:
    assert [spec.population_id for spec in (
        BASE_RESEARCH,
        LEGACY_SCORE,
        JUDGE_CLUSTER_RESEARCH,
        LANGUAGE_RESEARCH,
    )] == [
        "base_research",
        "legacy_score",
        "judge_cluster_research",
        "language_research",
    ]
    assert all(spec.population_spec_version == POPULATION_SPEC_SCHEMA_VERSION for spec in (
        BASE_RESEARCH,
        LEGACY_SCORE,
        JUDGE_CLUSTER_RESEARCH,
        LANGUAGE_RESEARCH,
    ))
    assert all(spec.require_anonymous for spec in (
        BASE_RESEARCH,
        LEGACY_SCORE,
        JUDGE_CLUSTER_RESEARCH,
        LANGUAGE_RESEARCH,
    ))


def test_anonymous_battle_is_required_by_formal_populations() -> None:
    result = apply_population(_canonical([_row(anony=True)]), BASE_RESEARCH)

    assert result.audit.loc[0, "eligible"]
    assert result.audit.loc[0, "exclusion_reasons"] == ()


def test_valid_non_anonymous_battle_has_explicit_exclusion_reason() -> None:
    result = apply_population(_canonical([_row(anony=False)]), BASE_RESEARCH)
    reasons = result.audit.loc[0, "exclusion_reasons"]

    assert not result.audit.loc[0, "eligible"]
    assert ExclusionReason.NON_ANONYMOUS_BATTLE.value in reasons
    assert ExclusionReason.INVALID_ANONY_FLAG.value not in reasons


def test_invalid_anony_flag_is_not_claimed_non_anonymous() -> None:
    result = apply_population(_canonical([_row(anony="unknown")]), BASE_RESEARCH)
    reasons = result.audit.loc[0, "exclusion_reasons"]

    assert not result.audit.loc[0, "eligible"]
    assert ExclusionReason.INVALID_ANONY_FLAG.value in reasons
    assert ExclusionReason.NON_ANONYMOUS_BATTLE.value not in reasons


def test_custom_population_can_skip_anonymous_requirement() -> None:
    custom = replace(
        BASE_RESEARCH,
        population_id="custom_non_anonymous",
        require_anonymous=False,
    )
    result = apply_population(_canonical([_row(anony=False)]), custom)

    assert result.audit.loc[0, "eligible"]
    assert result.audit.loc[0, "exclusion_reasons"] == ()


def test_canonical_invalidity_audit_preserves_multiple_granular_reasons() -> None:
    canonical = _canonical([
        _row(
            conversation_a=[{"role": "user", "content": "prompt"}],
            conversation_b=[{"role": "user", "content": "prompt"}],
            tstamp="not-a-timestamp",
        )
    ])
    result = apply_population(canonical, BASE_RESEARCH)
    reasons = result.audit.loc[0, "exclusion_reasons"]

    assert not result.audit.loc[0, "eligible"]
    assert ExclusionReason.SOURCE_RECORD_INVALID.value in reasons
    assert ExclusionReason.MISSING_ASSISTANT_TURN_A.value in reasons
    assert ExclusionReason.MISSING_ASSISTANT_TURN_B.value in reasons
    assert ExclusionReason.INVALID_TIMESTAMP.value in reasons


def test_missing_model_does_not_claim_same_model() -> None:
    reasons = apply_population(_canonical([_row(model_a=None)]), BASE_RESEARCH).audit.loc[0, "exclusion_reasons"]

    assert ExclusionReason.INVALID_MODEL_FIELDS.value in reasons
    assert ExclusionReason.SAME_MODEL.value not in reasons


def test_valid_same_model_ids_report_same_model_without_invalid_fields() -> None:
    reasons = apply_population(
        _canonical([_row(model_a="same-model", model_b="same-model")]), BASE_RESEARCH
    ).audit.loc[0, "exclusion_reasons"]

    assert ExclusionReason.SAME_MODEL.value in reasons
    assert ExclusionReason.INVALID_MODEL_FIELDS.value not in reasons


def test_malformed_conversation_does_not_claim_missing_turns_or_prompt_mismatch() -> None:
    reasons = apply_population(
        _canonical([_row(conversation_a="malformed")]), BASE_RESEARCH
    ).audit.loc[0, "exclusion_reasons"]

    assert ExclusionReason.INVALID_CONVERSATION_A.value in reasons
    assert ExclusionReason.MISSING_USER_TURN_A.value not in reasons
    assert ExclusionReason.MISSING_ASSISTANT_TURN_A.value not in reasons
    assert ExclusionReason.PROMPT_PAIR_MISMATCH.value not in reasons


def test_valid_user_only_conversation_reports_missing_assistant_only() -> None:
    user_only = [{"role": "user", "content": "prompt"}]
    reasons = apply_population(
        _canonical([_row(conversation_a=user_only, conversation_b=user_only)]), BASE_RESEARCH
    ).audit.loc[0, "exclusion_reasons"]

    assert ExclusionReason.MISSING_ASSISTANT_TURN_A.value in reasons
    assert ExclusionReason.INVALID_CONVERSATION_A.value not in reasons
    assert ExclusionReason.PROMPT_PAIR_MISMATCH.value not in reasons


def test_valid_different_user_sequences_report_prompt_mismatch() -> None:
    reasons = apply_population(
        _canonical([_row(
            conversation_a=_conversation("prompt-a"),
            conversation_b=_conversation("prompt-b"),
        )]), BASE_RESEARCH
    ).audit.loc[0, "exclusion_reasons"]

    assert ExclusionReason.PROMPT_PAIR_MISMATCH.value in reasons


def test_invalid_conversation_plus_valid_other_side_has_no_false_prompt_mismatch() -> None:
    reasons = apply_population(
        _canonical([_row(conversation_a="malformed", conversation_b=_conversation())]), BASE_RESEARCH
    ).audit.loc[0, "exclusion_reasons"]

    assert ExclusionReason.INVALID_CONVERSATION_A.value in reasons
    assert ExclusionReason.PROMPT_PAIR_MISMATCH.value not in reasons


def test_judge_and_language_requirements_are_population_specific() -> None:
    missing_judge = _canonical([_row(judge=None)])
    missing_language = _canonical([_row(language=" ")])

    assert apply_population(missing_judge, BASE_RESEARCH).audit.loc[0, "eligible"]
    judge_result = apply_population(missing_judge, JUDGE_CLUSTER_RESEARCH)
    assert ExclusionReason.MISSING_JUDGE.value in judge_result.audit.loc[0, "exclusion_reasons"]

    assert apply_population(missing_language, BASE_RESEARCH).audit.loc[0, "eligible"]
    language_result = apply_population(missing_language, LANGUAGE_RESEARCH)
    assert ExclusionReason.MISSING_LANGUAGE.value in language_result.audit.loc[0, "exclusion_reasons"]


def test_tie_policies_keep_tie_bothbad_for_base_but_not_legacy_score() -> None:
    ordinary_tie = _canonical([_row(winner="tie")])
    bothbad_tie = _canonical([_row(winner="tie (bothbad)")])

    assert apply_population(ordinary_tie, BASE_RESEARCH).audit.loc[0, "eligible"]
    assert apply_population(ordinary_tie, LEGACY_SCORE).audit.loc[0, "eligible"]
    assert apply_population(bothbad_tie, BASE_RESEARCH).audit.loc[0, "eligible"]
    legacy_result = apply_population(bothbad_tie, LEGACY_SCORE)
    assert ExclusionReason.OUTCOME_NOT_ALLOWED.value in legacy_result.audit.loc[0, "exclusion_reasons"]


def test_invalid_unknown_never_enters_base_research() -> None:
    result = apply_population(_canonical([_row(winner="unexpected")]), BASE_RESEARCH)
    reasons = result.audit.loc[0, "exclusion_reasons"]

    assert result.eligible.empty
    assert ExclusionReason.INVALID_OUTCOME.value in reasons
    assert ExclusionReason.OUTCOME_NOT_ALLOWED.value in reasons

    permissive = replace(BASE_RESEARCH, population_id="invalid-outcome-check", require_source_record_valid=False,
                         allowed_outcomes=frozenset({"invalid_unknown"}))
    assert apply_population(_canonical([_row(winner="unexpected")]), permissive).eligible.empty


def test_duplicate_exclusion_is_opt_in_and_never_mutates_or_reorders_input() -> None:
    canonical = _canonical([_row(), _row()], index=[20, 10])
    before = canonical.copy(deep=True)
    default_result = apply_population(canonical, BASE_RESEARCH)
    without_duplicates = replace(
        BASE_RESEARCH,
        population_id="base_research_without_exact_duplicates",
        exclude_exact_duplicates=True,
    )
    excluded_result = apply_population(canonical, without_duplicates)

    pd.testing.assert_frame_equal(canonical, before)
    assert default_result.eligible["battle_id"].tolist() == canonical["battle_id"].tolist()
    assert default_result.audit["battle_id"].tolist() == canonical["battle_id"].tolist()
    assert len(default_result.eligible) == 2
    assert excluded_result.eligible.empty
    assert excluded_result.audit["exclusion_reasons"].tolist() == [
        (ExclusionReason.EXACT_DUPLICATE_EXCLUDED.value,),
        (ExclusionReason.EXACT_DUPLICATE_EXCLUDED.value,),
    ]


def test_population_summary_counts_rows_and_overlapping_reasons() -> None:
    canonical = _canonical([
        _row(),
        _row(
            conversation_a=[{"role": "user", "content": "prompt"}],
            conversation_b=[{"role": "user", "content": "prompt"}],
            tstamp="not-a-timestamp",
        ),
    ])
    summary = apply_population(canonical, BASE_RESEARCH).summary

    assert summary["population_id"] == "base_research"
    assert summary["input_rows"] == 2
    assert summary["eligible_rows"] == 1
    assert summary["excluded_rows"] == 1
    assert summary["eligibility_rate"] == 0.5
    assert summary["exclusion_reason_counts"][ExclusionReason.SOURCE_RECORD_INVALID.value] == 1
    assert summary["exclusion_reason_counts"][ExclusionReason.INVALID_TIMESTAMP.value] == 1


def test_legacy_statistics_receives_only_legacy_score_population() -> None:
    canonical = _canonical([
        _row(winner="model_a"),
        _row(winner="tie"),
        _row(winner="tie (bothbad)"),
        _row(winner="model_a", conversation_a="malformed", conversation_b=_conversation()),
    ])
    legacy_result = apply_population(canonical, LEGACY_SCORE)
    statistics = build_model_statistics(legacy_result.eligible)

    assert legacy_result.eligible["canonical_outcome"].tolist() == ["model_a_win", "tie"]
    assert statistics["battle_count"].sum() == 4
    assert statistics["win_count"].sum() == 1
    assert statistics["lose_count"].sum() == 1
    assert statistics["tie_count"].sum() == 2
