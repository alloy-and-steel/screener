"""
Azqato numeric screening profile (no AI)
========================================
Pure, deterministic scoring of the azqato "individual stocks" growth screen.
No I/O, no network — every function takes already-fetched numbers and returns
a verdict, so the math is unit-testable in isolation from the data pipeline.

Three pieces:
  - wilder_rsi()        : 14-day Wilder RSI from a close series (entry timing)
  - pct_of_52w_range()  : where price sits in the trailing 52-week range
  - azqato_profile()    : evaluate the 9 "strong" bands -> pass / score / coverage

Band definitions follow the azqato "individual stocks" methodology (the manual
discipline this automates) and the screener's §1 spec. Revenue growth, EPS growth,
P/E, and PEG are FORWARD by azqato's definition; the caller sources them from
yfinance analyst-consensus figures (next-fiscal-year revenue growth, next-12-month
EPS growth, forward P/E, and PEG = forward P/E / forward EPS growth) and flags
basis="forward". Margins are evaluated TTM (azqato treats them as research signals).

Integrity: a missing input is None, never 0. A band with a None input evaluates
to None (unevaluable) and is excluded from both the score and the coverage count
— it is surfaced, never silently treated as a fail.
"""

# ── RSI ───────────────────────────────────────────────────────────────────────
RSI_PERIOD = 14

# ── Azqato "strong" pass bands ─────────────────────────────────────────────────
AZQATO_PEG_MAX = 1.0  # PEG (FWD = forward P/E / forward EPS growth) below 1.0 — primary
AZQATO_REVENUE_GROWTH_MIN = 15.0  # revenue growth % (FWD, next fiscal year) above 15
AZQATO_EPS_GROWTH_MIN = 15.0  # EPS growth % (FWD, next-12-month) above 15
AZQATO_GROSS_MARGIN_MIN = 50.0  # gross margin % above 50
AZQATO_NET_MARGIN_MIN = 25.0  # net margin % above 25
AZQATO_RSI_LOW = 30.0  # RSI entry band lower bound (see note below)
AZQATO_RSI_HIGH = 45.0  # RSI entry band upper bound
AZQATO_52W_LOWER_MAX = 25.0  # price in the lower 25% of the 52-week range

# azqato's own RSI entry band is internally inconsistent in the source site
# (prose "below 30"/"30-45", table "30-45", FAQ "30-50"). 30-45 is the chosen
# working band; widen AZQATO_RSI_HIGH to 50 to match the FAQ if preferred.

# Pass threshold: count-of-bands-met needed for azqato_pass. Mirrors the
# screener's existing DEFENSIVE_PASS_SCORE convention. 7 of 9 (~78%, holding the
# original 6-of-8 = 75% intent) is a demanding-but-reachable bar. Note peg_lt_1
# and pe_lt_growth are the SAME inequality (PEG = P/E / growth, so PEG < 1 iff
# P/E < growth) — azqato lists both as separate signals yet states the equivalence,
# so both count, faithful to its checklist. Tune as forward / margin coverage shifts.
AZQATO_PASS_SCORE = 7


def wilder_rsi(closes: list, period: int = RSI_PERIOD) -> float | None:
    """
    14-day Wilder RSI from a list of closing prices (oldest -> newest).

    Uses Wilder's smoothing (the canonical RSI, as Finviz/azqato report it):
    seed the average gain/loss over the first `period` deltas, then smooth.
    Returns None if fewer than period+1 usable closes. Degenerate cases:
    no losses with gains -> 100; perfectly flat -> 50 (neutral, so a flat
    series does not falsely satisfy the 30-45 entry band).
    """
    series = [c for c in closes if c is not None and c == c]  # c == c drops nan
    if len(series) < period + 1:
        return None

    gains, losses = [], []
    for prev, cur in zip(series[:-1], series[1:]):
        delta = cur - prev
        gains.append(delta if delta > 0 else 0.0)
        losses.append(-delta if delta < 0 else 0.0)

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for gain, loss in zip(gains[period:], losses[period:]):
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return round(100.0 - 100.0 / (1.0 + rs), 2)


def pct_of_52w_range(price: float | None, low_52w: float | None, high_52w: float | None) -> float | None:
    """
    Position of `price` in the trailing 52-week [low, high] range, as 0-100
    (0 = at the low, 100 = at the high). None on any missing input or a
    degenerate range; clipped to [0, 100] for prices outside the window.
    """
    if price is None or low_52w is None or high_52w is None:
        return None
    if high_52w <= low_52w:
        return None
    pos = (price - low_52w) / (high_52w - low_52w) * 100.0
    return round(min(max(pos, 0.0), 100.0), 1)


def azqato_profile(
    *,
    peg: float | None,
    revenue_growth_pct: float | None,
    eps_growth_pct: float | None,
    pe: float | None,
    total_cash: float | None,
    total_debt: float | None,
    gross_margin_pct: float | None,
    net_margin_pct: float | None,
    rsi: float | None,
    pos_52w_pct: float | None,
) -> dict:
    """
    Evaluate the 9 azqato "strong" bands. Each band is True / False / None
    (None = input missing -> unevaluable). Returns:
        pass     : score >= AZQATO_PASS_SCORE
        score    : count of bands met
        coverage : count of bands evaluable (not None)
        basis    : "forward" (revenue/EPS growth, P/E, PEG use forward estimates)
        bands    : per-band True/False/None
        plus the input metrics echoed for the dashboard / detail drawer.

    Note: azqato's PEG FWD is forward P/E / forward EPS growth, so `peg_lt_1` and
    `pe_lt_growth` are the SAME inequality (PEG < 1 iff P/E < growth). azqato lists
    them as separate signals while stating the equivalence, so both count here,
    faithful to its checklist. The caller passes peg=None when forward growth is
    non-positive, so a declining name's sign-flipped PEG never spuriously reads
    < 1.0; pe_lt_growth still evaluates (False) in that case.
    """
    bands = {
        "peg_lt_1": None if peg is None else peg < AZQATO_PEG_MAX,
        "revenue_growth_gt_15": None if revenue_growth_pct is None else revenue_growth_pct > AZQATO_REVENUE_GROWTH_MIN,
        "eps_growth_gt_15": None if eps_growth_pct is None else eps_growth_pct > AZQATO_EPS_GROWTH_MIN,
        "pe_lt_growth": None if (pe is None or eps_growth_pct is None) else pe < eps_growth_pct,
        "cash_gt_debt": None if (total_cash is None or total_debt is None) else total_cash > total_debt,
        "gross_gt_50": None if gross_margin_pct is None else gross_margin_pct > AZQATO_GROSS_MARGIN_MIN,
        "net_gt_25": None if net_margin_pct is None else net_margin_pct > AZQATO_NET_MARGIN_MIN,
        "rsi_30_45": None if rsi is None else AZQATO_RSI_LOW <= rsi <= AZQATO_RSI_HIGH,
        "pos_52w_lower_25": None if pos_52w_pct is None else pos_52w_pct <= AZQATO_52W_LOWER_MAX,
    }

    score = sum(1 for v in bands.values() if v is True)
    coverage = sum(1 for v in bands.values() if v is not None)

    return {
        "pass": score >= AZQATO_PASS_SCORE,
        "score": score,
        "coverage": coverage,
        "basis": "forward",
        "bands": bands,
        "peg": peg,
        "revenue_growth_pct": revenue_growth_pct,
        "eps_growth_pct": eps_growth_pct,
        "pe": pe,
        "gross_margin_pct": gross_margin_pct,
        "net_margin_pct": net_margin_pct,
        "rsi": rsi,
        "pos_52w_pct": pos_52w_pct,
        "total_cash": total_cash,
        "total_debt": total_debt,
    }
