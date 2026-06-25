from __future__ import annotations

import json
import random
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

MODEL_STRENGTH = {
    "gpt-4": 0.90,
    "claude-v1": 0.84,
    "palm-2": 0.72,
    "llama-2-70b-chat": 0.69,
    "vicuna-13b": 0.58,
    "chatglm-6b": 0.55,
}

TOPIC_TEMPLATES = {
    "编程开发": [
        "Write a Python function to sort a list and explain its complexity.",
        "请帮我调试这段 Python 代码，并说明错误原因。",
        "How can I optimize a SQL query with multiple joins?",
    ],
    "写作创作": [
        "Write a polite email asking for a project deadline extension.",
        "请写一段关于人工智能教育应用的短文。",
        "Create a short science-fiction story about a helpful robot.",
    ],
    "翻译语言": [
        "Translate this sentence into Chinese and explain the grammar.",
        "请把下面一段中文翻译成自然的英文。",
        "Explain the difference between affect and effect.",
    ],
    "数学推理": [
        "Solve the equation 2x + 7 = 19 and show the steps.",
        "请证明两个奇数之和是偶数。",
        "A train travels 180 km in 3 hours. What is its average speed?",
    ],
    "知识问答": [
        "Explain why the sky appears blue in simple terms.",
        "简述大语言模型中注意力机制的作用。",
        "What are the main causes of climate change?",
    ],
    "学习辅导": [
        "Make a seven-day study plan for learning data analysis.",
        "请用通俗语言解释 Pandas 的 groupby 用法。",
        "Summarize the key differences between classification and clustering.",
    ],
}

LANG_BY_TOPIC = {
    "编程开发": ["English", "Chinese"],
    "写作创作": ["English", "Chinese"],
    "翻译语言": ["English", "Chinese", "Spanish", "French"],
    "数学推理": ["English", "Chinese"],
    "知识问答": ["English", "Chinese", "Spanish"],
    "学习辅导": ["English", "Chinese"],
}


def _assistant_answer(model: str, prompt: str, topic: str, rng: random.Random) -> str:
    base = {
        "编程开发": "Here is a structured solution with code, explanation, and complexity analysis.",
        "写作创作": "Below is a clear and polished draft adapted to the requested tone.",
        "翻译语言": "The translation is provided first, followed by a brief language explanation.",
        "数学推理": "We solve the problem step by step and verify the result.",
        "知识问答": "The concept can be understood through the following concise explanation.",
        "学习辅导": "The topic is organized into definitions, examples, and a short practice plan.",
    }[topic]
    detail = " " + " ".join(["Detailed point" for _ in range(rng.randint(5, 30))])
    return f"[{model}] {base}{detail}"


def generate_sample_csv(output_path: str | Path, rows: int = 800, seed: int = 42) -> pd.DataFrame:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    np.random.seed(seed)

    models = list(MODEL_STRENGTH)
    topics = list(TOPIC_TEMPLATES)
    start = datetime(2023, 4, 1)
    records = []

    for i in range(rows):
        topic = rng.choice(topics)
        prompt = rng.choice(TOPIC_TEMPLATES[topic])
        language = rng.choice(LANG_BY_TOPIC[topic])
        model_a, model_b = rng.sample(models, 2)

        answer_a = _assistant_answer(model_a, prompt, topic, rng)
        answer_b = _assistant_answer(model_b, prompt, topic, rng)

        # 偏好概率由模型强度、回答长度与随机扰动共同决定，仅用于离线演示。
        score_a = MODEL_STRENGTH[model_a] + min(len(answer_a), 800) / 8000 + rng.gauss(0, 0.10)
        score_b = MODEL_STRENGTH[model_b] + min(len(answer_b), 800) / 8000 + rng.gauss(0, 0.10)
        diff = score_a - score_b
        if abs(diff) < 0.05:
            winner = rng.choice(["tie", "tie (bothbad)"])
        else:
            winner = "model_a" if diff > 0 else "model_b"

        conv_a = [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": answer_a},
        ]
        conv_b = [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": answer_b},
        ]
        dt = start + timedelta(hours=rng.randint(0, 24 * 120))

        records.append({
            "question_id": f"Q{i+1:05d}",
            "model_a": model_a,
            "model_b": model_b,
            "winner": winner,
            "judge": f"demo_user_{rng.randint(1, 80)}",
            "conversation_a": json.dumps(conv_a, ensure_ascii=False),
            "conversation_b": json.dumps(conv_b, ensure_ascii=False),
            "turn": 1,
            "anony": True,
            "language": language,
            "tstamp": int(dt.timestamp()),
            "openai_moderation": json.dumps({"flagged": False}),
            "toxicity": round(max(0.0, rng.gauss(0.03, 0.02)), 4),
            "redacted": False,
        })

    df = pd.DataFrame(records)

    # 添加少量重复、缺失和异常记录，便于展示清洗过程。
    if rows >= 100:
        df = pd.concat([df, df.iloc[:5]], ignore_index=True)
        df.loc[10, "language"] = None
        df.loc[20, "model_a"] = None
        df.loc[30, "conversation_a"] = "invalid_json"
        df.loc[40, "tstamp"] = -1

    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    return df
