from __future__ import annotations

from pathlib import Path
import pandas as pd


def download_chatbot_arena(output_path: str | Path) -> pd.DataFrame:
    """从 Hugging Face 下载真实数据。需要联网和 datasets 包。"""
    try:
        from datasets import load_dataset
    except ImportError as exc:
        raise RuntimeError("缺少 datasets 包，请先 pip install datasets") from exc

    dataset = load_dataset("lmsys/chatbot_arena_conversations", split="train")
    df = dataset.to_pandas()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    return df


def load_csv(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"找不到数据文件：{path}")
    return pd.read_csv(path)
