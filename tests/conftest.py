import pytest
from sqlalchemy import text


def _warehouse_ready() -> bool:
    try:
        from common.db import engine

        with engine().connect() as conn:
            conn.execute(text("select 1 from marts.fct_orders limit 1"))
        return True
    except Exception:
        return False


WAREHOUSE_READY = _warehouse_ready()


def pytest_collection_modifyitems(config, items):
    if WAREHOUSE_READY:
        return
    skip = pytest.mark.skip(reason="postgres with the dbt models is not available")
    for item in items:
        if "db" in item.keywords:
            item.add_marker(skip)
