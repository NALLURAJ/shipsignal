import os
from functools import lru_cache

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

DEFAULT_URL = "postgresql://shipsignal:shipsignal@localhost:5432/shipsignal"


def database_url() -> str:
    url = os.environ.get("DATABASE_URL", DEFAULT_URL)
    # sqlalchemy needs the driver spelled out for psycopg 3
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


@lru_cache(maxsize=1)
def engine() -> Engine:
    return create_engine(database_url(), pool_pre_ping=True)


def query(sql: str, **params) -> pd.DataFrame:
    with engine().connect() as conn:
        return pd.read_sql(text(sql), conn, params=params)
