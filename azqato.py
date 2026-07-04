"""
Azqato relative percentile scoring model (no AI)
================================================
Port of the LIVE azqato screener's scoring model v2 (azqato.github.io/stocks/
screener.js, v3.30.0-v3.31.0). Pure, deterministic, no I/O — the scorer takes
already-fetched numbers for the WHOLE universe and returns scores/tiers, so the
math is unit-testable in isolation from the data pipeline.

The model is RELATIVE, not absolute: six metrics in three pillars — Growth 60
(Rev TTM 10, Rev FWD 20, EPS TTM 10, EPS FWD 20; forward growth counts double),
Valuation 20 (PEG FWD), Balance sheet 20 (cash vs debt). Each metric's points
ramp with the stock's percentile rank among its loaded peers, clamped at the
top/bottom 22%: only the top 22% of a metric earns full marks. Tiers are ranks
(S = top 10% of scored names, A = next 10%, B = 20-50%, C = 50-75%, F = bottom
25%; a perfect 100 earns S+), not buy/sell ratings.

Missing data scores a hard ZERO for that metric — the denominator stays 100, so
an incomplete stock can never outscore a complete one. This is the model's own
documented semantic (the missing cell renders dark red in the UI); the input
itself stays None end-to-end, never a fabricated value.

Also here (unchanged, scorecard display only — the v2 model dropped RSI and the
52-week position from scoring):
  - wilder_rsi()        : 14-day Wilder RSI from a close series
  - pct_of_52w_range()  : where price sits in the trailing 52-week range
"""

import math

# ── RSI ───────────────────────────────────────────────────────────────────────
RSI_PERIOD = 14

# ── Percentile ramp ───────────────────────────────────────────────────────────
CLAMP_Q = 0.22  # full marks at the (1-q)th percentile, zero below the qth
METRIC_MAX_POINTS = 20.0  # every metric's points live on a 0-20 scale
PASS_POINTS = 15.0  # points >= this = "upper part of the pack" on that metric

# ── Metrics: (key, weight, higher_is_better) ─────────────────────────────────
# weight > 0 metrics feed the Score; the weight-0 P/E-vs-growth context ratio is
# ranked only so its cell can be colored by percentile in the UI.
METRICS = (
    ("revTTM", 10, True),
    ("revFwd", 20, True),
    ("epsTTM", 10, True),
    ("epsFwd", 20, True),
    ("peVsG", 0, False),
    ("pegFwd", 20, False),
    ("cashDebt", 20, True),
)
TOTAL_WEIGHT = sum(w for _, w, _ in METRICS)  # 100
SCORED_COUNT = sum(1 for _, w, _ in METRICS if w > 0)  # 6

# ── Tier cuts by rank: S = top 10% of scored names, A = next 10%, B = 20-50%,
#    C = 50-75%, F = the rest. A perfect 100/100 earns S+ on top of the bands. ──
TIER_CUTS = (("s", 0.10), ("a", 0.20), ("b", 0.50), ("c", 0.75))


def _js_round(x: float) -> int:
    """JS Math.round (half away from zero toward +inf), not banker's rounding."""
    return math.floor(x + 0.5)


def wilder_rsi(closes: list, period: int = RSI_PERIOD) -> float | None:
    """
    14-day Wilder RSI from a list of closing prices (oldest -> newest).

    Uses Wilder's smoothing (the canonical RSI, as Finviz/azqato report it):
    seed the average gain/loss over the first `period` deltas, then smooth.
    Returns None if fewer than period+1 usable closes. Degenerate cases:
    no losses with gains -> 100; perfectly flat -> 50 (neutral).
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


def _metric_value(key: str, d: dict) -> float | None:
    """
    The rankable value for one metric of one stock, or None if unevaluable.
    Mirrors screener.js METRICS[].get exactly, including the sentinel ranks:
      - peVsG / pegFwd: unprofitable (fwd P/E <= 0) or shrinking earnings ranks
        WORST (+inf), not best or dropped — Yahoo's PEG is unreliable there.
      - cashDebt: no debt with positive cash is effectively unbounded (+inf).
    """
    if key == "peVsG":
        pe, eg = d.get("peFwd"), d.get("epsFwd")
        if pe is None or eg is None:
            return None
        return math.inf if (pe <= 0 or eg <= 0) else pe / eg
    if key == "pegFwd":
        pe, peg = d.get("peFwd"), d.get("pegFwd")
        if pe is not None and pe <= 0:
            return math.inf
        return peg if (peg is not None and peg > 0) else None
    if key == "cashDebt":
        cash, debt = d.get("cash"), d.get("debt")
        if cash is None or debt is None:
            return None
        if debt == 0:
            return math.inf if cash > 0 else None
        return cash / debt
    return d.get(key)


def _points_from_pct(p: float) -> float:
    """Points ramp: zero at/below the qth percentile, full at/above the (1-q)th."""
    pts = METRIC_MAX_POINTS * (p - CLAMP_Q) / (1.0 - 2.0 * CLAMP_Q)
    return min(max(pts, 0.0), METRIC_MAX_POINTS)


def azqato_score_all(stocks: dict[str, dict]) -> dict[str, dict]:
    """
    Score every stock relative to its loaded peers. `stocks` maps ticker ->
    metric inputs {revTTM, revFwd, epsTTM, epsFwd, peFwd, pegFwd, cash, debt}
    (None for any missing input). Returns ticker ->
        score   : 0-100 int, or None if no metric was evaluable
        tier    : 'sp'/'s'/'a'/'b'/'c'/'f', or None when score is None
        passes  : metrics in the upper part of the pack (points >= 15)
        total   : fixed 6 — a missing metric is a miss, not a pass
        parts   : per-metric points on the 0-20 scale (missing key = hard zero)
        pctiles : per-metric raw percentile 0..1 (for the breakdown UI)

    Percentiles use average-rank ties over the metric's evaluable values,
    perc = midrank / (n-1) (0.5 when n == 1), inverted for lower-is-better.
    """
    tickers = list(stocks)
    pts: dict[str, dict] = {t: {} for t in tickers}
    pcts: dict[str, dict] = {t: {} for t in tickers}

    for key, _, higher in METRICS:
        vals = [(t, v) for t in tickers if (v := _metric_value(key, stocks[t])) is not None]
        n = len(vals)
        if not n:
            continue
        vals.sort(key=lambda tv: tv[1])
        i = 0
        while i < n:
            j = i
            while j + 1 < n and vals[j + 1][1] == vals[i][1]:
                j += 1  # average-rank ties
            perc = ((i + j) / 2) / (n - 1) if n > 1 else 0.5
            if not higher:
                perc = 1.0 - perc
            p = _points_from_pct(perc)
            for k in range(i, j + 1):
                pts[vals[k][0]][key] = p
                pcts[vals[k][0]][key] = perc
            i = j + 1

    out: dict[str, dict] = {}
    for t in tickers:
        total_pts = 0.0
        have = 0
        passes = 0
        for key, weight, _ in METRICS:
            if not weight:
                continue
            p = pts[t].get(key)
            if p is None:
                continue  # missing = hard zero (adds nothing, denominator stays 100)
            have += 1
            total_pts += p * (weight / METRIC_MAX_POINTS)
            if p >= PASS_POINTS:
                passes += 1
        out[t] = {
            "score": _js_round(total_pts / TOTAL_WEIGHT * 100) if have else None,
            "passes": passes,
            "total": SCORED_COUNT,
            "parts": {k: round(v, 2) for k, v in pts[t].items()},
            "pctiles": {k: round(v, 4) for k, v in pcts[t].items()},
        }

    _assign_tiers(out)
    return out


def _assign_tiers(scored: dict[str, dict]) -> None:
    """
    Tier each scored stock by rank (screener.js computeTierMap). Boundary ties
    round UP: every stock whose score matches the last stock inside a band
    joins that band. A perfect 100 earns 'sp' out of the S band's headcount.
    Unscored stocks (score None) get tier None.
    """
    order = sorted((t for t in scored if scored[t]["score"] is not None), key=lambda t: -scored[t]["score"])
    n = len(order)
    for t in scored:
        scored[t]["tier"] = None
    if not n:
        return
    cuts = [max(1, _js_round(frac * n)) for _, frac in TIER_CUTS]
    for k in range(len(cuts)):
        j = min(cuts[k], n) - 1  # last stock inside the band
        boundary = scored[order[j]]["score"]
        while j + 1 < n and scored[order[j + 1]]["score"] == boundary:
            j += 1  # ties round up
        cuts[k] = j + 1
        if k > 0 and cuts[k] < cuts[k - 1]:
            cuts[k] = cuts[k - 1]
    ci = 0
    for i, t in enumerate(order):
        while ci < len(cuts) and i >= cuts[ci]:
            ci += 1
        scored[t]["tier"] = "sp" if scored[t]["score"] >= 100 else (TIER_CUTS[ci][0] if ci < len(TIER_CUTS) else "f")
