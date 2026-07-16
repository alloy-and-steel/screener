"""
FCFF/WACC DCF orchestration tests
===================================
Covers _project_fcff_enterprise_value and the DCF_GROWTH_FLOOR sanity check.
The FCFF base/reverse/paired-range/guardrail tests live in
tests/test_remediation.py alongside the output-validation guard; this file
covers the lower-level enterprise-value projection those build on.

DESIGN RULES (match test_factors_phase6.py):
  - Vanilla assert only -- no pytest dependency.
  - Dummy env vars retained for compatibility with network-entry-point guards.
  - No network calls -- all inputs are plain numeric values.

HOW TO RUN:
    python tests/test_dcf_phase7.py
"""

import os
import sys

os.environ.setdefault("FRED_API_KEY", "test")
os.environ.setdefault("FINNHUB_API_KEY", "test")

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from stock_screener import (
    _project_fcff_enterprise_value,
    DCF_GROWTH_FLOOR,
    DCF_FORECAST_YEARS,
)


def test_project_fcff_enterprise_value_positive_and_terminal_share_bounded():
    ev, terminal_share_pct = _project_fcff_enterprise_value(base_fcff=100.0, initial_growth_pct=5.0, wacc=0.09, terminal_growth_pct=2.0)
    assert ev is not None and ev > 0, f"expected positive EV, got {ev}"
    assert terminal_share_pct is not None and 0 <= terminal_share_pct <= 100, f"expected terminal share in [0,100], got {terminal_share_pct}"


def test_project_fcff_enterprise_value_none_when_base_fcff_non_positive():
    ev, terminal_share_pct = _project_fcff_enterprise_value(base_fcff=0.0, initial_growth_pct=5.0, wacc=0.09, terminal_growth_pct=2.0)
    assert ev is None
    assert terminal_share_pct is None


def test_project_fcff_enterprise_value_raises_when_wacc_le_terminal_growth():
    raised = False
    try:
        _project_fcff_enterprise_value(base_fcff=100.0, initial_growth_pct=5.0, wacc=0.02, terminal_growth_pct=3.0)
    except ValueError as e:
        raised = True
        assert "WACC" in str(e)
    assert raised, "expected ValueError when WACC <= terminal growth"


def test_project_fcff_enterprise_value_higher_growth_yields_higher_ev():
    low_growth_ev, _ = _project_fcff_enterprise_value(base_fcff=100.0, initial_growth_pct=1.0, wacc=0.09, terminal_growth_pct=2.0)
    high_growth_ev, _ = _project_fcff_enterprise_value(base_fcff=100.0, initial_growth_pct=10.0, wacc=0.09, terminal_growth_pct=2.0)
    assert high_growth_ev > low_growth_ev, f"higher initial growth should raise EV: {high_growth_ev} > {low_growth_ev}"


def test_project_fcff_enterprise_value_uses_forecast_years_constant():
    # Sanity: DCF_FORECAST_YEARS must be a small positive integer (the loop bound).
    assert isinstance(DCF_FORECAST_YEARS, int) and DCF_FORECAST_YEARS >= 1


def test_dcf_growth_floor_constant_is_sane():
    """DCF_GROWTH_FLOOR must be strictly between -100% (keeps (1+g) positive) and 0% (a floor on decline)."""
    assert DCF_GROWTH_FLOOR > -100.0, f"DCF_GROWTH_FLOOR must be > -100.0 to keep (1+g) positive, got {DCF_GROWTH_FLOOR}"
    assert DCF_GROWTH_FLOOR < 0.0, f"DCF_GROWTH_FLOOR must be < 0.0 (a floor on decline), got {DCF_GROWTH_FLOOR}"


def run_all():
    tests = [
        test_project_fcff_enterprise_value_positive_and_terminal_share_bounded,
        test_project_fcff_enterprise_value_none_when_base_fcff_non_positive,
        test_project_fcff_enterprise_value_raises_when_wacc_le_terminal_growth,
        test_project_fcff_enterprise_value_higher_growth_yields_higher_ev,
        test_project_fcff_enterprise_value_uses_forecast_years_constant,
        test_dcf_growth_floor_constant_is_sane,
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
