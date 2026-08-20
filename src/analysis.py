from __future__ import annotations

import pandas as pd


def build_model_statistics(df: pd.DataFrame) -> pd.DataFrame:
    """Summarize only canonical outcomes supported by the legacy score policy.

    Rows without both model IDs, ``tie_bothbad``, and ``invalid_unknown`` are
    deliberately excluded rather than silently treated as ordinary ties.
    """
    rows = []
    for item in df[["model_a", "model_b", "winner"]].itertuples(index=False):
        if not all(isinstance(model, str) and model.strip() for model in (item.model_a, item.model_b)):
            continue
        if item.winner == "model_a_win":
            rows.extend([(item.model_a, 1, 1, 0, 0), (item.model_b, 1, 0, 1, 0)])
        elif item.winner == "model_b_win":
            rows.extend([(item.model_a, 1, 0, 1, 0), (item.model_b, 1, 1, 0, 0)])
        elif item.winner == "tie":
            rows.extend([(item.model_a, 1, 0, 0, 1), (item.model_b, 1, 0, 0, 1)])

    stat = pd.DataFrame(rows, columns=["model_name", "battle_count", "win_count", "lose_count", "tie_count"])
    if stat.empty:
        return stat.assign(
            win_rate=pd.Series(dtype=float),
            tie_rate=pd.Series(dtype=float),
            score=pd.Series(dtype=float),
            score_rate=pd.Series(dtype=float),
        )
    result = stat.groupby("model_name", as_index=False).sum()
    result["win_rate"] = result["win_count"] / result["battle_count"]
    result["tie_rate"] = result["tie_count"] / result["battle_count"]
    result["score"] = result["win_count"] + 0.5 * result["tie_count"]
    result["score_rate"] = result["score"] / result["battle_count"]
    return result.sort_values(["score_rate", "battle_count"], ascending=[False, False]).reset_index(drop=True)


def create_summary_tables(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    vote = df["winner"].value_counts(dropna=False).rename_axis("winner").reset_index(name="count")
    vote["proportion"] = vote["count"] / vote["count"].sum()

    language = df["language"].value_counts(dropna=False).rename_axis("language").reset_index(name="count")
    language["proportion"] = language["count"] / language["count"].sum()

    topic = df["topic_name"].value_counts(dropna=False).rename_axis("topic_name").reset_index(name="count")
    topic["proportion"] = topic["count"] / topic["count"].sum()

    daily = df.dropna(subset=["battle_date"]).groupby("battle_date").size().reset_index(name="count")
    hourly = df.dropna(subset=["battle_hour"]).groupby("battle_hour").size().reset_index(name="count")
    topic_vote = pd.crosstab(df["topic_name"], df["winner"]).reset_index()

    return {
        "vote_statistics": vote,
        "language_statistics": language,
        "topic_statistics": topic,
        "daily_statistics": daily,
        "hourly_statistics": hourly,
        "topic_vote_crosstab": topic_vote,
    }
