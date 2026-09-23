"""Daily order forecasting: a seasonal naive baseline and a SARIMA model.

Used by notebook 04 and by the api's /forecast endpoint.
"""

import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd
from statsmodels.tsa.statespace.sarimax import SARIMAX

from analysis.stats import mape, mase, seasonal_naive

SEASON = 7  # weekly pattern in daily orders
DEFAULT_ORDER = (2, 1, 1)  # chosen by AIC on the training data in notebook 04
DEFAULT_SEASONAL = (1, 0, 1, SEASON)

DAILY_ORDERS_SQL = """
select purchase_date as day, count(*) as orders
from marts.fct_orders
where purchase_date >= :start
group by 1
order by 1
"""


def clean_daily_series(df: pd.DataFrame, min_share: float = 0.75) -> pd.Series:
    """Turn (day, orders) rows into a gap-free daily series.

    The extract stops part way through August 2018: volume falls off over the
    last week and then there are only a few stray orders into October. Walking
    back from the end, the series is cut at the last day where the average of
    that day and the next six is at least `min_share` of the typical day.
    Walking back (instead of forward) means dips like Christmas can't end it early.
    """
    s = df.set_index(pd.to_datetime(df["day"]))["orders"].astype(float)
    s = s.asfreq("D", fill_value=0.0)
    typical = s[s > 0].median()
    next_week = s[::-1].rolling(7, min_periods=1).mean()[::-1]
    healthy = next_week[next_week >= min_share * typical]
    return s.loc[: healthy.index.max()]


@dataclass
class Backtest:
    horizon: int
    actual: pd.Series
    naive: pd.Series
    sarima: pd.Series
    metrics: pd.DataFrame


def fit_sarima(train: pd.Series, order=DEFAULT_ORDER, seasonal_order=DEFAULT_SEASONAL):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = SARIMAX(np.log1p(train), order=order, seasonal_order=seasonal_order,
                        enforce_stationarity=False, enforce_invertibility=False)
        return model.fit(disp=False)


def sarima_forecast(train: pd.Series, horizon: int, alpha: float = 0.2,
                    order=DEFAULT_ORDER, seasonal_order=DEFAULT_SEASONAL) -> pd.DataFrame:
    """Forecast on the original scale. Model is fit on log1p(orders)."""
    res = fit_sarima(train, order, seasonal_order)
    fc = res.get_forecast(horizon)
    ci = fc.conf_int(alpha=alpha)
    idx = pd.date_range(train.index[-1] + pd.Timedelta(days=1), periods=horizon, freq="D")
    return pd.DataFrame({
        "forecast": np.expm1(fc.predicted_mean.to_numpy()),
        "low": np.expm1(ci.iloc[:, 0].to_numpy()),
        "high": np.expm1(ci.iloc[:, 1].to_numpy()),
    }, index=idx)


def backtest(series: pd.Series, horizon: int = 91, order=DEFAULT_ORDER,
             seasonal_order=DEFAULT_SEASONAL) -> Backtest:
    train, test = series.iloc[:-horizon], series.iloc[-horizon:]

    naive = pd.Series(seasonal_naive(train, horizon, SEASON), index=test.index)
    sarima = sarima_forecast(train, horizon, order=order, seasonal_order=seasonal_order)["forecast"]
    sarima.index = test.index

    rows = []
    for name, f in [("seasonal naive", naive), ("SARIMA", sarima)]:
        rows.append({
            "model": name,
            "MAPE_daily_%": mape(test, f),
            "MASE_daily": mase(test, f, train, SEASON),
            "total_forecast": f.sum(),
            "total_actual": test.sum(),
            "total_error_%": (f.sum() - test.sum()) / test.sum() * 100,
        })
    return Backtest(horizon, test, naive, sarima, pd.DataFrame(rows).set_index("model"))
