from __future__ import annotations

from typing import Any

import pandas as pd

from src.battle_contract import (
    SourceProvenance,
    canonicalize_battles,
    canonicalize_outcome,
    parse_conversation,
)


def safe_parse_conversation(value: Any) -> list:
    parsed = parse_conversation(value)
    return [{"role": role, "content": content} for role, content in parsed.turns] if parsed.valid else []


def extract_first_user_prompt(value: Any) -> str:
    for item in safe_parse_conversation(value):
        if isinstance(item, dict) and item.get("role") == "user":
            return str(item.get("content", ""))
    return ""


def extract_assistant_text(value: Any) -> str:
    texts = []
    for item in safe_parse_conversation(value):
        if isinstance(item, dict) and item.get("role") == "assistant":
            texts.append(str(item.get("content", "")))
    return " ".join(texts)


def normalize_winner(value: Any) -> str:
    """Compatibility helper returning the lossless canonical outcome label."""
    return canonicalize_outcome(value)[0].value


def parse_timestamp(series: pd.Series) -> pd.Series:
    source_index = series.index
    canonical = canonicalize_battles(
        pd.DataFrame({"source_row_index": range(len(series)), "tstamp": series.to_numpy()}),
        provenance=SourceProvenance(source_dataset="legacy_timestamp_series"),
    )
    return canonical["timestamp_utc"].set_axis(source_index)


def clean_arena_data(
    df: pd.DataFrame,
    *,
    provenance: SourceProvenance | None = None,
) -> tuple[pd.DataFrame, dict]:
    """Return a legacy-compatible view of every canonical source row.

    This function no longer deduplicates, filters invalid rows, fabricates
    question IDs, or maps unknown outcomes to ties. Consumers must select
    analysis populations from the explicit canonical validity flags.
    """
    before_rows = len(df)
    provenance = provenance or SourceProvenance(source_dataset="legacy_in_memory_dataframe")
    result = canonicalize_battles(df, provenance=provenance)

    # Existing downstream modules expect these names; their semantics are UTC or character counts.
    result["winner"] = result["canonical_outcome"]
    result["model_a"] = result["model_a_id"]
    result["model_b"] = result["model_b_id"]
    result["language"] = result["language_canonical"]
    result["tstamp"] = result["timestamp_utc"]
    result["battle_date"] = result["battle_date_utc"]
    result["battle_hour"] = result["battle_hour_utc"]
    result["battle_month"] = result["battle_month_utc"]
    result["prompt_len"] = result["prompt_chars"]
    result["response_a_len"] = result["response_a_chars"]
    result["response_b_len"] = result["response_b_chars"]
    result["len_diff"] = result["response_char_diff"]
    result["abs_len_diff"] = result["response_abs_char_diff"]

    report = {
        "原始记录数": before_rows,
        "去重后记录数": len(result),
        "清洗后记录数": len(result),
        "删除重复记录数": 0,
        "其他无效记录数": 0,
        "字段数": len(result.columns),
    }
    return result, report
