from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from config import RAW_DIR, SAMPLE_DIR, PROCESSED_DIR, FIGURE_DIR, HTML_DIR, TABLE_DIR, MODEL_DIR, MYSQL_CONFIG
from src.sample_data import generate_sample_csv
from src.data_io import download_chatbot_arena, load_csv
from src.preprocess import clean_arena_data
from src.topic import add_rule_topics, add_kmeans_topics
from src.analysis import build_model_statistics, create_summary_tables
from src.visualization import create_static_charts, create_pyecharts
from src.ml_model import train_preference_model


def parse_args():
    parser = argparse.ArgumentParser(description="大模型用户偏好分析一键流水线")
    parser.add_argument("--mode", choices=["sample", "real", "existing"], default="sample", help="数据来源")
    parser.add_argument("--mysql", action="store_true", help="将结果写入 MySQL")
    parser.add_argument("--skip-ml", action="store_true", help="跳过机器学习")
    parser.add_argument("--skip-kmeans", action="store_true", help="跳过 TF-IDF + KMeans 聚类")
    return parser.parse_args()


def main():
    args = parse_args()
    print("=" * 60)
    print("基于 Chatbot Arena 数据的大模型用户偏好分析系统")
    print("=" * 60)

    sample_path = SAMPLE_DIR / "arena_sample.csv"
    real_path = RAW_DIR / "chatbot_arena_raw.csv"

    if args.mode == "sample":
        if not sample_path.exists():
            print("正在生成离线样例数据……")
            generate_sample_csv(sample_path)
        source_path = sample_path
    elif args.mode == "real":
        print("正在从 Hugging Face 下载真实数据……")
        download_chatbot_arena(real_path)
        source_path = real_path
    else:
        source_path = real_path

    print(f"读取数据：{source_path}")
    raw = load_csv(source_path)
    cleaned, cleaning_report = clean_arena_data(raw)
    cleaned = add_rule_topics(cleaned)

    if not args.skip_kmeans:
        try:
            cleaned, keywords, _, _ = add_kmeans_topics(cleaned)
            keywords.to_csv(TABLE_DIR / "topic_cluster_keywords.csv", index=False, encoding="utf-8-sig")
        except Exception as exc:
            print(f"KMeans 主题聚类跳过：{exc}")

    cleaned_path = PROCESSED_DIR / "arena_cleaned.csv"
    cleaned.to_csv(cleaned_path, index=False, encoding="utf-8-sig")
    (TABLE_DIR / "cleaning_report.json").write_text(json.dumps(cleaning_report, ensure_ascii=False, indent=2), encoding="utf-8")

    model_stat = build_model_statistics(cleaned)
    model_stat.to_csv(TABLE_DIR / "model_statistics.csv", index=False, encoding="utf-8-sig")

    tables = create_summary_tables(cleaned)
    for name, table in tables.items():
        table.to_csv(TABLE_DIR / f"{name}.csv", index=False, encoding="utf-8-sig")

    print("生成静态图表……")
    static_files = create_static_charts(cleaned, model_stat, FIGURE_DIR)
    print("生成 pyecharts 动态图表……")
    html_files = create_pyecharts(cleaned, model_stat, HTML_DIR)

    ml_result = {"status": "skipped"}
    if not args.skip_ml:
        print("训练用户偏好预测模型……")
        ml_result = train_preference_model(cleaned, MODEL_DIR, FIGURE_DIR)

    if args.mysql:
        print("写入 MySQL……")
        from src.database import export_to_mysql
        export_to_mysql(cleaned, model_stat, tables["topic_statistics"], MYSQL_CONFIG)

    print("\n运行完成：")
    print(f"- 清洗后数据：{cleaned_path}")
    print(f"- 统计表格：{TABLE_DIR}")
    print(f"- 静态图表：{len(static_files)} 张，位于 {FIGURE_DIR}")
    print(f"- 动态图表：{len(html_files)} 个，位于 {HTML_DIR}")
    print(f"- 机器学习：{ml_result.get('status')}，准确率：{ml_result.get('accuracy', 'N/A')}")
    print("下一步可运行：streamlit run app.py")


if __name__ == "__main__":
    main()
