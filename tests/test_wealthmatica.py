"""
Wealthmatica checklist fixture
==============================
The 4th gating system (wealthmatica.py): nine trend checks distilled from the
"Financial Data Overview" section Wealthmatica repeats in every stock report
(docs/research/wealthmatica.md). Thresholds are ours [ASSUMED]; he publishes
none. Every expected value below is worked by hand from the fixture numbers.

Pass = at least MIN_APPLICABLE checks could be evaluated AND
passed >= ceil(7/9 x applicable). A check whose inputs are absent is N/A
(None), never a fail and never a pass.

HOW TO RUN:
    python tests/test_wealthmatica.py
"""

import os
import sys

os.environ.setdefault("FRED_API_KEY", "test")
os.environ.setdefault("FINNHUB_API_KEY", "test")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import pandas as pd  # noqa: E402

import stock_screener as screener  # noqa: E402
from test_remediation import _SYNTHETIC_LOSS_MAKER  # noqa: E402
from wealthmatica import CHECKS, wealthmatica_profile  # noqa: E402

# A compounder that clears every check (series are newest year first):
#   revenue 1300 / 1000 / 850   -> growth 30.0% now, 17.6% a year ago (re-accelerating)
#   FCF 260 / 180               -> positive and rising; SBC 60 -> FCF - SBC = 200
#   shares 100 / 101            -> -1.0%
#   gross margin 80.0% / 78.0%  -> up 2 pts; operating margin 15.4% / 10.0% -> up
#   EPS 2.10 / 1.40             -> positive and rising; cash 500 vs debt 200
COMPOUNDER = dict(
    revenue=[1300.0, 1000.0, 850.0],
    gross_profit=[1040.0, 780.0, 650.0],
    operating_income=[200.0, 100.0, 60.0],
    eps=[2.10, 1.40, 1.00],
    fcf=[260.0, 180.0, 120.0],
    sbc=[60.0, 55.0, 50.0],
    shares=[100.0, 101.0, 102.0],
    cash=500.0,
    debt=200.0,
)


def test_a_compounder_passes_all_nine():
    p = wealthmatica_profile(**COMPOUNDER)
    assert tuple(p["checks"]) == CHECKS
    assert [c["pass"] for c in p["checks"].values()] == [True] * 9, p["checks"]
    assert (p["passed"], p["applicable"], p["pass"]) == (9, 9, True), p


def profile(**over):
    return wealthmatica_profile(**{**COMPOUNDER, **over})


def failing(p) -> list[str]:
    return [k for k, c in p["checks"].items() if c["pass"] is False]


def test_seven_of_nine_passes_and_six_does_not():
    # Revenue 1100 / 1000: growth 10% (< 15%) and slower than last year's 17.6% -> two fails.
    p = profile(revenue=[1100.0, 1000.0, 850.0])
    assert failing(p) == ["revGrowth", "revAccel"], p["checks"]
    assert (p["passed"], p["pass"]) == (7, True), p
    # ... plus 106 / 101 shares: +4.95% dilution -> a third fail.
    p = profile(revenue=[1100.0, 1000.0, 850.0], shares=[106.0, 101.0])
    assert (p["passed"], p["applicable"], p["pass"]) == (6, 9, False), p


def test_a_bank_is_judged_on_the_checks_it_reports():
    # No gross profit, operating income or stock-comp line: 6 checks apply,
    # and 7/9 of 6 rounds up to 5 needed.
    bank = dict(gross_profit=None, operating_income=None, sbc=None)
    p = profile(**bank, shares=[106.0, 101.0])
    assert [k for k, c in p["checks"].items() if c["pass"] is None] == ["fcfSbc", "grossMargin", "opMargin"]
    assert (p["passed"], p["applicable"], p["pass"]) == (5, 6, True), p
    p = profile(**bank, revenue=[1100.0, 1000.0, 850.0])
    assert (p["passed"], p["applicable"], p["pass"]) == (4, 6, False), p


def test_too_few_evaluable_checks_is_no_verdict_not_a_fail():
    p = profile(gross_profit=None, operating_income=None, sbc=None, fcf=None, eps=[None, None])
    assert (p["applicable"], p["pass"]) == (4, None), p


def test_missing_is_none_never_zero():
    p = profile(shares=None, cash=None)
    assert p["checks"]["shareChange"] == {"value": None, "pass": None}
    assert p["checks"]["cashDebt"] == {"value": None, "pass": None}
    # Zero debt is a real value: 500 of net cash, a pass.
    assert profile(debt=0.0)["checks"]["cashDebt"] == {"value": 500.0, "pass": True}


def test_eps_rewards_rising_profit_or_a_narrowing_loss():
    eps_pass = lambda e0, e1: profile(eps=[e0, e1])["checks"]["eps"]["pass"]  # noqa: E731
    assert eps_pass(2.0, 1.0) is True  # profitable and rising
    assert eps_pass(0.5, -0.3) is True  # turned profitable
    assert eps_pass(-0.2, -0.9) is True  # loss narrowed (ZETA 2025: "losses decreasing by over 72%")
    assert eps_pass(-0.9, -0.2) is False  # loss widened
    assert eps_pass(1.0, 2.0) is False  # profitable but falling


def test_fast_growth_counts_as_reaccelerating_but_slowing_growth_does_not():
    # 1260 / 1000 = 26% now vs 17.6% a year ago: faster AND above 25%.
    # 1260 / 1000 / 700 = 26% vs 42.9%: slowing, but 26% >= 25% still passes.
    assert profile(revenue=[1260.0, 1000.0, 700.0])["checks"]["revAccel"]["pass"] is True
    # 1200 / 1000 / 700 = 20% vs 42.9%: slowing and under 25% -> fail.
    assert profile(revenue=[1200.0, 1000.0, 700.0])["checks"]["revAccel"]["pass"] is False
    # 1200 / 1000 with no third year: can't tell -> N/A.
    assert profile(revenue=[1200.0, 1000.0])["checks"]["revAccel"]["pass"] is None


def test_thresholds_are_inclusive_at_the_edge():
    # exactly 15% growth, exactly +2% shares, gross margin down exactly 1 pt (80 -> 79 vs 80).
    p = profile(revenue=[1150.0, 1000.0, 850.0], gross_profit=[908.5, 800.0], shares=[102.0, 100.0])
    assert p["checks"]["revGrowth"]["pass"] is True, p["checks"]["revGrowth"]
    assert p["checks"]["shareChange"]["pass"] is True, p["checks"]["shareChange"]
    assert p["checks"]["grossMargin"]["pass"] is True, p["checks"]["grossMargin"]
    assert profile(shares=[102.1, 100.0])["checks"]["shareChange"]["pass"] is False


def test_fcf_must_be_positive_and_growing_and_cover_stock_comp():
    assert profile(fcf=[-50.0, -120.0])["checks"]["fcf"]["pass"] is False  # burn shrinking is still burn
    assert profile(fcf=[150.0, 180.0])["checks"]["fcf"]["pass"] is False  # positive but falling
    # FCF 260 minus SBC 300 = -40: stock comp eats all the cash.
    assert profile(sbc=[300.0])["checks"]["fcfSbc"]["pass"] is False


# ── Pipeline: process_ticker reads the annual statements it already fetched ──

YEARS = pd.to_datetime(["2025-12-31", "2024-12-31", "2023-12-31"])  # newest first, like yfinance


def statement(rows: dict) -> pd.DataFrame:
    return pd.DataFrame({k: v + [None] * (3 - len(v)) for k, v in rows.items()}, index=YEARS).T


def screened(**fund_over) -> dict:
    fund = {**_SYNTHETIC_LOSS_MAKER, **fund_over}
    original = screener.get_combined_data
    try:
        screener.get_combined_data = lambda _ticker, finnhub=None: fund
        return screener.process_ticker("WM", aaa_yield=5.0, risk_free_rate=4.0)
    finally:
        screener.get_combined_data = original


COMPOUNDER_STATEMENTS = dict(
    income_stmt_df=statement({
        "Total Revenue": [1300.0, 1000.0, 850.0],
        "Gross Profit": [1040.0, 780.0, 650.0],
        "Operating Income": [200.0, 100.0, 60.0],
        "Diluted EPS": [2.10, 1.40, 1.00],
    }),
    # No "Free Cash Flow" row: FCF = operating cash flow + capex (capex is negative).
    cashflow_df=statement({
        "Operating Cash Flow": [300.0, 210.0],
        "Capital Expenditure": [-40.0, -30.0],
        "Stock Based Compensation": [60.0, 55.0],
    }),
    balance_sheet_df=statement({"Ordinary Shares Number": [100.0, 101.0]}),
    az_cash=500.0,
    az_debt=200.0,
)


def test_process_ticker_scores_the_checklist_from_the_fetched_statements():
    wm = screened(**COMPOUNDER_STATEMENTS)["wealthmatica"]
    assert (wm["passed"], wm["applicable"], wm["pass"]) == (9, 9, True), wm
    assert wm["checks"]["revGrowth"]["value"] == 30.0
    assert wm["checks"]["fcf"]["value"] == 20.0  # (300 - 40) / 1300
    assert wm["checks"]["cashDebt"]["value"] == 300.0


def test_a_row_without_statements_has_no_verdict():
    wm = screened()["wealthmatica"]  # the synthetic fund carries no frames
    assert (wm["applicable"], wm["pass"]) == (1, None), wm  # only cash vs debt (50 vs 100)
    assert wm["checks"]["cashDebt"]["pass"] is False


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
