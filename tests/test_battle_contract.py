from __future__ import annotations

import pandas as pd

from src.battle_contract import (
    CANONICAL_BATTLE_SCHEMA_VERSION,
    CanonicalOutcome,
    SourceProvenance,
    canonicalize_battles,
    parse_conversation,
    source_snapshot_id,
)


PROVENANCE = SourceProvenance(
    source_dataset="synthetic/arena",
    source_revision="revision-1",
    source_split="train",
    source_file="synthetic.parquet",
    source_file_sha256="a" * 64,
)


def _conversation(prompt: str = "prompt", response: str = "response") -> list[dict[str, str]]:
    return [
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": response},
    ]


def _row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "question_id": "question-1",
        "model_a": " model-a ",
        "model_b": "model-b",
        "winner": "model_a",
        "conversation_a": _conversation(),
        "conversation_b": _conversation(),
        "tstamp": 0,
        "judge": "cluster-1",
        "language": " en ",
    }
    row.update(overrides)
    return row


def _canonical(rows: list[dict[str, object]]) -> pd.DataFrame:
    return canonicalize_battles(pd.DataFrame(rows), provenance=PROVENANCE)


def test_outcome_taxonomy_preserves_raw_winner() -> None:
    raw_winners = ["model_a", "model_b", "tie", "tie (bothbad)", "a", "winner_b"]
    result = _canonical([_row(winner=winner) for winner in raw_winners])

    assert result["winner_raw"].tolist() == raw_winners
    assert result["canonical_outcome"].tolist() == [
        CanonicalOutcome.MODEL_A_WIN.value,
        CanonicalOutcome.MODEL_B_WIN.value,
        CanonicalOutcome.TIE.value,
        CanonicalOutcome.TIE_BOTHBAD.value,
        CanonicalOutcome.MODEL_A_WIN.value,
        CanonicalOutcome.MODEL_B_WIN.value,
    ]
    assert result["outcome_valid"].all()


def test_unknown_and_missing_outcomes_are_never_ties() -> None:
    result = _canonical([_row(winner=value) for value in ["garbage", None, ""]])

    assert result["canonical_outcome"].tolist() == [CanonicalOutcome.INVALID_UNKNOWN.value] * 3
    assert not result["outcome_valid"].any()
    assert result.loc[0, "winner_raw"] == "garbage"
    assert pd.isna(result.loc[1, "winner_raw"])


def test_battle_ids_are_snapshot_and_source_row_deterministic() -> None:
    result = _canonical([_row(), _row(question_id="question-2")])
    repeated = _canonical([_row(), _row(question_id="question-2")])
    other_snapshot = canonicalize_battles(
        pd.DataFrame([_row(), _row(question_id="question-2")]),
        provenance=SourceProvenance(source_dataset="synthetic/arena", source_revision="revision-2"),
    )

    assert result["battle_id"].tolist() == repeated["battle_id"].tolist()
    assert result.loc[0, "battle_id"] != result.loc[1, "battle_id"]
    assert result["battle_id"].tolist() != other_snapshot["battle_id"].tolist()


def test_battle_ids_do_not_change_when_dataframe_order_changes() -> None:
    raw = pd.DataFrame([_row(question_id="one"), _row(question_id="two")], index=[20, 21])
    original = canonicalize_battles(raw, provenance=PROVENANCE)
    reordered = canonicalize_battles(raw.iloc[[1, 0]], provenance=PROVENANCE)

    original_ids = dict(zip(original["source_row_index"], original["battle_id"]))
    reordered_ids = dict(zip(reordered["source_row_index"], reordered["battle_id"]))
    assert original_ids == reordered_ids


def test_conversation_parse_contract_and_prompt_consistency() -> None:
    assert parse_conversation(_conversation()).valid
    assert parse_conversation('[{"role": "user", "content": "x"}]').valid
    assert parse_conversation("[{'role': 'user', 'content': 'x'}]").valid
    assert parse_conversation("not valid").error_code == "parse_error"
    assert parse_conversation({"role": "user"}).error_code == "not_list"
    assert parse_conversation([{"role": "user"}]).error_code == "missing_content"
    assert parse_conversation(["not-a-turn"]).error_code == "invalid_turn"

    result = _canonical([
        _row(conversation_a=_conversation("one"), conversation_b=_conversation("one")),
        _row(conversation_a=_conversation("one"), conversation_b=_conversation("two")),
        _row(conversation_a="broken", conversation_b=_conversation()),
    ])
    assert result["prompt_pair_consistent"].tolist() == [True, False, False]
    assert result.loc[0, "prompt_text"] == "one"
    assert result.loc[0, "response_a_text"] == "response"
    assert result.loc[2, "conversation_a_error"] == "parse_error"
    assert not result.loc[2, "conversation_a_valid"]


def test_timestamp_is_canonical_utc_without_local_timezone_dependence() -> None:
    result = _canonical([
        _row(tstamp=0),
        _row(tstamp="1970-01-01T02:00:00+02:00"),
        _row(tstamp="1970-01-01T00:00:00"),
        _row(tstamp="not-a-timestamp"),
    ])

    assert result["timestamp_valid"].tolist() == [True, True, True, False]
    assert result.loc[0, "timestamp_utc"].isoformat() == "1970-01-01T00:00:00+00:00"
    assert result.loc[1, "timestamp_utc"].isoformat() == "1970-01-01T00:00:00+00:00"
    assert result.loc[2, "timestamp_utc"].isoformat() == "1970-01-01T00:00:00+00:00"
    assert result.loc[3, "timestamp_error"] == "invalid"
    assert str(result["timestamp_utc"].dt.tz) == "UTC"


def test_model_language_judge_and_source_validity_flags() -> None:
    result = _canonical([
        _row(model_a="", language=" ", judge=None),
        _row(model_a="same", model_b="same"),
    ])

    assert not result.loc[0, "model_fields_valid"]
    assert not result.loc[0, "distinct_models"]
    assert not result.loc[0, "language_present"]
    assert not result.loc[0, "judge_present"]
    assert not result.loc[0, "source_record_valid"]
    assert result.loc[1, "model_fields_valid"]
    assert not result.loc[1, "distinct_models"]
    assert not result.loc[1, "source_record_valid"]


def test_exact_duplicates_are_retained_and_marked_as_a_group() -> None:
    raw = pd.DataFrame([_row(), _row()], index=[7, 8])
    result = canonicalize_battles(raw, provenance=PROVENANCE)

    assert len(result) == 2
    assert result["battle_id"].nunique() == 2
    assert result["exact_duplicate"].tolist() == [True, True]


def test_missing_question_id_is_not_fabricated() -> None:
    raw = _row()
    raw.pop("question_id")
    result = _canonical([raw])

    assert "question_id" not in result.columns
    assert pd.isna(result.loc[0, "question_id_raw"])


def test_snapshot_id_is_mapping_order_independent_and_schema_is_explicit() -> None:
    first = {
        "source_dataset": "synthetic/arena",
        "source_revision": "revision-1",
        "source_split": "train",
        "source_file": "synthetic.parquet",
        "source_file_sha256": "a" * 64,
    }
    second = dict(reversed(list(first.items())))
    assert source_snapshot_id(SourceProvenance.from_mapping(first)) == source_snapshot_id(
        SourceProvenance.from_mapping(second)
    )

    result = _canonical([_row()])
    assert result["schema_version"].tolist() == [CANONICAL_BATTLE_SCHEMA_VERSION]
    assert result.loc[0, "question_id_raw"] == "question-1"
