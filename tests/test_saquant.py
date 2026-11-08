"""
Seeking Alpha-style quant rating (saquant.py)
=============================================
Pins the rules this approximation takes from what Seeking Alpha publishes
(docs/research/seeking-alpha-quant.md section 4): every metric is graded
against the stock's own SECTOR, a stock with no analyst coverage is not rated,
one very bad factor grade caps the rating at Hold, and the five buckets follow
SA's observed distribution (8 / 8 / 64 / 10.4 / 9.5 %). Expected values are
worked out by hand from those rules, not recorded from a run.

HOW TO RUN:
    python tests/test_saquant.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from saquant import (  # noqa: E402
    FACTORS,
    GRADES,
    METRICS,
    sa_quant_all,
)

METRIC_KEYS = [k for k, _, _, _ in METRICS]


def _metrics(level: float, factor_levels: dict | None = None, **overrides) -> dict:
    """Every metric at one level (higher level = better on every metric):
    lower-is-better metrics get 1/level so they improve as level rises.
    `factor_levels` sets a different level for every metric of one factor."""
    out = {}
    for key, factor, higher_better, _ in METRICS:
        lv = (factor_levels or {}).get(factor, level)
        out[key] = lv if higher_better else 1.0 / lv
    out.update(overrides)
    return out


def _stock(sector="Technology", covered=True, level=1.0, factor_levels=None, **overrides) -> dict:
    return {"sector": sector, "covered": covered, "metrics": _metrics(level, factor_levels, **overrides)}


def test_tables_are_consistent():
    assert set(f for _, f, _, _ in METRICS) == set(FACTORS)
    assert len(GRADES) == 13 and GRADES[0] == "A+" and GRADES[-1] == "F"


def test_grades_are_sector_relative():
    # Tech names are all far "better" in raw numbers than every Energy name,
    # yet the best Energy name still grades A+ inside Energy.
    inputs = {f"T{i}": _stock("Technology", level=100.0 + i) for i in range(20)}
    inputs.update({f"E{i}": _stock("Energy", level=1.0 + i / 100) for i in range(20)})
    out = sa_quant_all(inputs)
    assert out["E19"]["grades"]["momentum"] == "A+", out["E19"]
    assert out["E0"]["grades"]["momentum"] == "F", out["E0"]
    assert out["T0"]["grades"]["momentum"] == "F", out["T0"]
    assert out["E19"]["rating"] == "Strong Buy"
    assert out["T0"]["rating"] == "Strong Sell"


def test_rating_buckets_follow_sa_distribution():
    # 100 names, strictly ordered, so composite percentile p = rank / 99.
    # Strong Buy p >= 0.905 -> rank >= 89.6 -> ranks 90..99 (10 names)
    # Buy        p >= 0.801 -> rank >= 79.3 -> ranks 80..89 (10)
    # Strong Sell p < 0.08  -> rank < 7.92  -> ranks 0..7   (8)
    # Sell        p < 0.16  -> rank < 15.84 -> ranks 8..15  (8); Hold the other 64.
    inputs = {f"S{i:03d}": _stock(level=1.0 + i) for i in range(100)}
    out = sa_quant_all(inputs)
    counts = {}
    for r in out.values():
        counts[r["rating"]] = counts.get(r["rating"], 0) + 1
    assert counts == {"Strong Buy": 10, "Buy": 10, "Hold": 64, "Sell": 8, "Strong Sell": 8}, counts
    assert out["S099"]["score"] == 100.0 and out["S000"]["score"] == 0.0


def test_non_positive_multiple_ranks_worst():
    # A negative forward P/E (a loss) is present-but-terrible: it ranks below
    # every positive P/E, including a very expensive one.
    inputs = {f"S{i}": _stock(level=10.0) for i in range(10)}
    inputs["LOSS"] = _stock(level=10.0, peFwd=-5.0)
    inputs["PRICEY"] = _stock(level=10.0, peFwd=500.0)
    out = sa_quant_all(inputs)
    assert out["LOSS"]["metricPctiles"]["peFwd"] == 0.0
    assert out["PRICEY"]["metricPctiles"]["peFwd"] > 0.0


def test_missing_metric_is_skipped_not_zero():
    # Same numbers everywhere except one name lacks P/B. Skipping (not zeroing)
    # leaves its value grade equal to its identical peers'.
    inputs = {f"S{i}": _stock(level=5.0) for i in range(10)}
    inputs["NOPB"] = _stock(level=5.0, pb=None)
    out = sa_quant_all(inputs)
    assert out["NOPB"]["metricPctiles"].get("pb") is None
    assert out["NOPB"]["pctiles"]["value"] == out["S0"]["pctiles"]["value"]


def test_factor_needs_half_its_metrics():
    momentum_keys = [k for k, f, _, _ in METRICS if f == "momentum"]
    gone = {k: None for k in momentum_keys[: len(momentum_keys) // 2 + 1]}
    inputs = {f"S{i}": _stock(level=1.0 + i) for i in range(10)}
    inputs["THIN"] = _stock(level=3.0, **gone)
    out = sa_quant_all(inputs)
    assert out["THIN"]["grades"]["momentum"] is None
    assert out["THIN"]["rating"] is not None  # 4 of 5 factors still rate it


def test_uncovered_or_sectorless_names_are_not_rated():
    inputs = {f"S{i}": _stock(level=1.0 + i) for i in range(10)}
    inputs["NOCOV"] = _stock(level=50.0, covered=False)
    inputs["NOSEC"] = _stock(sector=None, level=50.0)
    out = sa_quant_all(inputs)
    assert out["NOCOV"]["rating"] is None and out["NOCOV"]["score"] is None
    assert out["NOSEC"]["rating"] is None and out["NOSEC"]["grades"]["value"] is None
    # Unrated names are not in the peer set the others are bucketed against.
    assert out["S9"]["score"] == 100.0


def test_one_bad_grade_caps_at_hold_and_frees_the_slot():
    # STAR is the best name on every factor but Growth, where it is the
    # worst (grade F). Its composite still ranks in the Buy band, but the cap
    # rule holds it at Hold -- and the Buy bucket keeps its size, the slot
    # going to the next qualified name.
    def ratings(inputs):
        out = sa_quant_all(inputs)
        counts = {}
        for r in out.values():
            counts[r["rating"]] = counts.get(r["rating"], 0) + 1
        return out, counts

    base = {f"S{i:02d}": _stock(level=1.0 + i) for i in range(40)}
    _, before = ratings({**base, "PLAIN": _stock(level=34.5)})
    out, after = ratings({**base, "STAR": _stock(level=1000.0, factor_levels={"growth": 0.5})})
    assert out["STAR"]["grades"]["growth"] == "F"
    assert out["STAR"]["capped"] is True
    assert out["STAR"]["rating"] == "Hold", out["STAR"]
    assert 80.1 <= out["STAR"]["score"] < 90.5, out["STAR"]  # Buy band before the cap
    assert after["Strong Buy"] == before["Strong Buy"] and after["Buy"] == before["Buy"], (before, after)
    assert out["S39"]["capped"] is False and out["S39"]["rating"] == "Strong Buy"


def test_value_cap_needs_d_minus_or_worse():
    # 13 equal grade bands: band index = floor((1 - p) * 13), so D (index 10)
    # is 0.1538 < p <= 0.2308 and D- / F are below that. With 41 names in the
    # sector a factor percentile is rank / 40.
    def run(value_level):
        inputs = {f"S{i:02d}": _stock(level=1.0 + i) for i in range(40)}
        inputs["X"] = _stock(level=1000.0, factor_levels={"value": value_level})
        return sa_quant_all(inputs)["X"]

    at_d = run(7.5)  # 7 peers below -> p = 0.175 -> D: Value at D does not cap
    assert at_d["grades"]["value"] == "D", at_d
    assert at_d["capped"] is False, at_d
    at_f = run(1.5)  # 1 peer below -> p = 0.025 -> F: caps
    assert at_f["grades"]["value"] == "F", at_f
    assert at_f["capped"] is True and at_f["rating"] == "Hold", at_f


def test_growth_cap_reaches_d_plus():
    # Growth, Momentum and Revisions cap from D+ (index 9: 0.2308 < p <= 0.3077).
    inputs = {f"S{i:02d}": _stock(level=1.0 + i) for i in range(40)}
    inputs["X"] = _stock(level=1000.0, factor_levels={"growth": 11.5})  # 11 below -> p = 0.275
    x = sa_quant_all(inputs)["X"]
    assert x["grades"]["growth"] == "D+", x
    assert x["capped"] is True and x["rating"] == "Hold", x


def test_ratings_match_the_frontend_type():
    # web/src/types.ts SaRating is the frontend's copy of RATINGS; alphapicks
    # reads its Strong Buy / Hold / Sell names from here.
    import re
    from saquant import RATINGS
    ts = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "web", "src", "types.ts"), encoding="utf-8").read()
    union = re.search(r"export type SaRating = ([^\n]+)", ts).group(1)
    assert set(re.findall(r"'([^']+)'", union)) == set(RATINGS), union


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for t in tests:
        t()
    print(f"OK: {len(tests)} saquant tests passed")
