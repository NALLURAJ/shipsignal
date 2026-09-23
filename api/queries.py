"""SQL behind each endpoint. Definitions match docs/definitions.md."""

from datetime import date

from common.db import query

# orders that count toward revenue
VALID_ORDER = "order_status not in ('canceled', 'unavailable')"


def _range_filter(column: str, start: date | None, end: date | None) -> tuple[str, dict]:
    clauses, params = [], {}
    if start:
        clauses.append(f"{column} >= :start")
        params["start"] = start
    if end:
        clauses.append(f"{column} <= :end")
        params["end"] = end
    return (" and " + " and ".join(clauses)) if clauses else "", params


def summary(start=None, end=None) -> dict:
    where, params = _range_filter("purchase_date", start, end)
    df = query(f"""
        select
            count(*) filter (where {VALID_ORDER})                     as orders,
            coalesce(sum(items_value) filter (where {VALID_ORDER}), 0) as revenue,
            avg(case when is_late then 0.0 else 1.0 end)
                filter (where is_delivered)                           as on_time_rate,
            avg(review_score)                                         as average_review
        from marts.fct_orders
        where true {where}
    """, **params)
    row = df.iloc[0]
    orders = int(row["orders"])
    revenue = float(row["revenue"])
    return {
        "orders": orders,
        "revenue": round(revenue, 2),
        "average_order_value": round(revenue / orders, 2) if orders else 0.0,
        "on_time_rate": None if row["on_time_rate"] is None else round(float(row["on_time_rate"]), 4),
        "average_review": None if row["average_review"] is None else round(float(row["average_review"]), 3),
    }


def revenue_series(grain: str, start=None, end=None) -> list[dict]:
    if grain not in {"day", "week", "month"}:
        raise ValueError(f"unsupported grain: {grain}")
    where, params = _range_filter("purchase_date", start, end)
    df = query(f"""
        select
            date_trunc('{grain}', purchase_date)::date as period,
            count(*) as orders,
            sum(items_value) as revenue
        from marts.fct_orders
        where {VALID_ORDER} {where}
        group by 1
        order by 1
    """, **params)
    df["revenue"] = df["revenue"].astype(float).round(2)
    return df.to_dict(orient="records")


def top_categories(limit: int, start=None, end=None) -> list[dict]:
    where, params = _range_filter("purchase_date", start, end)
    df = query(f"""
        with by_cat as (
            select category, sum(price) as revenue, count(*) as items
            from marts.fct_order_items
            where {VALID_ORDER} {where}
            group by category
        )
        select category, revenue, items, revenue / sum(revenue) over () as share
        from by_cat
        order by revenue desc
        limit :limit
    """, limit=limit, **params)
    df["revenue"] = df["revenue"].astype(float).round(2)
    df["share"] = df["share"].astype(float).round(4)
    return df.to_dict(orient="records")


def on_time(by: str, start=None, end=None) -> list[dict]:
    group_sql = {
        "state": "customer_state",
        "month": "to_char(date_trunc('month', purchase_date), 'YYYY-MM')",
        "overall": "'all'",
    }.get(by)
    if group_sql is None:
        raise ValueError(f"unsupported grouping: {by}")
    where, params = _range_filter("purchase_date", start, end)
    df = query(f"""
        select
            {group_sql} as "group",
            count(*) as delivered_orders,
            avg(case when is_late then 0.0 else 1.0 end) as on_time_rate,
            avg(delay_days) as average_delay_days
        from marts.fct_orders
        where is_delivered {where}
        group by 1
        order by 1
    """, **params)
    df["on_time_rate"] = df["on_time_rate"].astype(float).round(4)
    df["average_delay_days"] = df["average_delay_days"].astype(float).round(2)
    return df.to_dict(orient="records")


def daily_orders():
    return query("""
        select purchase_date as day, count(*) as orders
        from marts.fct_orders
        where purchase_date >= '2017-01-01'
        group by 1 order by 1
    """)
