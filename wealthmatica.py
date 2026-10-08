"""
Wealthmatica checklist -- the 4th gating system.

Wealthmatica (wealthmatica.substack.com) publishes no screen. What he repeats
in every stock report is a "Financial Data Overview": revenue, free cash flow,
FCF vs stock-based comp, EPS, debt vs cash, shares outstanding, gross and
operating margin -- each judged by its TREND, not against a fixed level
(docs/research/wealthmatica.md). This module turns those headings into seven
pass/fail checks on the last annual statements. Every threshold is ours
[ASSUMED]: he states none.

Share count and debt vs cash are his headings too, but not checks: his own
picks contradict them as cut-offs (ZETA rated "Strong Buy" on a rising share
count, its $1B credit line welcomed), so they were dropped 2026-10-08.

A check whose inputs are absent is N/A (None): a bank reports no gross profit,
some feeds carry no stock-comp row. N/A is neither a fail nor a pass -- the
verdict is judged on the checks that apply, as long as enough of them do.

Pure: no I/O, no network. Series are annual values, newest year first (the
order yfinance returns), with None for a missing year.
"""

from __future__ import annotations

import math

REV_GROWTH_MIN_PCT = 15.0  # check 1: revenue growth at least this
REV_GROWTH_STRONG_PCT = 25.0  # check 2: this fast counts even without acceleration
MAX_GROSS_MARGIN_DROP_PTS = 1.0  # check 5: gross-margin slippage tolerated
# pass = ceil(3/4 x applicable): 6 of 7, 5 of 6, 4 of 5. Not 6/7, which would need 5 of 5.
PASS_NUMERATOR, PASS_DENOMINATOR = 3, 4
MIN_APPLICABLE = 5  # fewer evaluable checks than this -> no verdict (a bank: no margins)

# Display order; also the keys of profile["checks"].
CHECKS = ("revGrowth", "revAccel", "fcf", "fcfSbc", "grossMargin", "opMargin", "eps")


def _at(series, i: int) -> float | None:
    if series is None or len(series) <= i:
        return None
    v = series[i]
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    return float(v)


# Ratios are rounded before comparing so a threshold is inclusive in decimal
# terms: 1150 / 1000 is 15% growth, not 14.999999999999996%.
_DP = 6


def _growth_pct(new: float | None, old: float | None) -> float | None:
    if new is None or old is None or old <= 0:
        return None
    return round((new / old - 1.0) * 100.0, _DP)


def _margin_pct(part: float | None, revenue: float | None) -> float | None:
    if part is None or revenue is None or revenue <= 0:
        return None
    return round(part / revenue * 100.0, _DP)


def _check(value: float | None, passed: bool | None) -> dict:
    return {"value": round(value, 4) if value is not None else None, "pass": passed}


def required_passes(applicable: int) -> int:
    """ceil(3/4 x applicable), in integers: 7 -> 6, 6 -> 5, 5 -> 4."""
    return -(-PASS_NUMERATOR * applicable // PASS_DENOMINATOR)


def wealthmatica_profile(revenue, gross_profit, operating_income, eps, fcf, sbc) -> dict:
    """
    The seven checks, each {"value", "pass"} with pass None when N/A, plus the
    verdict: "pass" is True/False, or None when fewer than MIN_APPLICABLE
    checks could be evaluated.
    """
    rev0, rev1, rev2 = _at(revenue, 0), _at(revenue, 1), _at(revenue, 2)
    g0, g1 = _growth_pct(rev0, rev1), _growth_pct(rev1, rev2)
    fcf0 = _at(fcf, 0)
    sbc0 = _at(sbc, 0)
    gm0, gm1 = _margin_pct(_at(gross_profit, 0), rev0), _margin_pct(_at(gross_profit, 1), rev1)
    om0, om1 = _margin_pct(_at(operating_income, 0), rev0), _margin_pct(_at(operating_income, 1), rev1)
    eps0, eps1 = _at(eps, 0), _at(eps, 1)
    gm_change = round(gm0 - gm1, _DP) if gm0 is not None and gm1 is not None else None
    om_change = round(om0 - om1, _DP) if om0 is not None and om1 is not None else None

    if g0 is None:
        accel = None
    elif g0 >= REV_GROWTH_STRONG_PCT:
        accel = True
    else:
        accel = (g0 > g1) if g1 is not None else None

    checks = {
        "revGrowth": _check(g0, None if g0 is None else g0 >= REV_GROWTH_MIN_PCT),
        "revAccel": _check(round(g0 - g1, _DP) if g0 is not None and g1 is not None else None, accel),
        "fcf": _check(_margin_pct(fcf0, rev0), None if fcf0 is None else fcf0 > 0),
        "fcfSbc": _check(
            _margin_pct(fcf0 - sbc0, rev0) if fcf0 is not None and sbc0 is not None else None,
            None if fcf0 is None or sbc0 is None else fcf0 - sbc0 > 0,
        ),
        "grossMargin": _check(
            gm_change,
            None if gm_change is None else gm_change >= -MAX_GROSS_MARGIN_DROP_PTS,
        ),
        "opMargin": _check(
            om_change,
            None if om_change is None else om_change > 0,
        ),
        "eps": _check(eps0, None if eps0 is None or eps1 is None else (eps0 > eps1 and (eps0 > 0 or eps1 < 0))),
    }

    results = [c["pass"] for c in checks.values() if c["pass"] is not None]
    applicable, passed = len(results), sum(results)
    verdict = passed >= required_passes(applicable) if applicable >= MIN_APPLICABLE else None
    return {"checks": checks, "passed": passed, "applicable": applicable, "pass": verdict}
