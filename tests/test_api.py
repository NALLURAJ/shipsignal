import pytest
from fastapi.testclient import TestClient

from api.main import app, get_assistant
from common.db import query

client = TestClient(app)


class StubAssistant:
    def ask(self, question):
        return {"answer": f"stub: {question}", "sql": "select 1", "rows": [{"n": 1}],
                "tools_used": ["run_sql"], "chart": None}


class OfflineAssistant:
    def ask(self, question):
        raise ConnectionError("cannot reach ollama")


@pytest.fixture
def stub_assistant():
    app.dependency_overrides[get_assistant] = lambda: StubAssistant()
    yield
    app.dependency_overrides.clear()


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
    assert "x-request-id" in r.headers


def test_bad_date_range_is_rejected():
    r = client.get("/metrics/summary", params={"start": "2018-05-01", "end": "2018-01-01"})
    assert r.status_code == 422


def test_bad_grain_is_rejected():
    assert client.get("/metrics/revenue", params={"grain": "year"}).status_code == 422


def test_limit_is_validated():
    assert client.get("/categories/top", params={"limit": 0}).status_code == 422
    assert client.get("/categories/top", params={"limit": 500}).status_code == 422


def test_ask_validates_question(stub_assistant):
    assert client.post("/ask", json={"question": ""}).status_code == 422
    assert client.post("/ask", json={"question": "x" * 501}).status_code == 422


def test_ask_returns_answer(stub_assistant):
    r = client.post("/ask", json={"question": "how many orders?"})
    assert r.status_code == 200
    body = r.json()
    assert body["answer"] == "stub: how many orders?"
    assert body["latency_ms"] >= 0


def test_ask_when_model_is_down():
    app.dependency_overrides[get_assistant] = lambda: OfflineAssistant()
    try:
        r = client.post("/ask", json={"question": "how many orders?"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 503


# ---- these need the warehouse ------------------------------------------------

@pytest.mark.db
def test_summary_matches_warehouse():
    s = client.get("/metrics/summary").json()
    expected = query("""
        select count(*) as n, sum(items_value) as rev
        from marts.fct_orders where order_status not in ('canceled', 'unavailable')
    """).iloc[0]
    assert s["orders"] == int(expected["n"])
    assert s["revenue"] == pytest.approx(float(expected["rev"]), abs=0.01)
    assert 0 <= s["on_time_rate"] <= 1


@pytest.mark.db
def test_revenue_series_adds_up_to_summary():
    params = {"start": "2017-01-01", "end": "2017-12-31"}
    total = client.get("/metrics/summary", params=params).json()["revenue"]
    points = client.get("/metrics/revenue", params={**params, "grain": "month"}).json()["points"]
    assert sum(p["revenue"] for p in points) == pytest.approx(total, abs=1)
    assert len(points) <= 12


@pytest.mark.db
def test_top_categories_sorted_and_shares_valid():
    rows = client.get("/categories/top", params={"limit": 5}).json()
    revenues = [r["revenue"] for r in rows]
    assert revenues == sorted(revenues, reverse=True)
    assert 0 < sum(r["share"] for r in rows) <= 1.0001


@pytest.mark.db
def test_on_time_by_state():
    rows = client.get("/delivery/on-time", params={"by": "state"}).json()
    assert rows and all(0 <= r["on_time_rate"] <= 1 for r in rows)


@pytest.mark.db
def test_forecast_shape():
    r = client.get("/forecast", params={"horizon": 14})
    assert r.status_code == 200
    body = r.json()
    assert len(body["points"]) == 14
    assert all(p["low"] <= p["forecast"] <= p["high"] for p in body["points"])
