from __future__ import annotations

from pathlib import Path
import json

import pandas as pd
import streamlit as st

from config import PROCESSED_DIR, TABLE_DIR, FIGURE_DIR, HTML_DIR, MODEL_DIR

st.set_page_config(page_title="大模型用户偏好分析系统", page_icon="🤖", layout="wide")
st.title("🤖 基于 Chatbot Arena 数据的大模型用户偏好分析系统")
st.caption("课程实训演示系统：数据清洗、统计分析、可视化和机器学习预测")

cleaned_path = PROCESSED_DIR / "arena_cleaned.csv"
model_path = TABLE_DIR / "model_statistics.csv"

if not cleaned_path.exists() or not model_path.exists():
    st.error("尚未生成分析结果。请先运行：python run_pipeline.py --mode sample")
    st.stop()

@st.cache_data
def load_data():
    df = pd.read_csv(cleaned_path)
    model_stat = pd.read_csv(model_path)
    return df, model_stat

df, model_stat = load_data()

menu = st.sidebar.radio(
    "功能菜单",
    ["项目首页", "数据概览", "模型表现", "用户问题分析", "时间与语言", "机器学习结果", "动态图表"],
)

if menu == "项目首页":
    st.subheader("系统概述")
    st.write("本系统通过分析成对大模型对话及用户投票数据，展示不同模型的出场次数、胜率、综合得分率，以及用户问题的语言、主题和时间分布。")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("清洗后记录数", f"{len(df):,}")
    c2.metric("模型数量", df[["model_a", "model_b"]].stack().nunique())
    c3.metric("语言数量", df["language"].nunique())
    c4.metric("主题数量", df["topic_name"].nunique())
    st.image(str(FIGURE_DIR / "01_vote_distribution.png"), caption="用户投票结果分布", use_container_width=True)

elif menu == "数据概览":
    st.subheader("清洗后数据")
    c1, c2 = st.columns(2)
    c1.metric("记录数", f"{len(df):,}")
    c2.metric("字段数", len(df.columns))
    st.dataframe(df[["question_id", "model_a", "model_b", "winner", "language", "topic_name", "prompt_len", "response_a_len", "response_b_len"]].head(200), use_container_width=True)
    report_path = TABLE_DIR / "cleaning_report.json"
    if report_path.exists():
        st.subheader("数据清洗报告")
        st.json(json.loads(report_path.read_text(encoding="utf-8")))

elif menu == "模型表现":
    st.subheader("模型统计排名")
    min_battles = st.slider("最少出场次数", 1, int(model_stat["battle_count"].max()), min(50, int(model_stat["battle_count"].max())))
    filtered = model_stat[model_stat["battle_count"] >= min_battles].copy()
    st.dataframe(filtered.sort_values("score_rate", ascending=False), use_container_width=True)
    c1, c2 = st.columns(2)
    c1.image(str(FIGURE_DIR / "02_model_battle_top10.png"), use_container_width=True)
    c2.image(str(FIGURE_DIR / "03_model_score_top10.png"), use_container_width=True)

elif menu == "用户问题分析":
    st.subheader("用户问题主题与长度")
    topic_filter = st.multiselect("选择主题", sorted(df["topic_name"].dropna().unique()), default=sorted(df["topic_name"].dropna().unique()))
    filtered = df[df["topic_name"].isin(topic_filter)]
    st.bar_chart(filtered["topic_name"].value_counts())
    c1, c2 = st.columns(2)
    c1.image(str(FIGURE_DIR / "07_topic_vote_heatmap.png"), use_container_width=True)
    c2.image(str(FIGURE_DIR / "09_prompt_length_histogram.png"), use_container_width=True)

elif menu == "时间与语言":
    st.subheader("时间趋势和语言分布")
    c1, c2 = st.columns(2)
    c1.image(str(FIGURE_DIR / "04_language_top10.png"), use_container_width=True)
    c2.image(str(FIGURE_DIR / "05_daily_trend.png"), use_container_width=True)

elif menu == "机器学习结果":
    st.subheader("用户偏好分类预测")
    metrics_path = MODEL_DIR / "metrics.json"
    if metrics_path.exists():
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        st.metric("测试集准确率", f"{metrics.get('accuracy', 0):.3f}")
        st.write(f"训练集：{metrics.get('train_size')}，测试集：{metrics.get('test_size')}")
        st.image(str(FIGURE_DIR / "10_confusion_matrix.png"), use_container_width=True)
        report_csv = MODEL_DIR / "classification_report.csv"
        if report_csv.exists():
            st.dataframe(pd.read_csv(report_csv, index_col=0), use_container_width=True)
    else:
        st.info("尚未生成机器学习结果。请重新运行流水线且不要使用 --skip-ml。")

elif menu == "动态图表":
    st.subheader("pyecharts 交互式图表")
    files = sorted(HTML_DIR.glob("*.html"))
    if not files:
        st.info("暂无动态 HTML 图表。")
    for file in files:
        st.markdown(f"### {file.stem}")
        st.components.v1.html(file.read_text(encoding="utf-8"), height=620, scrolling=True)
