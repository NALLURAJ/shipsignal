"""Static summary dashboard, saved to images/dashboard.png.

Everything is pulled from the warehouse, so rerun it after rebuilding:

    python -m analysis.make_dashboard
"""

from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyBboxPatch

from analysis.forecast import backtest, clean_daily_series
from analysis.stats import compare_proportions
from api import queries
from common.db import query

OUT = Path(__file__).resolve().parent.parent / "images" / "dashboard.png"

SURF = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#8a8984"
GRID = "#e6e5e0"
BLUE = "#2a78d6"
ORANGE = "#eb6834"
GRAY = "#b9b8b2"


def load():
    out = {"summary": queries.summary()}

    rev = query("""
        select date_trunc('month', purchase_date)::date as m, sum(items_value) as r
        from marts.fct_orders
        where order_status not in ('canceled', 'unavailable')
          and purchase_date >= '2017-01-01' and purchase_date < '2018-09-01'
        group by 1 order by 1
    """)
    out["rev"] = [[str(m), float(r)] for m, r in rev.values]

    # same definition as notebook 01
    firsts = query("""
        with lp as (select max(purchased_at) as ts from marts.fct_orders),
        firsts as (
            select o.customer_unique_id, o.delivered_at, o.is_late
            from marts.fct_orders o, lp
            where o.customer_order_number = 1 and o.is_delivered
              and o.delivered_at <= lp.ts - interval '180 days'
        )
        select f.customer_unique_id, f.is_late,
               bool_or(o2.purchased_at > f.delivered_at
                       and o2.purchased_at <= f.delivered_at + interval '180 days') as rep
        from firsts f
        left join marts.fct_orders o2
            on o2.customer_unique_id = f.customer_unique_id and o2.customer_order_number > 1
        group by 1, 2
    """)
    firsts["rep"] = firsts["rep"].fillna(False).astype(bool)
    g = firsts.groupby("is_late")["rep"].agg(["sum", "count"])
    out["repeat"] = compare_proportions(int(g.loc[True, "sum"]), int(g.loc[True, "count"]),
                                        int(g.loc[False, "sum"]), int(g.loc[False, "count"])).__dict__

    d = query("select delay_days, review_score from marts.fct_orders "
              "where is_delivered and review_score is not null")
    d["g"] = pd.cut(d["delay_days"].astype(float), [-np.inf, -7, 0, 3, 7, 14, np.inf],
                    labels=["7+ early", "0-6 early", "1-3 late", "4-7 late", "8-14 late", "15+ late"])
    b = d.groupby("g", observed=True)["review_score"].agg(n="size", bad=lambda s: (s <= 2).mean())
    out["bad"] = [[str(i), int(x.n), float(x.bad)] for i, x in b.iterrows()]

    s = query("""
        select date_trunc('month', purchase_date)::date as m, category, sum(price) as r
        from marts.fct_order_items
        where order_status not in ('canceled', 'unavailable')
          and purchase_date >= '2017-01-01' and purchase_date < '2018-09-01'
        group by 1, 2
    """)
    w = s.pivot(index="m", columns="category", values="r").fillna(0).sort_index()
    tot = w.sum(axis=1)
    top = w.sum().sort_values(ascending=False).index[:10]
    out["share"] = [[c, float(w[c][:6].sum() / tot[:6].sum()), float(w[c][-6:].sum() / tot[-6:].sum())]
                    for c in top]

    out["state"] = [[x["group"], x["delivered_orders"], x["on_time_rate"]] for x in queries.on_time("state")]

    series = clean_daily_series(queries.daily_orders())
    bt = backtest(series, 91)
    wk = pd.DataFrame({"actual": bt.actual, "naive": bt.naive, "sarima": bt.sarima}).resample("W-SUN").sum()
    hist = series.iloc[-91 - 84:-91].resample("W-SUN").sum()
    out["fc"] = {
        "hist": [[str(i.date()), float(v)] for i, v in hist.items()],
        "wk": [[str(i.date()), *map(float, r)] for i, r in wk.iterrows()],
        "metrics": bt.metrics.round(2).reset_index().to_dict("records"),
    }
    return out


def main():
    D = load()
    plt.rcParams.update({
        "font.family": "Poppins", "font.size": 10,
        "axes.edgecolor": GRID, "axes.labelcolor": INK2,
        "xtick.color": INK2, "ytick.color": INK2,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
        "figure.facecolor": SURF, "axes.facecolor": SURF,
    })

    fig = plt.figure(figsize=(18, 11.2), dpi=150)
    gs = fig.add_gridspec(3, 3, height_ratios=[0.34, 1, 1], hspace=0.62, wspace=0.28,
                          left=0.045, right=0.975, top=0.905, bottom=0.095)
    fig.text(0.045, 0.95, "ShipSignal", fontsize=24,
             fontweight="bold", color=INK)

    def title(ax, t, sub=None):
        ax.set_title(t, loc="left", fontsize=12.5, fontweight="bold", color=INK, pad=22)
        if sub:
            ax.text(0, 1.035, sub, transform=ax.transAxes, fontsize=9.5, color=INK2, va="bottom")

    # ---- KPI row --------------------------------------------------------------
    s = D["summary"]
    kpis = [
        ("Revenue (R$)", f"{s['revenue'] / 1e6:.2f}M", "items only, excl. freight & canceled"),
        ("Orders", f"{s['orders']:,}", "excl. canceled / unavailable"),
        ("Avg order value", f"R$ {s['average_order_value']:.2f}", "revenue / orders"),
        ("On-time delivery", f"{s['on_time_rate'] * 100:.1f}%", "delivered by the promised date"),
        ("Avg review", f"{s['average_review']:.2f} / 5", "latest review per order"),
    ]
    kax = fig.add_subplot(gs[0, :])
    kax.axis("off")
    w = 1 / len(kpis)
    for i, (lab, val, note) in enumerate(kpis):
        x0 = i * w + 0.004
        kax.add_patch(FancyBboxPatch((x0, 0.02), w - 0.012, 0.96, boxstyle="round,pad=0,rounding_size=0.02",
                                     transform=kax.transAxes, facecolor="white", edgecolor=GRID, lw=1))
        kax.text(x0 + 0.015, 0.74, lab, transform=kax.transAxes, fontsize=10.5, color=INK2)
        kax.text(x0 + 0.015, 0.34, val, transform=kax.transAxes, fontsize=22, fontweight="bold", color=INK)
        kax.text(x0 + 0.015, 0.1, note, transform=kax.transAxes, fontsize=8.5, color=MUTED)

    # ---- A: revenue by month ---------------------------------------------------
    ax = fig.add_subplot(gs[1, 0])
    rev = pd.DataFrame(D["rev"], columns=["m", "r"])
    rev["m"] = pd.to_datetime(rev["m"])
    ax.plot(rev["m"], rev["r"] / 1e6, color=BLUE, lw=2, marker="o", ms=4.5,
            markeredgecolor=SURF, markeredgewidth=1.5)
    peak = rev.loc[rev["r"].idxmax()]
    ax.annotate(f"Nov 2017 (Black Friday)\nR$ {peak.r / 1e6:.2f}M", (peak.m, peak.r / 1e6),
                xytext=(-150, -8), textcoords="offset points", fontsize=9, color=INK2,
                arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.8))
    ax.set_ylabel("R$ millions")
    ax.set_ylim(0, 1.15)
    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 4, 7, 10]))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))
    title(ax, "Monthly revenue", "Grew fast through 2017, then flattened in 2018")

    # ---- B: repeat purchase by first-order delivery ------------------------------
    ax = fig.add_subplot(gs[1, 1])
    r = D["repeat"]
    rates = [r["rate_b"], r["rate_a"]]
    ns = [r["n_b"], r["n_a"]]
    errs = [1.96 * np.sqrt(p * (1 - p) / n) for p, n in zip(rates, ns)]
    ax.bar(["On time", "Late"], [p * 100 for p in rates], color=[BLUE, ORANGE], width=0.5)
    ax.errorbar([0, 1], [p * 100 for p in rates], yerr=[e * 100 for e in errs], fmt="none",
                ecolor=INK2, capsize=6, lw=1.2)
    for i, (p, n) in enumerate(zip(rates, ns)):
        ax.text(i, p * 100 + errs[i] * 100 + 0.08, f"{p * 100:.2f}%", ha="center", fontsize=12,
                fontweight="bold", color=INK)
        ax.text(i, 0.08, f"n = {n:,}", ha="center", fontsize=9, color="white")
    ax.set_ylim(0, 2.5)
    ax.set_ylabel("% who ordered again within 180 days")
    ax.grid(axis="x", visible=False)
    ax.text(0.5, 0.93, f"{r['diff'] * 100:+.2f} pp  (95% CI {r['ci_low'] * 100:.2f} to {r['ci_high'] * 100:.2f}),  "
            f"p = {r['p_value']:.3f}", transform=ax.transAxes, ha="center", fontsize=9.5, color=INK2)
    title(ax, "Late first order = about a third fewer repeat buyers",
          "Repeat rate by how the customer's first order arrived (whiskers = 95% CI)")

    # ---- C: bad review rate by delivery timing -----------------------------------
    ax = fig.add_subplot(gs[1, 2])
    bad = pd.DataFrame(D["bad"], columns=["g", "n", "bad"])
    cols = [BLUE if "early" in g else ORANGE for g in bad["g"]]
    ax.bar(range(len(bad)), bad["bad"] * 100, color=cols, width=0.62)
    for i, row in bad.iterrows():
        ax.text(i, row.bad * 100 + 2, f"{row.bad * 100:.0f}%", ha="center", fontsize=10.5, fontweight="bold",
                color=INK)
    ax.set_xticks(range(len(bad)))
    ax.set_xticklabels([g.replace(" ", "\n", 1) for g in bad["g"]], fontsize=9)
    ax.set_ylim(0, 100)
    ax.set_ylabel("% of reviews that are 1-2 stars")
    ax.grid(axis="x", visible=False)
    title(ax, "Bad reviews jump once an order is late",
          "Share of 1-2 star reviews by delivery vs promised date (n = 95,824)")

    # ---- D: category share, first 6 vs last 6 months --------------------------
    ax = fig.add_subplot(gs[2, 0])
    sh = pd.DataFrame(D["share"], columns=["c", "a", "b"]).sort_values("b")
    gain, lose = {"watches_gifts"}, {"cool_stuff", "garden_tools"}
    for i, row in enumerate(sh.itertuples()):
        col = BLUE if row.c in gain else ORANGE if row.c in lose else GRAY
        ax.plot([row.a * 100, row.b * 100], [i, i], color=col, lw=2.2, zorder=1)
        ax.scatter([row.a * 100], [i], s=40, facecolor=SURF, edgecolor=col, lw=1.8, zorder=2)
        ax.scatter([row.b * 100], [i], s=55, color=col, edgecolor=SURF, lw=1.5, zorder=3)
        weight = "bold" if col != GRAY else "normal"
        ax.text(-0.3, i, row.c.replace("_", " "), ha="right", va="center", fontsize=9.5,
                color=INK if col != GRAY else INK2, fontweight=weight)
    ax.set_yticks([])
    ax.set_xlim(0, 12)
    ax.set_xlabel("% of marketplace revenue")
    ax.spines["left"].set_visible(False)
    ax.set_xlim(-6.8, 12)
    ax.set_xticks([0, 2, 4, 6, 8, 10, 12])
    ax.axvline(0, color=GRID, lw=1)
    ax.text(0.0, -0.2, "hollow dot = Jan-Jun 2017, filled dot = Mar-Aug 2018. blue = gained share, orange = lost (Holm-adjusted)",
            transform=ax.transAxes, fontsize=8.5, color=INK2)
    title(ax, "Only watches & gifts truly gained share",
          "Top 10 categories: revenue share, first 6 vs last 6 months")

    # ---- E: on-time rate by state (worst 10) -----------------------------------
    ax = fig.add_subplot(gs[2, 1])
    st = pd.DataFrame(D["state"], columns=["s", "n", "r"])
    overall = D["summary"]["on_time_rate"] * 100
    worst = st.sort_values("r").head(10).iloc[::-1]
    ys = range(len(worst))
    ax.hlines(list(ys), 70, worst["r"] * 100, color=GRID, lw=1.2)
    ax.scatter(worst["r"] * 100, list(ys), s=70, color=ORANGE, edgecolor=SURF, lw=1.5, zorder=3)
    ax.set_yticks(list(ys))
    ax.set_yticklabels(worst["s"])
    for i, row in enumerate(worst.itertuples()):
        ax.text(row.r * 100 - 0.8, i, f"{row.r * 100:.1f}%  ({row.n:,})", va="center", ha="right", fontsize=9,
                color=INK2)
    ax.axvline(overall, color=BLUE, lw=1.6, ls="--")
    ax.text(overall + 0.4, 0.2, f"all states\n{overall:.1f}%", color=BLUE, fontsize=9, ha="left", va="bottom")
    ax.set_xlim(70, 100)
    ax.set_xlabel("on-time delivery rate (%)")
    ax.grid(axis="y", visible=False)
    title(ax, "The 5 worst states are all in the Northeast",
          "10 customer states with the lowest on-time rate (delivered orders in brackets)")

    # ---- F: forecast hold-out ----------------------------------------------------
    ax = fig.add_subplot(gs[2, 2])
    fc = D["fc"]
    hist = pd.DataFrame(fc["hist"], columns=["d", "v"])
    wk = pd.DataFrame(fc["wk"], columns=["d", "actual", "naive", "sarima"])
    for df_ in (hist, wk):
        df_["d"] = pd.to_datetime(df_["d"])
    # drop partial first/last weeks of the hold-out so weekly totals compare like with like
    wk = wk.iloc[1:-1]
    ax.plot(hist["d"].iloc[1:-1], hist["v"].iloc[1:-1], color=INK2, lw=2)
    ax.plot(wk["d"], wk["actual"], color=INK2, lw=2, marker="o", ms=4.5, markeredgecolor=SURF, label="actual")
    ax.plot(wk["d"], wk["sarima"], color=BLUE, lw=2, marker="o", ms=4.5, markeredgecolor=SURF, label="SARIMA")
    ax.plot(wk["d"], wk["naive"], color=ORANGE, lw=2, ls="--", label="seasonal naive (baseline)")
    ax.axvline(wk["d"].iloc[0] - pd.Timedelta(days=7), color=MUTED, lw=1, ls=":")
    ax.text(wk["d"].iloc[0] - pd.Timedelta(days=5), 2150, "hold-out", fontsize=9, color=MUTED)
    ax.set_ylabel("orders per week")
    ax.set_ylim(0, 2700)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.legend(loc="upper left", fontsize=8.5, frameon=False, ncol=3)
    m = {x["model"]: x for x in fc["metrics"]}
    ax.text(0.99, 0.04, f"daily MAPE  SARIMA {m['SARIMA']['MAPE_daily_%']:.1f}%  vs  baseline "
            f"{m['seasonal naive']['MAPE_daily_%']:.1f}%\nquarter total  SARIMA {m['SARIMA']['total_error_%']:+.1f}%  vs  "
            f"baseline {m['seasonal naive']['total_error_%']:+.1f}%", transform=ax.transAxes, ha="right",
            fontsize=8.5, color=INK2)
    title(ax, "Forecast: better day to day, not on the quarter total",
          "91-day hold-out, weekly totals (partial weeks dropped)")

    fig.text(0.045, 0.016, "Data: Olist Brazilian E-Commerce Public Dataset (Kaggle, CC BY-NC-SA 4.0). "
             "Findings are observational associations, not proven causes. Late = delivered after the estimated date "
             "shown at purchase.", fontsize=8.5, color=MUTED)
    OUT.parent.mkdir(exist_ok=True)
    fig.savefig(OUT, facecolor=SURF)
    print(f"saved {OUT}")


if __name__ == "__main__":
    main()
