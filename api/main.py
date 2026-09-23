import logging
import time
import uuid
from datetime import date
from functools import lru_cache
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError, ProgrammingError

from api import queries
from api.logging_setup import setup_logging
from api.schemas import (
    AskRequest,
    AskResponse,
    CategoryRow,
    DateRange,
    ForecastResponse,
    OnTimeRow,
    RevenueResponse,
    Summary,
)

setup_logging()
log = logging.getLogger("api")

app = FastAPI(
    title="ShipSignal API",
    version="0.1.0",
    description="Metrics, forecast and a question-answering endpoint over the Olist warehouse.",
)


@app.middleware("http")
async def request_log(request: Request, call_next):
    request_id = uuid.uuid4().hex[:8]
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        log.exception("unhandled error", extra={"fields": {"request_id": request_id}})
        raise
    ms = int((time.perf_counter() - started) * 1000)
    log.info("request", extra={"fields": {
        "request_id": request_id,
        "method": request.method,
        "path": request.url.path,
        "status": response.status_code,
        "ms": ms,
    }})
    response.headers["x-request-id"] = request_id
    return response


@app.exception_handler(OperationalError)
async def db_down(_: Request, exc: OperationalError):
    log.error("database unavailable: %s", exc.orig)
    return JSONResponse(status_code=503, content={"detail": "database unavailable"})


@app.exception_handler(ProgrammingError)
async def warehouse_missing(_: Request, exc: ProgrammingError):
    # usually means dbt hasn't been run yet
    log.error("query failed: %s", exc.orig)
    return JSONResponse(status_code=503, content={"detail": "warehouse tables not found, run the loader first"})


def date_range(start: date | None = None, end: date | None = None) -> DateRange:
    try:
        return DateRange(start=start, end=end)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/metrics/summary", response_model=Summary)
def metrics_summary(rng: DateRange = Depends(date_range)):
    return queries.summary(rng.start, rng.end)


@app.get("/metrics/revenue", response_model=RevenueResponse)
def metrics_revenue(
    grain: Literal["day", "week", "month"] = "month",
    rng: DateRange = Depends(date_range),
):
    return {"grain": grain, "points": queries.revenue_series(grain, rng.start, rng.end)}


@app.get("/categories/top", response_model=list[CategoryRow])
def categories_top(
    limit: int = Query(10, ge=1, le=50),
    rng: DateRange = Depends(date_range),
):
    return queries.top_categories(limit, rng.start, rng.end)


@app.get("/delivery/on-time", response_model=list[OnTimeRow])
def delivery_on_time(
    by: Literal["overall", "state", "month"] = "overall",
    rng: DateRange = Depends(date_range),
):
    return queries.on_time(by, rng.start, rng.end)


@lru_cache(maxsize=8)
def _forecast(horizon: int) -> dict:
    # fitting takes a couple of seconds, so results are cached per horizon
    from analysis.forecast import clean_daily_series, sarima_forecast

    series = clean_daily_series(queries.daily_orders())
    fc = sarima_forecast(series, horizon)
    points = [
        {"day": d.date(), "forecast": round(r.forecast, 1), "low": round(r.low, 1), "high": round(r.high, 1)}
        for d, r in fc.iterrows()
    ]
    return {
        "model": "SARIMA(2,1,1)(1,0,1,7) on log daily orders",
        "trained_through": series.index[-1].date(),
        "horizon_days": horizon,
        "total_forecast": round(float(fc["forecast"].sum()), 0),
        "points": points,
    }


@app.get("/forecast", response_model=ForecastResponse)
def forecast(horizon: int = Query(91, ge=7, le=182)):
    return _forecast(horizon)


def get_assistant():
    from assistant.agent import Assistant

    return Assistant.from_env()


@app.post("/ask", response_model=AskResponse)
def ask(body: AskRequest, assistant=Depends(get_assistant)):
    started = time.perf_counter()
    try:
        result = assistant.ask(body.question)
    except ConnectionError as exc:
        raise HTTPException(status_code=503, detail=f"language model unavailable: {exc}") from exc
    result["latency_ms"] = int((time.perf_counter() - started) * 1000)
    log.info("ask", extra={"fields": {
        "question": body.question,
        "tools": result.get("tools_used"),
        "ms": result["latency_ms"],
    }})
    return result
