"""Versioned, lossless canonical representation for pairwise battle rows."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import math
from collections.abc import Mapping
from numbers import Integral, Real
from typing import Any

import pandas as pd


CANONICAL_BATTLE_SCHEMA_VERSION = 2


class CanonicalOutcome(str, Enum):
    MODEL_A_WIN = "model_a_win"
    MODEL_B_WIN = "model_b_win"
    TIE = "tie"
    TIE_BOTHBAD = "tie_bothbad"
    INVALID_UNKNOWN = "invalid_unknown"


@dataclass(frozen=True)
class SourceProvenance:
    """Immutable identifiers for one source snapshot."""

    source_dataset: str | None
    source_revision: str | None = None
    source_split: str | None = None
    source_file: str | None = None
    source_file_sha256: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return {
            "source_dataset": self.source_dataset,
            "source_revision": self.source_revision,
            "source_split": self.source_split,
            "source_file": self.source_file,
            "source_file_sha256": self.source_file_sha256,
        }

    @classmethod
    def from_mapping(cls, values: Mapping[str, str | None]) -> "SourceProvenance":
        return cls(
            source_dataset=values.get("source_dataset"),
            source_revision=values.get("source_revision"),
            source_split=values.get("source_split"),
            source_file=values.get("source_file"),
            source_file_sha256=values.get("source_file_sha256"),
        )


@dataclass(frozen=True)
class ConversationParseResult:
    turns: tuple[tuple[str, str], ...]
    valid: bool
    error_code: str


def _is_missing(value: Any) -> bool:
    if value is None or value is pd.NA:
        return True
    if pd.api.types.is_scalar(value):
        try:
            return bool(pd.isna(value))
        except (TypeError, ValueError):
            return False
    return False


def _trimmed_string(value: Any) -> str | None:
    if _is_missing(value):
        return None
    try:
        text = str(value).strip()
    except Exception:
        return None
    return text or None


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def source_snapshot_id(provenance: SourceProvenance) -> str:
    """Return the SHA-256 identifier for source provenance fields."""
    return hashlib.sha256(_canonical_json(provenance.as_dict()).encode("utf-8")).hexdigest()


def battle_id_for(source_snapshot: str, source_row_index: int) -> str:
    """Return the SHA-256 identity for one raw row in a source snapshot."""
    payload = f"{source_snapshot}\x1f{source_row_index}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _source_row_indices(df: pd.DataFrame) -> list[int]:
    values = df["source_row_index"] if "source_row_index" in df.columns else df.index
    indices: list[int] = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, Integral) or int(value) < 0:
            raise ValueError("source_row_index must contain unique non-negative integers")
        indices.append(int(value))
    if len(set(indices)) != len(indices):
        raise ValueError("source_row_index must be unique within a source snapshot")
    return indices


def canonicalize_outcome(value: Any) -> tuple[CanonicalOutcome, bool]:
    text = _trimmed_string(value)
    normalized = text.lower() if text is not None else None
    mapping = {
        "model_a": CanonicalOutcome.MODEL_A_WIN,
        "a": CanonicalOutcome.MODEL_A_WIN,
        "winner_a": CanonicalOutcome.MODEL_A_WIN,
        "model_b": CanonicalOutcome.MODEL_B_WIN,
        "b": CanonicalOutcome.MODEL_B_WIN,
        "winner_b": CanonicalOutcome.MODEL_B_WIN,
        "tie": CanonicalOutcome.TIE,
        "tie (bothbad)": CanonicalOutcome.TIE_BOTHBAD,
    }
    outcome = mapping.get(normalized, CanonicalOutcome.INVALID_UNKNOWN)
    return outcome, outcome is not CanonicalOutcome.INVALID_UNKNOWN


def canonicalize_anony(value: Any) -> tuple[Any, bool, bool]:
    """Return raw value, strict validity, and anonymous-battle meaning."""
    if isinstance(value, bool):
        return value, True, value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1"}:
            return value, True, True
        if normalized in {"false", "0"}:
            return value, True, False
    return value, False, False


def parse_conversation(value: Any) -> ConversationParseResult:
    """Parse a conversation into role/content turns using stable error codes."""
    if _is_missing(value):
        return ConversationParseResult((), False, "missing")

    parsed = value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return ConversationParseResult((), False, "empty")
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            try:
                parsed = ast.literal_eval(text)
            except (SyntaxError, ValueError):
                return ConversationParseResult((), False, "parse_error")

    if not isinstance(parsed, list):
        return ConversationParseResult((), False, "not_list")

    turns: list[tuple[str, str]] = []
    allowed_roles = {"user", "assistant", "system", "tool", "function"}
    for item in parsed:
        if not isinstance(item, Mapping):
            return ConversationParseResult((), False, "invalid_turn")
        if "role" not in item:
            return ConversationParseResult((), False, "missing_role")
        role = _trimmed_string(item["role"])
        if role is None or role.lower() not in allowed_roles:
            return ConversationParseResult((), False, "invalid_role")
        if "content" not in item or _is_missing(item["content"]):
            return ConversationParseResult((), False, "missing_content")
        try:
            content = str(item["content"])
        except Exception:
            return ConversationParseResult((), False, "invalid_content")
        turns.append((role.lower(), content))
    return ConversationParseResult(tuple(turns), True, "ok")


def _user_turns(parsed: ConversationParseResult) -> tuple[str, ...]:
    return tuple(content for role, content in parsed.turns if role == "user")


def _first_user_text(parsed: ConversationParseResult) -> str:
    for role, content in parsed.turns:
        if role == "user":
            return content
    return ""


def _assistant_text(parsed: ConversationParseResult) -> str:
    return " ".join(content for role, content in parsed.turns if role == "assistant")


def _canonical_timestamp(value: Any) -> tuple[pd.Timestamp | pd.NaT, bool, str]:
    if _is_missing(value):
        return pd.NaT, False, "missing"
    try:
        if isinstance(value, Real) and not isinstance(value, bool):
            timestamp = pd.to_datetime(value, unit="s", utc=True)
        elif isinstance(value, str):
            text = value.strip()
            if not text:
                return pd.NaT, False, "missing"
            try:
                numeric = float(text)
            except ValueError:
                timestamp = pd.Timestamp(text)
                timestamp = (
                    timestamp.tz_localize("UTC")
                    if timestamp.tzinfo is None
                    else timestamp.tz_convert("UTC")
                )
            else:
                if math.isnan(numeric):
                    return pd.NaT, False, "missing"
                timestamp = pd.to_datetime(numeric, unit="s", utc=True)
        else:
            return pd.NaT, False, "invalid"
    except (OverflowError, TypeError, ValueError):
        return pd.NaT, False, "invalid"
    return pd.Timestamp(timestamp), True, "ok"


def _json_value(value: Any) -> Any:
    if _is_missing(value):
        return None
    if isinstance(value, Mapping):
        return {str(key): _json_value(val) for key, val in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, bool):
        return value
    if isinstance(value, Integral):
        return int(value)
    if isinstance(value, Real):
        return float(value)
    return str(value)


def _exact_duplicate_flags(df: pd.DataFrame) -> pd.Series:
    identity_columns = {
        "source_row_index",
        "battle_id",
        "record_id",
        "source_snapshot_id",
        "schema_version",
    }
    substantive_columns = [column for column in df.columns if column not in identity_columns]
    keys = [
        _canonical_json({column: _json_value(row[column]) for column in substantive_columns})
        for _, row in df.iterrows()
    ]
    return pd.Series(keys, index=df.index).duplicated(keep=False)


def canonicalize_battles(df: pd.DataFrame, *, provenance: SourceProvenance) -> pd.DataFrame:
    """Return one lossless canonical record for every input source row.

    When a ``source_row_index`` column is absent, the caller-supplied dataframe
    index is treated as the raw source snapshot position. Callers that reset or
    replace that index must provide an explicit ``source_row_index`` column.
    """
    source_indices = _source_row_indices(df)
    result = df.copy()
    snapshot = source_snapshot_id(provenance)
    result["schema_version"] = CANONICAL_BATTLE_SCHEMA_VERSION
    for name, value in provenance.as_dict().items():
        result[name] = value
    result["source_snapshot_id"] = snapshot
    result["source_row_index"] = source_indices
    result["battle_id"] = [battle_id_for(snapshot, index) for index in source_indices]
    question_id_raw = df["question_id"] if "question_id" in df.columns else pd.Series(pd.NA, index=df.index)
    result["question_id_raw"] = question_id_raw

    winner_raw = df["winner"] if "winner" in df.columns else pd.Series(pd.NA, index=df.index)
    outcomes = [canonicalize_outcome(value) for value in winner_raw]
    result["winner_raw"] = winner_raw
    result["canonical_outcome"] = [outcome.value for outcome, _ in outcomes]
    result["outcome_valid"] = [valid for _, valid in outcomes]

    model_a_raw = df["model_a"] if "model_a" in df.columns else pd.Series(pd.NA, index=df.index)
    model_b_raw = df["model_b"] if "model_b" in df.columns else pd.Series(pd.NA, index=df.index)
    model_a_ids = [_trimmed_string(value) for value in model_a_raw]
    model_b_ids = [_trimmed_string(value) for value in model_b_raw]
    result["model_a_raw"] = model_a_raw
    result["model_b_raw"] = model_b_raw
    result["model_a_id"] = model_a_ids
    result["model_b_id"] = model_b_ids
    result["model_alias_map_version"] = "none"
    result["model_fields_valid"] = [a is not None and b is not None for a, b in zip(model_a_ids, model_b_ids)]
    result["distinct_models"] = [
        valid and a != b
        for a, b, valid in zip(model_a_ids, model_b_ids, result["model_fields_valid"])
    ]

    conversation_a_raw = df["conversation_a"] if "conversation_a" in df.columns else pd.Series(pd.NA, index=df.index)
    conversation_b_raw = df["conversation_b"] if "conversation_b" in df.columns else pd.Series(pd.NA, index=df.index)
    parsed_a = [parse_conversation(value) for value in conversation_a_raw]
    parsed_b = [parse_conversation(value) for value in conversation_b_raw]
    result["conversation_a_valid"] = [item.valid for item in parsed_a]
    result["conversation_b_valid"] = [item.valid for item in parsed_b]
    result["conversation_a_error"] = [item.error_code for item in parsed_a]
    result["conversation_b_error"] = [item.error_code for item in parsed_b]
    result["conversation_a_has_user"] = [item.valid and bool(_user_turns(item)) for item in parsed_a]
    result["conversation_b_has_user"] = [item.valid and bool(_user_turns(item)) for item in parsed_b]
    result["conversation_a_has_assistant"] = [
        item.valid and any(role == "assistant" for role, _ in item.turns)
        for item in parsed_a
    ]
    result["conversation_b_has_assistant"] = [
        item.valid and any(role == "assistant" for role, _ in item.turns)
        for item in parsed_b
    ]
    result["prompt_pair_consistent"] = [
        a.valid and b.valid and _user_turns(a) == _user_turns(b)
        for a, b in zip(parsed_a, parsed_b)
    ]
    result["prompt_text"] = [_first_user_text(item) if item.valid else "" for item in parsed_a]
    result["response_a_text"] = [_assistant_text(item) if item.valid else "" for item in parsed_a]
    result["response_b_text"] = [_assistant_text(item) if item.valid else "" for item in parsed_b]

    timestamp_raw = df["tstamp"] if "tstamp" in df.columns else pd.Series(pd.NA, index=df.index)
    timestamps = [_canonical_timestamp(value) for value in timestamp_raw]
    result["tstamp_raw"] = timestamp_raw
    result["timestamp_utc"] = pd.to_datetime([item[0] for item in timestamps], utc=True)
    result["timestamp_valid"] = [item[1] for item in timestamps]
    result["timestamp_error"] = [item[2] for item in timestamps]
    result["battle_date_utc"] = result["timestamp_utc"].dt.date
    result["battle_hour_utc"] = result["timestamp_utc"].dt.hour.astype("Int64")
    result["battle_month_utc"] = result["timestamp_utc"].dt.strftime("%Y-%m").astype("string")

    judge_raw = df["judge"] if "judge" in df.columns else pd.Series(pd.NA, index=df.index)
    language_raw = df["language"] if "language" in df.columns else pd.Series(pd.NA, index=df.index)
    anony_raw = df["anony"] if "anony" in df.columns else pd.Series(pd.NA, index=df.index)
    anony_values = [canonicalize_anony(value) for value in anony_raw]
    result["judge_cluster_id"] = judge_raw
    result["judge_present"] = [_trimmed_string(value) is not None for value in judge_raw]
    result["language_raw"] = language_raw
    result["language_canonical"] = [_trimmed_string(value) for value in language_raw]
    result["language_source"] = "source"
    result["language_present"] = result["language_canonical"].notna()
    result["anony_raw"] = [raw for raw, _, _ in anony_values]
    result["anony_valid"] = [valid for _, valid, _ in anony_values]
    result["anonymous_battle"] = [anonymous for _, _, anonymous in anony_values]

    result["prompt_chars"] = result["prompt_text"].str.len()
    result["response_a_chars"] = result["response_a_text"].str.len()
    result["response_b_chars"] = result["response_b_text"].str.len()
    result["response_char_diff"] = result["response_a_chars"] - result["response_b_chars"]
    result["response_abs_char_diff"] = result["response_char_diff"].abs()
    result["exact_duplicate"] = _exact_duplicate_flags(df)
    result["source_record_valid"] = (
        result["model_fields_valid"]
        & result["distinct_models"]
        & result["outcome_valid"]
        & result["conversation_a_valid"]
        & result["conversation_b_valid"]
        & result["conversation_a_has_user"]
        & result["conversation_b_has_user"]
        & result["conversation_a_has_assistant"]
        & result["conversation_b_has_assistant"]
        & result["prompt_pair_consistent"]
        & result["timestamp_valid"]
    )
    return result
