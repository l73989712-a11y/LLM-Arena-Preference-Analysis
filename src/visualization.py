from __future__ import annotations

from pathlib import Path
import warnings

import matplotlib.pyplot as plt
from matplotlib import font_manager
import pandas as pd
import seaborn as sns


def configure_chinese_font() -> None:
    candidates = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                font_manager.fontManager.addfont(path)
                family = font_manager.FontProperties(fname=path).get_name()
                plt.rcParams["font.family"] = family
                break
            except Exception:
                pass
    else:
        plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


def _save(path: Path) -> None:
    plt.tight_layout()
    plt.savefig(path, dpi=220, bbox_inches="tight")
    plt.close()


def create_static_charts(df: pd.DataFrame, model_stat: pd.DataFrame, figure_dir: str | Path) -> list[Path]:
    figure_dir = Path(figure_dir)
    figure_dir.mkdir(parents=True, exist_ok=True)
    configure_chinese_font()
    outputs = []

    vote = df["winner"].value_counts()
    plt.figure(figsize=(7, 6))
    plt.pie(vote.values, labels=vote.index, autopct="%1.1f%%", startangle=90)
    plt.title("用户投票结果分布")
    path = figure_dir / "01_vote_distribution.png"; _save(path); outputs.append(path)

    top_battle = model_stat.sort_values("battle_count", ascending=False).head(10).sort_values("battle_count")
    plt.figure(figsize=(10, 6))
    plt.barh(top_battle["model_name"], top_battle["battle_count"])
    plt.xlabel("出场次数"); plt.ylabel("模型名称"); plt.title("模型出场次数 TOP10")
    path = figure_dir / "02_model_battle_top10.png"; _save(path); outputs.append(path)

    threshold = max(10, int(model_stat["battle_count"].median() * 0.5))
    top_win = model_stat[model_stat["battle_count"] >= threshold].sort_values("score_rate", ascending=False).head(10).sort_values("score_rate")
    plt.figure(figsize=(10, 6))
    plt.barh(top_win["model_name"], top_win["score_rate"])
    plt.xlabel("综合得分率"); plt.ylabel("模型名称"); plt.title(f"模型综合表现 TOP10（出场次数不少于 {threshold}）")
    path = figure_dir / "03_model_score_top10.png"; _save(path); outputs.append(path)

    language = df["language"].value_counts().head(10)
    plt.figure(figsize=(10, 6))
    plt.bar(language.index.astype(str), language.values)
    plt.xlabel("语言"); plt.ylabel("记录数"); plt.title("用户问题语言分布 TOP10")
    plt.xticks(rotation=35)
    path = figure_dir / "04_language_top10.png"; _save(path); outputs.append(path)

    daily = df.dropna(subset=["battle_date"]).groupby("battle_date").size()
    plt.figure(figsize=(11, 5))
    plt.plot(daily.index.astype(str), daily.values)
    plt.xlabel("日期"); plt.ylabel("对话数量"); plt.title("对话数量时间趋势")
    ticks = max(1, len(daily) // 10)
    plt.xticks(range(0, len(daily), ticks), [str(x) for x in daily.index[::ticks]], rotation=35)
    path = figure_dir / "05_daily_trend.png"; _save(path); outputs.append(path)

    topic = df["topic_name"].value_counts()
    plt.figure(figsize=(9, 6))
    plt.bar(topic.index, topic.values)
    plt.xlabel("主题类别"); plt.ylabel("记录数"); plt.title("用户问题主题分布")
    plt.xticks(rotation=30)
    path = figure_dir / "06_topic_distribution.png"; _save(path); outputs.append(path)

    topic_vote = pd.crosstab(df["topic_name"], df["winner"])
    plt.figure(figsize=(9, 6))
    sns.heatmap(topic_vote, annot=True, fmt="d")
    plt.xlabel("投票结果"); plt.ylabel("问题主题"); plt.title("不同主题下的用户投票热力图")
    path = figure_dir / "07_topic_vote_heatmap.png"; _save(path); outputs.append(path)

    # 为避免极端长度影响阅读，按 1%-99% 分位数截取绘图数据。
    low, high = df["len_diff"].quantile([0.01, 0.99])
    plot_df = df[df["len_diff"].between(low, high)]
    plt.figure(figsize=(8, 6))
    sns.boxplot(data=plot_df, x="winner", y="len_diff")
    plt.xlabel("投票结果"); plt.ylabel("A回答长度 - B回答长度"); plt.title("回答长度差异与用户偏好")
    path = figure_dir / "08_length_difference_boxplot.png"; _save(path); outputs.append(path)

    plt.figure(figsize=(9, 6))
    plt.hist(df["prompt_len"].dropna(), bins=30)
    plt.xlabel("用户问题长度"); plt.ylabel("频数"); plt.title("用户问题长度分布")
    path = figure_dir / "09_prompt_length_histogram.png"; _save(path); outputs.append(path)

    return outputs


def create_pyecharts(df: pd.DataFrame, model_stat: pd.DataFrame, html_dir: str | Path) -> list[Path]:
    try:
        from pyecharts import options as opts
        from pyecharts.charts import Bar, Pie, Scatter
    except ImportError:
        warnings.warn("未安装 pyecharts，跳过动态图表。")
        return []

    html_dir = Path(html_dir); html_dir.mkdir(parents=True, exist_ok=True)
    outputs = []

    top = model_stat.sort_values("score_rate", ascending=False).head(10)
    chart = (
        Bar(init_opts=opts.InitOpts(width="1100px", height="600px"))
        .add_xaxis(top["model_name"].tolist())
        .add_yaxis("综合得分率", top["score_rate"].round(3).tolist())
        .set_global_opts(
            title_opts=opts.TitleOpts(title="模型综合表现 TOP10"),
            xaxis_opts=opts.AxisOpts(axislabel_opts=opts.LabelOpts(rotate=25)),
            yaxis_opts=opts.AxisOpts(name="得分率", min_=0, max_=1),
            toolbox_opts=opts.ToolboxOpts(is_show=True),
        )
    )
    path = html_dir / "model_score_top10.html"; chart.render(str(path)); outputs.append(path)

    topic = df["topic_name"].value_counts()
    chart = (
        Pie(init_opts=opts.InitOpts(width="1000px", height="600px"))
        .add("主题", list(zip(topic.index.tolist(), topic.values.tolist())), radius=["35%", "70%"])
        .set_global_opts(title_opts=opts.TitleOpts(title="用户问题主题分布"), legend_opts=opts.LegendOpts(orient="vertical", pos_left="2%"))
        .set_series_opts(label_opts=opts.LabelOpts(formatter="{b}: {d}%"))
    )
    path = html_dir / "topic_distribution.html"; chart.render(str(path)); outputs.append(path)

    scatter_df = model_stat.sort_values("battle_count", ascending=False).head(30)
    chart = (
        Scatter(init_opts=opts.InitOpts(width="1000px", height="600px"))
        .add_xaxis(scatter_df["battle_count"].tolist())
        .add_yaxis(
            "模型",
            [[float(rate), name] for rate, name in zip(scatter_df["score_rate"], scatter_df["model_name"])],
            label_opts=opts.LabelOpts(is_show=False),
        )
        .set_global_opts(
            title_opts=opts.TitleOpts(title="模型出场次数与综合得分率"),
            xaxis_opts=opts.AxisOpts(name="出场次数", type_="value"),
            yaxis_opts=opts.AxisOpts(name="综合得分率", type_="value", min_=0, max_=1),
            tooltip_opts=opts.TooltipOpts(formatter="{c}"),
        )
    )
    path = html_dir / "battle_score_scatter.html"; chart.render(str(path)); outputs.append(path)
    return outputs
