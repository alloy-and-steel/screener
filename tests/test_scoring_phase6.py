"""
Phase 6/7 Scoring Extension Tests
==================================
Tests for the 3-subgroup Value pillar, ROIC-in-Quality, and 17-leaf coverage
additions to overall_score() (Phase 6/7 of upstream's v2.0 methodology).

DESIGN RULES (match test_scoring.py):
  - Vanilla assert only -- no pytest dependency.
  - Dummy env vars retained for compatibility with network-entry-point guards.
  - All functions are pure -- no API calls.

HOW TO RUN:
    python tests/test_scoring_phase6.py
"""

import os
import sys

os.environ.setdefault("FRED_API_KEY", "test")
os.environ.setdefault("FINNHUB_API_KEY", "test")

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from stock_screener import (
    overall_score,
    _recency_multiplier,
    SCORE_DIST_52W_LOW_BANDS,
    SCORE_DIST_5Y_LOW_BANDS,
    SCORE_DIST_52W_HIGH_BANDS,
)

# ─────────────────────────────────────────────────────────────────────────────
# Shared base args. All values chosen to be valid / non-sentinel so pillars
# are present.
# ─────────────────────────────────────────────────────────────────────────────
BASE_ARGS = dict(
    lynch_discount=20.0,
    graham_discount=15.0,
    defensive_score=6,
    debt_equity=0.4,
    current_ratio=2.0,
    growth_g=10.0,
    growth_stability=0.8,
    aaa_yield=4.4,
)


def test_backward_compat():
    scores = overall_score(**BASE_ARGS)
    for key in ("overall", "value", "quality", "growth", "safety"):
        assert key in scores, f"Missing key: {key}"
    assert scores["value_discount"] is not None, "value_discount should not be None"
    assert scores["value_yield"] is None, "value_yield should be None when no yield args passed"
    assert scores["value_price"] is None, "value_price should be None when no price-position args passed"
    # 17 leaves total. With only the base args: present = lynch, graham, def, de,
    # cr, growth_g, growth_stab, piotroski(50.0), altman(50.0) = 9 of 17.
    assert scores["coverage_pct"] < 100.0, f"Expected coverage_pct < 100 with only base args, got {scores['coverage_pct']}"


def test_descending_bands():
    assert SCORE_DIST_52W_LOW_BANDS[0][2] > SCORE_DIST_52W_LOW_BANDS[0][3], (
        f"SCORE_DIST_52W_LOW_BANDS first band should be descending (score_lo={SCORE_DIST_52W_LOW_BANDS[0][2]} > score_hi={SCORE_DIST_52W_LOW_BANDS[0][3]})"
    )
    assert SCORE_DIST_5Y_LOW_BANDS[0][2] > SCORE_DIST_5Y_LOW_BANDS[0][3], (
        f"SCORE_DIST_5Y_LOW_BANDS first band should be descending (score_lo={SCORE_DIST_5Y_LOW_BANDS[0][2]} > score_hi={SCORE_DIST_5Y_LOW_BANDS[0][3]})"
    )
    assert SCORE_DIST_52W_HIGH_BANDS[0][2] < SCORE_DIST_52W_HIGH_BANDS[-1][3], (
        f"SCORE_DIST_52W_HIGH_BANDS should be ascending (first score_lo={SCORE_DIST_52W_HIGH_BANDS[0][2]} < last score_hi={SCORE_DIST_52W_HIGH_BANDS[-1][3]})"
    )


def test_higher_yield_scores_higher():
    low_yield = overall_score(**BASE_ARGS, earnings_yield=2.0)
    high_yield = overall_score(**BASE_ARGS, earnings_yield=8.0)
    assert high_yield["value"] > low_yield["value"], f"Higher earnings_yield should produce higher value score: {high_yield['value']} > {low_yield['value']}"


def test_nearer_low_scores_higher():
    far_from_low = overall_score(**BASE_ARGS, dist_52w_low=50.0)
    near_low = overall_score(**BASE_ARGS, dist_52w_low=5.0)
    assert near_low["value"] > far_from_low["value"], f"dist_52w_low=5.0 (near low) should score higher than dist_52w_low=50.0: {near_low['value']} > {far_from_low['value']}"


def test_three_subgroup_equality():
    scores = overall_score(
        **BASE_ARGS,
        fcf_yield=5.0,
        earnings_yield=7.0,
        shareholder_yield=3.0,
        dist_52w_low=15.0,
        dist_52w_high=25.0,
        dist_5y_low=40.0,
        weeks_since_52w_low=30.0,
        weeks_since_5y_low=30.0,
    )
    assert scores["value_discount"] is not None, "value_discount should be present"
    assert scores["value_yield"] is not None, "value_yield should be present"
    assert scores["value_price"] is not None, "value_price should be present"


def test_roic_into_quality():
    without_roic = overall_score(**BASE_ARGS)
    with_roic = overall_score(**BASE_ARGS, roic=20.0)
    assert with_roic["quality"] != without_roic["quality"], f"Adding roic=20.0 should change quality score: {with_roic['quality']} != {without_roic['quality']}"


def test_roic_negative_worst():
    without_roic = overall_score(**BASE_ARGS)
    negative_roic = overall_score(**BASE_ARGS, roic=-5.0)
    assert negative_roic["quality"] <= without_roic["quality"], f"Negative ROIC should pull quality down or equal: {negative_roic['quality']} <= {without_roic['quality']}"


def test_recency_multiplier_endpoints():
    assert _recency_multiplier(None) == 1.0, "None weeks -> multiplier 1.0"
    assert abs(_recency_multiplier(0) - 0.70) < 1e-9, "weeks=0 -> floor 0.70"
    assert abs(_recency_multiplier(26) - 1.0) < 1e-9, "weeks=26 -> full credit 1.0"
    assert abs(_recency_multiplier(52) - 1.0) < 1e-9, "weeks=52 -> full credit 1.0 (clamped)"


def test_recency_modulates_score():
    fresh_low = overall_score(**BASE_ARGS, dist_52w_low=10.0, weeks_since_52w_low=0)
    basing_low = overall_score(**BASE_ARGS, dist_52w_low=10.0, weeks_since_52w_low=52)
    assert fresh_low["value"] < basing_low["value"], (
        f"Fresh low (weeks=0, multiplier=0.70) should score lower than basing low (weeks=52, multiplier=1.0): {fresh_low['value']} < {basing_low['value']}"
    )


def test_negative_yield_is_worst():
    scores = overall_score(**BASE_ARGS, fcf_yield=-3.0, earnings_yield=-1.0, shareholder_yield=-2.0)
    assert scores["value_yield"] is not None, "value_yield should not be None when all three yields provided"
    assert scores["value_yield"] == 0.0, f"All-negative yields should produce value_yield=0.0, got {scores['value_yield']}"


def test_coverage_grows_to_17():
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
    assert scores["coverage_pct"] == 100.0, f"All 17 leaf inputs present should yield coverage_pct=100.0, got {scores['coverage_pct']}"


def run_all():
    tests = [
        test_backward_compat,
        test_descending_bands,
        test_higher_yield_scores_higher,
        test_nearer_low_scores_higher,
        test_three_subgroup_equality,
        test_roic_into_quality,
        test_roic_negative_worst,
        test_recency_multiplier_endpoints,
        test_recency_modulates_score,
        test_negative_yield_is_worst,
        test_coverage_grows_to_17,
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
