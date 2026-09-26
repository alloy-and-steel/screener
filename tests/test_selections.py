"""
Selection ledger
================
Pins how selections.py records the price a stock had when the screener first
SELECTED it (passes >= 2 of the three screens), and when it last re-entered
after dropping out. Every expectation is hand-derived from the rules below,
not recorded from a run.

RULES
  selected   = at least SELECTION_MIN_PASS of: Azqato tier S+/S/A, Lynch Strong
               Buy/Buy, Graham Deep Buy/Buy (same gates as web/src/score.ts)
  first      = the run and price it was first seen selected; never overwritten
  latest     = the run and price of its most recent entry (== first until it
               drops out and comes back)
  an error row (failed fetch) leaves its entry untouched -- unknown, not out
  a run older than, or equal to, the ledger's last run is refused, so a replay
  can't masquerade as a re-entry

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


def row(t, price, tier=None, lynch=None, graham=None, error=None):
    return {
        "Ticker": t,
        "Price": price,
        "azqato": {"tier": tier} if tier is not None else None,
        "Lynch_Lynch_Status": lynch,
        "Graham_Graham_Status": graham,
        "Error": error,
    }


TWO = dict(tier="a", lynch="Buy")  # passes 2
ONE = dict(tier="b", lynch="Buy")  # passes 1


def test_screens_passed_mirrors_the_frontend_gates():
    assert screens_passed(row("X", 1, tier="sp", lynch="Strong Buy", graham="Deep Buy")) == 3
    assert screens_passed(row("X", 1, tier="s", lynch="Hold", graham="Buy")) == 2
    assert screens_passed(row("X", 1, tier="b", lynch="Avoid", graham="Watch")) == 0
    assert screens_passed(row("X", 1)) == 0  # no azqato block, N/A valuations
    assert screens_passed(row("X", 1, error="Processing failed", **TWO)) == 0  # error rows never count


def test_first_entry_records_run_and_price():
    led = update_ledger(empty_ledger(), [row("AAA", 100.0, **TWO), row("BBB", 50.0, **ONE)], D1)
    assert led["tickers"] == {
        "AAA": {"first": {"at": D1, "price": 100.0}, "latest": {"at": D1, "price": 100.0}, "selected": True}
    }
    assert led["updated_at"] == D1


def test_staying_selected_changes_nothing():
    led = update_ledger(empty_ledger(), [row("AAA", 100.0, **TWO)], D1)
    led = update_ledger(led, [row("AAA", 120.0, **TWO)], D2)
    assert led["tickers"]["AAA"]["first"] == {"at": D1, "price": 100.0}
    assert led["tickers"]["AAA"]["latest"] == {"at": D1, "price": 100.0}


def test_drop_out_then_reentry_keeps_first_and_moves_latest():
    led = update_ledger(empty_ledger(), [row("AAA", 100.0, **TWO)], D1)
    led = update_ledger(led, [row("AAA", 90.0, **ONE)], D2)
    assert led["tickers"]["AAA"]["selected"] is False
    assert led["tickers"]["AAA"]["latest"] == {"at": D1, "price": 100.0}  # untouched while out
    led = update_ledger(led, [row("AAA", 80.0, **TWO)], D3)
    assert led["tickers"]["AAA"] == {"first": {"at": D1, "price": 100.0}, "latest": {"at": D3, "price": 80.0}, "selected": True}


def test_leaving_the_universe_counts_as_dropping_out():
    led = update_ledger(empty_ledger(), [row("AAA", 100.0, **TWO)], D1)
    led = update_ledger(led, [row("ZZZ", 1.0)], D2)
    assert led["tickers"]["AAA"]["selected"] is False


def test_an_error_row_is_unknown_not_a_drop_out():
    led = update_ledger(empty_ledger(), [row("AAA", 100.0, **TWO)], D1)
    led = update_ledger(led, [row("AAA", None, error="Processing failed")], D2)
    assert led["tickers"]["AAA"]["selected"] is True
    led = update_ledger(led, [row("AAA", 130.0, **TWO)], D3)
    assert led["tickers"]["AAA"]["latest"] == {"at": D1, "price": 100.0}  # no fake re-entry


def test_missing_price_is_recorded_as_none_not_zero():
    led = update_ledger(empty_ledger(), [row("AAA", None, **TWO)], D1)
    assert led["tickers"]["AAA"]["first"] == {"at": D1, "price": None}


def test_replaying_an_old_run_is_refused():
    led = update_ledger(empty_ledger(), [row("AAA", 100.0, **TWO)], D2)
    for stale in (D1, D2):
        try:
            update_ledger(led, [row("AAA", 1.0, **TWO)], stale)
        except ValueError:
            continue
        raise AssertionError(f"a run at {stale} was accepted after {D2}")


def test_input_ledger_is_not_mutated():
    led = update_ledger(empty_ledger(), [row("AAA", 100.0, **TWO)], D1)
    update_ledger(led, [row("AAA", 80.0, **ONE)], D2)
    assert led["tickers"]["AAA"]["selected"] is True


def test_annotate_rows_attaches_history_and_leaves_never_selected_rows_null():
    led = update_ledger(empty_ledger(), [row("AAA", 100.0, **TWO)], D1)
    led = update_ledger(led, [row("AAA", 90.0, **ONE), row("BBB", 5.0)], D4)
    rows = [row("AAA", 90.0, **ONE), row("BBB", 5.0)]
    annotate_rows(rows, led)
    assert rows[0]["selection"] == {"first": {"at": D1, "price": 100.0}, "latest": {"at": D1, "price": 100.0}, "selected": False}
    assert rows[1]["selection"] is None


def test_gates_match_the_frontend():
    # The same three pass rules live in web/src/score.ts; a drift here would
    # record selections the UI doesn't show as passing (or miss ones it does).
    ts = Path(ROOT, "web/src/score.ts").read_text(encoding="utf-8")

    def ts_set(name):
        m = re.search(name + r" = new Set(?:<\w+>)?\(\[([^\]]*)\]\)", ts)
        assert m, f"{name} not found in score.ts"
        return frozenset(re.findall(r"'([^']+)'", m.group(1)))

    assert ts_set("AZQATO_PASS_TIERS") == selections.AZQATO_PASS_TIERS
    assert ts_set("LYNCH_BUY") == selections.LYNCH_BUY
    assert ts_set("GRAHAM_BUY") == selections.GRAHAM_BUY


def _write_json_in(tmp, df):
    """Run the real write_json against temp paths. The publish guards'
    richer checks are stubbed: they are covered by their own tests, and this
    fixture's rows are not a full screen."""
    saved = (screener.OUTPUT_PATH, screener.STATS_PATH, screener.SELECTIONS_PATH,
             screener._validate_output_dataframe, screener._compute_stats)
    screener.OUTPUT_PATH = tmp / "results.json"
    screener.STATS_PATH = tmp / "stats.json"
    screener.SELECTIONS_PATH = tmp / "selections.json"
    screener._validate_output_dataframe = lambda _df: {"valid_rows": 0, "total_rows": 0, "valid_fraction": 1.0, "finnhub_fraction": 1.0, "dcf_rows": 0}
    screener._compute_stats = lambda _df: {}
    try:
        screener.write_json(df)
    finally:
        (screener.OUTPUT_PATH, screener.STATS_PATH, screener.SELECTIONS_PATH,
         screener._validate_output_dataframe, screener._compute_stats) = saved


def _screen_df():
    # 120 valued rows clear the row-count guard; AAA passes 2 screens.
    rows = [row(f"T{i}", 10.0, tier="c", lynch="Hold", graham="Watch") for i in range(120)]
    rows.append(row("AAA", 42.0, **TWO))
    return pd.DataFrame(rows)


def test_write_json_carries_the_ledger_forward():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        led = update_ledger(empty_ledger(), [row("AAA", 100.0, **TWO)], D1)
        led = update_ledger(led, [row("AAA", 90.0, **ONE)], D2)  # dropped out
        selections.save_ledger(tmp / "selections.json", led)

        _write_json_in(tmp, _screen_df())

        out = json.loads((tmp / "results.json").read_text())
        aaa = next(r for r in out["rows"] if r["Ticker"] == "AAA")
        assert aaa["selection"]["first"] == {"at": D1, "price": 100.0}
        assert aaa["selection"]["latest"] == {"at": out["generated_at"], "price": 42.0}
        assert aaa["selection"]["selected"] is True
        assert next(r for r in out["rows"] if r["Ticker"] == "T0")["selection"] is None
        saved = json.loads((tmp / "selections.json").read_text())
        assert saved["updated_at"] == out["generated_at"]


def test_write_json_refuses_an_unreadable_ledger():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        (tmp / "selections.json").write_text('{"version": 99}')
        try:
            _write_json_in(tmp, _screen_df())
        except SystemExit as exc:
            assert exc.code == 1
            assert not (tmp / "results.json").exists()
            return
        raise AssertionError("write_json published over an unreadable ledger")


def run_fixture():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"OK — {name}")
    print("OK — selection ledger fixture passed")


if __name__ == "__main__":
    run_fixture()
