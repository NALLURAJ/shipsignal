import numpy as np
import pandas as pd
import pytest
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.proportion import proportions_ztest

from analysis.stats import compare_proportions, holm, mann_kendall, mape, mase, seasonal_naive


def test_proportion_test_matches_statsmodels():
    res = compare_proportions(30, 1000, 55, 1200)
    z, p = proportions_ztest([30, 55], [1000, 1200])
    assert res.z == pytest.approx(z)
    assert res.p_value == pytest.approx(p)
    assert res.diff == pytest.approx(0.03 - 55 / 1200)


def test_proportion_interval_contains_difference():
    res = compare_proportions(120, 2000, 90, 2000)
    assert res.ci_low < res.diff < res.ci_high
    assert res.relative_risk == pytest.approx(120 / 90)


def test_identical_groups_give_no_effect():
    res = compare_proportions(50, 500, 50, 500)
    assert res.diff == 0
    assert res.p_value == pytest.approx(1.0)
    assert res.cohens_h == pytest.approx(0.0)


def test_empty_group_raises():
    with pytest.raises(ValueError):
        compare_proportions(0, 0, 5, 10)


def test_holm_matches_statsmodels():
    p = [0.01, 0.04, 0.03, 0.2, 0.001]
    expected = multipletests(p, method="holm")[1]
    assert np.allclose(holm(p), expected)


def test_mann_kendall_detects_trend():
    tau, p = mann_kendall(np.arange(20) + np.random.default_rng(0).normal(0, 1, 20))
    assert tau > 0.5 and p < 0.01


def test_mann_kendall_short_series():
    tau, p = mann_kendall([1, 2, 3])
    assert np.isnan(tau) and np.isnan(p)


def test_seasonal_naive_repeats_last_season():
    train = pd.Series([1, 2, 3, 4, 5, 6, 7, 10, 20, 30, 40, 50, 60, 70])
    assert list(seasonal_naive(train, 10, 7)) == [10, 20, 30, 40, 50, 60, 70, 10, 20, 30]


def test_mape_and_mase():
    assert mape([100, 200], [110, 180]) == pytest.approx(10.0)
    train = [1, 2, 3, 4, 5]
    # in-sample naive error is 1, forecast error is 2
    assert mase([10, 10], [12, 8], train, season=1) == pytest.approx(2.0)


def test_mase_needs_enough_history():
    with pytest.raises(ValueError):
        mase([1], [1], [1, 2], season=7)


def test_daily_series_is_cut_where_the_extract_tails_off():
    from analysis.forecast import clean_daily_series

    days = pd.date_range("2018-01-01", periods=120, freq="D")
    orders = [300] * 100 + [150, 90, 60, 40, 10, 3] + [1] * 14
    # christmas-style dip in the middle must not end the series
    orders[50:53] = [60, 50, 70]
    s = clean_daily_series(pd.DataFrame({"day": days, "orders": orders}))
    assert s.index.max() < days[100]
    assert s.index.max() > days[90]


def test_daily_series_fills_missing_days():
    from analysis.forecast import clean_daily_series

    df = pd.DataFrame({"day": pd.to_datetime(["2018-01-01", "2018-01-03"]), "orders": [5, 5]})
    s = clean_daily_series(df)
    assert len(s) == 3 and s.iloc[1] == 0
