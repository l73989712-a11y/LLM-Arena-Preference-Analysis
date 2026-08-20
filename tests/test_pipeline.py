from pathlib import Path

import pandas as pd

from src.analysis import build_model_statistics
from src.preprocess import clean_arena_data
from src.sample_data import generate_sample_csv
from src.topic import add_rule_topics


def test_core_pipeline(tmp_path: Path):
    raw = generate_sample_csv(tmp_path / "sample.csv", rows=150, seed=1)
    cleaned, report = clean_arena_data(raw)
    cleaned = add_rule_topics(cleaned)
    statistics = build_model_statistics(cleaned)

    assert len(cleaned) > 100
    assert report["清洗后记录数"] == len(cleaned)
    assert "topic_name" in cleaned.columns
    eligible = cleaned["canonical_outcome"].isin(["model_a_win", "model_b_win", "tie"])
    eligible = eligible & cleaned["model_fields_valid"]
    expected_appearances = 2 * eligible.sum()
    expected_ties = 2 * (eligible & cleaned["canonical_outcome"].eq("tie")).sum()
    assert statistics["battle_count"].sum() == expected_appearances
    assert statistics["win_count"].sum() > 0
    assert statistics["lose_count"].sum() > 0
    assert statistics["win_count"].sum() == statistics["lose_count"].sum()
    assert statistics["tie_count"].sum() == expected_ties


def test_model_statistics_only_count_explicitly_supported_canonical_outcomes():
    battles = pd.DataFrame([
        {"model_a": "a_winner", "model_b": "a_loser", "winner": "model_a_win"},
        {"model_a": "b_loser", "model_b": "b_winner", "winner": "model_b_win"},
        {"model_a": "tie_a", "model_b": "tie_b", "winner": "tie"},
        {"model_a": "bothbad_a", "model_b": "bothbad_b", "winner": "tie_bothbad"},
        {"model_a": "unknown_a", "model_b": "unknown_b", "winner": "invalid_unknown"},
    ])
    statistics = build_model_statistics(battles)
    by_model = statistics.set_index("model_name")

    assert statistics["battle_count"].sum() == 6
    assert statistics["win_count"].sum() == 2
    assert statistics["lose_count"].sum() == 2
    assert statistics["tie_count"].sum() == 2
    assert by_model.loc["a_winner", ["win_count", "lose_count", "tie_count"]].tolist() == [1, 0, 0]
    assert by_model.loc["a_loser", ["win_count", "lose_count", "tie_count"]].tolist() == [0, 1, 0]
    assert by_model.loc["b_loser", ["win_count", "lose_count", "tie_count"]].tolist() == [0, 1, 0]
    assert by_model.loc["b_winner", ["win_count", "lose_count", "tie_count"]].tolist() == [1, 0, 0]
    assert by_model.loc["tie_a", "tie_count"] == 1
    assert by_model.loc["tie_b", "tie_count"] == 1
    assert "bothbad_a" not in by_model.index
    assert "unknown_a" not in by_model.index


def test_versioned_sample_fixture_is_synthetic_and_cleanable():
    fixture_path = Path(__file__).parents[1] / "data" / "sample" / "arena_sample.csv"
    raw = pd.read_csv(fixture_path)
    cleaned, report = clean_arena_data(raw)

    assert len(raw) == 125
    assert raw["judge"].astype(str).str.fullmatch(r"demo_user_\d+").all()
    assert report["清洗后记录数"] == len(cleaned)
    assert len(cleaned) > 100
