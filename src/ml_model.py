from __future__ import annotations

from pathlib import Path
import json

import joblib
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src.visualization import configure_chinese_font


def train_preference_model(df: pd.DataFrame, model_dir: str | Path, figure_dir: str | Path, random_state: int = 42) -> dict:
    features = [
        "model_a", "model_b", "language", "topic_name",
        "prompt_len", "response_a_len", "response_b_len", "len_diff"
    ]
    dataset = df[features + ["winner"]].dropna().copy()
    if len(dataset) < 100 or dataset["winner"].nunique() < 2:
        return {"status": "skipped", "reason": "有效样本或类别数量不足"}

    X = dataset[features]
    y = dataset["winner"]
    cat_features = ["model_a", "model_b", "language", "topic_name"]
    num_features = ["prompt_len", "response_a_len", "response_b_len", "len_diff"]

    preprocessing = ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore"), cat_features),
        ("num", StandardScaler(), num_features),
    ])
    pipeline = Pipeline([
        ("preprocess", preprocessing),
        ("classifier", RandomForestClassifier(n_estimators=180, random_state=random_state, class_weight="balanced")),
    ])

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=random_state, stratify=y
    )
    pipeline.fit(X_train, y_train)
    pred = pipeline.predict(X_test)
    labels = sorted(y.unique().tolist())
    report = classification_report(y_test, pred, labels=labels, output_dict=True, zero_division=0)
    accuracy = float(accuracy_score(y_test, pred))

    model_dir = Path(model_dir); model_dir.mkdir(parents=True, exist_ok=True)
    figure_dir = Path(figure_dir); figure_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, model_dir / "preference_model.joblib")

    cm = confusion_matrix(y_test, pred, labels=labels)
    configure_chinese_font()
    plt.figure(figsize=(7, 6))
    sns.heatmap(cm, annot=True, fmt="d", xticklabels=labels, yticklabels=labels)
    plt.xlabel("预测类别"); plt.ylabel("真实类别"); plt.title("用户偏好预测混淆矩阵")
    plt.tight_layout(); plt.savefig(figure_dir / "10_confusion_matrix.png", dpi=220, bbox_inches="tight"); plt.close()

    result = {
        "status": "ok",
        "accuracy": accuracy,
        "train_size": len(X_train),
        "test_size": len(X_test),
        "labels": labels,
        "classification_report": report,
    }
    (model_dir / "metrics.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    pd.DataFrame(report).transpose().to_csv(model_dir / "classification_report.csv", encoding="utf-8-sig")
    return result
