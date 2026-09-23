from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class DateRange(BaseModel):
    start: date | None = None
    end: date | None = None

    @model_validator(mode="after")
    def check_order(self):
        if self.start and self.end and self.start > self.end:
            raise ValueError("start must be on or before end")
        return self


class Summary(BaseModel):
    orders: int
    revenue: float
    average_order_value: float
    on_time_rate: float | None
    average_review: float | None


class RevenuePoint(BaseModel):
    period: date
    orders: int
    revenue: float


class RevenueResponse(BaseModel):
    grain: Literal["day", "week", "month"]
    points: list[RevenuePoint]


class CategoryRow(BaseModel):
    category: str
    revenue: float
    items: int
    share: float


class OnTimeRow(BaseModel):
    group: str
    delivered_orders: int
    on_time_rate: float
    average_delay_days: float


class ForecastPoint(BaseModel):
    day: date
    forecast: float
    low: float
    high: float


class ForecastResponse(BaseModel):
    model: str
    trained_through: date
    horizon_days: int
    total_forecast: float
    points: list[ForecastPoint]


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)


class AskResponse(BaseModel):
    answer: str
    sql: str | None = None
    rows: list[dict[str, Any]] = []
    chart: dict[str, Any] | None = None
    tools_used: list[str | None] = []
    latency_ms: int
