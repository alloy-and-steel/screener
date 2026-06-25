"""
Quantitative thesis-break monitor (no AI)
=========================================
Closes the loop on the LLM qualitative layer's QUANTITATIVE falsifiers: each
names a numeric metric the screener already computes per row, plus a trip
expression like ">30". This module re-checks those falsifiers against the
screener's own fresh numbers every run — plain Python, no model call, no cost.

This is the deterministic half of §4. The LLM that emits the `thesis` dict is
deferred (v1 spine); these functions work the moment a thesis exists and are
unit-testable in isolation.

Fail-loud, never silent (pie financial-integrity rule + the plan's own §9):
  - an unparseable trip expression RAISES (caller records it as an error),
  - a falsifier metric that is not a known row key is surfaced as an error,
  - a metric present but None-valued is surfaced as `unevaluable`,
A falsifier that cannot be evaluated must show up as such — a thesis-break check
that silently never fires reads as "monitored" while being dead.
"""

import re

# Closed set of numeric row keys a quantitative falsifier may reference.
# Verified against the web/public/data/results.json schema (built fresh, not committed).
#
# CRITICAL: Lynch/Graham metric keys are DOUBLE-prefixed. process_ticker does
#   row.update({f"Graham_{k}": v for k, v in graham_metrics(...).items()})
# over a dict whose keys are already "Graham_*"/"Lynch_*", so the on-disk keys
# are e.g. Graham_Graham_Discount_Pct and Lynch_Lynch_Discount_Pct (NOT the
# idealized single-prefixed names). Any falsifier metric the LLM emits MUST be
# one of these literal keys, or the check below fails loud rather than no-op.
FALSIFIER_METRIC_KEYS = frozenset({
    "Growth_g_Pct",
    "Graham_Graham_Discount_Pct",   # double-prefixed (see note above)
    "Lynch_Lynch_Discount_Pct",     # double-prefixed
    "Lynch_PEG",
    "Lynch_PE",
    "DefensiveScore",
    "PB_Ratio",
    "EPS_TTM",
    "DivYield_Pct",
    "MarketCap_B",
    "CombinedScore",
})

# A trip expression is a comparison operator followed by a numeric literal.
# Longer operators first so ">=" is not partially matched as ">".
_TRIP_RE = re.compile(r"^\s*(>=|<=|==|!=|>|<)\s*(-?\d+(?:\.\d+)?)\s*$")

_OPS = {
    ">":  lambda a, b: a > b,
    "<":  lambda a, b: a < b,
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
}


def eval_trip(value, trips_when: str) -> bool:
    """
    Evaluate a trip expression (e.g. ">30", "<= 0.5", "== 0") against `value`.
    Returns True iff the falsifier's condition is currently met.

    Raises ValueError on a None/non-numeric value or an unparseable expression
    — an un-checkable falsifier must surface, never silently pass or skip.
    """
    if value is None:
        raise ValueError("eval_trip: value is None")
    match = _TRIP_RE.match(trips_when or "")
    if not match:
        raise ValueError(f"eval_trip: unparseable trips_when {trips_when!r}")
    try:
        val = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"eval_trip: non-numeric value {value!r}")
    op, threshold = match.group(1), float(match.group(2))
    return _OPS[op](val, threshold)


def check_falsifiers(row: dict, thesis: dict,
                     allowed_metrics: frozenset = FALSIFIER_METRIC_KEYS) -> dict:
    """
    Re-check a thesis's quantitative falsifiers against `row` (the screener's
    fresh numbers for that ticker). Returns a structured result:

        tripped     : falsifiers whose condition is met -> thesis impaired
        unevaluable : metric present but row value is None (data missing)
        errors      : fail-loud cases — metric not in the allowed row-key set,
                      metric absent from the row, or unparseable trip expression
        deferred    : qualitative falsifiers (handled by the v2 web-search loop)
        thesis_status: "impaired" if anything tripped, else "intact"

    `errors` are surfaced, not swallowed; the dashboard must show them so an
    operator never mistakes a dead falsifier for a passing one.
    """
    tripped, unevaluable, errors, deferred = [], [], [], []

    for f in thesis.get("falsifiers", []):
        if f.get("kind") != "quantitative":
            deferred.append(f)
            continue

        metric = f.get("metric")
        if allowed_metrics is not None and metric not in allowed_metrics:
            errors.append({**f, "error": f"metric {metric!r} not in allowed row-key set"})
            continue
        if metric not in row:
            errors.append({**f, "error": f"metric {metric!r} absent from row"})
            continue

        val = row.get(metric)
        if val is None:
            unevaluable.append({**f, "observed": None})
            continue

        try:
            if eval_trip(val, f.get("trips_when")):
                tripped.append({**f, "observed": val})
        except ValueError as exc:
            errors.append({**f, "observed": val, "error": str(exc)})

    return {
        "tripped": tripped,
        "unevaluable": unevaluable,
        "errors": errors,
        "deferred": deferred,
        "thesis_status": "impaired" if tripped else "intact",
    }
