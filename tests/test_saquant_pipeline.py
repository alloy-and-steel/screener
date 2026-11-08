"""
SA-style quant -- the pipeline side (stock_screener.py)
=======================================================
Pins how the screener turns already-fetched yfinance data into saquant.py's
metrics, and how write_json carries the Alpha Picks emulator ledger: no
metric is invented from a missing or meaningless input, and a run whose
ratings mostly failed leaves the emulator untouched. Expected values are
hand-computed.

HOW TO RUN:
    python tests/test_saquant_pipeline.py
"""

import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("FRED_API_KEY", "test")
os.environ.setdefault("FINNHUB_API_KEY", "test")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import pandas as pd  # noqa: E402

import alphapicks  # noqa: E402
import stock_screener as screener  # noqa: E402


def frame(rows: dict) -> pd.DataFrame:
    """A yfinance-shaped statement: index = line items, columns newest first."""
    return pd.DataFrame(rows, index=["2025", "2024", "2023"]).T


def fund(**overrides) -> dict:
    base = {
        "income_stmt_df": frame({
            "Total Revenue": [200.0, 160.0, 150.0],
            "Gross Profit": [100.0, 70.0, 60.0],
            "EBIT": [40.0, 30.0, 20.0],
            "EBITDA": [50.0, 40.0, 30.0],
            "Net Income": [20.0, 15.0, 10.0],
        }),
        "balance_sheet_df": frame({"Total Assets": [400.0, 380.0, 360.0]}),
        "cashflow_df": frame({
            "Operating Cash Flow": [60.0, 50.0, 40.0],
            "Free Cash Flow": [30.0, 20.0, 10.0],
        }),
        "equity": 100.0,
        "az_market_cap": 1000.0,
        "az_debt": 100.0,
        "az_cash": 50.0,
        "price_currency": "USD",
        "financial_currency": "USD",
        "closes": [float(i) for i in range(1, 252)],  # 251 closes: 1 .. 251
    }
    base.update(overrides)
    return base


def test_metrics_from_statements():
    m = screener._saquant_inputs(fund(), 1.5)
    # EV = 1000 + 100 - 50 = 1050
    assert m["evEbit"] == 1050.0 / 40.0 and m["evEbitda"] == 1050.0 / 50.0
    assert m["evSales"] == 1050.0 / 200.0 and m["ps"] == 1000.0 / 200.0 and m["pcf"] == 1000.0 / 60.0
    assert m["grossMargin"] == 0.5 and m["ebitMargin"] == 0.2 and m["netMargin"] == 0.1 and m["fcfMargin"] == 0.15
    assert m["roe"] == 0.2 and m["roa"] == 0.05 and m["assetTurnover"] == 0.5
    assert m["ebitdaYoY"] == 25.0 and m["ocfYoY"] == 20.0 and m["fcfYoY"] == 50.0
    assert m["divYield"] == 1.5


def test_momentum_windows_without_skip_month():
    m = screener._momentum_returns([float(i) for i in range(1, 252)])
    # last = 251; 63 back = 188, 126 back = 125, 189 back = 62, first = 1
    assert abs(m["ret3m"] - (251 / 188 - 1) * 100) < 1e-9
    assert abs(m["ret6m"] - (251 / 125 - 1) * 100) < 1e-9
    assert abs(m["ret9m"] - (251 / 62 - 1) * 100) < 1e-9
    assert abs(m["ret12m"] - 25000.0) < 1e-9
    short = screener._momentum_returns([10.0] * 100)
    assert short["ret3m"] == 0.0 and short["ret6m"] is None and short["ret12m"] is None


def test_meaningless_inputs_stay_none():
    loss_base = fund(cashflow_df=frame({"Operating Cash Flow": [60.0, -5.0, 1.0], "Free Cash Flow": [30.0, 0.0, 1.0]}))
    m = screener._saquant_inputs(loss_base, None)
    assert m["ocfYoY"] is None and m["fcfYoY"] is None  # growth off a loss / zero base
    assert m["divYield"] is None  # missing stays missing
    no_debt_figure = screener._saquant_inputs(fund(az_debt=None), 0.0)
    assert no_debt_figure["evEbit"] is None and no_debt_figure["ps"] == 5.0
    adr = screener._saquant_inputs(fund(financial_currency="TWD"), 0.0)
    assert adr["evEbit"] is None and adr["ps"] is None and adr["pcf"] is None
    assert adr["grossMargin"] == 0.5  # same-currency ratios survive
    neg_equity = screener._saquant_inputs(fund(equity=-10.0), 0.0)
    assert neg_equity["roe"] is None


def test_loss_maker_multiple_is_negative_not_dropped():
    loss = fund(income_stmt_df=frame({"Total Revenue": [200.0, 160.0, 150.0], "EBIT": [-40.0, 30.0, 20.0]}))
    m = screener._saquant_inputs(loss, 0.0)
    assert m["evEbit"] == 1050.0 / -40.0  # saquant ranks a non-positive multiple worst


def _rows(n_rated):
    rows = []
    for i in range(120):
        rating = "Hold" if i < n_rated else None
        rows.append({
            "Ticker": f"T{i}", "Price": 50.0, "MarketCap_B": 5.0, "Industry": "Software",
            "Lynch_Lynch_Status": "Buy", "Error": None,
            "saQuant": {"rating": rating, "score": 50.0},
        })
    return pd.DataFrame(rows)


def _write(tmp, df):
    saved = (screener.OUTPUT_PATH, screener.STATS_PATH, screener.SELECTIONS_PATH, screener.ALPHAPICKS_PATH,
             screener._validate_output_dataframe, screener._compute_stats)
    screener.OUTPUT_PATH = tmp / "results.json"
    screener.STATS_PATH = tmp / "stats.json"
    screener.SELECTIONS_PATH = tmp / "picks.json"
    screener.ALPHAPICKS_PATH = tmp / "alphapicks.json"
    screener._validate_output_dataframe = lambda _df: {"valid_rows": 0, "total_rows": 0, "valid_fraction": 1.0, "finnhub_fraction": 1.0, "dcf_rows": 0, "wealthmatica_rows": 0}
    screener._compute_stats = lambda _df: {}
    try:
        screener.write_json(df, 500.0)
    finally:
        (screener.OUTPUT_PATH, screener.STATS_PATH, screener.SELECTIONS_PATH, screener.ALPHAPICKS_PATH,
         screener._validate_output_dataframe, screener._compute_stats) = saved


def test_write_json_advances_the_emulator():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        _write(tmp, _rows(120))
        led = json.loads((tmp / "alphapicks.json").read_text())
        out = json.loads((tmp / "results.json").read_text())
        assert led["updated_at"] == out["generated_at"] and len(led["streaks"]) == 120
        assert out["alphaPicks"]["picks"] == 0 and out["alphaPicks"]["startedAt"] == out["generated_at"]
        t0 = next(r for r in out["rows"] if r["Ticker"] == "T0")
        assert t0[alphapicks.ROW_FIELD]["streak"]["rating"] == "Hold"


def test_write_json_holds_the_emulator_on_a_ratings_outage():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        _write(tmp, _rows(120))
        first = json.loads((tmp / "alphapicks.json").read_text())
        # Both runs can land in the same second; the selection ledger (not
        # under test here) would refuse the second as not newer.
        (tmp / "picks.json").unlink()
        _write(tmp, _rows(screener.MIN_SAQUANT_ROWS - 1))
        second = json.loads((tmp / "alphapicks.json").read_text())
        assert second == first  # not advanced: every streak survives


def test_write_json_refuses_an_unreadable_emulator_ledger():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        (tmp / "alphapicks.json").write_text('{"version": 999}')
        try:
            _write(tmp, _rows(120))
        except SystemExit as exc:
            assert exc.code == 1 and not (tmp / "results.json").exists()
            return
        raise AssertionError("write_json published over an unreadable emulator ledger")


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for t in tests:
        t()
    print(f"OK: {len(tests)} saquant pipeline tests passed")
