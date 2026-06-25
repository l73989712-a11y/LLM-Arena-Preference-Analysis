from __future__ import annotations

from urllib.parse import quote_plus
import pandas as pd
from sqlalchemy import create_engine, text


def create_mysql_engine(config: dict):
    password = quote_plus(str(config.get("password", "")))
    url = (
        f"mysql+pymysql://{config['user']}:{password}@{config['host']}:{config['port']}/"
        f"{config['database']}?charset=utf8mb4"
    )
    return create_engine(url, pool_pre_ping=True)


def export_to_mysql(cleaned: pd.DataFrame, model_stat: pd.DataFrame, topic_stat: pd.DataFrame, config: dict) -> None:
    engine = create_mysql_engine(config)
    with engine.begin() as connection:
        connection.execute(text("SELECT 1"))
    cleaned.to_sql("arena_battle", engine, if_exists="replace", index=False, chunksize=1000)
    model_stat.to_sql("model_statistics", engine, if_exists="replace", index=False)
    topic_stat.to_sql("topic_statistics", engine, if_exists="replace", index=False)
