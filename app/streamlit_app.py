"""Front end for the ShipSignal API. It only talks to the API, never the database."""

import os
from datetime import date

import httpx
import pandas as pd
import streamlit as st

API_URL = os.environ.get("API_URL", "http://localhost:8000")

st.set_page_config(page_title="ShipSignal", layout="wide")


@st.cache_data(ttl=300)
def get(path: str, **params):
    params = {k: v for k, v in params.items() if v is not None}
    r = httpx.get(f"{API_URL}{path}", params=params, timeout=60)
    r.raise_for_status()
    return r.json()


def post(path: str, body: dict):
    r = httpx.post(f"{API_URL}{path}", json=body, timeout=300)
    r.raise_for_status()
    return r.json()


st.title("ShipSignal")
st.caption("Olist Brazilian e-commerce, 2016-2018. Revenue excludes freight and canceled orders.")

with st.sidebar:
    st.header("Filters")
    start = st.date_input("From", value=date(2017, 1, 1), min_value=date(2016, 9, 1), max_value=date(2018, 10, 31))
    end = st.date_input("To", value=date(2018, 8, 31), min_value=date(2016, 9, 1), max_value=date(2018, 10, 31))
    grain = st.radio("Revenue by", ["month", "week", "day"], horizontal=True)

try:
    get("/health")
except httpx.HTTPError:
    st.error(f"Can't reach the API at {API_URL}. Start it with `uvicorn api.main:app`.")
    st.stop()

tab_overview, tab_delivery, tab_forecast, tab_ask = st.tabs(["Overview", "Delivery", "Forecast", "Ask"])

with tab_overview:
    s = get("/metrics/summary", start=start, end=end)
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Revenue (R$)", f"{s['revenue']:,.0f}")
    c2.metric("Orders", f"{s['orders']:,}")
    c3.metric("Avg order value (R$)", f"{s['average_order_value']:,.2f}")
    c4.metric("On-time rate", f"{s['on_time_rate']:.1%}" if s["on_time_rate"] is not None else "n/a")
    c5.metric("Avg review", f"{s['average_review']:.2f}" if s["average_review"] is not None else "n/a")

    rev = pd.DataFrame(get("/metrics/revenue", grain=grain, start=start, end=end)["points"])
    if not rev.empty:
        st.subheader("Revenue")
        st.line_chart(rev.set_index("period")["revenue"])

    st.subheader("Top categories")
    cats = pd.DataFrame(get("/categories/top", limit=10, start=start, end=end))
    if not cats.empty:
        left, right = st.columns([2, 1])
        left.bar_chart(cats.set_index("category")["revenue"])
        right.dataframe(cats.assign(share=cats["share"].map("{:.1%}".format)), hide_index=True)

with tab_delivery:
    by_state = pd.DataFrame(get("/delivery/on-time", by="state", start=start, end=end))
    by_month = pd.DataFrame(get("/delivery/on-time", by="month", start=start, end=end))
    if not by_month.empty:
        st.subheader("On-time rate by month")
        st.line_chart(by_month.set_index("group")["on_time_rate"])
    if not by_state.empty:
        st.subheader("By customer state")
        st.dataframe(by_state.sort_values("on_time_rate"), hide_index=True, use_container_width=True)

with tab_forecast:
    horizon = st.slider("Days ahead", 14, 182, 91, step=7)
    with st.spinner("Fitting the model..."):
        fc = get("/forecast", horizon=horizon)
    st.write(f"**{fc['model']}**, trained through {fc['trained_through']}. "
             f"Forecast total: **{fc['total_forecast']:,.0f} orders** over {fc['horizon_days']} days.")
    pts = pd.DataFrame(fc["points"]).set_index("day")
    st.line_chart(pts[["forecast", "low", "high"]])
    st.caption("Shaded band in the notebook is an 80% interval per day. Yearly holidays are not modelled.")

with tab_ask:
    st.write("Ask a question about the data. The assistant writes a read-only SQL query and shows it.")
    q = st.text_input("Question", placeholder="Which 5 categories had the most revenue in 2018?")
    if st.button("Ask", type="primary") and q:
        with st.spinner("Thinking..."):
            try:
                res = post("/ask", {"question": q})
            except httpx.HTTPStatusError as exc:
                st.error(exc.response.json().get("detail", str(exc)))
                st.stop()
        st.markdown(f"**Answer:** {res['answer']}")
        if res.get("sql"):
            with st.expander("SQL"):
                st.code(res["sql"], language="sql")
        if res.get("rows"):
            st.dataframe(pd.DataFrame(res["rows"]), hide_index=True)
        chart = res.get("chart")
        if chart:
            data = pd.DataFrame(chart["data"]).set_index(chart["x"])
            (st.line_chart if chart["kind"] == "line" else st.bar_chart)(data[chart["y"]])
        st.caption(f"{res['latency_ms']} ms · tools: {', '.join(t for t in res['tools_used'] if t)}")
