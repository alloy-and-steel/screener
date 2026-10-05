"""
Selection ledger
================
Pins how selections.py records the price a stock had when the screener first
PICKED it at each pass level -- exactly 1, 2, 3, or all 4 of the four
screens. Every expectation is hand-derived from the rules below, not recorded
from a run.

RULES
  passes     = how many of: Azqato tier S+/S/A, Lynch Strong Buy/Buy, Graham
               Deep Buy/Buy, Wealthmatica pass (same gates as web/src/score.ts);
               an error row is 0
  pick N     = the run and price of the first run the stock passed EXACTLY N
               screens (N = 1..4); written once, never overwritten, so a
               stock that jumps from 0 to 3 has a pick 3 and no pick 1 or 2
  a run older than, or equal to, the ledger's last run is refused, so a replay
  can't stamp an old price as a later run's
  a ledger of any other version is refused rather than started over

HOW TO RUN:
    python tests/test_selections.py

No pytest required -- uses only stdlib assert.
"""

import json
import os
import re
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("FRED_API_KEY", "test")
os.environ.setdefault("FINNHUB_API_KEY", "test")

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

import pandas as pd  # noqa: E402

import selections  # noqa: E402
import stock_screener as screener  # noqa: E402
from selections import annotate_rows, empty_ledger, screens_passed, update_ledger  # noqa: E402

D1, D2, D3, D4 = "2026-08-20T11:37:00Z", "2026-08-21T11:40:00Z", "2026-08-24T11:35:00Z", "2026-08-25T11:31:00Z"


def row(t, price, tier=None, lynch=None, graham=None, wm=None, error=None):
    return {
        "Ticker": t,
        "Price": price,
        "azqato": {"tier": tier} if tier is not None else None,
        "Lynch_Lynch_Status": lynch,
        "Graham_Graham_Status": graham,
        "wealthmatica": {"pass": wm},
        "Error": error,
    }


FOUR = dict(tier="s", lynch="Buy", graham="Buy", wm=True)
THREE = dict(tier="s", lynch="Buy", graham="Buy")
TWO = dict(tier="a", lynch="Buy")
ONE = dict(tier="b", lynch="Buy")
ZERO = dict(tier="c", lynch="Hold", graham="Watch")


def mark(at, price):
    return {"at": at, "price": price}


def test_screens_passed_mirrors_the_frontend_gates():
    assert screens_passed(row("X", 1, **FOUR)) == 4
    assert screens_passed(row("X", 1, tier="sp", lynch="Strong Buy", graham="Deep Buy")) == 3
    assert screens_passed(row("X", 1, tier="c", wm=True)) == 1
    assert screens_passed(row("X", 1, tier="s", wm=None)) == 1  # no Wealthmatica verdict is not a pass
    assert screens_passed({"Ticker": "X", "Price": 1, "azqato": {"tier": "a"}}) == 1  # pre-Wealthmatica row
    assert screens_passed(row("X", 1, tier="s", lynch="Hold", graham="Buy")) == 2
    assert screens_passed(row("X", 1, tier="b", lynch="Avoid", graham="Watch")) == 0
    assert screens_passed(row("X", 1)) == 0  # no azqato block, N/A valuations
    assert screens_passed(row("X", 1, error="Processing failed", **TWO)) == 0  # error rows never count


def test_a_pick_is_recorded_at_the_exact_level_passed():
    led = update_ledger(
        empty_ledger(),
        [row("AAA", 100.0, **TWO), row("BBB", 50.0, **ONE), row("CCC", 7.0, **THREE), row("DDD", 3.0, **ZERO),
         row("EEE", 9.0, **FOUR)],
        D1,
    )
    assert led["tickers"] == {
        "AAA": {"2": mark(D1, 100.0)},
        "BBB": {"1": mark(D1, 50.0)},
        "CCC": {"3": mark(D1, 7.0)},
        "EEE": {"4": mark(D1, 9.0)},
    }
    assert led["updated_at"] == D1


def test_each_level_keeps_only_its_first_pick():
    led = update_ledger(empty_ledger(), [row("AAA", 100.0, **ONE)], D1)
    led = update_ledger(led, [row("AAA", 120.0, **THREE)], D2)
    led = update_ledger(led, [row("AAA", 90.0, **ONE)], D3)  # back at 1: first pick 1 stands
    led = update_ledger(led, [row("AAA", 80.0, **TWO)], D4)
    assert led["tickers"]["AAA"] == {"1": mark(D1, 100.0), "3": mark(D2, 120.0), "2": mark(D4, 80.0)}


def test_dropping_out_or_leaving_the_universe_changes_nothing():
    led = update_ledger(empty_ledger(), [row("AAA", 100.0, **TWO)], D1)
    led = update_ledger(led, [row("AAA", 90.0, **ZERO)], D2)
    led = update_ledger(led, [row("ZZZ", 1.0)], D3)
    assert led["tickers"] == {"AAA": {"2": mark(D1, 100.0)}}


def test_an_error_row_records_no_pick():
    led = update_ledger(empty_ledger(), [row("AAA", 100.0, error="Processing failed", **TWO)], D1)
    assert led["tickers"] == {}


def test_missing_price_is_recorded_as_none_not_zero():
    led = update_ledger(empty_ledger(), [row("AAA", None, **TWO)], D1)
    assert led["tickers"]["AAA"] == {"2": mark(D1, None)}


def test_replaying_an_old_run_is_refused():
    led = update_ledger(empty_ledger(), [row("AAA", 100.0, **TWO)], D2)
    for stale in (D1, D2):
        try:
            update_ledger(led, [row("AAA", 1.0, **ONE)], stale)
        except ValueError:
            continue
        raise AssertionError(f"a run at {stale} was accepted after {D2}")


def test_input_ledger_is_not_mutated():
    led = update_ledger(empty_ledger(), [row("AAA", 100.0, **TWO)], D1)
    update_ledger(led, [row("AAA", 80.0, **ONE)], D2)
    assert led["tickers"] == {"AAA": {"2": mark(D1, 100.0)}}
    assert led["updated_at"] == D1


def test_annotate_rows_attaches_picks_and_leaves_never_picked_rows_null():
    led = update_ledger(empty_ledger(), [row("AAA", 100.0, **TWO)], D1)
    led = update_ledger(led, [row("AAA", 90.0, **ONE), row("BBB", 5.0)], D4)
    rows = [row("AAA", 90.0, **ONE), row("BBB", 5.0)]
    annotate_rows(rows, led)
    assert rows[0]["picks4"] == {"2": mark(D1, 100.0), "1": mark(D4, 90.0)}
    assert rows[1]["picks4"] is None
    assert "picks" not in rows[0]  # the 3-level field: an old cached app must not read 4-level picks


def test_gates_match_the_frontend():
    # The same pass rules live in web/src/score.ts; a drift here would
    # record selections the UI doesn't show as passing (or miss ones it does).
    ts = Path(ROOT, "web/src/score.ts").read_text(encoding="utf-8")

    def ts_set(name):
        m = re.search(name + r" = new Set(?:<\w+>)?\(\[([^\]]*)\]\)", ts)
        assert m, f"{name} not found in score.ts"
        return frozenset(re.findall(r"'([^']+)'", m.group(1)))

    assert ts_set("AZQATO_PASS_TIERS") == selections.AZQATO_PASS_TIERS
    assert ts_set("LYNCH_BUY") == selections.LYNCH_BUY
    assert ts_set("GRAHAM_BUY") == selections.GRAHAM_BUY
    # Wealthmatica's thresholds live only in wealthmatica.py; both sides read its boolean.
    assert "const wm = row.wealthmatica" in ts and "wm.pass === true" in ts


def _write_json_in(tmp, df):
    """Run the real write_json against temp paths. The publish guards'
    richer checks are stubbed: they are covered by their own tests, and this
    fixture's rows are not a full screen."""
    saved = (screener.OUTPUT_PATH, screener.STATS_PATH, screener.SELECTIONS_PATH,
             screener._validate_output_dataframe, screener._compute_stats)
    screener.OUTPUT_PATH = tmp / "results.json"
    screener.STATS_PATH = tmp / "stats.json"
    screener.SELECTIONS_PATH = tmp / "picks.json"
    screener._validate_output_dataframe = lambda _df: {"valid_rows": 0, "total_rows": 0, "valid_fraction": 1.0, "finnhub_fraction": 1.0, "dcf_rows": 0, "wealthmatica_rows": 0}
    screener._compute_stats = lambda _df: {}
    try:
        screener.write_json(df)
    finally:
        (screener.OUTPUT_PATH, screener.STATS_PATH, screener.SELECTIONS_PATH,
         screener._validate_output_dataframe, screener._compute_stats) = saved


def _screen_df():
    # 120 valued rows clear the row-count guard; AAA passes 2 screens.
    rows = [row(f"T{i}", 10.0, **ZERO) for i in range(120)]
    rows.append(row("AAA", 42.0, **TWO))
    return pd.DataFrame(rows)


def test_write_json_carries_the_ledger_forward():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        selections.save_ledger(tmp / "picks.json", update_ledger(empty_ledger(), [row("AAA", 100.0, **ONE)], D1))

        _write_json_in(tmp, _screen_df())

        out = json.loads((tmp / "results.json").read_text())
        aaa = next(r for r in out["rows"] if r["Ticker"] == "AAA")
        assert aaa["picks4"] == {"1": mark(D1, 100.0), "2": mark(out["generated_at"], 42.0)}
        assert next(r for r in out["rows"] if r["Ticker"] == "T0")["picks4"] is None
        saved = json.loads((tmp / "picks.json").read_text())
        assert saved["updated_at"] == out["generated_at"]
        assert saved["tickers"]["AAA"] == aaa["picks4"]


def test_write_json_refuses_a_ledger_it_cannot_read():
    # The version-1 ledger (one >= 2-screens entry per stock) can't be turned
    # into per-level picks, nor can a version-2 one (levels of 3 screens) into
    # levels of 4; starting over would stamp today's price everywhere.
    v1 = {"version": 1, "min_pass": 2, "updated_at": D1,
          "tickers": {"AAA": {"first": mark(D1, 1.0), "latest": mark(D1, 1.0), "selected": True}}}
    v2 = {"version": 2, "updated_at": D1, "tickers": {"AAA": {"3": mark(D1, 1.0)}}}
    for bad in ({"version": 99}, v1, v2):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            (tmp / "picks.json").write_text(json.dumps(bad))
            try:
                _write_json_in(tmp, _screen_df())
            except SystemExit as exc:
                assert exc.code == 1
                assert not (tmp / "results.json").exists()
                continue
            raise AssertionError(f"write_json published over an unreadable ledger {bad}")


def run_fixture():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"OK — {name}")
    print("OK — selection ledger fixture passed")


if __name__ == "__main__":
    run_fixture()
