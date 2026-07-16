"""
OverallScore Engine Unit Tests
===============================
Tests for the 4-pillar absolute OverallScore helpers (ported from upstream's
v2.0 methodology expansion): _piecewise_score, _winsorize, _avg_present,
trap_gate, overall_score.

DESIGN RULES:
  - Vanilla assert only -- no pytest dependency (matches test_valuation_fixture.py style).
  - Offline: dummy env vars guard against accidentally reaching a network entry point.
  - All scoring functions are pure (numeric inputs -> numeric outputs, no API calls).

HOW TO RUN:
    python tests/test_scoring.py
"""

import os
import sys

# Dummy credentials keep any accidentally reached network entry point deterministic.
os.environ.setdefault("FRED_API_KEY", "test")
os.environ.setdefault("FINNHUB_API_KEY", "test")

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from stock_screener import (
    _piecewise_score,
    _winsorize,
    _avg_present,
    trap_gate,
    overall_score,
    WORST_DISCOUNT,
    TRAP_MAX_DE,
    TRAP_MIN_CR,
)

# ─────────────────────────────────────────────────────────────────────────────
# _piecewise_score
# ─────────────────────────────────────────────────────────────────────────────

SIMPLE_BANDS = [
    (0.0, 50.0, 0, 50),
    (50.0, 100.0, 50, 100),
]


def test_piecewise_below_first_band():
    """Value below all bands -> score_lo of first band (0)."""
    result = _piecewise_score(-10.0, SIMPLE_BANDS)
    assert result == 0, f"Expected 0, got {result}"


def test_piecewise_at_lower_edge():
    """Value at the lower edge of the first band -> score_lo (0)."""
    result = _piecewise_score(0.0, SIMPLE_BANDS)
    assert result == 0, f"Expected 0, got {result}"


def test_piecewise_at_band_boundary():
    """Value exactly at the boundary between two bands -> score_hi of first band = score_lo of second."""
    result = _piecewise_score(50.0, SIMPLE_BANDS)
    assert result == 50, f"Expected 50, got {result}"


def test_piecewise_at_upper_edge():
    """Value at the top of the last band -> score_hi of last band (100)."""
    result = _piecewise_score(100.0, SIMPLE_BANDS)
    assert result == 100, f"Expected 100, got {result}"


def test_piecewise_above_all_bands():
    """Value above all bands -> score_hi of last band (100)."""
    result = _piecewise_score(200.0, SIMPLE_BANDS)
    assert result == 100, f"Expected 100, got {result}"


def test_piecewise_interior_interpolation():
    """Mid-band interpolation: at raw=25 in [0,50]->[0,50], score should be 25."""
    result = _piecewise_score(25.0, SIMPLE_BANDS)
    assert abs(result - 25.0) < 0.01, f"Expected ~25.0, got {result}"


def test_piecewise_interior_interpolation_second_band():
    """Mid second-band: at raw=75 in [50,100]->[50,100], score should be 75."""
    result = _piecewise_score(75.0, SIMPLE_BANDS)
    assert abs(result - 75.0) < 0.01, f"Expected ~75.0, got {result}"


def test_piecewise_inverted_bands():
    """Inverted direction (higher raw -> lower score) interpolates correctly."""
    inverted = [(0.0, 5.0, 100, 0)]
    result = _piecewise_score(2.5, inverted)
    assert abs(result - 50.0) < 0.01, f"Expected ~50.0, got {result}"


# ─────────────────────────────────────────────────────────────────────────────
# _winsorize
# ─────────────────────────────────────────────────────────────────────────────


def test_winsorize_within_bounds():
    """Value within bounds -> returned unchanged."""
    assert _winsorize(5.0, 0.0, 10.0) == 5.0


def test_winsorize_at_lower_bound():
    """Value at lo boundary -> returned as-is."""
    assert _winsorize(0.0, 0.0, 10.0) == 0.0


def test_winsorize_at_upper_bound():
    """Value at hi boundary -> returned as-is."""
    assert _winsorize(10.0, 0.0, 10.0) == 10.0


def test_winsorize_below_lower_bound():
    """Value below lo -> clamped to lo."""
    assert _winsorize(-50.0, -100.0, 60.0) == -50.0  # -50 is within bounds
    assert _winsorize(-150.0, -100.0, 60.0) == -100.0


def test_winsorize_above_upper_bound():
    """Value above hi -> clamped to hi."""
    assert _winsorize(200.0, 0.0, 60.0) == 60.0


# ─────────────────────────────────────────────────────────────────────────────
# _avg_present
# ─────────────────────────────────────────────────────────────────────────────


def test_avg_present_all_values():
    """Average over a list with no None values."""
    result = _avg_present([10.0, 20.0, 30.0])
    assert abs(result - 20.0) < 0.01, f"Expected 20.0, got {result}"


def test_avg_present_with_none():
    """None values are excluded from the average."""
    result = _avg_present([10.0, None, 30.0])
    assert abs(result - 20.0) < 0.01, f"Expected 20.0 (excl None), got {result}"


def test_avg_present_single_value():
    """Single non-None value -> that value."""
    result = _avg_present([None, None, 42.0])
    assert abs(result - 42.0) < 0.01, f"Expected 42.0, got {result}"


def test_avg_present_all_none():
    """All None -> returns None."""
    result = _avg_present([None, None, None])
    assert result is None, f"Expected None, got {result}"


def test_avg_present_empty():
    """Empty list -> returns None."""
    result = _avg_present([])
    assert result is None, f"Expected None for empty list, got {result}"


# ─────────────────────────────────────────────────────────────────────────────
# trap_gate
# ─────────────────────────────────────────────────────────────────────────────


def test_trap_gate_high_debt_equity_trips():
    """D/E above TRAP_MAX_DE trips the gate."""
    is_trap, cov = trap_gate(debt_equity=TRAP_MAX_DE + 0.1, current_ratio=2.0, eps_stability=1, fcf_per_share=1.0)
    assert is_trap is True, "High D/E should trip gate"
    assert abs(cov - 1.0) < 0.01, f"Expected coverage=1.0, got {cov}"


def test_trap_gate_low_current_ratio_trips():
    """Current ratio below TRAP_MIN_CR trips the gate."""
    is_trap, cov = trap_gate(debt_equity=0.5, current_ratio=TRAP_MIN_CR - 0.1, eps_stability=1, fcf_per_share=1.0)
    assert is_trap is True, "Low current ratio should trip gate"
    assert abs(cov - 1.0) < 0.01


def test_trap_gate_eps_instability_trips():
    """EPS stability == 0 trips the gate."""
    is_trap, cov = trap_gate(debt_equity=0.5, current_ratio=2.0, eps_stability=0, fcf_per_share=1.0)
    assert is_trap is True, "EPS instability should trip gate"
    assert abs(cov - 1.0) < 0.01


def test_trap_gate_negative_fcf_trips():
    """Negative FCF trips the gate."""
    is_trap, cov = trap_gate(debt_equity=0.5, current_ratio=2.0, eps_stability=1, fcf_per_share=-0.01)
    assert is_trap is True, "Negative FCF should trip gate"
    assert abs(cov - 1.0) < 0.01


def test_trap_gate_all_clear():
    """All inputs healthy -> no trap."""
    is_trap, cov = trap_gate(debt_equity=0.5, current_ratio=2.0, eps_stability=1, fcf_per_share=2.0)
    assert is_trap is False, "Healthy inputs should not trip gate"
    assert abs(cov - 1.0) < 0.01


def test_trap_gate_all_none_unknown():
    """All inputs None -> is_trap=False, coverage=0.0 (caller treats as unknown, not safe)."""
    is_trap, cov = trap_gate(debt_equity=None, current_ratio=None, eps_stability=None, fcf_per_share=None)
    assert is_trap is False, f"All-None should yield is_trap=False, got {is_trap}"
    assert abs(cov - 0.0) < 0.01, f"Expected coverage=0.0, got {cov}"


def test_trap_gate_partial_coverage():
    """Two of four inputs present -> coverage = 0.5."""
    is_trap, cov = trap_gate(debt_equity=0.5, current_ratio=None, eps_stability=1, fcf_per_share=None)
    assert abs(cov - 0.5) < 0.01, f"Expected coverage=0.5, got {cov}"


def test_trap_gate_coverage_fraction_arithmetic():
    """One input present -> coverage = 0.25."""
    is_trap, cov = trap_gate(debt_equity=None, current_ratio=None, eps_stability=None, fcf_per_share=1.0)
    assert abs(cov - 0.25) < 0.01, f"Expected coverage=0.25, got {cov}"


# ─────────────────────────────────────────────────────────────────────────────
# overall_score
# ─────────────────────────────────────────────────────────────────────────────


def test_overall_score_high_quality_row():
    """A row with healthy inputs across all pillars should yield OverallScore >= 55."""
    scores = overall_score(
        lynch_discount=30.0,
        graham_discount=25.0,
        defensive_score=7,
        debt_equity=0.3,
        current_ratio=2.5,
        growth_g=12.0,
        growth_stability=0.9,
        aaa_yield=4.4,  # at reference -> no rate scaling
    )
    assert scores["overall"] is not None, "OverallScore should not be None for healthy row"
    assert scores["overall"] >= 55, f"Expected OverallScore >= 55, got {scores['overall']}"
    assert scores["value"] is not None
    assert scores["quality"] is not None
    assert scores["growth"] is not None
    assert scores["safety"] is not None


def test_overall_score_worst_discount_floors_value_to_zero():
    """WORST_DISCOUNT sentinel -> Value sub-score = 0 (D-01 path, checked BEFORE winsorize)."""
    scores = overall_score(
        lynch_discount=WORST_DISCOUNT,
        graham_discount=WORST_DISCOUNT,
        defensive_score=6,
        debt_equity=0.5,
        current_ratio=2.0,
        growth_g=10.0,
        growth_stability=0.8,
        aaa_yield=4.4,
    )
    assert scores["value"] == 0, f"WORST_DISCOUNT -> value sub-score must be 0, got {scores['value']}"
    assert scores["overall"] is not None
    assert scores["overall"] < 55, f"OverallScore should be depressed by value=0, got {scores['overall']}"


def test_overall_score_all_distress_missing_is_still_scored():
    """
    Piotroski/Altman absent -> each contributes 50.0 (D-04 neutral fallback), so
    Safety is a meaningful numeric average (not None) when def/de/cr are present.
    """
    scores = overall_score(
        lynch_discount=20.0,
        graham_discount=15.0,
        defensive_score=5,
        debt_equity=0.5,
        current_ratio=2.0,
        growth_g=8.0,
        growth_stability=0.7,
        aaa_yield=4.4,
        # piotroski_f and altman_z absent -> contribute 50.0 each (D-04)
    )
    assert scores["safety"] is not None, "Safety must be computable when def/de/cr present"
    assert scores["safety"] > 0, f"Absent Piotroski+Altman (D-04 -> 50.0 each) should yield Safety > 0, got {scores['safety']}"


def test_overall_score_low_distress_scores_depress_safety():
    """Low Piotroski (f=1) + low Altman (z=0.5) drag Safety down relative to a strong pair."""
    scores_distressed = overall_score(
        lynch_discount=20.0, graham_discount=15.0, defensive_score=5,
        debt_equity=0.5, current_ratio=2.0, growth_g=8.0, growth_stability=0.7,
        aaa_yield=4.4, piotroski_f=1, altman_z=0.5,
    )
    scores_healthy = overall_score(
        lynch_discount=20.0, graham_discount=15.0, defensive_score=5,
        debt_equity=0.5, current_ratio=2.0, growth_g=8.0, growth_stability=0.7,
        aaa_yield=4.4, piotroski_f=8, altman_z=3.5,
    )
    assert scores_distressed["safety"] < scores_healthy["safety"], (
        f"Distressed scores should yield lower safety than healthy: {scores_distressed['safety']} < {scores_healthy['safety']}"
    )


def test_overall_score_pillar_renormalization_missing_growth():
    """When growth pillar inputs are all None, OverallScore is renormalized over present pillars."""
    scores_with_growth = overall_score(
        lynch_discount=20.0, graham_discount=15.0, defensive_score=5,
        debt_equity=0.5, current_ratio=2.0, growth_g=10.0, growth_stability=0.8, aaa_yield=4.4,
    )
    scores_no_growth = overall_score(
        lynch_discount=20.0, graham_discount=15.0, defensive_score=5,
        debt_equity=0.5, current_ratio=2.0, growth_g=None, growth_stability=None, aaa_yield=4.4,
    )
    assert scores_no_growth["overall"] is not None, "OverallScore must be computable when one pillar is missing"
    assert scores_no_growth["growth"] is None, "Growth pillar should be None when inputs are None"
    assert scores_no_growth["overall"] != scores_with_growth["overall"], "Missing growth pillar should change the OverallScore (renormalization)"


def test_overall_score_coverage_pct_reflects_present():
    """coverage_pct in [0, 100] and reflects the fraction of sub-scores present."""
    scores = overall_score(
        lynch_discount=20.0, graham_discount=15.0, defensive_score=5,
        debt_equity=0.5, current_ratio=2.0, growth_g=10.0, growth_stability=0.8, aaa_yield=4.4,
    )
    assert 0 <= scores["coverage_pct"] <= 100, f"coverage_pct out of range: {scores['coverage_pct']}"


def test_overall_score_negative_debt_equity_worst_score():
    """Negative debt/equity (negative equity) -> D/E quality sub-score = 0 (D-01)."""
    scores_neg_de = overall_score(
        lynch_discount=20.0, graham_discount=15.0, defensive_score=5,
        debt_equity=-1.0, current_ratio=2.0, growth_g=8.0, growth_stability=0.7, aaa_yield=4.4,
    )
    scores_pos_de = overall_score(
        lynch_discount=20.0, graham_discount=15.0, defensive_score=5,
        debt_equity=0.3, current_ratio=2.0, growth_g=8.0, growth_stability=0.7, aaa_yield=4.4,
    )
    assert scores_neg_de["quality"] < scores_pos_de["quality"], (
        f"Negative D/E should depress quality: {scores_neg_de['quality']} vs {scores_pos_de['quality']}"
    )


def test_high_rates_make_same_discount_less_attractive():
    """The same valuation discount must score lower when the live AAA yield is higher."""
    common = dict(
        lynch_discount=15.0, graham_discount=15.0, defensive_score=5,
        debt_equity=0.5, current_ratio=2.0, growth_g=8.0, growth_stability=0.7,
    )
    low_rate = overall_score(**common, aaa_yield=3.0)
    high_rate = overall_score(**common, aaa_yield=6.0)
    assert high_rate["value_discount"] < low_rate["value_discount"], (
        f"A fixed discount should be less attractive in a higher-rate environment: {high_rate['value_discount']} !< {low_rate['value_discount']}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────────────────────────────────────


def run_all():
    tests = [
        test_piecewise_below_first_band,
        test_piecewise_at_lower_edge,
        test_piecewise_at_band_boundary,
        test_piecewise_at_upper_edge,
        test_piecewise_above_all_bands,
        test_piecewise_interior_interpolation,
        test_piecewise_interior_interpolation_second_band,
        test_piecewise_inverted_bands,
        test_winsorize_within_bounds,
        test_winsorize_at_lower_bound,
        test_winsorize_at_upper_bound,
        test_winsorize_below_lower_bound,
        test_winsorize_above_upper_bound,
        test_avg_present_all_values,
        test_avg_present_with_none,
        test_avg_present_single_value,
        test_avg_present_all_none,
        test_avg_present_empty,
        test_trap_gate_high_debt_equity_trips,
        test_trap_gate_low_current_ratio_trips,
        test_trap_gate_eps_instability_trips,
        test_trap_gate_negative_fcf_trips,
        test_trap_gate_all_clear,
        test_trap_gate_all_none_unknown,
        test_trap_gate_partial_coverage,
        test_trap_gate_coverage_fraction_arithmetic,
        test_overall_score_high_quality_row,
        test_overall_score_worst_discount_floors_value_to_zero,
        test_overall_score_all_distress_missing_is_still_scored,
        test_overall_score_low_distress_scores_depress_safety,
        test_overall_score_pillar_renormalization_missing_growth,
        test_overall_score_coverage_pct_reflects_present,
        test_overall_score_negative_debt_equity_worst_score,
        test_high_rates_make_same_discount_less_attractive,
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
