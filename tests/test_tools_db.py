import pytest

from assistant.tools import make_chart, run_sql

pytestmark = pytest.mark.db


def test_select_runs():
    res = run_sql("select count(*) as n from marts.fct_orders")
    assert res["ok"] and res["rows"][0]["n"] > 0


def test_unqualified_table_resolves_to_marts():
    assert run_sql("select count(*) as n from fct_orders")["ok"]


def test_drop_never_reaches_the_database():
    res = run_sql("drop table marts.fct_orders")
    assert not res["ok"] and res["kind"] == "guard"
    assert run_sql("select count(*) from marts.fct_orders")["ok"]


def test_slow_query_times_out():
    res = run_sql(
        "select count(*) from marts.fct_orders a, marts.fct_orders b, marts.fct_orders c",
        timeout_ms=100,
    )
    assert not res["ok"]
    assert "timeout" in res["error"] or "canceling" in res["error"]


def test_row_limit():
    res = run_sql("select order_id from marts.fct_orders")
    assert res["ok"] and len(res["rows"]) <= 200


def test_bad_column_error_comes_back():
    res = run_sql("select review_score from marts.dim_customer")
    assert not res["ok"] and "does not exist" in res["error"]


def test_make_chart_checks_columns():
    rows = [{"a": 1, "b": 2}]
    assert make_chart(rows, "a", "b")["ok"]
    assert not make_chart(rows, "a", "zzz")["ok"]
    assert not make_chart([], "a", "b")["ok"]
