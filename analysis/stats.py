"""Small statistics helpers used by the notebooks and the api.

Kept here instead of inside the notebooks so they can be unit tested.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats


@dataclass
class ProportionComparison:
    n_a: int
    n_b: int
    rate_a: float
    rate_b: float
    diff: float          # rate_a - rate_b
    ci_low: float
    ci_high: float
    z: float
    p_value: float
    relative_risk: float
    cohens_h: float


def compare_proportions(success_a: int, n_a: int, success_b: int, n_b: int,
                        alpha: float = 0.05) -> ProportionComparison:
    """Two-sided z test for p_a - p_b, with a Wald interval on the difference.

    The test uses the pooled standard error (that is what the null assumes),
    the interval uses the unpooled one.
    """
    if n_a == 0 or n_b == 0:
        raise ValueError("both groups need at least one observation")

    p_a, p_b = success_a / n_a, success_b / n_b
    diff = p_a - p_b

    pooled = (success_a + success_b) / (n_a + n_b)
    se_pooled = np.sqrt(pooled * (1 - pooled) * (1 / n_a + 1 / n_b))
    z = diff / se_pooled if se_pooled > 0 else 0.0
    p_value = 2 * stats.norm.sf(abs(z))

    se = np.sqrt(p_a * (1 - p_a) / n_a + p_b * (1 - p_b) / n_b)
    crit = stats.norm.ppf(1 - alpha / 2)

    rr = p_a / p_b if p_b > 0 else float("nan")
    h = 2 * np.arcsin(np.sqrt(p_a)) - 2 * np.arcsin(np.sqrt(p_b))

    return ProportionComparison(
        n_a=n_a, n_b=n_b, rate_a=p_a, rate_b=p_b, diff=diff,
        ci_low=diff - crit * se, ci_high=diff + crit * se,
        z=float(z), p_value=float(p_value), relative_risk=float(rr), cohens_h=float(h),
    )


def mann_kendall(values) -> tuple[float, float]:
    """Mann-Kendall trend test. Returns (tau, p_value).

    Kendall's tau between time order and value is the same statistic; scipy
    gives the p-value with the tie correction.
    """
    y = np.asarray(values, dtype=float)
    y = y[~np.isnan(y)]
    if len(y) < 4:
        return float("nan"), float("nan")
    tau, p = stats.kendalltau(np.arange(len(y)), y)
    return float(tau), float(p)


def holm(p_values) -> np.ndarray:
    """Holm-Bonferroni adjusted p-values, same order as the input."""
    p = np.asarray(p_values, dtype=float)
    order = np.argsort(p)
    m = len(p)
    adjusted = np.empty(m)
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, (m - rank) * p[idx])
        adjusted[idx] = min(1.0, running)
    return adjusted


# ---- forecasting metrics -------------------------------------------------

def mape(actual, forecast) -> float:
    a, f = np.asarray(actual, float), np.asarray(forecast, float)
    mask = a != 0
    return float(np.mean(np.abs((a[mask] - f[mask]) / a[mask])) * 100)


def mase(actual, forecast, train, season: int = 1) -> float:
    """Mean absolute scaled error against the in-sample seasonal naive error."""
    a, f, t = (np.asarray(x, float) for x in (actual, forecast, train))
    if len(t) <= season:
        raise ValueError("training series is shorter than one season")
    scale = np.mean(np.abs(t[season:] - t[:-season]))
    return float(np.mean(np.abs(a - f)) / scale)


def seasonal_naive(train: pd.Series, horizon: int, season: int) -> np.ndarray:
    """Repeat the last full season forward."""
    last = np.asarray(train, float)[-season:]
    reps = int(np.ceil(horizon / season))
    return np.tile(last, reps)[:horizon]
