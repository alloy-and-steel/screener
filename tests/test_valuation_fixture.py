"""
KO (Coca-Cola) Hand-Verified Valuation Fixture
================================================
Formula-regression test for lynch_metrics() and graham_metrics().

PURPOSE: Guard against accidental formula changes. Every assert in this
file was hand-computed from the inputs below -- NOT by calling the code and
recording whatever it produced. If the code changes in a way that breaks
these asserts, that IS the bug-detection mechanism working correctly.

INPUTS: Fixed, documented snapshot values -- NOT live data.

FORMULA SOURCES (as implemented in stock_screener.py -- this fork's
single-formula Graham variant, NOT upstream's dual VA/VB):
  Lynch:  FV_GplusD = eps * (g + dy)
          Lynch_BuyPrice = FV_GplusD * LYNCH_DISCOUNT[cat]  (Slow=0.75)
          Lynch_Discount_Pct = (1 - price / Lynch_BuyPrice) * 100
  Graham: Graham_FV = eps * (8.5 + 2*g_capped) * 4.4 / aaa_yield
          Graham_Discount_Pct = (1 - price / Graham_FV) * 100

HOW TO RUN:
    python tests/test_valuation_fixture.py

No pytest required -- uses only stdlib assert.
"""

import os
import sys

os.environ.setdefault("FRED_API_KEY", "test")
os.environ.setdefault("FINNHUB_API_KEY", "test")

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from stock_screener import lynch_metrics, graham_metrics

# ─────────────────────────────────────────────────────────────────────────────
# FIXED INPUT SNAPSHOT
# KO-like: modest grower, dividend payer, quality franchise trading at premium.
# ─────────────────────────────────────────────────────────────────────────────
KO_INPUTS = {
    "price": 70.00,
    "eps": 2.50,
    "g": 7.0,  # g < 10 -> Lynch_Category "Slow"
    "dy": 3.0,
    "aaa_yield": 5.5,
}

# ─────────────────────────────────────────────────────────────────────────────
# HAND-COMPUTED EXPECTED VALUES
#
# LYNCH:
#   pe          = 70.00 / 2.50            = 28.0
#   g + dy      = 7.0 + 3.0               = 10.0
#   FV_GplusD   = 2.50 * 10.0             = 25.00
#   Lynch_Category: g=7 < 10              -> "Slow"
#   Lynch_BuyPrice = 25.00 * 0.75         = 18.75
#   Lynch_Discount_Pct = (1 - 70/18.75)*100 = -273.3%
#   LV_Ratio    = 70.00 / 25.00           = 2.8  -> > 1.3 -> "Avoid"
#
# GRAHAM (fork's single-formula variant, GRAHAM_GROWTH_CAP=15.0):
#   g_capped    = min(7.0, 15.0)          = 7.0
#   Graham_FV   = 2.50 * (8.5 + 14) * (4.4/5.5)
#               = 2.50 * 22.5 * 0.8
#               = 2.50 * 18.0             = 45.00
#   Graham_Discount_Pct = (1 - 70/45)*100 = -55.56%
#   Graham_Status: DEEP_BUY=27, BUY=36, WATCH=42.75; price=70 > 42.75 -> "Avoid"
# ─────────────────────────────────────────────────────────────────────────────
KO_EXPECTED = {
    "Lynch_Category": "Slow",
    "Lynch_BuyPrice": 18.75,
    "Lynch_Discount_Pct": -273.3,
    "Lynch_Status": "Avoid",
    "Graham_FV": 45.00,
    "Graham_Discount_Pct": -55.56,
    "Graham_Status": "Avoid",
}


def run_fixture():
    p = KO_INPUTS["price"]
    eps = KO_INPUTS["eps"]
    g = KO_INPUTS["g"]
    dy = KO_INPUTS["dy"]
    aaa = KO_INPUTS["aaa_yield"]

    lm = lynch_metrics(p, eps, g, dy)
    gm = graham_metrics(p, eps, g, aaa)

    # ── Lynch checks ─────────────────────────────────────────────────
    assert lm.get("Lynch_Category") == KO_EXPECTED["Lynch_Category"], f"Lynch_Category: expected {KO_EXPECTED['Lynch_Category']!r}, got {lm.get('Lynch_Category')!r}"

    bp = lm.get("Lynch_BuyPrice")
    assert bp is not None, "Lynch_BuyPrice is None — formula returned no value"
    assert abs(bp - KO_EXPECTED["Lynch_BuyPrice"]) <= 0.50, f"Lynch_BuyPrice: expected {KO_EXPECTED['Lynch_BuyPrice']} ± 0.50, got {bp}"

    ld = lm.get("Lynch_Discount_Pct")
    assert ld is not None, "Lynch_Discount_Pct is None — formula returned no value"
    assert abs(ld - KO_EXPECTED["Lynch_Discount_Pct"]) <= 10.0, f"Lynch_Discount_Pct: expected {KO_EXPECTED['Lynch_Discount_Pct']} ± 10, got {ld}"

    assert lm.get("Lynch_Status") == KO_EXPECTED["Lynch_Status"], f"Lynch_Status: expected {KO_EXPECTED['Lynch_Status']!r}, got {lm.get('Lynch_Status')!r}"

    # ── Graham checks ────────────────────────────────────────────────
    fv = gm.get("Graham_FV")
    assert fv is not None, "Graham_FV is None — formula returned no value"
    assert abs(fv - KO_EXPECTED["Graham_FV"]) <= 1.0, f"Graham_FV: expected {KO_EXPECTED['Graham_FV']} ± 1.0, got {fv}"

    gd = gm.get("Graham_Discount_Pct")
    assert gd is not None, "Graham_Discount_Pct is None — formula returned no value"
    assert abs(gd - KO_EXPECTED["Graham_Discount_Pct"]) <= 5.0, f"Graham_Discount_Pct: expected {KO_EXPECTED['Graham_Discount_Pct']} ± 5, got {gd}"

    assert gm.get("Graham_Status") == KO_EXPECTED["Graham_Status"], f"Graham_Status: expected {KO_EXPECTED['Graham_Status']!r}, got {gm.get('Graham_Status')!r}"

    print("OK — all KO fixture assertions passed")
    print(f"  Lynch_BuyPrice      = {bp}  (expected {KO_EXPECTED['Lynch_BuyPrice']})")
    print(f"  Lynch_Discount_Pct  = {ld}  (expected {KO_EXPECTED['Lynch_Discount_Pct']})")
    print(f"  Graham_FV           = {fv}  (expected {KO_EXPECTED['Graham_FV']})")
    print(f"  Graham_Discount_Pct = {gd}  (expected {KO_EXPECTED['Graham_Discount_Pct']})")


if __name__ == "__main__":
    run_fixture()
