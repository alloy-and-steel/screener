"""
Seeking Alpha-style quant rating -- an approximation, informational only.

Seeking Alpha's Quant Rating is proprietary. What it publishes, and what the
one academic test of it measured, is in docs/research/seeking-alpha-quant.md
(section 4 and the reconstruction spec in section 7). This module rebuilds
the parts that are public from data the screener already fetches:

  - five factor grades (Value, Growth, Profitability, Momentum, EPS
    Revisions), each a grade A+ .. F on 13 bands;
  - every metric ranked only against stocks in the SAME SECTOR (SA: "compared
    to the same metrics for the other stocks in its sector");
  - a stock with no analyst coverage is not rated (SA covers none);
  - one very bad grade caps the rating at Hold: D+ or worse on Growth,
    Momentum or EPS Revisions, D- or worse on Value or Profitability (SA's
    FAQ, verbatim rule);
  - five ratings cut from the composite's sector percentile at SA's observed
    distribution -- 9.5% Strong Buy, 10.4% Buy, 64% Hold, 8% Sell, 8% Strong
    Sell (Guo, Jame & Markov 2026, Table 1). That distribution is SA's output,
    i.e. after the cap rule, so a capped name's Buy / Strong Buy slot goes to
    the next qualified name [ASSUMED: how SA reconciles the two is unknown].

What SA does NOT publish is ours and marked [ASSUMED]: the metric list (taken
from the paper's 59-input replica, minus what free data lacks), the factor
weights, the grade band edges, and the minimum-coverage rules. SA's size/risk
adjustment is not modelled at all.

A missing metric is skipped, never scored as zero. A present-but-terrible
multiple (a negative P/E: losses) ranks below every positive one.

Pure: no I/O, no network.
"""

from __future__ import annotations

import bisect
import math

FACTORS = ("value", "growth", "profitability", "momentum", "revisions")

# (metric key, factor, higher_is_better, non_positive_is_worst) [ASSUMED] list.
# Lower-is-better multiples with non_positive_is_worst rank a value <= 0
# (negative earnings / book / cash flow) below every positive value.
METRICS = (
    ("peFwd", "value", False, True),
    ("pegFwd", "value", False, True),
    ("pb", "value", False, True),
    ("evEbit", "value", False, True),
    ("evEbitda", "value", False, True),
    ("evSales", "value", False, False),  # negative EV (net cash > cap) really is cheap
    ("ps", "value", False, True),
    ("pcf", "value", False, True),
    ("divYield", "value", True, False),
    ("revTTM", "growth", True, False),
    ("revFwd", "growth", True, False),
    ("epsTTM", "growth", True, False),
    ("epsFwd", "growth", True, False),
    ("ebitdaYoY", "growth", True, False),
    ("ocfYoY", "growth", True, False),
    ("fcfYoY", "growth", True, False),
    ("grossMargin", "profitability", True, False),
    ("ebitMargin", "profitability", True, False),
    ("ebitdaMargin", "profitability", True, False),
    ("netMargin", "profitability", True, False),
    ("fcfMargin", "profitability", True, False),
    ("roe", "profitability", True, False),
    ("roa", "profitability", True, False),
    ("roic", "profitability", True, False),
    ("assetTurnover", "profitability", True, False),
    ("ret3m", "momentum", True, False),
    ("ret6m", "momentum", True, False),
    ("ret9m", "momentum", True, False),
    ("ret12m", "momentum", True, False),
    ("epsTrend0y", "revisions", True, False),
    ("epsTrend1y", "revisions", True, False),
    ("netRevisions0y", "revisions", True, False),
)

# [ASSUMED] SA says only that weights are "not a simple average" and favour
# the most predictive factors. The paper finds the rating loads 0.50 on
# momentum and 0.14 on value; SA's head of quant calls momentum "the single
# strongest" factor. So momentum leads -- the exact numbers are ours.
FACTOR_WEIGHTS = {"value": 0.20, "growth": 0.15, "profitability": 0.15, "momentum": 0.30, "revisions": 0.20}

GRADES = ("A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "D-", "F")
# SA's cap rule, as grade indexes into GRADES: D+ (9) or worse, D- (11) or worse.
CAP_AT_GRADE = {"growth": 9, "momentum": 9, "revisions": 9, "value": 11, "profitability": 11}

MIN_PEERS = 5  # [ASSUMED] a metric ranked against fewer sector peers is not ranked
MIN_FACTORS = 4  # [ASSUMED] factors needed for a rating (revisions always among them)

# Ratings by the composite's percentile within the sector, at SA's observed
# distribution: the first bucket whose floor the percentile reaches.
RATINGS = ("Strong Buy", "Buy", "Hold", "Sell", "Strong Sell")  # best first; web/src/types.ts SaRating mirrors it
RATING_FLOORS = (
    ("Strong Buy", 1.0 - 0.095),
    ("Buy", 1.0 - 0.095 - 0.104),
    ("Hold", 0.16),
    ("Sell", 0.08),
)
LOWEST_RATING = RATINGS[-1]
HOLD = RATINGS[2]


def _usable(v) -> bool:
    return v is not None and isinstance(v, (int, float)) and math.isfinite(v)


def _pctiles(values: dict[str, float]) -> dict[str, float]:
    """Mid-rank percentile in [0, 1], higher value = higher percentile; ties
    share their average rank. Fewer than MIN_PEERS values -> {} (unranked)."""
    n = len(values)
    if n < MIN_PEERS:
        return {}
    ordered = sorted(values.values())
    out = {}
    for key, v in values.items():
        below = bisect.bisect_left(ordered, v)
        equal = bisect.bisect_right(ordered, v) - below
        out[key] = (below + (equal - 1) / 2.0) / (n - 1)
    return out


def _rank_key(v: float, higher_better: bool, non_positive_worst: bool) -> float:
    if not higher_better:
        if non_positive_worst and v <= 0:
            return -math.inf
        return -v
    return v


def grade_for(pctile: float) -> str:
    return GRADES[min(len(GRADES) - 1, int(math.floor((1.0 - pctile) * len(GRADES))))]


def rating_for(pctile: float) -> str:
    for rating, floor in RATING_FLOORS:
        if pctile >= floor:
            return rating
    return LOWEST_RATING


def _by_sector(tickers, sector_of) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    for t in tickers:
        groups.setdefault(sector_of[t], []).append(t)
    return groups


def _sector_ratings(rated: list[str], pct: dict, composite: dict, capped: dict) -> dict[str, str]:
    """One sector's ratings. The Strong Buy and Buy buckets hold as many names
    as their percentile floors admit (SA's observed 9.5% / 10.4%), filled in
    composite order by names the cap rule does not disqualify; a capped name
    is rated no higher than Hold. So the cap moves a slot to the next
    qualified name instead of shrinking the bucket below SA's distribution."""
    n_top = {name: sum(1 for t in rated if rating_for(pct[t]) == name) for name in ("Strong Buy", "Buy")}
    out = {}
    queue = [t for t in sorted(rated, key=lambda t: (-composite[t], t)) if not capped[t]]
    for name in ("Strong Buy", "Buy"):
        for t in queue[: n_top[name]]:
            out[t] = name
        queue = queue[n_top[name]:]
    for t in rated:
        if t not in out:
            r = rating_for(pct[t])
            out[t] = HOLD if r in ("Strong Buy", "Buy") else r
    return out


def sa_quant_all(inputs: dict[str, dict]) -> dict[str, dict]:
    """
    inputs: {ticker: {"sector": str | None, "covered": bool, "metrics": {key: float | None}}}
    Returns {ticker: {"rating", "score", "capped", "grades", "pctiles", "metricPctiles"}}
    for every input ticker. `score` is the composite's sector percentile x 100;
    `pctiles` are factor percentiles in [0, 1]. Unrated names carry None.

    Only covered names with a sector are peers: SA's universe has no uncovered
    stocks, and a stock with no sector has no peer set to be graded against.
    """
    peers = [t for t, x in inputs.items() if x.get("covered") and x.get("sector")]
    sector_of = {t: inputs[t]["sector"] for t in peers}
    groups = _by_sector(peers, sector_of)

    metric_pct: dict[str, dict[str, float]] = {t: {} for t in inputs}
    for key, _factor, higher_better, nonpos_worst in METRICS:
        for members in groups.values():
            vals = {}
            for t in members:
                v = inputs[t]["metrics"].get(key)
                if _usable(v):
                    vals[t] = _rank_key(float(v), higher_better, nonpos_worst)
            for t, p in _pctiles(vals).items():
                metric_pct[t][key] = p

    factor_keys = {f: [k for k, ff, _, _ in METRICS if ff == f] for f in FACTORS}
    factor_raw: dict[str, dict[str, float]] = {t: {} for t in inputs}
    for t in peers:
        for f, keys in factor_keys.items():
            present = [metric_pct[t][k] for k in keys if k in metric_pct[t]]
            if len(present) >= math.ceil(len(keys) / 2):
                factor_raw[t][f] = sum(present) / len(present)

    factor_pct: dict[str, dict[str, float]] = {t: {} for t in inputs}
    for f in FACTORS:
        for members in groups.values():
            vals = {t: factor_raw[t][f] for t in members if f in factor_raw[t]}
            for t, p in _pctiles(vals).items():
                factor_pct[t][f] = p

    composite = {}
    for t in peers:
        fp = factor_pct[t]
        if "revisions" in fp and len(fp) >= MIN_FACTORS:
            w = sum(FACTOR_WEIGHTS[f] for f in fp)
            composite[t] = sum(FACTOR_WEIGHTS[f] * p for f, p in fp.items()) / w

    score_pct: dict[str, float] = {}
    for members in groups.values():
        score_pct.update(_pctiles({t: composite[t] for t in members if t in composite}))

    grades_of = {t: {f: (grade_for(factor_pct[t][f]) if f in factor_pct[t] else None) for f in FACTORS} for t in inputs}
    capped_of = {
        t: any(g is not None and GRADES.index(g) >= CAP_AT_GRADE[f] for f, g in grades_of[t].items())
        for t in inputs
    }
    ratings = {}
    for members in groups.values():
        ratings.update(_sector_ratings([t for t in members if t in score_pct], score_pct, composite, capped_of))

    out = {}
    for t in inputs:
        fp = factor_pct[t]
        grades = grades_of[t]
        capped = capped_of[t]
        p = score_pct.get(t)
        rating = ratings.get(t)
        out[t] = {
            "rating": rating,
            "score": round(p * 100.0, 1) if p is not None else None,
            "capped": capped,
            "grades": grades,
            "pctiles": {f: round(fp[f], 3) for f in FACTORS if f in fp},
            "metricPctiles": metric_pct[t],
        }
    return out
