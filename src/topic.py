from __future__ import annotations

import re
import numpy as np
import pandas as pd

RULES = {
    "编程开发": ["python", "java", "sql", "code", "program", "debug", "function", "algorithm", "代码", "编程", "数据库", "函数", "算法"],
    "翻译语言": ["translate", "translation", "grammar", "english", "chinese", "spanish", "french", "翻译", "语法", "英文", "中文"],
    "写作创作": ["write", "essay", "story", "email", "letter", "poem", "文案", "作文", "邮件", "故事", "写作"],
    "数学推理": ["math", "calculate", "equation", "proof", "logic", "solve", "数学", "计算", "方程", "证明", "逻辑"],
    "学习辅导": ["study", "learn", "course", "homework", "plan", "学习", "课程", "作业", "复习", "计划"],
    "知识问答": ["explain", "what is", "why", "summarize", "science", "history", "解释", "什么是", "为什么", "总结", "简述"],
}


def classify_topic(text: str) -> str:
    lowered = str(text).lower()
    scores = {name: sum(1 for word in words if word in lowered) for name, words in RULES.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "其他主题"


def add_rule_topics(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    result["topic_name"] = result["prompt_text"].fillna("").apply(classify_topic)
    return result


def add_kmeans_topics(df: pd.DataFrame, n_clusters: int = 6, random_state: int = 42):
    """可选的无监督主题聚类。返回 DataFrame 和主题关键词表。"""
    from sklearn.cluster import KMeans
    from sklearn.feature_extraction.text import TfidfVectorizer

    texts = df["prompt_text"].fillna("").astype(str)
    min_df = 2 if len(texts) < 1000 else 5
    vectorizer = TfidfVectorizer(max_features=3000, min_df=min_df, max_df=0.95, token_pattern=r"(?u)\b\w+\b")
    matrix = vectorizer.fit_transform(texts)
    cluster_count = min(n_clusters, max(2, matrix.shape[0] // 10))
    model = KMeans(n_clusters=cluster_count, random_state=random_state, n_init=10)
    labels = model.fit_predict(matrix)

    result = df.copy()
    result["topic_cluster"] = labels
    terms = vectorizer.get_feature_names_out()
    order = model.cluster_centers_.argsort()[:, ::-1]
    keyword_rows = []
    for cluster_id in range(cluster_count):
        words = [terms[i] for i in order[cluster_id, :10]]
        keyword_rows.append({"topic_cluster": cluster_id, "keywords": ", ".join(words)})
    return result, pd.DataFrame(keyword_rows), model, vectorizer
