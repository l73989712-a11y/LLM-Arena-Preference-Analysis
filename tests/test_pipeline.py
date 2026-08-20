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
    assert statistics["battle_count"].sum() == len(cleaned) * 2


def test_versioned_sample_fixture_is_synthetic_and_cleanable():
    fixture_path = Path(__file__).parents[1] / "data" / "sample" / "arena_sample.csv"
    raw = pd.read_csv(fixture_path)
    cleaned, report = clean_arena_data(raw)

    assert len(raw) == 125
    assert raw["judge"].astype(str).str.fullmatch(r"demo_user_\d+").all()
    assert report["清洗后记录数"] == len(cleaned)
    assert len(cleaned) > 100
