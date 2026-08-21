"""
Azqato scoring-model v3 fixture
===============================
Formula-regression test for azqato.py, pinned against the LIVE upstream model
(Azqato/stocks screener.js, "relative percentile model v3 (four even pillars)").

PURPOSE: the upstream screener is the northstar for this screen -- his ratings
are the reference, ours must reproduce them. The weights below were read off
his METRICS table, and every expected number here was hand-computed from the
percentile curve, NOT recorded from a run of our code. If a future edit drifts
the weights or the curve, these asserts are what catches it.

UPSTREAM METRICS (screener.js):
  revTTM 10 | revFwd 10 | epsTTM 15 | epsFwd 15 | peVsG 0 | pegFwd 25 |
  cashDebt 25 | netCashMc 0

CURVE: points = clamp(20 * (percentile - 0.22) / (1 - 2*0.22), 0, 20)
SCORE: round(sum(points * weight/20) / 100 * 100)

HOW TO RUN:
    python tests/test_azqato_model.py

No pytest required -- uses only stdlib assert.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from azqato import (  # noqa: E402
    CLAMP_Q,
    METRICS,
    METRIC_MAX_POINTS,
    PASS_POINTS,
    SCORED_COUNT,
    TOTAL_WEIGHT,
    _points_from_pct,
    azqato_score_all,
)

# Upstream's METRICS table, verbatim: (key, weight, higher_is_better).
UPSTREAM_METRICS = (
    ("revTTM", 10, True),
    ("revFwd", 10, True),
    ("epsTTM", 15, True),
    ("epsFwd", 15, True),
    ("peVsG", 0, False),
    ("pegFwd", 25, False),
    ("cashDebt", 25, True),
    ("netCashMc", 0, True),
)


def test_weights_match_upstream():
    assert METRICS == UPSTREAM_METRICS, f"METRICS drifted from upstream v3: {METRICS}"
    assert TOTAL_WEIGHT == 100, TOTAL_WEIGHT
    assert SCORED_COUNT == 6, SCORED_COUNT
    assert CLAMP_Q == 0.22, CLAMP_Q
    assert METRIC_MAX_POINTS == 20.0 and PASS_POINTS == 15.0

    # The four pillars are even: TTM 25, FWD 25, Valuation 25, Balance sheet 25.
    w = {k: weight for k, weight, _ in METRICS}
    assert w["revTTM"] + w["epsTTM"] == 25
    assert w["revFwd"] + w["epsFwd"] == 25
    assert w["pegFwd"] == 25
    assert w["cashDebt"] == 25
    # EPS outweighs revenue inside both growth pillars.
    assert w["epsTTM"] > w["revTTM"] and w["epsFwd"] > w["revFwd"]


def test_points_curve():
    # Hand-computed off points = 20 * (p - 0.22) / 0.56, clamped to [0, 20].
    assert _points_from_pct(0.00) == 0.0
    assert _points_from_pct(0.22) == 0.0
    assert _points_from_pct(0.10) == 0.0  # below the clamp floors at zero
    assert abs(_points_from_pct(0.36) - 5.0) < 1e-9
    assert abs(_points_from_pct(0.50) - 10.0) < 1e-9
    assert abs(_points_from_pct(0.64) - 15.0) < 1e-9
    assert _points_from_pct(0.78) == 20.0
    assert _points_from_pct(1.00) == 20.0  # above the clamp caps at full marks


def _stock(rev_ttm, rev_fwd, eps_ttm, eps_fwd, pe_fwd, peg, cash, debt, mcap=1000.0):
    return {
        "revTTM": rev_ttm,
        "revFwd": rev_fwd,
        "epsTTM": eps_ttm,
        "epsFwd": eps_fwd,
        "peFwd": pe_fwd,
        "pegFwd": peg,
        "cash": cash,
        "debt": debt,
        "marketCap": mcap,
    }


# Three stocks, so each metric's percentiles are exactly 0, 0.5, 1 (or the
# inverse for lower-is-better) -> points 0, 10, 20. BEST wins every metric,
# MID is median on every metric, WORST loses every metric.
THREE = {
    "BEST": _stock(30.0, 30.0, 40.0, 40.0, 20.0, 1.0, 300.0, 100.0),
    "MID": _stock(20.0, 20.0, 25.0, 25.0, 25.0, 2.0, 200.0, 100.0),
    "WORST": _stock(10.0, 10.0, 10.0, 10.0, 30.0, 3.0, 100.0, 100.0),
}


def test_three_stock_extremes():
    out = azqato_score_all(THREE)

    # BEST: 20 points on all six -> 20 * (100/20) = 100.
    assert out["BEST"]["score"] == 100, out["BEST"]
    assert out["BEST"]["passes"] == 6
    assert out["BEST"]["total"] == 6
    assert out["BEST"]["tier"] == "sp", out["BEST"]["tier"]

    # MID: 10 points on all six -> 10 * (100/20) = 50, the documented
    # "exactly average on every metric scores 50".
    assert out["MID"]["score"] == 50, out["MID"]
    assert out["MID"]["passes"] == 0  # 10 points is below the 15-point pass bar

    # WORST: 0 everywhere.
    assert out["WORST"]["score"] == 0, out["WORST"]
    assert out["WORST"]["passes"] == 0


def test_weighting_is_pillar_even():
    """A stock that wins only the two growth pillars vs one that wins only
    Valuation + Balance sheet must tie -- that is what "four even pillars"
    means, and it is exactly what the v2 (Growth 60) weights got wrong."""
    universe = {
        # GROWTHY tops all four growth metrics; VALUEY tops PEG + cash/debt.
        "GROWTHY": _stock(30.0, 30.0, 40.0, 40.0, 25.0, 3.0, 100.0, 100.0),
        "VALUEY": _stock(10.0, 10.0, 10.0, 10.0, 20.0, 1.0, 300.0, 100.0),
        "MID": _stock(20.0, 20.0, 25.0, 25.0, 22.0, 2.0, 200.0, 100.0),
    }
    out = azqato_score_all(universe)
    # GROWTHY: 20 pts on revTTM/revFwd/epsTTM/epsFwd = (10+10+15+15) = 50.
    # VALUEY:  20 pts on pegFwd/cashDebt            = (25+25)        = 50.
    assert out["GROWTHY"]["score"] == 50, out["GROWTHY"]
    assert out["VALUEY"]["score"] == 50, out["VALUEY"]
    assert out["GROWTHY"]["score"] == out["VALUEY"]["score"]


def test_missing_metric_is_a_hard_zero():
    """A missing input scores zero and never shrinks the denominator: an
    incomplete stock cannot outscore a complete one."""
    universe = dict(THREE)
    # Clone BEST but strip its cash/debt -> loses the whole 25pt balance pillar.
    universe["NODATA"] = _stock(30.0, 30.0, 40.0, 40.0, 20.0, 1.0, None, None)
    out = azqato_score_all(universe)
    assert out["NODATA"]["total"] == 6, "missing metric must stay in the denominator"
    assert out["NODATA"]["passes"] == 5, out["NODATA"]["passes"]
    assert "cashDebt" not in out["NODATA"]["parts"]
    assert out["NODATA"]["score"] < out["BEST"]["score"], (out["NODATA"], out["BEST"])


def test_unprofitable_ranks_worst_on_valuation():
    """Negative forward P/E ranks WORST on PEG (and on the context P/E-vs-growth
    ratio), never best and never dropped -- Yahoo's positive PEG is misleading
    there. Upstream's sentinel is Infinity."""
    universe = dict(THREE)
    universe["LOSS"] = _stock(30.0, 30.0, 40.0, 40.0, -12.0, 0.4, 300.0, 100.0)
    out = azqato_score_all(universe)
    assert out["LOSS"]["parts"]["pegFwd"] == 0.0, out["LOSS"]["parts"]
    assert out["LOSS"]["pctiles"]["pegFwd"] == 0.0
    assert out["LOSS"]["parts"]["peVsG"] == 0.0


def test_no_debt_with_cash_ranks_best_on_balance_sheet():
    universe = dict(THREE)
    universe["DEBTFREE"] = _stock(20.0, 20.0, 25.0, 25.0, 25.0, 2.0, 500.0, 0.0)
    out = azqato_score_all(universe)
    assert out["DEBTFREE"]["parts"]["cashDebt"] == 20.0, out["DEBTFREE"]["parts"]
    # No cash AND no debt is unevaluable, not a win.
    universe["EMPTY"] = _stock(20.0, 20.0, 25.0, 25.0, 25.0, 2.0, 0.0, 0.0)
    out = azqato_score_all(universe)
    assert "cashDebt" not in out["EMPTY"]["parts"]


def test_unscorable_stock_gets_no_score_and_no_tier():
    universe = dict(THREE)
    universe["BLANK"] = _stock(None, None, None, None, None, None, None, None, mcap=None)
    out = azqato_score_all(universe)
    assert out["BLANK"]["score"] is None
    assert out["BLANK"]["tier"] is None
    # screener.js reports total 0 (not 6) when nothing was evaluable, so the
    # Factors cell reads "—" rather than a misleading "0/6".
    assert out["BLANK"]["total"] == 0, out["BLANK"]["total"]


def test_net_cash_over_market_cap_is_ranked_but_never_scored():
    """netCashMc is upstream's weight-0 context column: it gets a percentile
    (so the cell can be colored) but must not move the score."""
    rich = _stock(20.0, 20.0, 25.0, 25.0, 25.0, 2.0, 900.0, 100.0, mcap=1000.0)
    poor = _stock(20.0, 20.0, 25.0, 25.0, 25.0, 2.0, 900.0, 100.0, mcap=100_000.0)
    out = azqato_score_all({"RICH": rich, "POOR": poor, **THREE})

    # (900 - 100) / 1000 * 100 = 80% net cash, vs 0.8% for POOR.
    assert out["RICH"]["parts"]["netCashMc"] > out["POOR"]["parts"]["netCashMc"]
    # Identical on all six scored metrics -> identical score, despite the gap.
    assert out["RICH"]["score"] == out["POOR"]["score"], (out["RICH"], out["POOR"])
    assert out["RICH"]["passes"] == out["POOR"]["passes"]
    assert out["RICH"]["total"] == 6  # the weight-0 column is not a 7th factor

    # A missing or non-positive market cap leaves it unevaluable, not zero.
    out = azqato_score_all({"NOMC": _stock(20.0, 20.0, 25.0, 25.0, 25.0, 2.0, 900.0, 100.0, mcap=None), **THREE})
    assert "netCashMc" not in out["NOMC"]["parts"]
    out = azqato_score_all({"ZEROMC": _stock(20.0, 20.0, 25.0, 25.0, 25.0, 2.0, 900.0, 100.0, mcap=0.0), **THREE})
    assert "netCashMc" not in out["ZEROMC"]["parts"]


def run_fixture():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"OK — {name}")
    print("OK — azqato v3 model fixture passed")


if __name__ == "__main__":
    run_fixture()
