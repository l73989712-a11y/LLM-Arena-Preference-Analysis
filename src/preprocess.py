from __future__ import annotations

import ast
import json
from typing import Any

import numpy as np
import pandas as pd


def safe_parse_conversation(value: Any) -> list:
    if isinstance(value, list):
        return value
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return []
    text = str(value).strip()
    if not text:
        return []
    for parser in (json.loads, ast.literal_eval):
        try:
            parsed = parser(text)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            continue
    return []


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
    text = str(value).strip().lower()
    if text in {"model_a", "a", "winner_a"}:
        return "model_a"
    if text in {"model_b", "b", "winner_b"}:
        return "model_b"
    return "tie"


def parse_timestamp(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    parsed_numeric = pd.to_datetime(numeric, unit="s", errors="coerce")
    parsed_text = pd.to_datetime(series, errors="coerce")
    return parsed_numeric.fillna(parsed_text)


def clean_arena_data(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    required = ["model_a", "model_b", "winner", "conversation_a", "conversation_b"]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"原始数据缺少必要字段：{missing}。实际字段：{df.columns.tolist()}")

    before_rows = len(df)
    result = df.copy()
    result = result.drop_duplicates().copy()
    after_dedup = len(result)

    result["prompt_text"] = result["conversation_a"].apply(extract_first_user_prompt)
    result["response_a_text"] = result["conversation_a"].apply(extract_assistant_text)
    result["response_b_text"] = result["conversation_b"].apply(extract_assistant_text)
    result["winner"] = result["winner"].apply(normalize_winner)

    result["model_a"] = result["model_a"].astype("string").str.strip()
    result["model_b"] = result["model_b"].astype("string").str.strip()
    if "language" not in result.columns:
        result["language"] = "Unknown"
    result["language"] = result["language"].fillna("Unknown").astype(str).str.strip()

    result["prompt_len"] = result["prompt_text"].astype(str).str.len()
    result["response_a_len"] = result["response_a_text"].astype(str).str.len()
    result["response_b_len"] = result["response_b_text"].astype(str).str.len()
    result["len_diff"] = result["response_a_len"] - result["response_b_len"]
    result["abs_len_diff"] = result["len_diff"].abs()

    if "tstamp" in result.columns:
        result["tstamp"] = parse_timestamp(result["tstamp"])
    else:
        result["tstamp"] = pd.NaT
    result["battle_date"] = result["tstamp"].dt.date
    result["battle_hour"] = result["tstamp"].dt.hour
    result["battle_month"] = result["tstamp"].dt.to_period("M").astype(str)

    result = result.dropna(subset=["model_a", "model_b"]).copy()
    result = result[(result["model_a"] != "") & (result["model_b"] != "")]
    result = result[result["prompt_len"].between(1, 20000)]
    result = result[result["response_a_len"].between(1, 50000)]
    result = result[result["response_b_len"].between(1, 50000)]

    # 为数据库和建模保留稳定编号
    if "question_id" not in result.columns:
        result["question_id"] = [f"Q{i+1:06d}" for i in range(len(result))]
    result = result.reset_index(drop=True)
    result.insert(0, "record_id", range(1, len(result) + 1))

    report = {
        "原始记录数": before_rows,
        "去重后记录数": after_dedup,
        "清洗后记录数": len(result),
        "删除重复记录数": before_rows - after_dedup,
        "其他无效记录数": after_dedup - len(result),
        "字段数": len(result.columns),
    }
    return result, report
