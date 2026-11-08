"""
Alpha Picks emulator ledger (alphapicks.py)
===========================================
Pins the published Alpha Picks rules (docs/research/seeking-alpha-quant.md
section 2) as this forward test applies them to the SA-style rating:
75 business days at Strong Buy, price > $10, market cap > $500M, no REIT, no
repeat within a year, one pick per half-month slot, exit on Sell / Strong
Sell or after more than 180 days at Hold (winners exempt), trim above 15% of
the portfolio back to 10%, and a same-dollars SPY benchmark. Expected values
are worked out by hand.

HOW TO RUN:
    python tests/test_alphapicks.py
"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import alphapicks as ap  # noqa: E402


def row(t, rating="Strong Buy", score=95.0, price=50.0, cap_b=10.0, industry="Software", **extra):
    r = {"Ticker": t, "Price": price, "MarketCap_B": cap_b, "Industry": industry, "saQuant": {"rating": rating, "score": score}}
    r.update(extra)
    return r


def run(ledger, day, rows, spy=500.0):
    return ap.update_ledger(ledger, rows, f"{day}T11:30:00Z", spy)


def seeded(rows, since="2026-01-02"):
    """A ledger whose streaks for `rows` began on `since`."""
    led = ap.empty_ledger()
    return run(led, since, rows)


def test_streak_keeps_start_resets_on_change_and_drops_when_unrated():
    led = run(ap.empty_ledger(), "2026-01-05", [row("A"), row("B"), row("C")])
    led = run(led, "2026-01-06", [row("A"), row("B", rating="Hold"), row("C", rating=None)])
    assert led["streaks"]["A"] == {"rating": "Strong Buy", "since": "2026-01-05"}
    assert led["streaks"]["B"] == {"rating": "Hold", "since": "2026-01-06"}
    assert "C" not in led["streaks"]


def test_no_pick_before_75_business_days():
    # 2026-01-02 (Fri) + 74 business days = 2026-04-16; +75 = 2026-04-17.
    led = seeded([row("A")], since="2026-01-02")
    led = run(led, "2026-04-16", [row("A")])
    assert led["open"] == [], led["open"]
    led = run(led, "2026-04-17", [row("A")])
    assert [p["ticker"] for p in led["open"]] == ["A"]


def test_filters_price_cap_reit_cooldown():
    rows = [
        row("CHEAP", price=9.99),
        row("SMALL", cap_b=0.4),
        row("REIT", industry="REIT - Retail"),
        row("OK", score=90.0),
    ]
    led = seeded(rows)
    led = run(led, "2026-06-01", rows)
    assert [p["ticker"] for p in led["open"]] == ["OK"]


def test_one_pick_per_slot_highest_score_first():
    rows = [row("LOW", score=91.0), row("HIGH", score=99.0), row("MID", score=95.0)]
    led = seeded(rows)
    led = run(led, "2026-06-01", rows)  # slot 2026-06-a
    led = run(led, "2026-06-02", rows)  # same slot: nothing new
    assert [p["ticker"] for p in led["open"]] == ["HIGH"]
    led = run(led, "2026-06-15", rows)  # slot 2026-06-b
    assert [p["ticker"] for p in led["open"]] == ["HIGH", "MID"]
    assert led["slots"] == ["2026-06-a", "2026-06-b"]


def test_repick_needs_a_year():
    rows = [row("A")]
    led = seeded(rows)
    led = run(led, "2026-06-01", rows)
    led = run(led, "2026-06-02", [row("A", rating="Sell")])  # exits
    led = run(led, "2026-06-03", rows)  # streak restarts today
    assert led["closed"][0]["ticker"] == "A" and led["open"] == []
    assert led["last_picked"]["A"] == "2026-06-01"
    # Strong Buy again long enough, but within 365 days of the last pick.
    led = run(led, "2026-11-02", rows)
    assert led["open"] == []


def test_entry_and_sell_exit_with_spy_lot():
    rows = [row("A", price=40.0)]
    led = seeded(rows)
    led = run(led, "2026-06-01", rows, spy=500.0)
    pos = led["open"][0]
    assert pos["cost"] == ap.PICK_DOLLARS and pos["shares"] == ap.PICK_DOLLARS / 40.0
    assert pos["spy_shares"] == ap.PICK_DOLLARS / 500.0
    led = run(led, "2026-06-02", [row("A", rating="Strong Sell", price=50.0)], spy=550.0)
    c = led["closed"][0]
    assert c["reason"] == "sell" and c["exit_price"] == 50.0 and c["proceeds"] == 1250.0
    assert c["spy_proceeds"] == 1100.0


def test_hold_over_180_days_exits_but_winner_stays():
    rows = [row("A", price=40.0), row("W", price=40.0, score=90.0)]
    led = seeded(rows)
    led = run(led, "2026-06-01", rows)  # A
    led = run(led, "2026-06-15", rows)  # W
    hold = [row("A", rating="Hold", price=41.0), row("W", rating="Hold", price=80.0, score=90.0)]
    led = run(led, "2026-07-01", hold)  # Hold since 07-01
    led = run(led, "2026-12-28", hold)  # 180 days: not yet
    assert {p["ticker"] for p in led["open"]} == {"A", "W"}
    led = run(led, "2026-12-29", hold)  # 181 days: A exits, W (2x) is a winner
    assert {p["ticker"] for p in led["open"]} == {"W"}
    assert led["closed"][0]["ticker"] == "A" and led["closed"][0]["reason"] == "hold180"


def test_trim_above_15pct_back_to_10pct():
    # Ten picks at $1,000; one runs to $3,000 (3000 / 12000 = 25% > 15%).
    rows = [row(f"S{i}", score=99.0 - i) for i in range(10)]
    led = seeded(rows, since="2025-01-02")
    days = ["2025-06-02", "2025-06-16", "2025-07-01", "2025-07-15", "2025-08-01",
            "2025-08-15", "2025-09-02", "2025-09-15", "2025-10-01", "2025-10-15"]
    for d in days:
        led = run(led, d, rows)
    assert len(led["open"]) == 10
    # Under ten holdings every equal-weight name is above 15%: no trims yet.
    assert led["trims"] == [], led["trims"]
    moved = [row("S0", score=99.0, price=150.0)] + rows[1:]
    led = run(led, "2025-10-16", moved)
    total = 9 * 1000.0 + 3000.0
    pos = {p["ticker"]: p for p in led["open"]}
    assert abs(pos["S0"]["shares"] * 150.0 - 0.10 * total) < 1e-6
    freed = 3000.0 - 0.10 * total
    assert abs(pos["S1"]["shares"] * 50.0 - (1000.0 + freed / 9)) < 1e-6
    assert [t["ticker"] for t in led["trims"]] == ["S0"]


def test_summary_returns_against_spy():
    rows = [row("A", price=40.0)]
    led = seeded(rows)
    led = run(led, "2026-06-01", rows, spy=500.0)
    s = ap.summary(led, [row("A", price=60.0)], spy_price=550.0)
    assert s["picks"] == 1 and s["open"] == 1 and s["invested"] == 1000.0
    assert abs(s["returnPct"] - 50.0) < 1e-9 and abs(s["spyReturnPct"] - 10.0) < 1e-9


def test_annotate_rows():
    rows = [row("A", price=40.0), row("B", rating="Hold")]
    led = seeded(rows)
    led = run(led, "2026-06-01", rows)
    out = [row("A", price=44.0), row("B", rating="Hold"), row("Z")]
    ap.annotate_rows(out, led, "2026-06-01T11:30:00Z")
    assert out[0][ap.ROW_FIELD]["position"]["at"] == "2026-06-01"
    assert out[0][ap.ROW_FIELD]["streak"]["since"] == "2026-01-02"
    assert out[1][ap.ROW_FIELD]["position"] is None
    assert out[2][ap.ROW_FIELD] is None


def test_out_of_order_run_and_bad_file_raise():
    led = run(ap.empty_ledger(), "2026-06-02", [row("A")])
    try:
        run(led, "2026-06-01", [row("A")])
        raise AssertionError("an older run must be refused")
    except ValueError:
        pass
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "alphapicks.json"
        assert ap.load_ledger(p) is None
        p.write_text('{"version": 999}', encoding="utf-8")
        try:
            ap.load_ledger(p)
            raise AssertionError("a wrong-version ledger must be refused")
        except ValueError:
            pass
        ap.save_ledger(p, led)
        assert ap.load_ledger(p) == led


def test_missing_spy_price_defers_the_pick():
    rows = [row("A")]
    led = seeded(rows)
    led = run(led, "2026-06-01", rows, spy=None)
    assert led["open"] == [] and led["slots"] == []
    led = run(led, "2026-06-02", rows, spy=500.0)
    assert [p["ticker"] for p in led["open"]] == ["A"]


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for t in tests:
        t()
    print(f"OK: {len(tests)} alphapicks tests passed")
