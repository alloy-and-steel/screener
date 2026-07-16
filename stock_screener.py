"""
Lynch & Graham Stock Screener
==============================
Fetches S&P 500, Dow 30, and Nasdaq-100 constituents dynamically,
pulls fundamentals from yfinance and Finnhub, computes Lynch and
Graham valuation metrics plus a 4-pillar OverallScore (Value/Quality/
Growth/Safety -- ported from upstream's v2.0 methodology expansion,
informational only, does not gate the three independent Lynch/Graham/
Azqato verdicts), and writes results to web/public/data/results.json
and web/public/data/stats.json, which the Vite frontend ships as a
same-origin Pages artifact.

Local setup:
    1. Copy .env.example to .env and fill in your API keys.
    2. Run: python stock_screener.py

GitHub Actions setup:
    Add each variable from .env.example as a repository secret
    (Settings → Secrets and variables → Actions).
    The provided workflow file handles injection automatically.
"""

import os
import sys
import json
import math
import logging
import requests
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta, timezone
from fredapi import Fred
from dotenv import load_dotenv
from scipy.optimize import brentq

from azqato import azqato_score_all, pct_of_52w_range, wilder_rsi

# Load .env when running locally; no-op in GitHub Actions (env vars already set)
load_dotenv()

# ─────────────────────────────────────────────
# CONFIGURATION — all values come from env vars
# ─────────────────────────────────────────────
FRED_API_KEY = os.environ["FRED_API_KEY"]
FINNHUB_API_KEY = os.environ["FINNHUB_API_KEY"]

# Screener parameters
GROWTH_CAP = 25.0  # cap 'g' at this % to prevent distortion
GROWTH_FINNHUB_FLOOR = -100.0  # below this, Finnhub epsGrowth5Y is impossible (EPS can't fall >100% from a positive base) -- treat as bad data, not real growth
GRAHAM_NO_GROWTH_PE = 8.5  # Graham's base no-growth P/E (revised 1962 formula)
GRAHAM_GROWTH_CAP = 15.0  # practitioner cap on g inside the Graham formula (NOT Graham's own rule)
GRAHAM_HIST_AAA = 4.4  # Graham's original historical AAA yield constant
FRED_AAA_SERIES = "AAA"  # Moody's AAA corporate bond yield series on FRED
FRED_RISK_FREE_SERIES = "DGS10"  # 10-year Treasury constant maturity rate, for the FCFF DCF's cost of equity

# Graham defensive-investor filter thresholds (canonical -- The Intelligent Investor, Ch. 14)
MIN_MARKET_CAP_B = 2.0  # adequate size: modern market-cap proxy for Graham's sales/assets floor
MIN_CURRENT_RATIO = 2.0  # current assets / current liabilities >= 2
REQUIRED_EPS_YEARS = 10  # earnings stability + 10y growth both span the last 10 fiscal years
MIN_DIV_YEARS = 20  # uninterrupted dividends for at least the last 20 years
MIN_EPS_GROWTH_10Y = 33.0  # cumulative % EPS growth over 10y (3-yr-avg endpoints), ~one-third
MAX_PE_GRAHAM = 15.0  # P/E <= 15 (based on 3-yr avg EPS)
MAX_PB_GRAHAM = 1.5  # P/B <= 1.5
MAX_PE_X_PB = 22.5  # P/E x P/B <= 22.5
DEFENSIVE_PASS_SCORE = 6  # minimum score to be "Pass"
DEFENSIVE_BORDER_SCORE = 4  # minimum score to be "Borderline" (below = Fail)

# Lynch price-band multipliers
LYNCH_PEG_CHEAP = 0.7
LYNCH_PEG_FAIR = 1.0
LYNCH_PEGY_CHEAP = 0.8
LYNCH_PEGY_FAIR = 1.2
LYNCH_LV_STRONG_BUY = 0.7
LYNCH_LV_BUY = 1.0
LYNCH_LV_HOLD = 1.3

# Graham price-band multipliers (fraction of fair value)
GRAHAM_DEEP_BUY = 0.60
GRAHAM_BUY = 0.80
GRAHAM_WATCH = 0.95

# Category-specific Lynch buy discount factors
LYNCH_DISCOUNT = {"Slow": 0.75, "Stalwart": 0.80, "Fast": 0.70}

# Sentinel discount for tickers with negative/zero growth or EPS that breaks the
# Lynch/Graham formulas. The OverallScore engine below maps this to sub-score 0
# (worst). The stock is RETAINED in the output and ranks at the bottom -- it is
# NOT dropped. Distinct from a genuine no-price/no-EPS fetch failure, which
# early-returns as Error.
WORST_DISCOUNT = -999.0

# ─────────────────────────────────────────────────────────────────────────────
# OVERALLSCORE ENGINE CONFIG — SCORE_* / TRAP_* / PILLAR_WEIGHTS / DCF_*
#
# Ported from upstream's v2.0 methodology expansion (VoxMachina1/graham-screener,
# Phases 5-7). OverallScore is a 4-pillar ABSOLUTE composite -- informational,
# alongside (not gating) the three independent Azqato/Lynch/Graham verdicts this
# fork's UI treats as the pass/fail signal.
#
# All weights, band thresholds, and winsorization bounds live here as
# version-controlled loud constants. THESE HAVE NO EMPIRICAL ANCHOR YET -- they
# are upstream's first-pass estimates. Distribution is monitored via stats.json
# after real production runs.
#
# Rate-relativized thresholds (discount bands): scaled by live AAA yield /
# SCORE_AAA_REFERENCE at runtime so a 15% discount is less impressive in a
# high-rate environment.
# ─────────────────────────────────────────────────────────────────────────────

SCORE_AAA_REFERENCE = 4.4  # % — Graham's original 1963 reference; DO NOT CHANGE

# ── Value pillar: discount winsorization + bands ──────────────────────────
SCORE_DISC_WIN_LO = -100.0  # floor discount at -100% (2x fair value)
SCORE_DISC_WIN_HI = 60.0  # cap discount at 60% (deep value)
SCORE_DISC_BANDS = [  # [ASSUMED] at AAA=4.4%; scaled by aaa_yield/SCORE_AAA_REFERENCE at runtime
    (-100.0, -30.0, 0, 10),
    (-30.0, 0.0, 10, 40),
    (0.0, 15.0, 40, 70),
    (15.0, 30.0, 70, 90),
    (30.0, 60.0, 90, 100),
]

# ── Quality pillar: DefensiveScore bands (0-8) ───────────────────────────
SCORE_DEF_BANDS = [  # [ASSUMED]
    (0, 2, 0, 20),
    (2, 4, 20, 50),
    (4, 6, 50, 80),
    (6, 8, 80, 100),
]

# ── Quality pillar: Debt/Equity bands (total_debt / equity) ──────────────
SCORE_DE_WIN_HI = 5.0
SCORE_DE_BANDS = [  # [ASSUMED]
    (0.0, 0.5, 100, 90),
    (0.5, 1.0, 90, 70),
    (1.0, 2.0, 70, 40),
    (2.0, 5.0, 40, 0),
]

# ── Quality pillar: Current Ratio bands ──────────────────────────────────
SCORE_CR_WIN_HI = 8.0
SCORE_CR_BANDS = [  # [ASSUMED]
    (0.0, 1.0, 0, 30),
    (1.0, 1.5, 30, 60),
    (1.5, 2.0, 60, 80),
    (2.0, 4.0, 80, 100),
    (4.0, 8.0, 100, 90),
]

# ── Growth pillar: growth-level bands (g, already GROWTH_CAP-capped) ─────
SCORE_G_BANDS = [  # [ASSUMED]
    (0.0, 3.0, 0, 20),
    (3.0, 7.0, 20, 50),
    (7.0, 12.0, 50, 75),
    (12.0, 20.0, 75, 90),
    (20.0, 25.0, 90, 100),
]

# ── Growth pillar: growth-stability bands (fraction of positive-EPS years) ─
SCORE_GSTAB_BANDS = [  # [ASSUMED]
    (0.0, 0.4, 0, 20),
    (0.4, 0.6, 20, 50),
    (0.6, 0.8, 50, 80),
    (0.8, 1.0, 80, 100),
]

# ── Trap gate thresholds — interim value-trap trip-wire, diagnostic-only ──
TRAP_MAX_DE = 2.0  # D/E above this trips the gate
TRAP_MIN_CR = 1.0  # current ratio below this trips the gate

# ── Value sub-group 2: cash/earnings-yield cheapness (ascending bands) ───
SCORE_FCF_YIELD_WIN_LO = 0.0
SCORE_FCF_YIELD_WIN_HI = 15.0
SCORE_FCF_YIELD_BANDS = [  # [ASSUMED]
    (0.0, 2.0, 0, 20),
    (2.0, 5.0, 20, 60),
    (5.0, 8.0, 60, 85),
    (8.0, 15.0, 85, 100),
]

SCORE_EARN_YIELD_WIN_LO = 0.0
SCORE_EARN_YIELD_WIN_HI = 20.0
SCORE_EARN_YIELD_BANDS = [  # [ASSUMED]
    (0.0, 3.0, 0, 20),
    (3.0, 6.0, 20, 50),
    (6.0, 10.0, 50, 80),
    (10.0, 20.0, 80, 100),
]

SCORE_SH_YIELD_WIN_LO = 0.0
SCORE_SH_YIELD_WIN_HI = 12.0
SCORE_SH_YIELD_BANDS = [  # [ASSUMED]
    (0.0, 2.0, 0, 30),
    (2.0, 4.0, 30, 60),
    (4.0, 6.0, 60, 85),
    (6.0, 12.0, 85, 100),
]

# ── Value sub-group 3: price-position (descending — nearer-low scores higher) ──
SCORE_DIST_52W_LOW_WIN_LO = 0.0
SCORE_DIST_52W_LOW_WIN_HI = 200.0
SCORE_DIST_52W_LOW_BANDS = [  # [ASSUMED]
    (0.0, 10.0, 100, 85),
    (10.0, 30.0, 85, 55),
    (30.0, 60.0, 55, 25),
    (60.0, 200.0, 25, 0),
]

SCORE_DIST_52W_HIGH_WIN_LO = 0.0
SCORE_DIST_52W_HIGH_WIN_HI = 100.0
SCORE_DIST_52W_HIGH_BANDS = [  # [ASSUMED] ascending: far from high = 100
    (0.0, 5.0, 0, 10),
    (5.0, 20.0, 10, 50),
    (20.0, 40.0, 50, 80),
    (40.0, 100.0, 80, 100),
]

SCORE_DIST_5Y_LOW_WIN_LO = 0.0
SCORE_DIST_5Y_LOW_WIN_HI = 400.0
SCORE_DIST_5Y_LOW_BANDS = [  # [ASSUMED]
    (0.0, 20.0, 100, 85),
    (20.0, 60.0, 85, 55),
    (60.0, 120.0, 55, 25),
    (120.0, 400.0, 25, 0),
]

SCORE_RECENCY_FLOOR = 0.70  # [ASSUMED] multiplier at weeks_since_low == 0
SCORE_RECENCY_FULL_WK = 26  # [ASSUMED] weeks at which full credit is granted

# ── Quality pillar: ROIC bands ────────────────────────────────────────────
SCORE_ROIC_WIN_LO = 0.0
SCORE_ROIC_WIN_HI = 50.0
SCORE_ROIC_BANDS = [  # [ASSUMED]
    (0.0, 5.0, 0, 20),
    (5.0, 10.0, 20, 50),
    (10.0, 20.0, 50, 85),
    (20.0, 50.0, 85, 100),
]

# ── Pillar weights (renormalized over present pillars at runtime) ────────
PILLAR_WEIGHTS = {
    "value": 0.35,
    "quality": 0.30,
    "growth": 0.20,
    "safety": 0.15,
}

# ── Safety pillar: Piotroski F-Score bands (0-9) ─────────────────────────
SCORE_PIOTROSKI_BANDS = [  # [ASSUMED]
    (0, 2, 0, 20),
    (2, 4, 20, 40),
    (4, 6, 40, 65),
    (6, 8, 65, 85),
    (8, 9, 85, 100),
]

# ── Safety pillar: Altman Z'' bands ──────────────────────────────────────
SCORE_ALTMAN_BANDS = [  # [ASSUMED]
    (-999.0, 1.1, 0, 0),
    (1.1, 2.6, 0, 70),
    (2.6, 10.0, 70, 100),
]

# ── DCF config (screen-grade FCFF/WACC) ───────────────────────────────────
DCF_ERP = 5.5  # [ASSUMED] mature-market equity risk premium %
DCF_TERMINAL_GROWTH_CAP = 3.0  # [ASSUMED] maximum perpetual nominal growth %
DCF_FORECAST_YEARS = 5
DCF_INITIAL_GROWTH_FLOOR = -20.0
DCF_INITIAL_GROWTH_CAP = 15.0
DCF_DEFAULT_TAX_RATE = 0.21
DCF_BETA_FLOOR = 0.50
DCF_BETA_CAP = 2.00
DCF_SENSITIVITY_WACC_STEP = 0.01
DCF_SENSITIVITY_GROWTH_STEP = 0.005
DCF_MIN_WACC_RISK_FREE_SPREAD_PCT = 2.5
DCF_MIN_WACC_TERMINAL_SPREAD_PCT = 4.0
DCF_HIGH_TERMINAL_VALUE_PCT = 85.0
DCF_HIGH_DEBT_WEIGHT = 0.50
DCF_EXCLUDED_SECTORS = {"Financial Services", "Real Estate"}
ALTMAN_EXCLUDED_SECTORS = {"Financial Services"}
# [ASSUMED] Lower bound on the reconciled growth g before it reaches the DCF
# helpers; keeps (1+g) positive. Never applied to the shared g used by Lynch/
# Graham/OverallScore-growth -- only at the DCF call site.
DCF_GROWTH_FLOOR = -50.0
# yfinance GICS-like sector strings for the cyclical group. NOTE: yfinance
# returns "Basic Materials", not "Materials".
CYCLICAL_SECTORS = {"Energy", "Basic Materials"}

# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger(__name__)


# ═════════════════════════════════════════════
# OVERALLSCORE ENGINE — pure helpers + trap gate
# ═════════════════════════════════════════════
# All functions here are pure: numeric inputs -> numeric outputs, no I/O or
# side effects. Ported from upstream's v2.0 methodology expansion.


def _piecewise_score(value: float, bands: list) -> float:
    """
    Map a raw metric value to [0, 100] via linear interpolation between breakpoints.
    bands: list of (raw_lo, raw_hi, score_lo, score_hi) tuples, sorted ascending by raw_lo.
    Below the first band -> score_lo of the first band. Above the last -> score_hi of the last.
    """
    for raw_lo, raw_hi, score_lo, score_hi in bands:
        if value <= raw_hi:
            if raw_hi == raw_lo:
                return float(score_lo)
            t = (value - raw_lo) / (raw_hi - raw_lo)
            t = max(0.0, min(1.0, t))
            return score_lo + t * (score_hi - score_lo)
    return float(bands[-1][3])


def _winsorize(value: float, lo: float, hi: float) -> float:
    """Clamp value to [lo, hi] -- both-tail winsorization."""
    return max(lo, min(hi, value))


def _avg_present(values: list) -> float | None:
    """Average over non-None values. None when all inputs are absent."""
    present = [v for v in values if v is not None]
    return round(sum(present) / len(present), 2) if present else None


def _recency_multiplier(weeks_since_low: float | None) -> float:
    """Linear ramp SCORE_RECENCY_FLOOR -> 1.0 over SCORE_RECENCY_FULL_WK weeks."""
    if weeks_since_low is None:
        return 1.0
    t = min(1.0, weeks_since_low / SCORE_RECENCY_FULL_WK)
    return SCORE_RECENCY_FLOOR + t * (1.0 - SCORE_RECENCY_FLOOR)


def _trap_reasons(
    debt_equity: float | None,
    current_ratio: float | None,
    eps_stability: int | None,
    fcf_per_share: float | None,
) -> list:
    """Explicit research warnings for each present threshold breach."""
    reasons = []
    if debt_equity is not None and debt_equity > TRAP_MAX_DE:
        reasons.append("High leverage")
    if current_ratio is not None and current_ratio < TRAP_MIN_CR:
        reasons.append("Weak liquidity")
    if eps_stability is not None and eps_stability == 0:
        reasons.append("Unstable earnings")
    if fcf_per_share is not None and fcf_per_share < 0:
        reasons.append("Negative FCF")
    return reasons


def trap_gate(
    debt_equity: float | None,
    current_ratio: float | None,
    eps_stability: int | None,
    fcf_per_share: float | None,
) -> tuple:
    """
    Interim value-trap gate. Returns (is_trap, coverage_fraction).
    is_trap is True if ANY *present* input trips its threshold. Diagnostic
    only (see Trap_Reasons) -- does NOT feed overall_score() or veto a row.
    """
    checks = []
    if debt_equity is not None:
        checks.append(debt_equity > TRAP_MAX_DE)
    if current_ratio is not None:
        checks.append(current_ratio < TRAP_MIN_CR)
    if eps_stability is not None:
        checks.append(eps_stability == 0)
    if fcf_per_share is not None:
        checks.append(fcf_per_share < 0)

    is_trap = bool(_trap_reasons(debt_equity, current_ratio, eps_stability, fcf_per_share))
    coverage_fraction = len(checks) / 4
    return is_trap, coverage_fraction


def _sector_allows(fund: dict, metric: str) -> bool:
    """
    Sector applicability gate. Returns False when the ticker's sector excludes
    `metric` ("dcf" | "altman" | "earnings_yield" | "ev_ebit"), so the caller
    substitutes None (never zero). sector=None/"" means unknown -> no exclusion.
    """
    sector = fund.get("sector") or ""
    if metric == "dcf" and sector in DCF_EXCLUDED_SECTORS:
        return False
    if metric == "altman" and sector in ALTMAN_EXCLUDED_SECTORS:
        return False
    if metric in ("earnings_yield", "ev_ebit") and sector == "Financial Services":
        return False
    return True


def overall_score(
    lynch_discount: float | None,
    graham_discount: float | None,
    defensive_score: float | None,
    debt_equity: float | None,
    current_ratio: float | None,
    growth_g: float | None,
    growth_stability: float | None,
    aaa_yield: float,
    fcf_yield: float | None = None,
    earnings_yield: float | None = None,
    shareholder_yield: float | None = None,
    roic: float | None = None,
    dist_52w_low: float | None = None,
    dist_52w_high: float | None = None,
    dist_5y_low: float | None = None,
    weeks_since_52w_low: float | None = None,
    weeks_since_5y_low: float | None = None,
    piotroski_f: int | None = None,
    altman_z: float | None = None,
    dcf_discount_pct: float | None = None,
) -> dict:
    """
    Compute the 4-pillar absolute OverallScore (0-100) and return a breakdown.

    VALUE (0.35)   = avg-present(discount[Lynch+Graham], yield[FCF+earnings+
                      shareholder], price-position[dist-52w-low*recency +
                      dist-52w-high + dist-5y-low*recency], DCF discount)
    QUALITY (0.30) = avg-present(DefensiveScore, debt/equity, current ratio, ROIC)
    GROWTH (0.20)  = avg-present(growth level g, growth stability)
    SAFETY (0.15)  = avg-present(Piotroski, Altman [both neutral-50 when absent],
                      DefensiveScore, debt/equity, current ratio [reused from Quality])

    Present-but-terrible inputs (WORST_DISCOUNT sentinel, negative D/E, non-
    positive growth, negative DCF discount) route to sub-score 0 before
    winsorize. Genuinely-absent inputs are skipped (avg-over-present). Pillars
    are renormalized over whichever pillars are present. Discount bands are
    rate-relativized by aaa_yield / SCORE_AAA_REFERENCE.
    """
    rate_scale = aaa_yield / SCORE_AAA_REFERENCE if aaa_yield > 0 else 1.0

    def _scaled_disc_bands():
        return [(lo * rate_scale, hi * rate_scale, s_lo, s_hi) for (lo, hi, s_lo, s_hi) in SCORE_DISC_BANDS]

    def _score_discount(disc: float | None) -> float | None:
        if disc is None:
            return None
        if disc <= WORST_DISCOUNT + 1.0:
            return 0.0
        w = _winsorize(disc, SCORE_DISC_WIN_LO, SCORE_DISC_WIN_HI)
        return _piecewise_score(w, _scaled_disc_bands())

    lynch_sub = _score_discount(lynch_discount)
    graham_sub = _score_discount(graham_discount)
    discount_group = _avg_present([lynch_sub, graham_sub])

    def _score_yield(v, win_lo, win_hi, bands):
        if v is None:
            return None
        if v <= 0:
            return 0.0
        return _piecewise_score(_winsorize(v, win_lo, win_hi), bands)

    fcf_sub = _score_yield(fcf_yield, SCORE_FCF_YIELD_WIN_LO, SCORE_FCF_YIELD_WIN_HI, SCORE_FCF_YIELD_BANDS)
    earny_sub = _score_yield(earnings_yield, SCORE_EARN_YIELD_WIN_LO, SCORE_EARN_YIELD_WIN_HI, SCORE_EARN_YIELD_BANDS)
    shy_sub = _score_yield(shareholder_yield, SCORE_SH_YIELD_WIN_LO, SCORE_SH_YIELD_WIN_HI, SCORE_SH_YIELD_BANDS)
    yield_group = _avg_present([fcf_sub, earny_sub, shy_sub])

    if dist_52w_low is None:
        s_52w_lo = None
    else:
        raw = _piecewise_score(_winsorize(dist_52w_low, SCORE_DIST_52W_LOW_WIN_LO, SCORE_DIST_52W_LOW_WIN_HI), SCORE_DIST_52W_LOW_BANDS)
        s_52w_lo = raw * _recency_multiplier(weeks_since_52w_low)

    if dist_52w_high is None:
        s_52w_hi = None
    else:
        s_52w_hi = _piecewise_score(_winsorize(dist_52w_high, SCORE_DIST_52W_HIGH_WIN_LO, SCORE_DIST_52W_HIGH_WIN_HI), SCORE_DIST_52W_HIGH_BANDS)

    if dist_5y_low is None:
        s_5y_lo = None
    else:
        raw = _piecewise_score(_winsorize(dist_5y_low, SCORE_DIST_5Y_LOW_WIN_LO, SCORE_DIST_5Y_LOW_WIN_HI), SCORE_DIST_5Y_LOW_BANDS)
        s_5y_lo = raw * _recency_multiplier(weeks_since_5y_low)

    price_group = _avg_present([s_52w_lo, s_52w_hi, s_5y_lo])

    def _score_dcf_discount(d: float | None) -> float | None:
        if d is None:
            return None
        if d < 0:
            return 0.0
        return _piecewise_score(_winsorize(d, SCORE_DISC_WIN_LO, SCORE_DISC_WIN_HI), SCORE_DISC_BANDS)

    dcf_sub = _score_dcf_discount(dcf_discount_pct)
    dcf_group = _avg_present([dcf_sub])

    score_value = _avg_present([discount_group, yield_group, price_group, dcf_group])

    def _score_defensive(ds: float | None) -> float | None:
        if ds is None:
            return None
        return _piecewise_score(_winsorize(ds, 0.0, 8.0), SCORE_DEF_BANDS)

    def _score_debt_equity(de: float | None) -> float | None:
        if de is None:
            return None
        if de < 0:
            return 0.0
        return _piecewise_score(_winsorize(de, 0.0, SCORE_DE_WIN_HI), SCORE_DE_BANDS)

    def _score_current_ratio(cr: float | None) -> float | None:
        if cr is None:
            return None
        return _piecewise_score(_winsorize(cr, 0.0, SCORE_CR_WIN_HI), SCORE_CR_BANDS)

    def_sub = _score_defensive(defensive_score)
    de_sub = _score_debt_equity(debt_equity)
    cr_sub = _score_current_ratio(current_ratio)

    if roic is None:
        roic_sub = None
    elif roic <= 0:
        roic_sub = 0.0
    else:
        roic_sub = _piecewise_score(_winsorize(roic, SCORE_ROIC_WIN_LO, SCORE_ROIC_WIN_HI), SCORE_ROIC_BANDS)

    score_quality = _avg_present([def_sub, de_sub, cr_sub, roic_sub])

    def _score_growth_g(gg: float | None) -> float | None:
        if gg is None:
            return None
        if gg <= 0:
            return 0.0
        return _piecewise_score(_winsorize(gg, 0.0, GROWTH_CAP), SCORE_G_BANDS)

    def _score_growth_stability(gs: float | None) -> float | None:
        if gs is None:
            return None
        return _piecewise_score(_winsorize(gs, 0.0, 1.0), SCORE_GSTAB_BANDS)

    growth_g_sub = _score_growth_g(growth_g)
    growth_stab_sub = _score_growth_stability(growth_stability)
    score_growth = _avg_present([growth_g_sub, growth_stab_sub])

    # Piotroski/Altman absent -> neutral 50.0 (not avg-over-present skip). This
    # prevents sector-excluded stocks from inheriting artificially high Safety
    # from the remaining, double-used Quality inputs.
    def _score_piotroski(f: int | None) -> float:
        if f is None:
            return 50.0
        return _piecewise_score(float(f), SCORE_PIOTROSKI_BANDS)

    def _score_altman(z: float | None) -> float:
        if z is None:
            return 50.0
        return _piecewise_score(_winsorize(z, -999.0, 10.0), SCORE_ALTMAN_BANDS)

    piotroski_sub = _score_piotroski(piotroski_f)
    altman_sub = _score_altman(altman_z)
    # def_sub/de_sub/cr_sub are intentionally reused from the Quality block —
    # both pillars feed off the same defensive/leverage/liquidity signal.
    score_safety = _avg_present([piotroski_sub, altman_sub, def_sub, de_sub, cr_sub])

    pillars = {"value": score_value, "quality": score_quality, "growth": score_growth, "safety": score_safety}
    total_weight = 0.0
    weighted_sum = 0.0

    all_sub_scores = [
        lynch_sub, graham_sub,
        fcf_sub, earny_sub, shy_sub,
        s_52w_lo, s_52w_hi, s_5y_lo,
        dcf_sub,
        def_sub, de_sub, cr_sub, roic_sub,
        growth_g_sub, growth_stab_sub,
        piotroski_sub, altman_sub,
    ]  # 17 leaves — piotroski_sub/altman_sub always float (D-04), rest may be None
    present_sub_count = sum(1 for s in all_sub_scores if s is not None)
    total_sub_count = len(all_sub_scores)

    for pillar_name, pillar_val in pillars.items():
        if pillar_val is not None:
            w = PILLAR_WEIGHTS[pillar_name]
            weighted_sum += pillar_val * w
            total_weight += w

    overall = round(weighted_sum / total_weight, 2) if total_weight > 0 else None
    coverage_pct = round(present_sub_count / total_sub_count * 100, 1) if total_sub_count > 0 else 0.0

    return {
        "overall": overall,
        "value": round(score_value, 2) if score_value is not None else None,
        "quality": round(score_quality, 2) if score_quality is not None else None,
        "growth": round(score_growth, 2) if score_growth is not None else None,
        "safety": round(score_safety, 2) if score_safety is not None else None,
        "coverage_pct": coverage_pct,
        "value_discount": round(discount_group, 2) if discount_group is not None else None,
        "value_yield": round(yield_group, 2) if yield_group is not None else None,
        "value_price": round(price_group, 2) if price_group is not None else None,
        "value_dcf": round(dcf_group, 2) if dcf_group is not None else None,
        "piotroski": round(piotroski_sub, 2),
        "altman": round(altman_sub, 2),
        "dcf_discount": round(dcf_sub, 2) if dcf_sub is not None else None,
    }


# ═════════════════════════════════════════════
# STEP 1 — FETCH UNIVERSE
# ═════════════════════════════════════════════

# Wikipedia blocks requests that don't include a browser-like User-Agent.
# We fetch the HTML ourselves with requests, then pass it to pd.read_html().
WIKI_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
}


def _wiki_tables(url: str) -> list:
    """Fetch a Wikipedia page and return all HTML tables as a list of DataFrames."""
    from io import StringIO

    resp = requests.get(url, headers=WIKI_HEADERS, timeout=15)
    resp.raise_for_status()
    return pd.read_html(StringIO(resp.text))


def fetch_sp500() -> set:
    """Scrape current S&P 500 constituents from Wikipedia."""
    log.info("Fetching S&P 500 constituents from Wikipedia...")
    tables = _wiki_tables("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
    tickers = set(tables[0]["Symbol"].str.replace(".", "-", regex=False).tolist())
    log.info(f"  → {len(tickers)} S&P 500 tickers")
    return tickers


def fetch_dow30() -> set:
    """Scrape current Dow 30 constituents from Wikipedia."""
    log.info("Fetching Dow 30 constituents from Wikipedia...")
    tables = _wiki_tables("https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average")
    for t in tables:
        if "Symbol" in t.columns:
            tickers = set(t["Symbol"].str.replace(".", "-", regex=False).tolist())
            log.info(f"  → {len(tickers)} Dow 30 tickers")
            return tickers
    raise ValueError("Could not find Dow 30 constituents table on Wikipedia.")


def fetch_nasdaq100() -> set:
    """Scrape current Nasdaq-100 constituents from Wikipedia."""
    log.info("Fetching Nasdaq-100 constituents from Wikipedia...")
    tables = _wiki_tables("https://en.wikipedia.org/wiki/List_of_NASDAQ-100_companies")
    for t in tables:
        if "Ticker" in t.columns:
            tickers = set(t["Ticker"].str.replace(".", "-", regex=False).tolist())
            log.info(f"  → {len(tickers)} Nasdaq-100 tickers")
            return tickers
    raise ValueError("Could not find Nasdaq-100 constituents table on Wikipedia.")


def get_universe() -> pd.DataFrame:
    """Return a deduplicated DataFrame with columns: ticker, indexes."""
    sp500 = fetch_sp500()
    dow30 = fetch_dow30()
    nasdaq = fetch_nasdaq100()
    all_tickers = sp500 | dow30 | nasdaq

    rows = []
    for t in sorted(all_tickers):
        membership = []
        if t in sp500:
            membership.append("S&P500")
        if t in dow30:
            membership.append("Dow30")
        if t in nasdaq:
            membership.append("Nasdaq100")
        rows.append({"ticker": t, "indexes": ", ".join(membership)})

    df = pd.DataFrame(rows)
    log.info(f"Total deduplicated universe: {len(df)} tickers")
    return df


# ═════════════════════════════════════════════
# STEP 2 — FETCH MARKET DISCOUNT-RATE ANCHORS FROM FRED
# ═════════════════════════════════════════════


def fetch_aaa_yield() -> float:
    """Fetch the latest Moody's AAA corporate bond yield from FRED."""
    log.info("Fetching AAA yield from FRED...")
    fred = Fred(api_key=FRED_API_KEY)
    series = fred.get_series(FRED_AAA_SERIES)
    yield_val = float(series.dropna().iloc[-1])
    log.info(f"  → AAA yield: {yield_val:.2f}%")
    return yield_val


def fetch_risk_free_rate() -> float:
    """Fetch the latest 10-year Treasury constant-maturity rate from FRED (FCFF DCF cost of equity)."""
    log.info("Fetching 10-year Treasury rate from FRED...")
    fred = Fred(api_key=FRED_API_KEY)
    series = fred.get_series(FRED_RISK_FREE_SERIES)
    rate = float(series.dropna().iloc[-1])
    log.info(f"  → 10-year Treasury rate: {rate:.2f}%")
    return rate


# ═════════════════════════════════════════════
# STEP 3 — FETCH FUNDAMENTALS
# ═════════════════════════════════════════════
# Data sources:
#   yfinance  → price (fast_info), EPS history for defensive checks, dividends,
#               sector/beta/currency, 5y weekly history, cashflow/income/balance
#               sheet for the Phase 6 factors and Phase 7 distress/DCF inputs
#   Finnhub   → EPS (current + growth), balance sheet ratios, market cap, BVPS
#
# Finnhub provides pre-calculated 5Y EPS CAGR and clean current-year values,
# which are more reliable than computing CAGR from 4-5 years of yfinance data.
# yfinance is kept for price (fastest) and historical EPS for defensive checks.

import yfinance as yf

FINNHUB_BASE = "https://finnhub.io/api/v1"


def get_finnhub_metrics(ticker: str) -> dict:
    """
    Fetch the full metric bundle from Finnhub stock/metric endpoint.
    Returns the raw metric dict, or empty dict on failure.
    """
    try:
        r = requests.get(
            f"{FINNHUB_BASE}/stock/metric",
            params={"symbol": ticker, "metric": "all", "token": FINNHUB_API_KEY},
            timeout=15,
        )
        if r.status_code == 200:
            return r.json().get("metric", {})
        log.warning(f"Finnhub {r.status_code} for {ticker}")
    except Exception as e:
        log.warning(f"Finnhub error for {ticker}: {e}")
    return {}


def _validate_finnhub_access() -> None:
    """Fail before the universe run when Finnhub cannot return a normal metric bundle."""
    log.info("Validating Finnhub access...")
    metrics = get_finnhub_metrics("AAPL")
    if not metrics:
        raise RuntimeError("Finnhub preflight returned no metrics for AAPL; refusing to run with silently degraded provider coverage")
    log.info("  → Finnhub access validated")


def _safe_float(v) -> float | None:
    """Return a FINITE float, else None (rejects None, np.nan, and ±inf)."""
    try:
        f = float(v)
        return f if math.isfinite(f) else None
    except TypeError, ValueError:
        return None


# ── Phase 6 yfinance candidate label lists (module-level constants) ────────

OCF_LABELS = [
    "Operating Cash Flow",
    "Total Cash From Operating Activities",
    "Cash Flow From Operations",
    "Cash From Operating Activities",
]
CAPEX_LABELS = [
    "Capital Expenditure",
    "Capital Expenditures",
    "Purchase Of Property Plant And Equipment",
    "Acquisition Of Property Plant Equipment And Software",
]
EBIT_LABELS = ["EBIT", "Operating Income", "Ebit", "Total Operating Income As Reported"]
INTEREST_EXPENSE_LABELS = ["Interest Expense Non Operating", "Interest Expense", "Interest And Debt Expense"]
TAX_PROVISION_LABELS = ["Tax Provision", "Income Tax Expense"]
PRETAX_INCOME_LABELS = ["Pretax Income", "Income Before Tax"]
TOTAL_DEBT_LABELS = ["Total Debt"]
CURRENT_DEBT_LABELS = ["Current Debt", "Current Portion Of Long Term Debt", "Short Long Term Debt"]
CASH_LABELS = ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments", "Cash And Short Term Investments"]
EQUITY_LABELS = ["Stockholders Equity", "Total Stockholders Equity", "Common Stock Equity", "Total Equity Gross Minority Interest"]
SHARES_LABELS = ["Ordinary Shares Number", "Share Issued", "Common Stock Shares Outstanding"]
DILUTED_SHARES_LABELS = ["Diluted Average Shares", "Diluted Average Shares Outstanding"]

# ── Phase 7 yfinance candidate label lists ─────────────────────────────────
NET_INCOME_LABELS = ["Net Income", "Net Income Common Stockholders", "Net Income Including Noncontrolling Interests"]
TOTAL_ASSETS_LABELS = ["Total Assets"]
GROSS_PROFIT_LABELS = ["Gross Profit"]
REVENUE_LABELS = ["Total Revenue", "Revenue", "Operating Revenue"]
CURRENT_ASSETS_LABELS = ["Current Assets", "Total Current Assets"]
CURRENT_LIABILITIES_LABELS = ["Current Liabilities", "Total Current Liabilities", "Current Liabilities Net Minority Interest"]
LONG_TERM_DEBT_LABELS = ["Long Term Debt", "Long Term Debt And Capital Lease Obligation"]
RETAINED_EARNINGS_LABELS = ["Retained Earnings", "Retained Earnings Deficit"]
TOTAL_LIABILITIES_LABELS = ["Total Liabilities Net Minority Interest", "Total Liabilities"]


# ── Phase 6/7 pure helpers ───────────────────────────────────────────────


def _yf_row(df, labels) -> float | None:
    """Most-recent annual value for the first matching label (newest column = index 0), or None."""
    if df is None or df.empty:
        return None
    for label in labels:
        if label in df.index:
            return _safe_float(df.loc[label, df.columns[0]])
    return None


def _yf_row_prev(df, labels) -> float | None:
    """Prior-year (second column) value for the first matching label, or None."""
    if df is None or df.empty or df.shape[1] < 2:
        return None
    for label in labels:
        if label in df.index:
            return _safe_float(df.loc[label, df.columns[1]])
    return None


def _extract_total_debt(balance_sheet) -> float | None:
    """Use aggregate total debt when present; otherwise sum current and long-term debt."""
    aggregate = _yf_row(balance_sheet, TOTAL_DEBT_LABELS)
    if aggregate is not None:
        return aggregate
    long_term = _yf_row(balance_sheet, LONG_TERM_DEBT_LABELS)
    current = _yf_row(balance_sheet, CURRENT_DEBT_LABELS)
    if long_term is None and current is None:
        return None
    return (long_term or 0.0) + (current or 0.0)


def _extract_total_debt_prev(balance_sheet) -> float | None:
    """Prior-year counterpart to _extract_total_debt."""
    aggregate = _yf_row_prev(balance_sheet, TOTAL_DEBT_LABELS)
    if aggregate is not None:
        return aggregate
    long_term = _yf_row_prev(balance_sheet, LONG_TERM_DEBT_LABELS)
    current = _yf_row_prev(balance_sheet, CURRENT_DEBT_LABELS)
    if long_term is None and current is None:
        return None
    return (long_term or 0.0) + (current or 0.0)


def _effective_tax_rate(income_statement) -> float:
    """Derive a bounded effective tax rate; fall back to the configured rate."""
    tax = _yf_row(income_statement, TAX_PROVISION_LABELS)
    pretax = _yf_row(income_statement, PRETAX_INCOME_LABELS)
    if tax is None or pretax is None or pretax <= 0:
        return DCF_DEFAULT_TAX_RATE
    return _winsorize(tax / pretax, 0.0, 0.35)


def _currency_mismatch(price_currency, financial_currency) -> bool:
    """True when quoted price and reported financials use different currencies (e.g. ADRs)."""
    if not price_currency or not financial_currency:
        return False
    return str(price_currency).strip().upper() != str(financial_currency).strip().upper()


def _compute_price_signals(closes, price) -> dict:
    """
    Five distance/recency signals from a pandas Close series (oldest->newest)
    and the current price: dist_52w_high, dist_52w_low, dist_5y_low,
    weeks_since_52w_low, weeks_since_5y_low, short_history.
    """
    none_result = {
        "dist_52w_high": None,
        "dist_52w_low": None,
        "dist_5y_low": None,
        "weeks_since_52w_low": None,
        "weeks_since_5y_low": None,
        "short_history": False,
    }
    if closes is None or len(closes) == 0:
        return none_result

    n = len(closes)
    if n < 8:
        return none_result

    short_history = n < 52
    w52 = closes.iloc[-min(n, 52):]
    high_52w = w52.max()
    low_52w = w52.min()
    low_5y = closes.min()

    if high_52w == 0 or low_52w == 0 or low_5y == 0:
        return {
            "dist_52w_high": None if high_52w == 0 else max(0.0, (high_52w - price) / high_52w * 100),
            "dist_52w_low": None if low_52w == 0 else max(0.0, (price - low_52w) / low_52w * 100),
            "dist_5y_low": None if low_5y == 0 else max(0.0, (price - low_5y) / low_5y * 100),
            "weeks_since_52w_low": len(w52) - 1 - int(w52.values.argmin()),
            "weeks_since_5y_low": len(closes) - 1 - int(closes.values.argmin()),
            "short_history": short_history,
        }

    return {
        "dist_52w_high": max(0.0, (high_52w - price) / high_52w * 100),
        "dist_52w_low": max(0.0, (price - low_52w) / low_52w * 100),
        "dist_5y_low": max(0.0, (price - low_5y) / low_5y * 100),
        "weeks_since_52w_low": len(w52) - 1 - int(w52.values.argmin()),
        "weeks_since_5y_low": len(closes) - 1 - int(closes.values.argmin()),
        "short_history": short_history,
    }


def _compute_fcf_yield(ocf, capex, market_cap) -> float | None:
    """FCF yield as a whole-number percent. FCF = ocf + capex (capex negative in yfinance)."""
    if ocf is None:
        return None
    fcf = ocf + capex if capex is not None else ocf
    if not market_cap:
        return None
    return fcf / market_cap * 100


def _compute_ev_ebit(ebit, total_debt, cash, market_cap) -> tuple:
    """(EV/EBIT, EBIT/EV*100); both None unless ebit>0 and EV>0. market_cap None -> (None, None)."""
    if market_cap is None:
        return (None, None)
    td = total_debt if total_debt is not None else 0
    cash = cash if cash is not None else 0
    ev = market_cap + td - cash
    if ebit is None or ebit <= 0 or ev <= 0:
        return (None, None)
    return (ev / ebit, ebit / ev * 100)


def _compute_roic(ebit, total_debt, equity, cash) -> float | None:
    """ROIC = EBIT*(1-0.21) / (total_debt + equity - cash) * 100. invested<=0 -> None (data anomaly)."""
    if ebit is None or total_debt is None or equity is None:
        return None
    c = cash if cash is not None else 0
    invested = total_debt + equity - c
    if invested <= 0:
        return None
    return ebit * (1 - 0.21) / invested * 100


def _compute_shareholder_yield(div_yield, shares_now, shares_prev) -> tuple:
    """(shareholder_yield, partial_flag). div_yield already a whole-number percent."""
    net_buyback = None
    if shares_now is not None and shares_prev is not None and shares_prev > 0:
        net_buyback = (shares_prev - shares_now) / shares_prev * 100
    partial_flag = net_buyback is None
    total = (div_yield or 0.0) + (net_buyback if net_buyback is not None else 0.0)
    return (total, partial_flag)


def _compute_piotroski(inc_curr, inc_prev, bs_curr, bs_prev, cf_curr, cf_prev) -> int | None:
    """
    Piotroski F-Score (0-9) from two years of statement DataFrames (newest-first
    columns; caller passes curr/prev split via columns[0]/prior-frame columns[0]).
    None when all current-year statements are None. Missing prior-year data skips
    (not fails) the affected 2-year comparison criterion. Returns None (routes to
    the D-04 neutral-50 Safety fallback) when 3 or fewer criteria were evaluable —
    a raw score out of 9 in that case would unfairly penalize thin-history/IPO tickers.
    """
    if inc_curr is None and bs_curr is None and cf_curr is None:
        return None

    def _get(df, labels):
        if df is None or df.empty or df.shape[1] < 1:
            return None
        for label in labels:
            if label in df.index:
                return _safe_float(df.loc[label, df.columns[0]])
        return None

    net_income_curr = _get(inc_curr, NET_INCOME_LABELS)
    total_assets_curr = _get(bs_curr, TOTAL_ASSETS_LABELS)
    ocf_curr = _get(cf_curr, OCF_LABELS)
    gross_profit_curr = _get(inc_curr, GROSS_PROFIT_LABELS)
    revenue_curr = _get(inc_curr, REVENUE_LABELS)
    current_assets_curr = _get(bs_curr, CURRENT_ASSETS_LABELS)
    current_liabilities_curr = _get(bs_curr, CURRENT_LIABILITIES_LABELS)
    long_term_debt_curr = _get(bs_curr, LONG_TERM_DEBT_LABELS)
    shares_curr = _get(bs_curr, SHARES_LABELS)

    net_income_prev = _get(inc_prev, NET_INCOME_LABELS)
    total_assets_prev = _get(bs_prev, TOTAL_ASSETS_LABELS)
    gross_profit_prev = _get(inc_prev, GROSS_PROFIT_LABELS)
    revenue_prev = _get(inc_prev, REVENUE_LABELS)
    current_assets_prev = _get(bs_prev, CURRENT_ASSETS_LABELS)
    current_liabilities_prev = _get(bs_prev, CURRENT_LIABILITIES_LABELS)
    long_term_debt_prev = _get(bs_prev, LONG_TERM_DEBT_LABELS)
    shares_prev = _get(bs_prev, SHARES_LABELS)

    score = 0
    criteria_counted = 0

    # F1: ROA > 0
    if net_income_curr is not None and total_assets_curr:
        criteria_counted += 1
        if (net_income_curr / total_assets_curr) > 0:
            score += 1
    else:
        criteria_counted += 1  # missing -> conservative fail

    # F2: OCF > 0
    if ocf_curr is not None:
        criteria_counted += 1
        if ocf_curr > 0:
            score += 1
    else:
        criteria_counted += 1

    # F3: ROA improved (requires prior year)
    if net_income_prev is not None and total_assets_prev and total_assets_curr:
        criteria_counted += 1
        roa_curr = (net_income_curr / total_assets_curr) if net_income_curr is not None and total_assets_curr else None
        roa_prev = net_income_prev / total_assets_prev
        if roa_curr is not None and roa_curr > roa_prev:
            score += 1

    # F4: Accruals — OCF/TA > ROA (quality of earnings)
    if ocf_curr is not None and total_assets_curr and net_income_curr is not None:
        criteria_counted += 1
        roa_curr = net_income_curr / total_assets_curr
        cfo_assets = ocf_curr / total_assets_curr
        if cfo_assets > roa_curr:
            score += 1
    elif total_assets_curr:
        criteria_counted += 1

    # F5: Leverage decreased — fail-safe if current-year LTD absent
    if long_term_debt_prev is not None and total_assets_prev and total_assets_curr and long_term_debt_curr is not None:
        criteria_counted += 1
        avg_assets = (total_assets_curr + total_assets_prev) / 2.0
        ltd_ratio_curr = long_term_debt_curr / avg_assets
        ltd_ratio_prev = long_term_debt_prev / total_assets_prev
        if ltd_ratio_curr < ltd_ratio_prev:
            score += 1

    # F6: Current ratio improved
    if current_assets_prev is not None and current_liabilities_prev and current_liabilities_curr:
        criteria_counted += 1
        cr_curr = (current_assets_curr / current_liabilities_curr) if current_assets_curr is not None else 0
        cr_prev = current_assets_prev / current_liabilities_prev
        if cr_curr > cr_prev:
            score += 1

    # F7: No dilution
    if shares_prev is not None and shares_curr is not None:
        criteria_counted += 1
        if shares_curr <= shares_prev:
            score += 1

    # F8: Gross margin improved
    if gross_profit_prev is not None and revenue_prev and revenue_curr:
        criteria_counted += 1
        gm_curr = (gross_profit_curr / revenue_curr) if gross_profit_curr is not None else 0
        gm_prev = gross_profit_prev / revenue_prev
        if gm_curr > gm_prev:
            score += 1

    # F9: Asset turnover improved
    if revenue_prev is not None and total_assets_prev and total_assets_curr and revenue_curr:
        criteria_counted += 1
        at_curr = revenue_curr / total_assets_curr
        at_prev = revenue_prev / total_assets_prev
        if at_curr > at_prev:
            score += 1

    if criteria_counted <= 3:
        return None
    return score


def _compute_altman_z(bs_curr, inc_curr) -> float | None:
    """
    Altman Z'' for non-financial/non-manufacturer firms.
    Z'' = 6.56*X1 + 3.26*X2 + 6.72*X3 + 1.05*X4
      X1 = Working Capital / Total Assets     X2 = Retained Earnings / Total Assets
      X3 = EBIT / Total Assets                X4 = Book Equity / Total Liabilities
    None if total_assets/total_liabilities/any required numerator is absent.
    Negative Z'' returned as-is (band table starts at -999.0).
    """
    if bs_curr is None or bs_curr.empty:
        return None

    def _get(df, labels):
        if df is None or df.empty or df.shape[1] < 1:
            return None
        for label in labels:
            if label in df.index:
                return _safe_float(df.loc[label, df.columns[0]])
        return None

    total_assets = _get(bs_curr, TOTAL_ASSETS_LABELS)
    if not total_assets:
        return None
    total_liabilities = _get(bs_curr, TOTAL_LIABILITIES_LABELS)
    if not total_liabilities:
        return None

    current_assets = _get(bs_curr, CURRENT_ASSETS_LABELS)
    current_liabilities = _get(bs_curr, CURRENT_LIABILITIES_LABELS)
    retained_earnings = _get(bs_curr, RETAINED_EARNINGS_LABELS)
    equity = _get(bs_curr, EQUITY_LABELS)
    ebit = _get(inc_curr, EBIT_LABELS) if inc_curr is not None else None

    if current_assets is None or current_liabilities is None:
        return None
    wc = current_assets - current_liabilities
    X1 = wc / total_assets

    if retained_earnings is None:
        return None
    X2 = retained_earnings / total_assets

    if ebit is None:
        return None
    X3 = ebit / total_assets

    if equity is None:
        return None
    X4 = equity / total_liabilities

    return 6.56 * X1 + 3.26 * X2 + 6.72 * X3 + 1.05 * X4


# ── FCFF/WACC DCF stack (screen-grade) ──────────────────────────────────


def _apply_screen_wacc_guardrail(calculated_wacc, risk_free_rate_pct, terminal_growth_pct) -> dict:
    """Transparent screen-level floors on unstable low-WACC estimates."""
    risk_free_floor = (risk_free_rate_pct + DCF_MIN_WACC_RISK_FREE_SPREAD_PCT) / 100.0
    terminal_floor = (terminal_growth_pct + DCF_MIN_WACC_TERMINAL_SPREAD_PCT) / 100.0
    floor = max(risk_free_floor, terminal_floor)
    guarded_wacc = max(calculated_wacc, floor)
    return {
        "wacc": guarded_wacc,
        "unfloored_wacc": calculated_wacc,
        "wacc_floor": floor,
        "floor_applied": guarded_wacc > calculated_wacc + 1e-12,
    }


def _compute_base_fcff(ocf, capex, interest_expense, tax_rate) -> float | None:
    """FCFF = OCF - |capex| + |interest_expense| * (1 - tax_rate)."""
    if ocf is None or capex is None:
        return None
    interest = abs(interest_expense) if interest_expense is not None else 0.0
    capex_outflow = abs(capex)
    return ocf - capex_outflow + interest * (1.0 - tax_rate)


def _estimate_screen_wacc(risk_free_rate_pct, aaa_yield_pct, beta, market_cap, total_debt, prior_total_debt, interest_expense, tax_rate) -> dict | None:
    """Transparent screen-grade WACC and its component assumptions."""
    if risk_free_rate_pct is None or aaa_yield_pct is None or market_cap is None or market_cap <= 0 or total_debt is None or total_debt < 0:
        return None

    beta_used = _winsorize(beta if beta is not None and beta > 0 else 1.0, DCF_BETA_FLOOR, DCF_BETA_CAP)
    cost_of_equity = (risk_free_rate_pct + beta_used * DCF_ERP) / 100.0

    observed_cost = None
    debt_base = total_debt
    if prior_total_debt is not None and prior_total_debt >= 0:
        debt_base = (total_debt + prior_total_debt) / 2.0
    if interest_expense is not None and debt_base > 0:
        observed_cost = abs(interest_expense) / debt_base
        if observed_cost <= 0 or observed_cost > 0.30:
            observed_cost = None

    aaa_cost = max(0.0, aaa_yield_pct / 100.0)
    pre_tax_cost_of_debt = max(aaa_cost, observed_cost or 0.0)
    after_tax_cost_of_debt = pre_tax_cost_of_debt * (1.0 - tax_rate)

    total_capital = market_cap + total_debt
    equity_weight = market_cap / total_capital
    debt_weight = total_debt / total_capital
    wacc = equity_weight * cost_of_equity + debt_weight * after_tax_cost_of_debt

    return {
        "wacc": wacc,
        "beta": beta_used,
        "cost_of_equity": cost_of_equity,
        "pre_tax_cost_of_debt": pre_tax_cost_of_debt,
        "equity_weight": equity_weight,
        "debt_weight": debt_weight,
        "observed_cost_of_debt": observed_cost,
    }


def _project_fcff_enterprise_value(base_fcff, initial_growth_pct, wacc, terminal_growth_pct, years=DCF_FORECAST_YEARS) -> tuple:
    """Project FCFF with a linear growth fade; return (enterprise_value, terminal_share_pct)."""
    if base_fcff is None or base_fcff <= 0 or years < 1:
        return (None, None)

    terminal_growth = terminal_growth_pct / 100.0
    if wacc <= terminal_growth:
        raise ValueError(f"FCFF DCF requires WACC ({wacc:.4f}) above terminal growth ({terminal_growth:.4f})")

    initial_growth = initial_growth_pct / 100.0
    fcff_t = base_fcff
    pv_explicit = 0.0
    for year in range(1, years + 1):
        fade = (year - 1) / max(1, years - 1)
        growth_t = initial_growth + (terminal_growth - initial_growth) * fade
        fcff_t *= 1.0 + growth_t
        pv_explicit += fcff_t / (1.0 + wacc) ** year

    terminal_value = fcff_t * (1.0 + terminal_growth) / (wacc - terminal_growth)
    pv_terminal = terminal_value / (1.0 + wacc) ** years
    enterprise_value = pv_explicit + pv_terminal
    if enterprise_value <= 0:
        return (None, None)
    terminal_share_pct = pv_terminal / enterprise_value * 100.0
    return (enterprise_value, terminal_share_pct)


def _fcff_value_per_share(base_fcff, initial_growth_pct, wacc, terminal_growth_pct, cash, total_debt, diluted_shares) -> tuple:
    """Bridge projected enterprise value to common-equity value per share."""
    if cash is None or total_debt is None or diluted_shares is None or diluted_shares <= 0:
        return (None, None, None)

    enterprise_value, terminal_share_pct = _project_fcff_enterprise_value(base_fcff, initial_growth_pct, wacc, terminal_growth_pct)
    if enterprise_value is None:
        return (None, None, None)

    equity_value = enterprise_value + cash - total_debt
    if equity_value <= 0:
        # Common equity has limited liability: an EV bridge below net debt is
        # economically a zero-value outcome, not a missing calculation.
        return (0.0, enterprise_value, terminal_share_pct)
    return (equity_value / diluted_shares, enterprise_value, terminal_share_pct)


def _compute_fcff_dcf(base_fcff, initial_growth_pct, wacc, terminal_growth_pct, cash, total_debt, diluted_shares, price) -> dict | None:
    """Screen-grade FCFF DCF: intrinsic value, discount %, EV bridge, and a paired sensitivity range."""
    if initial_growth_pct is None or price is None or price <= 0:
        return None

    growth_used = _winsorize(initial_growth_pct, DCF_INITIAL_GROWTH_FLOOR, DCF_INITIAL_GROWTH_CAP)
    value, enterprise_value, terminal_share_pct = _fcff_value_per_share(base_fcff, growth_used, wacc, terminal_growth_pct, cash, total_debt, diluted_shares)
    if value is None or value <= 0:
        return None

    low_value, _, _ = _fcff_value_per_share(
        base_fcff,
        max(DCF_INITIAL_GROWTH_FLOOR, growth_used - 2.0),
        wacc + DCF_SENSITIVITY_WACC_STEP,
        max(0.0, terminal_growth_pct - DCF_SENSITIVITY_GROWTH_STEP * 100.0),
        cash, total_debt, diluted_shares,
    )
    high_wacc = wacc - DCF_SENSITIVITY_WACC_STEP
    high_terminal_growth = min(DCF_TERMINAL_GROWTH_CAP, terminal_growth_pct + DCF_SENSITIVITY_GROWTH_STEP * 100.0)
    if high_wacc <= high_terminal_growth / 100.0:
        high_value = None
    else:
        high_value, _, _ = _fcff_value_per_share(
            base_fcff,
            min(DCF_INITIAL_GROWTH_CAP, growth_used + 2.0),
            high_wacc, high_terminal_growth,
            cash, total_debt, diluted_shares,
        )

    return {
        "intrinsic_value": value,
        "discount_pct": (1.0 - price / value) * 100.0,
        "enterprise_value": enterprise_value,
        "terminal_value_pct": terminal_share_pct,
        "growth_used_pct": growth_used,
        "value_low": low_value,
        "value_high": high_value,
    }


def _compute_fcff_reverse_dcf(price, base_fcff, wacc, terminal_growth_pct, cash, total_debt, diluted_shares) -> tuple:
    """Solve for the initial FCFF growth rate implied by the current equity price (scipy.optimize.brentq)."""
    if price is None or price <= 0 or base_fcff is None or base_fcff <= 0 or cash is None or total_debt is None or diluted_shares is None or diluted_shares <= 0:
        return (None, False)

    target_enterprise_value = price * diluted_shares + total_debt - cash
    if target_enterprise_value <= 0:
        return (None, False)

    def objective(growth_pct: float) -> float:
        enterprise_value, _ = _project_fcff_enterprise_value(base_fcff, growth_pct, wacc, terminal_growth_pct)
        if enterprise_value is None:
            return -target_enterprise_value
        return enterprise_value - target_enterprise_value

    try:
        lo, hi = -50.0, 50.0
        if objective(lo) * objective(hi) > 0:
            return (None, False)
        root = brentq(objective, lo, hi, xtol=1e-4, maxiter=100)
        return (round(root, 2), True)
    except (ValueError, RuntimeError):
        return (None, False)


LONG_TERM_DEBT_BS_ROWS = LONG_TERM_DEBT_LABELS
CURRENT_ASSETS_BS_ROWS = CURRENT_ASSETS_LABELS
CURRENT_LIABILITIES_BS_ROWS = CURRENT_LIABILITIES_LABELS


def _bs_lookup(bs, col, candidate_rows: tuple) -> float | None:
    """First matching balance-sheet row value for `col`, or None if none match."""
    for row_name in candidate_rows:
        if row_name in bs.index:
            return _safe_float(bs.loc[row_name, col])
    return None


def get_yf_price_and_history(ticker: str) -> dict:
    """
    Fetch from yfinance: price, historical EPS (defensive checks), dividends,
    1y daily closes (RSI + 52-week range), Graham working-capital rows, the
    azqato scoring-model inputs, sector/beta/currency, 5y weekly history (Phase
    6 price-distance signals), and raw cashflow/income/balance-sheet components
    for the Phase 6 factor helpers and Phase 7 distress/DCF inputs.
    Each fetch is independently guarded so one failure does not lose the others.
    """
    result = {
        "price": None,
        "annual_eps": [],
        "annual_dividends": [],
        "closes": [],
        "high_52w": None,
        "low_52w": None,
        "long_term_debt": None,
        "current_assets": None,
        "current_liabilities": None,
        "az_rev_ttm": None,
        "az_rev_fwd": None,
        "az_eps_ttm": None,
        "az_eps_fwd": None,
        "az_pe_fwd": None,
        "az_peg_fwd": None,
        "az_cash": None,
        "az_debt": None,
        # Phase 6 additions
        "sector": None,
        "beta": None,
        "price_currency": None,
        "financial_currency": None,
        "dist_52w_high": None,
        "dist_52w_low": None,
        "dist_5y_low": None,
        "weeks_since_52w_low": None,
        "weeks_since_5y_low": None,
        "short_history": False,
        "ocf": None,
        "capex": None,
        "ebit": None,
        "interest_expense": None,
        "tax_rate": DCF_DEFAULT_TAX_RATE,
        "total_debt": None,
        "prior_total_debt": None,
        "cash": None,
        "equity": None,
        "shares_now": None,
        "shares_prev": None,
        "diluted_shares": None,
        # Phase 7 additions: raw DataFrames for Piotroski/Altman (newest-first columns)
        "income_stmt_df": None,
        "balance_sheet_df": None,
        "cashflow_df": None,
    }
    t = yf.Ticker(ticker)
    # Raw (newest-first) statement frames, captured once below and reused for
    # both the Phase 6 factor lookups and the Phase 7 Piotroski/Altman inputs
    # (yfinance caches these per-Ticker-instance, but there's no reason to
    # re-trigger the property getter a second time for the same object).
    inc = bs = cf = None

    try:
        # ── Price ───────────────────────────────────────────────────────
        fi = t.fast_info
        result["price"] = getattr(fi, "last_price", None)

        # ── Sector/beta/currency — guarded separately; .info can raise on
        #    delisted tickers independently of the price fetch ───────────
        try:
            info = t.info or {}
            result["sector"] = info.get("sector")
            result["beta"] = _safe_float(info.get("beta"))
            result["price_currency"] = info.get("currency")
            result["financial_currency"] = info.get("financialCurrency")
        except Exception:
            result["sector"] = None

        # ── Historical EPS (for 10yr defensive checks) + EBIT/interest/tax ──
        inc = t.income_stmt
        if inc is not None and not inc.empty:
            inc_sorted = inc.sort_index(axis=1)  # oldest→newest
            for label in ["Basic EPS", "Diluted EPS", "Basic Eps", "Diluted Eps"]:
                if label in inc_sorted.index:
                    result["annual_eps"] = [_safe_float(v) for v in inc_sorted.loc[label].values]
                    break
            # EBIT/interest/tax/diluted-shares from the RAW (newest-first) frame.
            result["ebit"] = _yf_row(inc, EBIT_LABELS)
            result["interest_expense"] = _yf_row(inc, INTEREST_EXPENSE_LABELS)
            result["tax_rate"] = _effective_tax_rate(inc)
            result["diluted_shares"] = _yf_row(inc, DILUTED_SHARES_LABELS)

        # ── Dividend history ────────────────────────────────────────────
        # Keep up to 25 years so the Graham defensive check can test the full
        # 20-year uninterrupted record. resample("YE") fills a gap year inside the
        # span with 0, so an interruption surfaces as a zero bin (not dropped).
        divs = t.dividends
        if divs is not None and not divs.empty:
            divs.index = divs.index.tz_localize(None) if divs.index.tz else divs.index
            annual_divs = divs.resample("YE").sum()
            result["annual_dividends"] = [float(v) for v in annual_divs.values[-25:]]

        # ── 5-year weekly history → Phase 6 price distance/recency signals ──
        try:
            hist_5y = t.history(period="5y", interval="1wk")
        except Exception:
            hist_5y = pd.DataFrame()
        if hist_5y is not None and not hist_5y.empty and "Close" in hist_5y.columns and result["price"]:
            signals = _compute_price_signals(hist_5y["Close"], result["price"])
            result["dist_52w_high"] = signals["dist_52w_high"]
            result["dist_52w_low"] = signals["dist_52w_low"]
            result["dist_5y_low"] = signals["dist_5y_low"]
            result["weeks_since_52w_low"] = signals["weeks_since_52w_low"]
            result["weeks_since_5y_low"] = signals["weeks_since_5y_low"]
            result["short_history"] = signals["short_history"]

        # ── Cashflow statement — OCF and capex (Phase 6/7) ───────────────
        cf = t.cashflow
        if cf is not None and not cf.empty:
            result["ocf"] = _yf_row(cf, OCF_LABELS)
            result["capex"] = _yf_row(cf, CAPEX_LABELS)

    except Exception as e:
        log.warning(f"yfinance error for {ticker}: {e}")

    # ── 1y daily bars → RSI(14) from closes + 52-week range from intraday
    #    High/Low. auto_adjust=False keeps NOMINAL prices, matching the raw
    #    fast_info last price and the Finviz/azqato nominal 52-week convention ──
    try:
        hist = t.history(period="1y", auto_adjust=False)
        if hist is not None and not hist.empty and "Close" in hist.columns:
            result["closes"] = [float(c) for c in hist["Close"].dropna().tolist()]
            if "High" in hist.columns and not hist["High"].dropna().empty:
                result["high_52w"] = float(hist["High"].dropna().max())
            if "Low" in hist.columns and not hist["Low"].dropna().empty:
                result["low_52w"] = float(hist["Low"].dropna().min())
    except Exception as e:
        log.warning(f"yfinance history error for {ticker}: {e}")

    # ── Graham working-capital rows + Phase 6/7 balance-sheet fields ────
    # Best-effort: any gap leaves None so the check is unevaluable rather than
    # fabricated (financial-integrity rule).
    try:
        bs = t.balance_sheet
        if bs is not None and not bs.empty:
            recent = bs.columns[0]  # most recent period
            result["long_term_debt"] = _bs_lookup(bs, recent, LONG_TERM_DEBT_BS_ROWS)
            result["current_assets"] = _bs_lookup(bs, recent, CURRENT_ASSETS_BS_ROWS)
            result["current_liabilities"] = _bs_lookup(bs, recent, CURRENT_LIABILITIES_BS_ROWS)
            result["total_debt"] = _extract_total_debt(bs)
            result["prior_total_debt"] = _extract_total_debt_prev(bs)
            result["cash"] = _yf_row(bs, CASH_LABELS)
            result["equity"] = _yf_row(bs, EQUITY_LABELS)
            for label in SHARES_LABELS:
                if label in bs.index:
                    shares_row = bs.loc[label]
                    result["shares_now"] = _safe_float(shares_row.iloc[0]) if len(shares_row) >= 1 else None
                    result["shares_prev"] = _safe_float(shares_row.iloc[1]) if len(shares_row) >= 2 else None
                    break
    except Exception as e:
        log.warning(f"yfinance balance sheet error for {ticker}: {e}")

    # ── Phase 7: store the raw (newest-first) frames for Piotroski / Altman ──
    # Reuses the `inc`/`bs`/`cf` frames already fetched above (NOT the
    # oldest→newest `inc_sorted` local — Piotroski/Altman read columns[0] as
    # current year, which requires the raw newest-first frame).
    result["income_stmt_df"] = inc
    result["balance_sheet_df"] = bs
    result["cashflow_df"] = cf

    # ── Azqato scoring-model inputs ──────────────────────────────────────
    # Definitions match azqato's own feed generator (Azqato/stocks
    # scripts/fetch_screener_data.py) field for field, so our scores rank the
    # same quantities his live screener ranks:
    #   revTTM/epsTTM  = Yahoo info revenueGrowth / earningsGrowth (as percent)
    #   cash/debt      = Yahoo info totalCash / totalDebt (absolute dollars)
    #   FWD figures    = CURRENT fiscal-year ("0y") analyst consensus, matching
    #                    Seeking Alpha's "FWD" convention — NOT forwardEps/"+1y",
    #                    which look a year further out and read too low
    #   peFwd          = priceEpsCurrentYear, falling back to price / 0y EPS
    #                    estimate, then forwardPE
    #   pegFwd         = Yahoo pegRatio (tracks SA's long-term-growth PEG),
    #                    falling back to trailingPegRatio, then peFwd / epsFwd
    # Any gap leaves None so the metric is unevaluable rather than fabricated.
    try:
        info = t.info
        rg = _safe_float(info.get("revenueGrowth"))
        result["az_rev_ttm"] = rg * 100.0 if rg is not None else None
        eg = _safe_float(info.get("earningsGrowth"))
        result["az_eps_ttm"] = eg * 100.0 if eg is not None else None
        result["az_cash"] = _safe_float(info.get("totalCash"))
        result["az_debt"] = _safe_float(info.get("totalDebt"))
    except Exception as e:
        log.warning(f"yfinance info error for {ticker}: {e}")
        info = {}

    earn_est = None
    rev_est = None
    try:
        earn_est = t.earnings_estimate
    except Exception as e:
        log.warning(f"yfinance earnings estimate error for {ticker}: {e}")
    try:
        rev_est = t.revenue_estimate
    except Exception as e:
        log.warning(f"yfinance revenue estimate error for {ticker}: {e}")

    def _estimate(df, col) -> float | None:
        try:
            return _safe_float(df.loc["0y", col])
        except Exception:
            return None

    eg_fwd = _estimate(earn_est, "growth")
    result["az_eps_fwd"] = eg_fwd * 100.0 if eg_fwd is not None else None
    rg_fwd = _estimate(rev_est, "growth")
    result["az_rev_fwd"] = rg_fwd * 100.0 if rg_fwd is not None else None

    price = result["price"]
    pe = _safe_float(info.get("priceEpsCurrentYear"))
    if pe is None:
        eps_cur = _estimate(earn_est, "avg")
        if price is not None and eps_cur is not None and eps_cur > 0:
            pe = price / eps_cur
        else:
            pe = _safe_float(info.get("forwardPE"))
    result["az_pe_fwd"] = pe

    peg = _safe_float(info.get("pegRatio"))
    if peg is None or peg == 0:
        peg = _safe_float(info.get("trailingPegRatio"))
    if (peg is None or peg == 0) and pe is not None and result["az_eps_fwd"] is not None and result["az_eps_fwd"] > 0:
        peg = pe / result["az_eps_fwd"]
    result["az_peg_fwd"] = peg

    return result


def get_combined_data(ticker: str) -> dict:
    """
    Merge yfinance (price, EPS history, Phase 6/7 statement components) and
    Finnhub (current fundamentals). Finnhub values take precedence for current
    EPS, growth, and balance sheet. Falls back to yfinance values where Finnhub
    is missing.

    Returns a unified dict with all fields downstream code expects:
        price, market_cap_b, annual_eps, annual_dividends,
        ttm_eps, ttm_dps, growth_pct,
        current_ratio, book_value_ps,
        closes, high_52w, low_52w,
        long_term_debt, current_assets, current_liabilities,
        az_rev_ttm, az_rev_fwd, az_eps_ttm, az_eps_fwd,
        az_pe_fwd, az_peg_fwd, az_cash, az_debt,
        sector, beta, price_currency, financial_currency,
        dist_52w_high, dist_52w_low, dist_5y_low,
        weeks_since_52w_low, weeks_since_5y_low, short_history,
        ocf, capex, interest_expense, tax_rate,
        total_debt, prior_total_debt, cash, equity,
        shares_now, shares_prev, diluted_shares,
        debt_equity, fcf_yield, ev_ebit, earnings_yield, roic,
        shareholder_yield, shareholder_yield_partial,
        income_stmt_df, balance_sheet_df, cashflow_df
    """
    yf_data = get_yf_price_and_history(ticker)
    fh = get_finnhub_metrics(ticker)

    # ── Price (yfinance is fastest) ─────────────────────────────────
    price = yf_data["price"]

    # ── Current EPS — Finnhub first, yfinance history as fallback ───
    eps_annual = fh.get("epsAnnual")
    ttm_eps = _safe_float(eps_annual if eps_annual is not None else fh.get("epsBasicExclExtraItemsAnnual"))
    # BRK-B: Finnhub returns Class A equivalent EPS; scale to Class B before falling back.
    # yfinance already reports per-Class-B-share EPS, so the fallback needs no scaling.
    if ticker in ("BRK-B", "BRK.B") and ttm_eps is not None:
        ttm_eps = ttm_eps / 1500.0
    # Fall back to yfinance history when Finnhub EPS is missing OR non-positive —
    # a stale/negative Finnhub value should not block a usable trailing EPS.
    if (ttm_eps is None or ttm_eps <= 0) and yf_data["annual_eps"]:
        valid = [e for e in yf_data["annual_eps"] if e is not None and e == e]
        ttm_eps = valid[-1] if valid else ttm_eps

    # ── EPS growth — Finnhub pre-calculated CAGR ────────────────────
    # Prefer 5Y, fall back to 3Y, then compute from history
    # Finnhub /stock/metric returns these as whole-number percents (e.g. 11.79 ==
    # 11.79%), NOT decimal fractions — do NOT rescale by 100 (verified live: AAPL
    # epsGrowth5Y=17.91, KO=11.14, NVDA=95.27 — a *100 rescale would be absurd).
    # Explicit None check so a genuine 0.0 (flat earnings) is not discarded in
    # favour of the 3Y value.
    growth_5y = fh.get("epsGrowth5Y")
    growth_pct = _safe_float(growth_5y if growth_5y is not None else fh.get("epsGrowth3Y"))
    if growth_pct is not None:
        growth_pct = round(growth_pct, 2)

    # ── Dividends per share ─────────────────────────────────────────
    # Explicit None check so a genuine 0.0 in the annual field is not replaced by
    # the TTM field. A truly missing value (None) defaults to 0.0 — the common
    # non-payer case (a dividend payer with a Finnhub data gap is rare).
    dps_annual = fh.get("dividendPerShareAnnual")
    ttm_dps = _safe_float(dps_annual if dps_annual is not None else fh.get("dividendPerShareTTM")) or 0.0

    # ── Market cap ──────────────────────────────────────────────────
    # Finnhub returns marketCapitalization in $millions
    mkt_cap_b = None
    fh_mktcap = _safe_float(fh.get("marketCapitalization"))
    if fh_mktcap:
        mkt_cap_b = fh_mktcap / 1000.0  # millions → billions
    mkt_cap = mkt_cap_b * 1e9 if mkt_cap_b is not None else None

    # ── Balance sheet ratios (Finnhub direct) ───────────────────────
    # Graham's financial-condition test uses long-term debt vs working capital
    # (absolute dollars from the yfinance balance sheet), not a debt/equity ratio,
    # so no Finnhub leverage ratio is pulled here for the defensive check.
    current_ratio = _safe_float(fh.get("currentRatioAnnual") or fh.get("currentRatioQuarterly"))
    book_value_ps = _safe_float(fh.get("bookValuePerShareAnnual") or fh.get("bookValuePerShareQuarterly"))
    pb_ratio = _safe_float(fh.get("pb"))

    # ── Debt/equity — Phase 6/7 OverallScore Quality/Safety input only
    # (separate from the canonical Graham long-term-debt-vs-working-capital
    # defensive check above; total_debt/equity come from the yfinance balance
    # sheet fetched in get_yf_price_and_history). Negative equity -> negative
    # D/E, handled by overall_score()'s D-01 negative-routing path.
    total_debt = yf_data["total_debt"]
    equity = yf_data["equity"]
    debt_equity = (total_debt / equity) if (total_debt is not None and equity) else None

    # ── FCF per share — Finnhub bundle (Plan 02 trap gate fallback) ──
    fcf_per_share = _safe_float(fh.get("freeCashFlowPerShareTTM") or fh.get("freeCashFlowPerShareAnnual"))

    # ── Phase 6 factor computations from yfinance statement components ──
    fcf_yield = _compute_fcf_yield(ocf=yf_data["ocf"], capex=yf_data["capex"], market_cap=mkt_cap)
    ev_ebit, earnings_yield = _compute_ev_ebit(ebit=yf_data["ebit"], total_debt=total_debt, cash=yf_data["cash"], market_cap=mkt_cap)
    roic = _compute_roic(ebit=yf_data["ebit"], total_debt=total_debt, equity=equity, cash=yf_data["cash"])
    div_yield_pct = (float(ttm_dps) / float(price) * 100.0) if (price and ttm_dps) else 0.0
    shareholder_yield, sh_partial = _compute_shareholder_yield(div_yield=div_yield_pct, shares_now=yf_data["shares_now"], shares_prev=yf_data["shares_prev"])

    return {
        "price": price,
        "finnhub_ok": bool(fh),
        "market_cap_b": mkt_cap_b,
        "annual_eps": yf_data["annual_eps"],  # historical list for defensive checks
        "annual_dividends": yf_data["annual_dividends"],
        "ttm_eps": ttm_eps,
        "ttm_dps": ttm_dps,
        "growth_pct": growth_pct,  # Finnhub 5Y CAGR
        "current_ratio": current_ratio,
        "book_value_ps": book_value_ps,
        "pb_ratio": pb_ratio,
        # ── Graham defensive working-capital inputs (yfinance balance sheet) ──
        "long_term_debt": yf_data["long_term_debt"],
        "current_assets": yf_data["current_assets"],
        "current_liabilities": yf_data["current_liabilities"],
        # ── Azqato scoring-model inputs + scorecard timing display ──
        "closes": yf_data["closes"],  # 1y daily closes (RSI)
        "high_52w": yf_data["high_52w"],
        "low_52w": yf_data["low_52w"],
        "az_rev_ttm": yf_data["az_rev_ttm"],
        "az_rev_fwd": yf_data["az_rev_fwd"],
        "az_eps_ttm": yf_data["az_eps_ttm"],
        "az_eps_fwd": yf_data["az_eps_fwd"],
        "az_pe_fwd": yf_data["az_pe_fwd"],
        "az_peg_fwd": yf_data["az_peg_fwd"],
        "az_cash": yf_data["az_cash"],
        "az_debt": yf_data["az_debt"],
        # ── Phase 6/7 additions — sector/beta/currency, price signals, factors ──
        "sector": yf_data["sector"],
        "beta": yf_data["beta"],
        "price_currency": yf_data["price_currency"],
        "financial_currency": yf_data["financial_currency"],
        "dist_52w_high": yf_data["dist_52w_high"],
        "dist_52w_low": yf_data["dist_52w_low"],
        "dist_5y_low": yf_data["dist_5y_low"],
        "weeks_since_52w_low": yf_data["weeks_since_52w_low"],
        "weeks_since_5y_low": yf_data["weeks_since_5y_low"],
        "short_history": yf_data["short_history"],
        "ocf": yf_data["ocf"],
        "capex": yf_data["capex"],
        "interest_expense": yf_data["interest_expense"],
        "tax_rate": yf_data["tax_rate"],
        "total_debt": total_debt,
        "prior_total_debt": yf_data["prior_total_debt"],
        "cash": yf_data["cash"],
        "equity": equity,
        "shares_now": yf_data["shares_now"],
        "shares_prev": yf_data["shares_prev"],
        "diluted_shares": yf_data["diluted_shares"],
        "debt_equity": debt_equity,
        "fcf_per_share": fcf_per_share,
        "fcf_yield": fcf_yield,
        "ev_ebit": ev_ebit,
        "earnings_yield": earnings_yield,
        "roic": roic,
        "shareholder_yield": shareholder_yield,
        "shareholder_yield_partial": sh_partial,
        "income_stmt_df": yf_data["income_stmt_df"],
        "balance_sheet_df": yf_data["balance_sheet_df"],
        "cashflow_df": yf_data["cashflow_df"],
    }


# ═════════════════════════════════════════════
# STEP 4 — COMPUTE METRICS
# ═════════════════════════════════════════════


def compute_growth_5yr_cagr(annual_eps: list) -> float | None:
    """
    EPS CAGR using the longest available window up to 5 years.
    yfinance typically returns 4-5 years of annual data, so we use
    whatever span is available rather than requiring exactly 6 points.
    Minimum 2 data points required.
    Returns growth as a whole-number percent, capped at GROWTH_CAP.
    Returns None if data insufficient or base EPS is negative/zero.
    """
    eps = [e for e in annual_eps if e is not None and e == e]  # e == e filters np.nan
    if len(eps) < 2:
        return None
    eps_now = eps[-1]
    eps_base = eps[0]  # oldest available
    years = len(eps) - 1
    if eps_base <= 0 or eps_now <= 0:
        return None
    cagr = ((eps_now / eps_base) ** (1 / years) - 1) * 100
    return min(round(cagr, 2), GROWTH_CAP)


def _reconcile_growth(g_finnhub: float | None, g_cagr: float | None) -> float | None:
    """
    Reconcile Finnhub's reported 5Y EPS growth against the realized CAGR from
    EPS history. Finnhub free-tier epsGrowth5Y is occasionally inflated for
    flat/declining-EPS names — left unchecked it inflates Lynch/Graham fair
    values. When a realized CAGR exists, take the lower (reality-anchored)
    value; otherwise fall back to whichever single value is present.

    Finnhub values below GROWTH_FINNHUB_FLOOR are mathematically impossible
    (EPS can't drop >100% from a positive base) and are discarded before
    reconciliation — taking min() with them would only make the inflation
    guard worse (a wildly negative Finnhub value would win over a sane CAGR
    just for being lower).
    """
    if g_finnhub is not None and g_finnhub < GROWTH_FINNHUB_FLOOR:
        g_finnhub = None
    if g_finnhub is None:
        return g_cagr
    if g_cagr is None:
        return g_finnhub
    return min(g_finnhub, g_cagr)


def _eps_stable_for_gate(annual_eps: list) -> int | None:
    """
    Window-appropriate EPS-stability signal for the value-trap gate. The
    defensive EPS_Stability criterion needs 8-of-10 years, but yfinance
    supplies only ~4 years, so that field is structurally 0 for every
    ticker and useless as a gate input. Judge stability over the *available*
    window instead: stable (1) only if every available year had positive
    EPS; unstable (0) if any year was <= 0; None when too few years to judge.
    """
    eps = [e for e in annual_eps if e is not None and e == e]  # e == e filters np.nan
    if len(eps) < 2:
        return None
    return 1 if all(e > 0 for e in eps) else 0


def lynch_metrics(price: float, eps: float, g: float, dy: float) -> dict:
    """
    Compute all Lynch valuation metrics.
    g and dy are whole-number percentages (e.g. 15.0 for 15%).
    """
    m = {}

    if eps <= 0 or g <= 0:
        return {"error": "Non-positive EPS or growth"}

    pe = price / eps
    m["PE"] = round(pe, 2)
    m["PEG"] = round(pe / g, 3)
    m["PEGY"] = round(pe / (g + dy), 3) if (g + dy) > 0 else None
    m["Lynch_Score"] = round((g + dy) / pe, 3) if pe > 0 else None  # inverse PEGY

    # Fair values
    m["FV_PEG"] = round(eps * g, 2)  # PEG=1 fair value
    m["FV_PEG_Con"] = round(eps * 0.8 * g, 2)  # conservative (PEG=0.8)
    m["FV_GplusD"] = round(eps * (g + dy), 2)  # G+D method

    # Category — Lynch's Slow / Stalwart / Fast tiers (One Up on Wall Street, Ch. 8).
    # The exact cutoffs are a house quantization: Lynch pegs stalwarts at ~10-12%
    # and fast growers at ~20-25%, leaving 13-19% undefined; we fold that gap into
    # Stalwart (10-20) so it lands in the more conservative bucket.
    if g < 10:
        cat = "Slow"
    elif g <= 20:
        cat = "Stalwart"
    else:
        cat = "Fast"
    m["Lynch_Category"] = cat
    m["Lynch_BuyPrice"] = round(m["FV_GplusD"] * LYNCH_DISCOUNT[cat], 2)

    # PEG status
    if m["PEG"] < LYNCH_PEG_CHEAP:
        m["PEG_Status"] = "Cheap"
    elif m["PEG"] <= LYNCH_PEG_FAIR:
        m["PEG_Status"] = "Reasonable"
    else:
        m["PEG_Status"] = "Rich"

    # PEGY status
    if m["PEGY"] is not None:
        if m["PEGY"] < LYNCH_PEGY_CHEAP:
            m["PEGY_Status"] = "Cheap"
        elif m["PEGY"] <= LYNCH_PEGY_FAIR:
            m["PEGY_Status"] = "Reasonable"
        else:
            m["PEGY_Status"] = "Rich"

    # Lynch value ratio (G+D method)
    lv = price / m["FV_GplusD"] if m["FV_GplusD"] > 0 else None
    m["LV_Ratio"] = round(lv, 3) if lv else None
    if lv is not None:
        if lv <= LYNCH_LV_STRONG_BUY:
            m["Lynch_Status"] = "Strong Buy"
        elif lv <= LYNCH_LV_BUY:
            m["Lynch_Status"] = "Buy"
        elif lv <= LYNCH_LV_HOLD:
            m["Lynch_Status"] = "Hold"
        else:
            m["Lynch_Status"] = "Avoid"

    # Price band status (PEG-based)
    fv_con = m["FV_PEG_Con"]
    fv = m["FV_PEG"]
    if price <= 0.7 * fv_con:
        m["Lynch_PEG_Band"] = "Strong Buy"
    elif price <= fv_con:
        m["Lynch_PEG_Band"] = "Buy"
    elif price <= fv:
        m["Lynch_PEG_Band"] = "Hold"
    else:
        m["Lynch_PEG_Band"] = "Avoid"

    # Discount to Lynch buy price
    m["Lynch_Discount_Pct"] = round((1 - price / m["Lynch_BuyPrice"]) * 100, 1) if m["Lynch_BuyPrice"] > 0 else None

    return m


def graham_metrics(price: float, eps: float, g: float, aaa_yield: float) -> dict:
    """
    Compute Graham's rate-adjusted intrinsic value and price bands.
    g is a whole-number percent, capped upstream.
    """
    m = {}

    if eps <= 0 or aaa_yield <= 0:
        return {"error": "Non-positive EPS or AAA yield"}

    g_capped = min(g, GRAHAM_GROWTH_CAP)  # practitioner cap (not Graham's), see constant

    # Graham's revised intrinsic value (The Intelligent Investor, Ch. 11):
    #   V = EPS x (8.5 + 2g) x 4.4 / current AAA corporate-bond yield.
    m["Graham_FV"] = round(eps * (GRAHAM_NO_GROWTH_PE + 2 * g_capped) * GRAHAM_HIST_AAA / aaa_yield, 2)

    # Price band
    fv = m["Graham_FV"]
    if fv > 0:
        if price <= GRAHAM_DEEP_BUY * fv:
            m["Graham_Status"] = "Deep Buy"
        elif price <= GRAHAM_BUY * fv:
            m["Graham_Status"] = "Buy"
        elif price <= GRAHAM_WATCH * fv:
            m["Graham_Status"] = "Watch"
        else:
            m["Graham_Status"] = "Avoid"
        m["Graham_Discount_Pct"] = round((1 - price / fv) * 100, 1)
    else:
        m["Graham_Status"] = "N/A"
        m["Graham_Discount_Pct"] = None

    return m


def graham_defensive_score(
    market_cap_b: float | None,
    current_ratio: float | None,
    long_term_debt: float | None,
    current_assets: float | None,
    current_liabilities: float | None,
    annual_eps: list,
    annual_dividends: list,
    price: float,
    eps_3yr_avg: float | None,
    pb: float | None,
) -> dict:
    """
    Score each Graham defensive-investor criterion (0 or 1 per check).
    Returns score, breakdown, and Pass/Borderline/Fail label.

    A criterion whose inputs are missing scores 0 (cannot confirm safety) --
    consistent with the rest of the defensive screen. The 10-year EPS criteria
    require a full 10 fiscal years of data; the free yfinance income statement
    usually supplies fewer, so those two checks rarely fire on this data source.
    """
    checks = {}

    # 1) Size
    checks["Size_OK"] = int(market_cap_b is not None and market_cap_b >= MIN_MARKET_CAP_B)

    # 2) Current ratio
    checks["CurrRatio_OK"] = int(current_ratio is not None and current_ratio >= MIN_CURRENT_RATIO)

    # 3) Financial condition — Graham: long-term debt must not exceed net current
    #    assets (working capital = current assets - current liabilities).
    if long_term_debt is not None and current_assets is not None and current_liabilities is not None:
        working_capital = current_assets - current_liabilities
        checks["LTDebt_OK"] = int(working_capital > 0 and long_term_debt <= working_capital)
    else:
        checks["LTDebt_OK"] = 0

    # 4) Earnings stability — positive EPS in EACH of the last 10 years
    valid_eps = [e for e in annual_eps if e is not None and e == e]  # e == e filters np.nan
    recent_eps = valid_eps[-REQUIRED_EPS_YEARS:]
    checks["EPS_Stability"] = int(len(recent_eps) >= REQUIRED_EPS_YEARS and all(e > 0 for e in recent_eps))

    # 5) Dividend record — uninterrupted dividends for at least the last 20 years
    recent_divs = annual_dividends[-MIN_DIV_YEARS:]
    checks["Div_Record"] = int(len(recent_divs) >= MIN_DIV_YEARS and all(d is not None and d > 0 for d in recent_divs))

    # 6) 10-year EPS growth >= 33% cumulative, using 3-year averages at the
    #    beginning (years 1-3) and end (years 8-10) of the 10-year span.
    if len(valid_eps) >= REQUIRED_EPS_YEARS:
        window = valid_eps[-REQUIRED_EPS_YEARS:]
        begin_avg = sum(window[:3]) / 3
        end_avg = sum(window[-3:]) / 3
        if begin_avg > 0:
            cum_growth = (end_avg / begin_avg - 1) * 100
            checks["EPS_Growth10Y"] = int(cum_growth >= MIN_EPS_GROWTH_10Y)
        else:
            checks["EPS_Growth10Y"] = 0
    else:
        checks["EPS_Growth10Y"] = 0

    # 7) P/E <= 15 (based on 3-yr avg EPS)
    if eps_3yr_avg and eps_3yr_avg > 0:
        pe_3yr = price / eps_3yr_avg
        checks["PE_Limit"] = int(pe_3yr <= MAX_PE_GRAHAM)
    else:
        checks["PE_Limit"] = 0

    # 8) P/B ≤ 1.5 OR P/E × P/B ≤ 22.5. The P/E×P/B leg needs a POSITIVE current
    # EPS — a loss-maker's negative P/E makes the product negative and would
    # trivially satisfy the ≤ test, awarding the point it should fail.
    if pb and pb > 0:
        cur_eps = valid_eps[-1] if valid_eps else None
        if cur_eps is not None and cur_eps > 0:
            pe_cur = price / cur_eps
            checks["PB_Limit"] = int(pb <= MAX_PB_GRAHAM or (pe_cur * pb) <= MAX_PE_X_PB)
        else:
            checks["PB_Limit"] = int(pb <= MAX_PB_GRAHAM)
    else:
        checks["PB_Limit"] = 0

    score = sum(checks.values())

    if score >= DEFENSIVE_PASS_SCORE:
        label = "Pass"
    elif score >= DEFENSIVE_BORDER_SCORE:
        label = "Borderline"
    else:
        label = "Fail"

    return {"DefensiveScore": score, "DefensiveLabel": label, **checks}


def combined_score(lynch_discount: float | None, graham_discount: float | None) -> float | None:
    """
    Blended price score (higher = cheaper). Averages ONLY the legs that are
    present — a missing (None) framework is excluded, never counted as a real 0%
    discount. Each present discount is clipped to [0, 60]% (overvalued floors at 0).
    """
    legs = [d for d in (lynch_discount, graham_discount) if d is not None]
    if not legs:
        return None
    clipped = [min(max(d, 0), 60) for d in legs]
    return round(sum(clipped) / len(clipped), 1)


# ═════════════════════════════════════════════
# STEP 5 — PROCESS ALL TICKERS
# ═════════════════════════════════════════════


def process_ticker(ticker: str, aaa_yield: float, risk_free_rate: float | None = None) -> dict:
    """Run the full pipeline for one ticker. Returns a flat result dict."""
    # Error defaults to None (not omitted) so the column always exists in the
    # output DataFrame even on a run where every ticker succeeds --
    # _validate_output_dataframe requires it as a structural guarantee.
    row = {"Ticker": ticker, "Error": None}

    def _r2(value):
        return round(float(value), 2) if value is not None else None

    # --- Fetch all data (yfinance price + history, Finnhub fundamentals) ---
    fund = get_combined_data(ticker)
    row["Provider_Finnhub_OK"] = bool(fund.get("finnhub_ok"))

    # ── Price ───────────────────────────────────────────────────────
    price = fund["price"]
    if not price:
        log.warning(f"{ticker}: no price data")
        row["Error"] = "No price"
        return row
    row["Price"] = round(float(price), 2)
    mkt_cap_b = fund["market_cap_b"]

    # ── EPS ─────────────────────────────────────────────────────────
    # A name with no usable (positive) trailing EPS stays VISIBLE: Lynch/Graham
    # need positive earnings and are marked N/A, but the azqato relative model
    # deliberately ranks unprofitable names (worst on valuation) instead of
    # dropping them — matching his live screener, which scores every listed name.
    eps = fund["ttm_eps"]
    usable_eps = eps is not None and eps > 0
    if usable_eps:
        row["EPS_TTM"] = round(float(eps), 4)
    row["EPS_Annual"] = str([round(e, 2) for e in fund["annual_eps"] if e is not None and e == e])

    # ── Dividend yield ───────────────────────────────────────────────
    dps = fund["ttm_dps"] or 0.0
    dy = round((float(dps) / float(price)) * 100, 4) if price and float(dps) > 0 else 0.0
    row["DivYield_Pct"] = round(dy, 2)

    # ── Growth — Finnhub 5Y CAGR reconciled against realized EPS CAGR ───
    # (fixes Finnhub occasionally over-reporting growth for flat/declining names;
    # never floors or fabricates a positive rate — non-positive growth is
    # present-but-terrible and routes to WORST_DISCOUNT below, not dropped).
    g = _reconcile_growth(fund["growth_pct"], compute_growth_5yr_cagr(fund["annual_eps"]))
    if g is not None:
        g = min(g, GROWTH_CAP)
    row["Growth_g_Pct"] = round(g, 2) if g is not None else None
    row["AAA_Yield"] = aaa_yield
    row["MarketCap_B"] = round(mkt_cap_b, 2) if mkt_cap_b else None

    # Lynch/Graham valuation needs POSITIVE EPS and POSITIVE growth. For a
    # loss-making, contracting (g <= 0), or growth-unknown name the row stays
    # VISIBLE — valuation is marked N/A and only the earnings-independent
    # signals (Graham defensive, the azqato model) are computed. We never
    # fabricate an EPS or a growth rate.
    can_value = usable_eps and g is not None and g > 0

    # ── P/B ratio — Finnhub direct, or compute from BVPS ────────────
    pb = fund["pb_ratio"]
    if pb is None:
        bvps = fund["book_value_ps"]
        pb = round(float(price) / float(bvps), 2) if bvps and float(bvps) > 0 else None
    row["PB_Ratio"] = pb

    # ── 3-yr avg EPS for Graham P/E check ───────────────────────────
    valid_eps = [e for e in fund["annual_eps"] if e is not None and e == e]
    eps_3yr_avg = sum(valid_eps[-3:]) / len(valid_eps[-3:]) if len(valid_eps) >= 3 else None

    # ── Lynch + Graham valuation (positive growth only) ─────────────
    # D-01 (OverallScore engine): a name that CANNOT be valued (non-positive
    # EPS/growth) routes to WORST_DISCOUNT so OverallScore ranks it at the
    # bottom instead of silently excluding it from the Value pillar average.
    lm: dict = {}
    gm: dict = {}
    if can_value:
        lm = lynch_metrics(price, eps, g, dy)
        row.update({f"Lynch_{k}": v for k, v in lm.items()})
        gm = graham_metrics(price, eps, g, aaa_yield)
        row.update({f"Graham_{k}": v for k, v in gm.items()})
    else:
        if not usable_eps:
            reason = "no usable (positive) EPS"
        elif g is not None:
            reason = f"non-positive growth ({g:.1f}%)"
        else:
            reason = "growth not computable"
        log.info(f"{ticker}: {reason}, valuation N/A (kept visible)")
        row["Lynch_Lynch_Status"] = "N/A"
        row["Graham_Graham_Status"] = "N/A"
        lm = {"Lynch_Discount_Pct": WORST_DISCOUNT}
        gm = {"Graham_Discount_Pct": WORST_DISCOUNT}

    # ── Graham defensive score ───────────────────────────────────────
    ds = graham_defensive_score(
        market_cap_b=mkt_cap_b,
        current_ratio=fund["current_ratio"],
        long_term_debt=fund["long_term_debt"],
        current_assets=fund["current_assets"],
        current_liabilities=fund["current_liabilities"],
        annual_eps=fund["annual_eps"],
        annual_dividends=fund["annual_dividends"],
        price=price,
        eps_3yr_avg=eps_3yr_avg,
        pb=pb,
    )
    row.update(ds)

    # ── Combined score ───────────────────────────────────────────────
    row["CombinedScore"] = combined_score(
        lm.get("Lynch_Discount_Pct") if can_value else None,
        gm.get("Graham_Discount_Pct") if can_value else None,
    )

    # ── Show? — at least one Buy signal ─────────────────────────────
    buy_signals = {"Strong Buy", "Buy", "Deep Buy"}
    lynch_buy = lm.get("Lynch_Status") in buy_signals or lm.get("Lynch_PEG_Band") in buy_signals
    graham_buy = gm.get("Graham_Status") in buy_signals
    row["Show"] = lynch_buy or graham_buy

    # ── Azqato scoring-model inputs (no AI) ─────────────────────────
    # Metric values only here; the score/tier are RELATIVE (percentile rank vs
    # the whole universe), so they are computed in one cross-sectional pass in
    # run_screener once every ticker is fetched. RSI and the 52-week position
    # are scorecard display only — the model does not score them.
    closes = fund.get("closes") or []
    row["azqato"] = {
        "revTTM": fund["az_rev_ttm"],
        "revFwd": fund["az_rev_fwd"],
        "epsTTM": fund["az_eps_ttm"],
        "epsFwd": fund["az_eps_fwd"],
        "peFwd": fund["az_pe_fwd"],
        "pegFwd": fund["az_peg_fwd"],
        "cash": fund["az_cash"],
        "debt": fund["az_debt"],
        "rsi": wilder_rsi(closes),
        "pos_52w_pct": pct_of_52w_range(price, fund.get("low_52w"), fund.get("high_52w")),
    }

    # ── Growth stability — fraction of years with positive EPS ───────
    # None when fewer than 3 years available (genuinely unknown, not zero).
    if len(valid_eps) >= 3:
        growth_stability = sum(1 for e in valid_eps if e > 0) / len(valid_eps)
    else:
        growth_stability = None

    # ── Trap gate (diagnostic-only value-trap trip-wire) ─────────────
    eps_stab_for_gate = _eps_stable_for_gate(fund["annual_eps"])
    trap_fcf_metric = fund["fcf_yield"] if fund.get("fcf_yield") is not None else fund["fcf_per_share"]
    is_trap, _cov_fraction = trap_gate(
        debt_equity=fund["debt_equity"],
        current_ratio=fund["current_ratio"],
        eps_stability=eps_stab_for_gate,
        fcf_per_share=trap_fcf_metric,
    )
    trap_reasons = _trap_reasons(fund["debt_equity"], fund["current_ratio"], eps_stab_for_gate, trap_fcf_metric)

    # ── Distress signals (Piotroski / Altman) ─────────────────────────
    def _prev_frame(df):
        if df is None or df.empty or df.shape[1] < 2:
            return None
        return df.iloc[:, 1:]

    inc_df = fund.get("income_stmt_df")
    bs_df = fund.get("balance_sheet_df")
    cf_df = fund.get("cashflow_df")
    piotroski_f = _compute_piotroski(inc_df, _prev_frame(inc_df), bs_df, _prev_frame(bs_df), cf_df, _prev_frame(cf_df))
    altman_z = _compute_altman_z(bs_df, inc_df) if _sector_allows(fund, "altman") else None

    # ── Screen-grade FCFF/WACC DCF ────────────────────────────────────
    dcf_result = None
    dcf_implied_growth = None
    dcf_reverse_converged = False
    dcf_growth_gap = None
    dcf_wacc = None
    wacc_detail = None
    wacc_guard = None
    dcf_terminal_growth = None
    dcf_price_currency = fund.get("price_currency")
    dcf_financial_currency = fund.get("financial_currency")
    dcf_currency_mismatch = _currency_mismatch(dcf_price_currency, dcf_financial_currency)
    dcf_base_fcff = _compute_base_fcff(fund.get("ocf"), fund.get("capex"), fund.get("interest_expense"), fund.get("tax_rate", DCF_DEFAULT_TAX_RATE))
    dcf_missing_inputs = []
    dcf_assumption_warnings = []

    if _sector_allows(fund, "dcf") and g is not None and not dcf_currency_mismatch:
        market_cap = mkt_cap_b * 1e9 if mkt_cap_b is not None else None
        diluted_shares = fund.get("diluted_shares") or fund.get("shares_now")
        if diluted_shares is None and market_cap is not None and price > 0:
            diluted_shares = market_cap / price

        wacc_inputs = {
            "risk-free rate": risk_free_rate,
            "market cap": market_cap,
            "total debt": fund.get("total_debt"),
            "cash": fund.get("cash"),
            "diluted shares": diluted_shares,
            "base FCFF": dcf_base_fcff,
        }
        dcf_missing_inputs = [name for name, value in wacc_inputs.items() if value is None]
        if not dcf_price_currency or not dcf_financial_currency:
            dcf_assumption_warnings.append("Currency metadata incomplete")
        if dcf_base_fcff is not None and dcf_base_fcff <= 0:
            dcf_assumption_warnings.append("Non-positive base FCFF")
        if fund.get("beta") is None:
            dcf_assumption_warnings.append("Beta unavailable; defaulted to 1.0")
        if fund.get("interest_expense") is None and (fund.get("total_debt") or 0) > 0:
            dcf_assumption_warnings.append("Interest expense unavailable; AAA debt cost used")

        wacc_detail = _estimate_screen_wacc(
            risk_free_rate_pct=risk_free_rate,
            aaa_yield_pct=aaa_yield,
            beta=fund.get("beta"),
            market_cap=market_cap,
            total_debt=fund.get("total_debt"),
            prior_total_debt=fund.get("prior_total_debt"),
            interest_expense=fund.get("interest_expense"),
            tax_rate=fund.get("tax_rate", DCF_DEFAULT_TAX_RATE),
        )
        if not dcf_missing_inputs and wacc_detail is not None:
            dcf_terminal_growth = max(0.0, min(g, DCF_TERMINAL_GROWTH_CAP))
            wacc_guard = _apply_screen_wacc_guardrail(
                calculated_wacc=wacc_detail["wacc"],
                risk_free_rate_pct=risk_free_rate,
                terminal_growth_pct=dcf_terminal_growth,
            )
            dcf_wacc = wacc_guard["wacc"]
            if wacc_guard["floor_applied"]:
                dcf_assumption_warnings.append(f"WACC guardrail applied ({wacc_guard['unfloored_wacc'] * 100.0:.2f}% to {dcf_wacc * 100.0:.2f}%)")
            if wacc_detail["debt_weight"] > DCF_HIGH_DEBT_WEIGHT:
                dcf_assumption_warnings.append("High leverage makes DCF equity value highly sensitive")
            try:
                dcf_g = max(g, DCF_GROWTH_FLOOR)
                dcf_result = _compute_fcff_dcf(
                    base_fcff=dcf_base_fcff,
                    initial_growth_pct=dcf_g,
                    wacc=dcf_wacc,
                    terminal_growth_pct=dcf_terminal_growth,
                    cash=fund["cash"],
                    total_debt=fund["total_debt"],
                    diluted_shares=diluted_shares,
                    price=price,
                )
                dcf_implied_growth, dcf_reverse_converged = _compute_fcff_reverse_dcf(
                    price=price,
                    base_fcff=dcf_base_fcff,
                    wacc=dcf_wacc,
                    terminal_growth_pct=dcf_terminal_growth,
                    cash=fund["cash"],
                    total_debt=fund["total_debt"],
                    diluted_shares=diluted_shares,
                )
                if dcf_implied_growth is not None and dcf_result is not None:
                    dcf_growth_gap = dcf_result["growth_used_pct"] - dcf_implied_growth
                if dcf_result is not None and dcf_result["value_low"] == 0:
                    dcf_assumption_warnings.append("Stressed DCF case implies zero common-equity value")
                if dcf_result is not None and dcf_result["terminal_value_pct"] > DCF_HIGH_TERMINAL_VALUE_PCT:
                    dcf_assumption_warnings.append(f"Terminal value exceeds {DCF_HIGH_TERMINAL_VALUE_PCT:.0f}% of EV")
            except ValueError as exc:
                log.warning(f"FCFF DCF error for {ticker}: {exc}")
    elif dcf_currency_mismatch:
        dcf_missing_inputs.append("compatible price and financial currencies")
        dcf_assumption_warnings.append(f"Currency mismatch ({dcf_price_currency} price vs {dcf_financial_currency} financials); DCF excluded")

    dcf_intrinsic = dcf_result["intrinsic_value"] if dcf_result else None
    dcf_discount_pct = dcf_result["discount_pct"] if dcf_result else None
    dcf_cyclical_flag = (fund.get("sector") in CYCLICAL_SECTORS) and _sector_allows(fund, "dcf")

    # Financial Services excluded from EV/EBIT + earnings yield (None, never zero)
    earnings_yield = fund.get("earnings_yield") if _sector_allows(fund, "earnings_yield") else None
    ev_ebit = fund.get("ev_ebit") if _sector_allows(fund, "ev_ebit") else None

    # ── OverallScore — 4-pillar informational composite ───────────────
    # Uses the already sentinel-routed Lynch/Graham discounts (WORST_DISCOUNT
    # for non-valuable names above), so those names reach here and score 0 on
    # the Value pillar's discount sub-group rather than being silently skipped.
    scores = overall_score(
        lynch_discount=lm.get("Lynch_Discount_Pct"),
        graham_discount=gm.get("Graham_Discount_Pct"),
        defensive_score=ds.get("DefensiveScore"),
        debt_equity=fund["debt_equity"],
        current_ratio=fund["current_ratio"],
        growth_g=g,
        growth_stability=growth_stability,
        aaa_yield=aaa_yield,
        fcf_yield=fund.get("fcf_yield"),
        earnings_yield=earnings_yield,
        shareholder_yield=fund.get("shareholder_yield"),
        roic=fund.get("roic"),
        dist_52w_low=fund.get("dist_52w_low"),
        dist_52w_high=fund.get("dist_52w_high"),
        dist_5y_low=fund.get("dist_5y_low"),
        weeks_since_52w_low=fund.get("weeks_since_52w_low"),
        weeks_since_5y_low=fund.get("weeks_since_5y_low"),
        piotroski_f=piotroski_f,
        altman_z=altman_z,
        dcf_discount_pct=dcf_discount_pct,
    )

    row["OverallScore"] = scores["overall"]
    row["score_value"] = scores["value"]
    row["score_value_discount"] = scores["value_discount"]
    row["score_value_yield"] = scores["value_yield"]
    row["score_value_price"] = scores["value_price"]
    row["score_quality"] = scores["quality"]
    row["score_growth"] = scores["growth"]
    row["score_safety"] = scores["safety"]
    row["coverage_pct"] = scores["coverage_pct"]
    row["Trap_Reasons"] = "; ".join(trap_reasons) or None

    # ── Distress signals + DCF — additive diagnostic/scoring columns ──
    row["Piotroski_F"] = piotroski_f  # int | None (no rounding)
    row["Altman_Z"] = round(float(altman_z), 2) if altman_z is not None else None
    row["DCF_Intrinsic_Value"] = round(float(dcf_intrinsic), 2) if dcf_intrinsic is not None else None
    row["DCF_Value_Low"] = _r2(dcf_result["value_low"]) if dcf_result else None
    row["DCF_Value_High"] = _r2(dcf_result["value_high"]) if dcf_result else None
    row["DCF_Discount_Pct"] = round(float(dcf_discount_pct), 2) if dcf_discount_pct is not None else None
    row["DCF_Implied_Growth"] = round(float(dcf_implied_growth), 2) if dcf_implied_growth is not None else None
    row["DCF_Growth_Used_Pct"] = _r2(dcf_result["growth_used_pct"]) if dcf_result else None
    row["DCF_Growth_Gap_Pct"] = round(float(dcf_growth_gap), 2) if dcf_growth_gap is not None else None
    row["DCF_WACC_Pct"] = round(dcf_wacc * 100.0, 2) if dcf_wacc is not None else None
    row["DCF_WACC_Unfloored_Pct"] = _r2(wacc_guard["unfloored_wacc"] * 100.0) if wacc_guard else None
    row["DCF_WACC_Floor_Applied"] = wacc_guard["floor_applied"] if wacc_guard else False
    row["DCF_Beta"] = _r2(wacc_detail["beta"]) if wacc_detail else None
    row["DCF_Cost_Equity_Pct"] = _r2(wacc_detail["cost_of_equity"] * 100.0) if wacc_detail else None
    row["DCF_PreTax_Cost_Debt_Pct"] = _r2(wacc_detail["pre_tax_cost_of_debt"] * 100.0) if wacc_detail else None
    row["DCF_Debt_Weight_Pct"] = _r2(wacc_detail["debt_weight"] * 100.0) if wacc_detail else None
    row["DCF_Terminal_Growth_Pct"] = _r2(dcf_terminal_growth)
    row["DCF_Terminal_Value_Pct"] = _r2(dcf_result["terminal_value_pct"]) if dcf_result else None
    row["DCF_Base_FCFF_B"] = _r2(dcf_base_fcff / 1e9) if dcf_base_fcff is not None else None
    row["DCF_Price_Currency"] = dcf_price_currency
    row["DCF_Financial_Currency"] = dcf_financial_currency
    row["DCF_Currency_Mismatch"] = dcf_currency_mismatch
    row["DCF_Method"] = "FCFF screen-grade" if dcf_result else None
    row["DCF_Data_Warning"] = "; ".join((["Missing " + ", ".join(dcf_missing_inputs)] if dcf_missing_inputs else []) + dcf_assumption_warnings) or None
    row["dcf_reverse_converged"] = dcf_reverse_converged
    row["DCF_Cyclical_Flag"] = dcf_cyclical_flag
    row["score_piotroski_sub"] = scores["piotroski"]
    row["score_altman_sub"] = scores["altman"]
    row["score_dcf_discount_sub"] = scores["dcf_discount"]

    # ── Sector + price signals + fundamental factors ──────────────────
    row["Sector"] = fund["sector"]
    row["Dist_52w_High_Pct"] = _r2(fund["dist_52w_high"])
    row["Dist_52w_Low_Pct"] = _r2(fund["dist_52w_low"])
    row["Dist_5y_Low_Pct"] = _r2(fund["dist_5y_low"])
    row["Weeks_Since_52w_Low"] = _r2(fund["weeks_since_52w_low"])
    row["Weeks_Since_5y_Low"] = _r2(fund["weeks_since_5y_low"])
    row["short_history"] = fund["short_history"]
    row["FCF_Yield_Pct"] = _r2(fund["fcf_yield"])
    row["EV_EBIT"] = _r2(ev_ebit)
    row["Earnings_Yield_Pct"] = _r2(earnings_yield)
    row["ROIC_Pct"] = _r2(fund["roic"])
    row["Shareholder_Yield_Pct"] = _r2(fund["shareholder_yield"])
    row["shareholder_yield_partial"] = fund["shareholder_yield_partial"]

    # ── Nested scores block (mirrors row["azqato"] — dict-valued DataFrame
    #    column, serializes cleanly via df.to_json(orient="records")) ──────
    row["scores"] = {
        "overall": scores["overall"],
        "value": scores["value"],
        "value_discount": scores["value_discount"],
        "value_yield": scores["value_yield"],
        "value_price": scores["value_price"],
        "quality": scores["quality"],
        "growth": scores["growth"],
        "safety": scores["safety"],
        "coverage_pct": scores["coverage_pct"],
        "trap": is_trap,
        "piotroski": scores["piotroski"],
        "altman": scores["altman"],
        "dcf_discount": scores["dcf_discount"],
    }

    return row


def run_screener(universe: pd.DataFrame, aaa_yield: float, risk_free_rate: float | None = None) -> pd.DataFrame:
    results = []
    total = len(universe)
    for i, row in universe.iterrows():
        ticker = row["ticker"]
        log.info(f"[{i + 1}/{total}] Processing {ticker}...")
        result = process_ticker(ticker, aaa_yield, risk_free_rate)
        result["Indexes"] = row["indexes"]
        results.append(result)

    # ── Azqato relative scoring — one cross-sectional pass ──────────────
    # The model ranks every metric against the loaded peers, so it can only run
    # once the whole universe is fetched. Error rows (no price) carry no azqato
    # block and are excluded from the peer pool; loss-makers stay in and rank.
    scorable = {r["Ticker"]: r["azqato"] for r in results if "azqato" in r}
    scored = azqato_score_all(scorable)
    for r in results:
        if "azqato" in r:
            r["azqato"].update(scored[r["Ticker"]])
    tier_counts = pd.Series([s["tier"] for s in scored.values()]).value_counts().to_dict()
    log.info(f"Azqato tiers over {len(scorable)} names: {tier_counts}")

    df = pd.DataFrame(results)
    # Sort by OverallScore descending (best opportunities first); fall back to
    # the legacy CombinedScore sort for any row the new engine couldn't score.
    if "OverallScore" in df.columns:
        df = df.sort_values("OverallScore", ascending=False, na_position="last")
    elif "CombinedScore" in df.columns:
        df = df.sort_values("CombinedScore", ascending=False, na_position="last")
    return df


# ═════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════

OUTPUT_PATH = Path("web/public/data/results.json")
STATS_PATH = Path("web/public/data/stats.json")
SNAPSHOTS_DIR = Path("web/public/data/snapshots")
SNAPSHOTS_INDEX = SNAPSHOTS_DIR / "index.json"

MIN_VALID_ROWS = 100  # abort the publish if fewer real (non-error) rows than this
MIN_VALID_FRACTION = 0.60  # ... or if fewer than this fraction of rows are valid
MIN_FINNHUB_VALID_FRACTION = 0.60  # ... or if fewer than this fraction have live Finnhub data
MIN_DCF_ROWS = 100  # ... or if fewer than this many rows carry a complete FCFF DCF

# [ASSUMED] — no empirical anchor; low_safety_count flags rows the Safety
# pillar considers distressed, surfaced in stats.json for monitoring.
LOW_SAFETY_THRESHOLD = 30.0


def _is_first_weekday_of_month(day) -> bool:
    """True only for the first Monday-Friday date in `day`'s month (monthly snapshot gate)."""
    first = day.replace(day=1)
    weekend_offset = 7 - first.weekday() if first.weekday() > 4 else 0
    return day == first + timedelta(days=weekend_offset)


def _compute_stats(df: pd.DataFrame) -> dict:
    """
    Universe-level aggregate stats for a future stats page. Pure DataFrame
    transform -- no I/O. Columns not present in `df` (e.g. in unit-test
    fixtures populating only a subset of fields) are treated as entirely
    absent rather than raising.
    """
    universe_count = len(df)

    show_col = df["Show"] if "Show" in df.columns else None
    buy_signal_count = int(show_col.fillna(False).astype(bool).sum()) if show_col is not None else 0

    safety_col = df["score_safety"] if "score_safety" in df.columns else None
    low_safety_count = int((safety_col.dropna() < LOW_SAFETY_THRESHOLD).sum()) if safety_col is not None else 0

    buckets = {"0_20": 0, "20_40": 0, "40_60": 0, "60_80": 0, "80_100": 0}
    overall_col = df["OverallScore"] if "OverallScore" in df.columns else None
    if overall_col is not None:
        for v in overall_col.dropna():
            if v < 20:
                buckets["0_20"] += 1
            elif v < 40:
                buckets["20_40"] += 1
            elif v < 60:
                buckets["40_60"] += 1
            elif v < 80:
                buckets["60_80"] += 1
            else:
                buckets["80_100"] += 1

    pillar_averages = {}
    for pillar, col_name in (("value", "score_value"), ("quality", "score_quality"), ("growth", "score_growth"), ("safety", "score_safety")):
        col = df[col_name] if col_name in df.columns else None
        vals = col.dropna() if col is not None else None
        pillar_averages[pillar] = round(float(vals.mean()), 2) if vals is not None and len(vals) > 0 else None

    breakdown = []
    if "Sector" in df.columns:
        tmp = df.copy()
        tmp["_sector"] = tmp["Sector"].fillna("Unknown").replace("", "Unknown")
        for sector_name, group in tmp.groupby("_sector"):
            overall_vals = group["OverallScore"].dropna() if "OverallScore" in group.columns else None
            avg_score = round(float(overall_vals.mean()), 2) if overall_vals is not None and len(overall_vals) > 0 else None
            buy_count = int(group["Show"].fillna(False).astype(bool).sum()) if "Show" in group.columns else 0
            breakdown.append({"sector": sector_name, "count": int(len(group)), "avg_score": avg_score, "buy_signal_count": buy_count})
        breakdown.sort(key=lambda b: b["count"], reverse=True)

    cov_col = df["coverage_pct"] if "coverage_pct" in df.columns else None
    cov_vals = cov_col.dropna() if cov_col is not None else None
    coverage_stats = {"avg_coverage_pct": round(float(cov_vals.mean()), 2) if cov_vals is not None and len(cov_vals) > 0 else None}
    finnhub_col = df["Provider_Finnhub_OK"] if "Provider_Finnhub_OK" in df.columns else None
    finnhub_ok_rows = int(finnhub_col.fillna(False).astype(bool).sum()) if finnhub_col is not None else 0
    coverage_stats["finnhub_ok_rows"] = finnhub_ok_rows
    coverage_stats["finnhub_coverage_pct"] = round(finnhub_ok_rows / len(df) * 100.0, 2) if len(df) else None
    for key, col_name in (
        ("tickers_with_piotroski", "Piotroski_F"),
        ("tickers_with_altman", "Altman_Z"),
        ("tickers_with_dcf", "DCF_Intrinsic_Value"),
        ("tickers_with_fcf_yield", "FCF_Yield_Pct"),
    ):
        col = df[col_name] if col_name in df.columns else None
        coverage_stats[key] = int(col.notna().sum()) if col is not None else 0

    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "universe_count": universe_count,
        "buy_signal_count": buy_signal_count,
        "low_safety_count": low_safety_count,
        "score_distribution": buckets,
        "pillar_averages": pillar_averages,
        "sector_breakdown": breakdown,
        "coverage_stats": coverage_stats,
    }


def _validate_output_dataframe(df: pd.DataFrame) -> dict:
    """Reject structurally complete-looking output that is not decision-useful."""
    total_rows = len(df)
    if total_rows < MIN_VALID_ROWS:
        raise ValueError(f"Only {total_rows} rows produced; minimum total is {MIN_VALID_ROWS}")

    required_columns = {
        "Ticker", "Price", "OverallScore", "Error", "Provider_Finnhub_OK",
        "DCF_Intrinsic_Value", "DCF_Value_Low", "DCF_Value_High",
        "DCF_WACC_Pct", "DCF_Terminal_Growth_Pct", "DCF_Terminal_Value_Pct",
    }
    missing_columns = sorted(required_columns - set(df.columns))
    if missing_columns:
        raise ValueError(f"Output is missing required columns: {', '.join(missing_columns)}")

    ticker_values = df["Ticker"].fillna("").astype(str).str.strip()
    missing_ticker_count = int(ticker_values.eq("").sum())
    if missing_ticker_count:
        raise ValueError(f"Output contains {missing_ticker_count} blank ticker rows")

    duplicate_count = int(ticker_values.duplicated().sum())
    if duplicate_count:
        raise ValueError(f"Output contains {duplicate_count} duplicate ticker rows")

    error_col = df["Error"] if "Error" in df.columns else pd.Series([None] * total_rows)
    valid_mask = error_col.isna() & df["OverallScore"].notna()
    valid_rows = int(valid_mask.sum())
    valid_fraction = valid_rows / total_rows if total_rows else 0.0
    if valid_rows < MIN_VALID_ROWS:
        raise ValueError(f"Only {valid_rows} valid scored rows produced; minimum is {MIN_VALID_ROWS}")
    if valid_fraction < MIN_VALID_FRACTION:
        raise ValueError(f"Only {valid_fraction:.1%} of rows are valid and scored; minimum is {MIN_VALID_FRACTION:.0%}")

    finnhub_rows = int(df["Provider_Finnhub_OK"].eq(True).sum())
    finnhub_fraction = finnhub_rows / total_rows if total_rows else 0.0
    if finnhub_fraction < MIN_FINNHUB_VALID_FRACTION:
        raise ValueError(f"Only {finnhub_fraction:.1%} of rows have valid Finnhub data; minimum is {MIN_FINNHUB_VALID_FRACTION:.0%}")

    dcf_rows = df[error_col.isna() & df["DCF_Intrinsic_Value"].notna()].copy()
    dcf_count = len(dcf_rows)
    if dcf_count < MIN_DCF_ROWS:
        raise ValueError(f"Only {dcf_count} valid FCFF DCF rows produced; minimum is {MIN_DCF_ROWS}")
    if bool((dcf_rows["DCF_Intrinsic_Value"] <= 0).any()):
        raise ValueError("FCFF DCF output contains non-positive intrinsic values")

    range_columns = ["DCF_Value_Low", "DCF_Intrinsic_Value", "DCF_Value_High"]
    missing_range_count = int(dcf_rows[range_columns].isna().any(axis=1).sum())
    if missing_range_count:
        raise ValueError(f"FCFF DCF output contains {missing_range_count} incomplete ranges")
    invalid_range_count = int(((dcf_rows["DCF_Value_Low"] > dcf_rows["DCF_Intrinsic_Value"]) | (dcf_rows["DCF_Value_High"] < dcf_rows["DCF_Intrinsic_Value"])).sum())
    if invalid_range_count:
        raise ValueError(f"FCFF DCF output contains {invalid_range_count} misordered ranges")

    invalid_rate_count = int((dcf_rows["DCF_WACC_Pct"] <= dcf_rows["DCF_Terminal_Growth_Pct"]).sum())
    if invalid_rate_count:
        raise ValueError(f"FCFF DCF output contains {invalid_rate_count} rows with WACC at or below terminal growth")
    invalid_terminal_count = int(((dcf_rows["DCF_Terminal_Value_Pct"] < 0) | (dcf_rows["DCF_Terminal_Value_Pct"] > 100)).sum())
    if invalid_terminal_count:
        raise ValueError(f"FCFF DCF output contains {invalid_terminal_count} invalid terminal-value shares")

    return {
        "total_rows": total_rows,
        "valid_rows": valid_rows,
        "valid_fraction": valid_fraction,
        "finnhub_rows": finnhub_rows,
        "finnhub_fraction": finnhub_fraction,
        "dcf_rows": dcf_count,
    }


def write_json(df: pd.DataFrame) -> None:
    # Two independent legacy publish guards (row-count based) plus the richer
    # _validate_output_dataframe checks (required columns, blank/duplicate
    # tickers, Finnhub coverage fraction, FCFF DCF row-quality) below --
    # together they catch a total fetch outage, a growth-feed outage that
    # leaves every name visible-but-N/A, AND a degraded/malformed DCF run.
    n_valid = int(df["Error"].isna().sum()) if "Error" in df.columns else len(df)
    n_valued = int((df["Lynch_Lynch_Status"].fillna("N/A") != "N/A").sum()) if "Lynch_Lynch_Status" in df.columns else 0
    if n_valid < MIN_VALID_ROWS or n_valued < MIN_VALID_ROWS:
        log.error(
            f"Degraded run — {n_valid} non-error rows, {n_valued} with a valuation, "
            f"of {len(df)} processed (minimum {MIN_VALID_ROWS} each) — aborting JSON write"
        )
        sys.exit(1)

    try:
        validation = _validate_output_dataframe(df)
    except ValueError as exc:
        log.error(f"Aborting JSON write: {exc}")
        sys.exit(1)
    log.info(
        f"Output validation passed: {validation['valid_rows']}/{validation['total_rows']} valid scored rows "
        f"({validation['valid_fraction']:.1%}); Finnhub {validation['finnhub_fraction']:.1%}; "
        f"FCFF DCF {validation['dcf_rows']} rows"
    )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    rows = json.loads(df.to_json(orient="records"))
    payload = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "rows": rows,
    }
    OUTPUT_PATH.write_text(
        json.dumps(payload, separators=(",", ":")),
        encoding="utf-8",
    )
    log.info(f"Results written to {OUTPUT_PATH} ({len(rows)} rows)")

    stats = _compute_stats(df)
    STATS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATS_PATH.write_text(json.dumps(stats, separators=(",", ":")), encoding="utf-8")
    log.info(f"Stats written to {STATS_PATH}")


def update_snapshot_manifest(filename: str) -> None:
    """
    Append `filename` to the snapshots/index.json manifest. Ensures
    SNAPSHOTS_DIR exists, loads the existing manifest (or starts a fresh
    {"snapshots": []} one), appends `filename` if not already present, sorts,
    writes back compact.

    NOT called during normal screener runs — snapshots are monthly, driven by
    the "first weekday of month" check in .github/workflows/screen.yml, which
    invokes this only when that condition is met, and only after restoring any
    prior snapshot files from the `data` branch into this working tree first
    (the `data` branch is force-pushed as a single flat commit each run, so
    snapshots must ride forward as files inside that commit, not as branch
    history).
    """
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    if SNAPSHOTS_INDEX.exists():
        manifest = json.loads(SNAPSHOTS_INDEX.read_text(encoding="utf-8"))
    else:
        manifest = {"snapshots": []}
    if filename not in manifest["snapshots"]:
        manifest["snapshots"].append(filename)
    manifest["snapshots"].sort()
    SNAPSHOTS_INDEX.write_text(
        json.dumps(manifest, separators=(",", ":")),
        encoding="utf-8",
    )
    log.info(f"Snapshot manifest updated: {filename} ({SNAPSHOTS_INDEX})")


def main():
    log.info("═══ Lynch & Graham Screener Starting ═══")

    # 1. Build universe
    universe = get_universe()

    # 2. Fetch market discount-rate anchors + preflight Finnhub access
    aaa_yield = fetch_aaa_yield()
    risk_free_rate = fetch_risk_free_rate()
    _validate_finnhub_access()

    # 3. Process all tickers
    results_df = run_screener(universe, aaa_yield, risk_free_rate)

    # 4. Write JSON output
    write_json(results_df)

    log.info("═══ Done ═══")
    log.info(f"Total tickers processed: {len(results_df)}")
    if "Show" in results_df.columns:
        log.info(f"Rows with Buy signals:   {results_df['Show'].astype(str).eq('True').sum()}")
    else:
        log.info("Rows with Buy signals:   0 (no tickers passed valuation filters)")


if __name__ == "__main__":
    main()
