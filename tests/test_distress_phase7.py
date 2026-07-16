"""
Phase 7 distress signal helper tests
======================================
Covers the pure helpers added for Phase 7 distress signals: _yf_row_prev,
_compute_piotroski, _compute_altman_z, _sector_allows, _compute_stats, and
the corresponding Safety-pillar additions to overall_score().

DESIGN RULES (match test_factors_phase6.py):
  - Vanilla assert only -- no pytest dependency.
  - Dummy env vars retained for compatibility with network-entry-point guards.
  - No network calls, no yf.Ticker -- all inputs are plain DataFrames with synthetic values.

HOW TO RUN:
    python tests/test_distress_phase7.py
"""

import os
import sys

os.environ.setdefault("FRED_API_KEY", "test")
os.environ.setdefault("FINNHUB_API_KEY", "test")

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import pandas as pd

from stock_screener import (
    _yf_row_prev,
    _compute_piotroski,
    _compute_altman_z,
    overall_score,
    _compute_stats,
    _sector_allows,
    DCF_EXCLUDED_SECTORS,
    ALTMAN_EXCLUDED_SECTORS,
)


# ── Fixture helpers ──────────────────────────────────────────────────────────


def _make_df(data: dict, cols=("2024", "2023")) -> pd.DataFrame:
    """Build a small DataFrame with two columns (newest-first) from a {label: (curr_val, prev_val)} dict."""
    rows = {label: list(vals) for label, vals in data.items()}
    df = pd.DataFrame.from_dict(rows, orient="index", columns=list(cols))
    return df


def _make_income_curr(net_income=1_000, gross_profit=4_000, revenue=10_000, ebit=1_500) -> pd.DataFrame:
    return _make_df(
        {
            "Net Income": (net_income, net_income * 0.8),
            "Gross Profit": (gross_profit, gross_profit * 0.9),
            "Total Revenue": (revenue, revenue * 0.9),
            "EBIT": (ebit, ebit * 0.9),
        }
    )


def _make_cashflow_curr(ocf=2_000) -> pd.DataFrame:
    return _make_df({"Operating Cash Flow": (ocf, ocf * 0.9)})


# ── _yf_row_prev ─────────────────────────────────────────────────────────────


def test_yf_row_prev_returns_prior_year_value():
    df = pd.DataFrame({"2024": [100.0, 200.0], "2023": [90.0, 180.0]}, index=["Operating Cash Flow", "Capital Expenditure"])
    result = _yf_row_prev(df, ["Operating Cash Flow"])
    assert result == 90.0, f"expected 90.0, got {result}"


def test_yf_row_prev_second_label_when_first_absent():
    df = pd.DataFrame({"2024": [100.0], "2023": [85.0]}, index=["Total Cash From Operating Activities"])
    result = _yf_row_prev(df, ["Operating Cash Flow", "Total Cash From Operating Activities"])
    assert result == 85.0, f"expected 85.0, got {result}"


def test_yf_row_prev_none_when_only_one_column():
    df = pd.DataFrame({"2024": [100.0]}, index=["Operating Cash Flow"])
    result = _yf_row_prev(df, ["Operating Cash Flow"])
    assert result is None, f"expected None (1 column), got {result}"


def test_yf_row_prev_none_on_none_df():
    result = _yf_row_prev(None, ["Operating Cash Flow"])
    assert result is None, "expected None for None df"


def test_yf_row_prev_none_on_empty_df():
    result = _yf_row_prev(pd.DataFrame(), ["Operating Cash Flow"])
    assert result is None, "expected None for empty df"


def test_yf_row_prev_none_when_no_label_matches():
    df = pd.DataFrame({"2024": [100.0], "2023": [90.0]}, index=["Something Else"])
    result = _yf_row_prev(df, ["Operating Cash Flow"])
    assert result is None, "expected None when no label matches"


# ── _compute_piotroski ───────────────────────────────────────────────────────


def test_piotroski_all_pass_returns_9():
    """All 9 criteria pass -> F-Score = 9 (hand-verified per criterion)."""
    inc_curr = _make_df({"Net Income": (1_000, 800), "Gross Profit": (4_000, 3_200), "Total Revenue": (10_000, 9_000), "EBIT": (1_500, 1_200)})
    inc_prev = _make_df({"Net Income": (800, 600), "Gross Profit": (3_200, 2_800), "Total Revenue": (9_000, 8_000), "EBIT": (1_200, 1_000)})
    bs_curr = _make_df(
        {
            "Total Assets": (20_000, 18_000),
            "Total Current Assets": (8_000, 7_000),
            "Total Current Liabilities": (3_000, 3_500),
            "Long Term Debt": (2_000, 2_500),
            "Stockholders Equity": (10_000, 9_000),
            "Retained Earnings": (5_000, 4_000),
            "Total Liabilities Net Minority Interest": (7_000, 7_500),
            "Ordinary Shares Number": (900, 1_000),
        }
    )
    bs_prev = _make_df(
        {
            "Total Assets": (25_000, 23_000),
            "Total Current Assets": (7_000, 6_000),
            "Total Current Liabilities": (3_500, 4_000),
            "Long Term Debt": (2_500, 3_000),
            "Stockholders Equity": (9_000, 8_000),
            "Retained Earnings": (4_000, 3_000),
            "Total Liabilities Net Minority Interest": (7_500, 8_000),
            "Ordinary Shares Number": (1_000, 1_100),
        }
    )
    cf_curr = _make_df({"Operating Cash Flow": (2_000, 1_800)})
    cf_prev = _make_df({"Operating Cash Flow": (1_800, 1_600)})

    result = _compute_piotroski(inc_curr, inc_prev, bs_curr, bs_prev, cf_curr, cf_prev)
    assert result == 9, f"expected 9 (all pass), got {result}"


def test_piotroski_all_fail_returns_0():
    """All 9 criteria fail -> F-Score = 0 (hand-verified per criterion)."""
    inc_curr = _make_df({"Net Income": (-100, -50), "Gross Profit": (1_000, 1_100), "Total Revenue": (9_000, 8_500), "EBIT": (-50, 50)})
    inc_prev = _make_df({"Net Income": (-50, -30), "Gross Profit": (1_200, 1_100), "Total Revenue": (9_000, 8_500), "EBIT": (50, 80)})
    bs_curr = _make_df(
        {
            "Total Assets": (20_000, 19_000),
            "Total Current Assets": (3_000, 3_200),
            "Total Current Liabilities": (4_000, 3_500),
            "Long Term Debt": (3_000, 2_500),
            "Stockholders Equity": (8_000, 9_000),
            "Retained Earnings": (2_000, 3_000),
            "Total Liabilities Net Minority Interest": (10_000, 9_000),
            "Ordinary Shares Number": (1_200, 1_000),
        }
    )
    bs_prev = _make_df(
        {
            "Total Assets": (19_000, 18_000),
            "Total Current Assets": (3_200, 3_000),
            "Total Current Liabilities": (3_500, 3_200),
            "Long Term Debt": (2_500, 2_000),
            "Stockholders Equity": (9_000, 8_500),
            "Retained Earnings": (3_000, 2_500),
            "Total Liabilities Net Minority Interest": (9_000, 8_500),
            "Ordinary Shares Number": (1_000, 900),
        }
    )
    cf_curr = _make_df({"Operating Cash Flow": (-200, 100)})
    cf_prev = _make_df({"Operating Cash Flow": (100, 90)})

    result = _compute_piotroski(inc_curr, inc_prev, bs_curr, bs_prev, cf_curr, cf_prev)
    assert result == 0, f"expected 0 (all fail), got {result}"


def test_piotroski_none_when_no_statements():
    result = _compute_piotroski(None, None, None, None, None, None)
    assert result is None, f"expected None, got {result}"


def test_piotroski_returns_none_when_only_single_year_criteria_available():
    """
    When prior-year DataFrames are entirely None, only the 3 always-available
    single-year criteria (F1, F2, F4) can be evaluated (criteria_counted == 3).
    _compute_piotroski returns None instead of a misleadingly low raw score,
    routing to the D-04 neutral-50 Safety-pillar fallback.
    """
    inc_curr = _make_df({"Net Income": (1_000, 800), "Gross Profit": (4_000, 3_200), "Total Revenue": (10_000, 9_000)})
    bs_curr = _make_df(
        {
            "Total Assets": (20_000, 18_000),
            "Total Current Assets": (8_000, 7_000),
            "Total Current Liabilities": (3_000, 3_500),
            "Long Term Debt": (2_000, 2_500),
            "Stockholders Equity": (10_000, 9_000),
            "Retained Earnings": (5_000, 4_000),
            "Total Liabilities Net Minority Interest": (7_000, 7_500),
            "Ordinary Shares Number": (900, 1_000),
        }
    )
    cf_curr = _make_df({"Operating Cash Flow": (2_000, 1_800)})

    result = _compute_piotroski(inc_curr, None, bs_curr, None, cf_curr, None)
    assert result is None, f"expected None (criteria_counted==3, at-or-below threshold), got {result}"


def test_piotroski_returns_score_when_one_comparison_criterion_available():
    """
    Boundary case: with a single comparison criterion available in addition to
    the 3 single-year criteria (criteria_counted == 4), _compute_piotroski must
    return a real int score, not None.
    """
    inc_curr = _make_df({"Net Income": (1_000, 800), "Gross Profit": (4_000, 3_200), "Total Revenue": (10_000, 9_000)})
    bs_curr = _make_df(
        {
            "Total Assets": (20_000, 18_000),
            "Total Current Assets": (8_000, 7_000),
            "Total Current Liabilities": (3_000, 3_500),
            "Long Term Debt": (2_000, 2_500),
            "Stockholders Equity": (10_000, 9_000),
            "Retained Earnings": (5_000, 4_000),
            "Total Liabilities Net Minority Interest": (7_000, 7_500),
            "Ordinary Shares Number": (900, 1_000),
        }
    )
    bs_prev = _make_df({"Ordinary Shares Number": (1_000, 1_100)})
    cf_curr = _make_df({"Operating Cash Flow": (2_000, 1_800)})

    result = _compute_piotroski(inc_curr, None, bs_curr, bs_prev, cf_curr, None)
    assert result is not None, "expected an int when 4 criteria (F1/F2/F4/F7) are evaluable"
    assert 0 <= result <= 4, f"expected 0-4 (F1/F2/F4/F7 count), got {result}"


def test_piotroski_f5_fails_safe_on_missing_ltd_curr():
    """
    F5 ('leverage decreased') must NOT award its point when current-year
    long-term-debt cannot be located. A fixture with prior-year LTD present but
    current-year LTD ABSENT must score exactly ONE point lower than an
    otherwise-identical fixture where current-year LTD IS present and passes.
    """
    inc_curr = _make_income_curr()
    inc_prev = _make_income_curr(net_income=800, gross_profit=3_200, revenue=9_000, ebit=1_200)
    cf_curr = _make_cashflow_curr()
    cf_prev = _make_cashflow_curr(ocf=1_800)

    bs_prev = _make_df(
        {
            "Total Assets": (25_000, 23_000),
            "Total Current Assets": (7_000, 6_000),
            "Total Current Liabilities": (3_500, 4_000),
            "Long Term Debt": (2_500, 3_000),
            "Stockholders Equity": (9_000, 8_000),
            "Retained Earnings": (4_000, 3_000),
            "Total Liabilities Net Minority Interest": (7_500, 8_000),
            "Ordinary Shares Number": (1_000, 1_100),
        }
    )
    bs_curr_missing_ltd = _make_df(
        {
            "Total Assets": (20_000, 18_000),
            "Total Current Assets": (8_000, 7_000),
            "Total Current Liabilities": (3_000, 3_500),
            "Stockholders Equity": (10_000, 9_000),
            "Retained Earnings": (5_000, 4_000),
            "Total Liabilities Net Minority Interest": (7_000, 7_500),
            "Ordinary Shares Number": (900, 1_000),
        }
    )
    bs_curr_present_ltd = _make_df(
        {
            "Total Assets": (20_000, 18_000),
            "Total Current Assets": (8_000, 7_000),
            "Total Current Liabilities": (3_000, 3_500),
            "Long Term Debt": (2_000, 2_500),
            "Stockholders Equity": (10_000, 9_000),
            "Retained Earnings": (5_000, 4_000),
            "Total Liabilities Net Minority Interest": (7_000, 7_500),
            "Ordinary Shares Number": (900, 1_000),
        }
    )

    score_missing = _compute_piotroski(inc_curr, inc_prev, bs_curr_missing_ltd, bs_prev, cf_curr, cf_prev)
    score_present = _compute_piotroski(inc_curr, inc_prev, bs_curr_present_ltd, bs_prev, cf_curr, cf_prev)

    assert score_missing is not None and score_present is not None
    assert score_present == score_missing + 1, (
        f"expected present-LTD score ({score_present}) to be exactly 1 higher than missing-LTD score ({score_missing})"
    )


# ── _compute_altman_z ────────────────────────────────────────────────────────


def test_altman_z_known_fixture():
    """Hand-computed Z'' for a controlled fixture."""
    bs = _make_df(
        {
            "Total Assets": (20_000, 18_000),
            "Total Current Assets": (8_000, 7_000),
            "Total Current Liabilities": (3_000, 3_500),
            "Stockholders Equity": (10_000, 9_000),
            "Retained Earnings": (5_000, 4_000),
            "Total Liabilities Net Minority Interest": (7_000, 7_500),
        }
    )
    inc = _make_df({"EBIT": (1_500, 1_200)})

    X1 = (8_000 - 3_000) / 20_000
    X2 = 5_000 / 20_000
    X3 = 1_500 / 20_000
    X4 = 10_000 / 7_000
    expected = 6.56 * X1 + 3.26 * X2 + 6.72 * X3 + 1.05 * X4

    result = _compute_altman_z(bs, inc)
    assert result is not None, "expected a float, got None"
    assert abs(result - expected) < 1e-6, f"expected {expected:.6f}, got {result:.6f}"


def test_altman_z_none_when_total_assets_zero():
    bs = _make_df(
        {
            "Total Assets": (0, 0),
            "Total Current Assets": (8_000, 7_000),
            "Total Current Liabilities": (3_000, 3_500),
            "Stockholders Equity": (10_000, 9_000),
            "Retained Earnings": (5_000, 4_000),
            "Total Liabilities Net Minority Interest": (7_000, 7_500),
        }
    )
    inc = _make_df({"EBIT": (1_500, 1_200)})
    result = _compute_altman_z(bs, inc)
    assert result is None, f"expected None when total_assets=0, got {result}"


def test_altman_z_none_when_total_liabilities_zero():
    bs = _make_df(
        {
            "Total Assets": (20_000, 18_000),
            "Total Current Assets": (8_000, 7_000),
            "Total Current Liabilities": (3_000, 3_500),
            "Stockholders Equity": (10_000, 9_000),
            "Retained Earnings": (5_000, 4_000),
            "Total Liabilities Net Minority Interest": (0, 0),
        }
    )
    inc = _make_df({"EBIT": (1_500, 1_200)})
    result = _compute_altman_z(bs, inc)
    assert result is None, f"expected None when total_liabilities=0, got {result}"


def test_altman_z_negative_equity_produces_negative_z():
    """Negative equity -> X4 negative -> Z'' can be negative. Must not crash."""
    bs = _make_df(
        {
            "Total Assets": (20_000, 18_000),
            "Total Current Assets": (8_000, 7_000),
            "Total Current Liabilities": (3_000, 3_500),
            "Stockholders Equity": (-5_000, -4_000),
            "Retained Earnings": (-10_000, -8_000),
            "Total Liabilities Net Minority Interest": (7_000, 7_500),
        }
    )
    inc = _make_df({"EBIT": (-500, 100)})
    result = _compute_altman_z(bs, inc)
    assert result is not None, "expected a float (even negative), got None"
    assert result < 0, f"expected negative Z'' for deeply distressed fixture, got {result}"


def test_altman_z_none_when_bs_none():
    result = _compute_altman_z(None, None)
    assert result is None, "expected None when bs_curr is None"


# ── overall_score() Safety pillar — Phase 7 additions ────────────────────────


def _base_score(**kwargs):
    """Minimal healthy overall_score() call, merged with any additional kwargs."""
    defaults = dict(
        lynch_discount=20.0,
        graham_discount=15.0,
        defensive_score=6,
        debt_equity=0.4,
        current_ratio=2.0,
        growth_g=10.0,
        growth_stability=0.8,
        aaa_yield=4.4,
    )
    defaults.update(kwargs)
    return overall_score(**defaults)


def test_overall_score_no_is_trap_param():
    """overall_score() must NOT accept is_trap -- calling with it raises TypeError."""
    raised = False
    try:
        _base_score(is_trap=False)
    except TypeError:
        raised = True
    assert raised, "overall_score() must raise TypeError when called with is_trap="


def test_overall_score_new_params_accepted():
    """piotroski_f, altman_z, dcf_discount_pct are accepted as keyword args."""
    scores = _base_score(piotroski_f=7, altman_z=3.0, dcf_discount_pct=20.0)
    assert scores["overall"] is not None


def test_low_piotroski_and_altman_depresses_safety():
    """Low Piotroski (f=1) + low Altman (z=0.5) -> score_safety lower than high scores."""
    scores_distressed = _base_score(piotroski_f=1, altman_z=0.5)
    scores_healthy = _base_score(piotroski_f=8, altman_z=3.5)
    assert scores_distressed["safety"] is not None
    assert scores_distressed["safety"] < scores_healthy["safety"], (
        f"Low Piotroski+Altman should depress safety vs healthy: {scores_distressed['safety']} < {scores_healthy['safety']}"
    )
    assert scores_distressed["piotroski"] < 20.0, f"Piotroski sub-score for f=1 should be < 20 (first band), got {scores_distressed['piotroski']}"
    assert scores_distressed["altman"] == 0.0, f"Altman sub-score for z=0.5 (distress zone) should be 0.0, got {scores_distressed['altman']}"


def test_absent_piotroski_and_altman_contributes_50():
    """When both Piotroski and Altman are None -> their D-04 contribution is 50.0 each."""
    scores_absent = _base_score()
    assert scores_absent["safety"] is not None, "Safety must not be None even with absent distress data"
    assert scores_absent["safety"] > 0, f"Absent Piotroski+Altman should yield Safety > 0 (D-04 neutral 50), got {scores_absent['safety']}"


def test_coverage_pct_denominator_is_17():
    """A fully-populated row (all 17 leaf inputs present) -> coverage_pct == 100.0."""
    scores = overall_score(
        lynch_discount=20.0,
        graham_discount=15.0,
        defensive_score=6,
        debt_equity=0.4,
        current_ratio=2.0,
        growth_g=10.0,
        growth_stability=0.8,
        aaa_yield=4.4,
        fcf_yield=5.0,
        earnings_yield=7.0,
        shareholder_yield=3.0,
        dist_52w_low=15.0,
        dist_52w_high=25.0,
        dist_5y_low=40.0,
        weeks_since_52w_low=30.0,
        weeks_since_5y_low=30.0,
        roic=20.0,
        piotroski_f=7,
        altman_z=3.0,
        dcf_discount_pct=20.0,
    )
    assert scores["coverage_pct"] == 100.0, f"All 17 leaf inputs should yield coverage_pct=100.0, got {scores['coverage_pct']}"


def test_dcf_discount_absent_does_not_affect_value():
    """dcf_discount_pct=None -> dcf_group is None, averaged-over-present with other groups."""
    scores_with = _base_score(dcf_discount_pct=30.0)
    scores_without = _base_score()
    assert scores_with["value"] is not None
    assert scores_without["value"] is not None
    assert scores_with["value"] >= scores_without["value"], (
        f"Adding dcf_discount_pct=30.0 should not depress value: {scores_with['value']} >= {scores_without['value']}"
    )


def test_dcf_discount_negative_routes_to_zero():
    """Negative dcf_discount_pct (overpriced) -> D-01 path -> dcf_discount sub = 0.0."""
    scores = _base_score(dcf_discount_pct=-20.0)
    assert scores.get("dcf_discount") is not None, "dcf_discount key should be in return dict"
    assert scores["dcf_discount"] == 0.0, f"Negative DCF discount should route to 0.0 (D-01), got {scores['dcf_discount']}"


def test_return_dict_has_new_keys():
    """Return dict includes piotroski, altman, dcf_discount, value_dcf keys."""
    scores = _base_score(piotroski_f=7, altman_z=3.0, dcf_discount_pct=20.0)
    for key in ("piotroski", "altman", "dcf_discount", "value_dcf"):
        assert key in scores, f"Missing key '{key}' in overall_score return dict"


# ── _compute_stats tests ─────────────────────────────────────────────────────


def _make_stats_df(rows):
    return pd.DataFrame(rows)


def test_compute_stats_bucket_counts_sum_to_universe():
    df = _make_stats_df(
        [
            {"OverallScore": 10.0, "score_safety": 20.0, "Sector": "Technology", "Show": True},
            {"OverallScore": 35.0, "score_safety": 40.0, "Sector": "Technology", "Show": False},
            {"OverallScore": 55.0, "score_safety": 50.0, "Sector": "Healthcare", "Show": True},
            {"OverallScore": 75.0, "score_safety": 60.0, "Sector": "Healthcare", "Show": True},
            {"OverallScore": 90.0, "score_safety": 70.0, "Sector": "Financial Services", "Show": False},
        ]
    )
    stats = _compute_stats(df)
    total = sum(stats["score_distribution"].values())
    assert total == stats["universe_count"], f"score_distribution bucket counts ({total}) must sum to universe_count ({stats['universe_count']})"


def test_compute_stats_low_safety_count():
    df = _make_stats_df(
        [
            {"OverallScore": 50.0, "score_safety": 10.0, "Sector": "Technology", "Show": True},
            {"OverallScore": 60.0, "score_safety": 29.9, "Sector": "Technology", "Show": True},
            {"OverallScore": 70.0, "score_safety": 30.0, "Sector": "Healthcare", "Show": False},
            {"OverallScore": 80.0, "score_safety": 50.0, "Sector": "Healthcare", "Show": True},
        ]
    )
    stats = _compute_stats(df)
    assert stats["low_safety_count"] == 2, f"Expected 2 rows with score_safety < 30, got {stats['low_safety_count']}"


def test_compute_stats_sector_breakdown_grouping():
    df = _make_stats_df(
        [
            {"OverallScore": 50.0, "score_safety": 40.0, "Sector": "Technology", "Show": True},
            {"OverallScore": 60.0, "score_safety": 50.0, "Sector": "Technology", "Show": True},
            {"OverallScore": 40.0, "score_safety": 35.0, "Sector": "Technology", "Show": False},
            {"OverallScore": 70.0, "score_safety": 60.0, "Sector": "Healthcare", "Show": True},
            {"OverallScore": 55.0, "score_safety": 45.0, "Sector": "Healthcare", "Show": False},
        ]
    )
    stats = _compute_stats(df)
    breakdown = stats["sector_breakdown"]
    assert breakdown[0]["sector"] == "Technology", f"Technology (3 rows) should be first in sector_breakdown, got {breakdown[0]['sector']}"
    assert breakdown[0]["count"] == 3
    assert breakdown[1]["sector"] == "Healthcare"
    assert breakdown[1]["count"] == 2


def test_compute_stats_buy_signal_count():
    df = _make_stats_df(
        [
            {"OverallScore": 50.0, "score_safety": 40.0, "Sector": "Technology", "Show": True},
            {"OverallScore": 30.0, "score_safety": 20.0, "Sector": "Technology", "Show": False},
            {"OverallScore": 60.0, "score_safety": 50.0, "Sector": "Healthcare", "Show": True},
        ]
    )
    stats = _compute_stats(df)
    assert stats["buy_signal_count"] == 2, f"Expected buy_signal_count=2, got {stats['buy_signal_count']}"


def test_compute_stats_has_required_keys():
    df = _make_stats_df([{"OverallScore": 50.0, "score_safety": 40.0, "Sector": "Technology", "Show": True}])
    stats = _compute_stats(df)
    required_keys = ["generated_at", "universe_count", "buy_signal_count", "low_safety_count", "score_distribution", "pillar_averages", "sector_breakdown", "coverage_stats"]
    for key in required_keys:
        assert key in stats, f"Missing required key '{key}' in _compute_stats output"


def test_compute_stats_sector_none_grouped_as_unknown():
    df = _make_stats_df(
        [
            {"OverallScore": 50.0, "score_safety": 40.0, "Sector": None, "Show": True},
            {"OverallScore": 60.0, "score_safety": 50.0, "Sector": None, "Show": False},
            {"OverallScore": 70.0, "score_safety": 60.0, "Sector": "Technology", "Show": True},
        ]
    )
    stats = _compute_stats(df)
    sectors = [b["sector"] for b in stats["sector_breakdown"]]
    assert "Unknown" in sectors, f"sector=None rows should appear as 'Unknown' in sector_breakdown, got {sectors}"


# ── Sector exclusion constants + _sector_allows ───────────────────────────────


def test_dcf_excluded_sectors_contains_financial_and_realestate():
    assert "Financial Services" in DCF_EXCLUDED_SECTORS
    assert "Real Estate" in DCF_EXCLUDED_SECTORS


def test_altman_excluded_sectors_contains_financial():
    assert "Financial Services" in ALTMAN_EXCLUDED_SECTORS


def test_sector_allows_financial_services_excludes_altman_dcf_and_ev_metrics():
    fund = {"sector": "Financial Services"}
    assert _sector_allows(fund, "altman") is False
    assert _sector_allows(fund, "dcf") is False
    assert _sector_allows(fund, "earnings_yield") is False
    assert _sector_allows(fund, "ev_ebit") is False


def test_sector_allows_real_estate_excludes_dcf_only():
    fund = {"sector": "Real Estate"}
    assert _sector_allows(fund, "dcf") is False
    assert _sector_allows(fund, "altman") is True
    assert _sector_allows(fund, "earnings_yield") is True
    assert _sector_allows(fund, "ev_ebit") is True


def test_sector_allows_none_sector_allows_all():
    fund = {"sector": None}
    for metric in ("altman", "dcf", "earnings_yield", "ev_ebit"):
        assert _sector_allows(fund, metric) is True, f"expected True for metric={metric}"


def test_sector_allows_other_sector_allows_all():
    fund = {"sector": "Technology"}
    for metric in ("altman", "dcf", "earnings_yield", "ev_ebit"):
        assert _sector_allows(fund, metric) is True, f"expected True for metric={metric}"


# ── test runner ──────────────────────────────────────────────────────────────


def run_all():
    tests = [
        test_yf_row_prev_returns_prior_year_value,
        test_yf_row_prev_second_label_when_first_absent,
        test_yf_row_prev_none_when_only_one_column,
        test_yf_row_prev_none_on_none_df,
        test_yf_row_prev_none_on_empty_df,
        test_yf_row_prev_none_when_no_label_matches,
        test_piotroski_all_pass_returns_9,
        test_piotroski_all_fail_returns_0,
        test_piotroski_none_when_no_statements,
        test_piotroski_returns_none_when_only_single_year_criteria_available,
        test_piotroski_returns_score_when_one_comparison_criterion_available,
        test_piotroski_f5_fails_safe_on_missing_ltd_curr,
        test_altman_z_known_fixture,
        test_altman_z_none_when_total_assets_zero,
        test_altman_z_none_when_total_liabilities_zero,
        test_altman_z_negative_equity_produces_negative_z,
        test_altman_z_none_when_bs_none,
        test_overall_score_no_is_trap_param,
        test_overall_score_new_params_accepted,
        test_low_piotroski_and_altman_depresses_safety,
        test_absent_piotroski_and_altman_contributes_50,
        test_coverage_pct_denominator_is_17,
        test_dcf_discount_absent_does_not_affect_value,
        test_dcf_discount_negative_routes_to_zero,
        test_return_dict_has_new_keys,
        test_compute_stats_bucket_counts_sum_to_universe,
        test_compute_stats_low_safety_count,
        test_compute_stats_sector_breakdown_grouping,
        test_compute_stats_buy_signal_count,
        test_compute_stats_has_required_keys,
        test_compute_stats_sector_none_grouped_as_unknown,
        test_dcf_excluded_sectors_contains_financial_and_realestate,
        test_altman_excluded_sectors_contains_financial,
        test_sector_allows_financial_services_excludes_altman_dcf_and_ev_metrics,
        test_sector_allows_real_estate_excludes_dcf_only,
        test_sector_allows_none_sector_allows_all,
        test_sector_allows_other_sector_allows_all,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {t.__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    run_all()
