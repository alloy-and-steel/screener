"""Offline regression tests for the FCFF/WACC DCF stack, output validation guard, and related ports."""

import json
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

import pandas as pd

os.environ.setdefault("FRED_API_KEY", "test")
os.environ.setdefault("FINNHUB_API_KEY", "test")

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import stock_screener as screener


def _guard_frame(tickers, scores, errors, finnhub_ok=None):
    """Build a structurally valid publication-guard fixture."""
    rows = len(tickers)
    active = [score is not None and error is None for score, error in zip(scores, errors)]
    return pd.DataFrame(
        {
            "Ticker": tickers,
            "Price": [5.0] * rows,
            "OverallScore": scores,
            "Error": errors,
            "Provider_Finnhub_OK": finnhub_ok if finnhub_ok is not None else [True] * rows,
            "DCF_Intrinsic_Value": [10.0 if ok else None for ok in active],
            "DCF_Value_Low": [8.0 if ok else None for ok in active],
            "DCF_Value_High": [12.0 if ok else None for ok in active],
            "DCF_WACC_Pct": [9.0 if ok else None for ok in active],
            "DCF_Terminal_Growth_Pct": [2.0 if ok else None for ok in active],
            "DCF_Terminal_Value_Pct": [70.0 if ok else None for ok in active],
        }
    )


def test_aggregate_total_debt_is_not_double_counted():
    balance_sheet = pd.DataFrame({"2025": [100.0, 80.0, 20.0]}, index=["Total Debt", "Long Term Debt", "Current Debt"])
    assert screener._extract_total_debt(balance_sheet) == 100.0


def test_total_debt_falls_back_to_long_plus_current():
    balance_sheet = pd.DataFrame({"2025": [80.0, 20.0]}, index=["Long Term Debt", "Current Debt"])
    assert screener._extract_total_debt(balance_sheet) == 100.0


def test_base_fcff_adds_back_after_tax_interest():
    result = screener._compute_base_fcff(ocf=100.0, capex=-20.0, interest_expense=-10.0, tax_rate=0.20)
    assert abs(result - 88.0) < 1e-9


def test_screen_wacc_responds_to_beta():
    common = dict(
        risk_free_rate_pct=4.0,
        aaa_yield_pct=5.0,
        market_cap=1000.0,
        total_debt=200.0,
        prior_total_debt=200.0,
        interest_expense=10.0,
        tax_rate=0.21,
    )
    lower = screener._estimate_screen_wacc(beta=0.8, **common)
    higher = screener._estimate_screen_wacc(beta=1.4, **common)
    assert higher["wacc"] > lower["wacc"]


def test_fcff_dcf_reverse_round_trip():
    result = screener._compute_fcff_dcf(
        base_fcff=100.0, initial_growth_pct=5.0, wacc=0.09, terminal_growth_pct=2.0,
        cash=20.0, total_debt=50.0, diluted_shares=10.0, price=80.0,
    )
    assert result is not None
    implied, converged = screener._compute_fcff_reverse_dcf(
        price=result["intrinsic_value"], base_fcff=100.0, wacc=0.09, terminal_growth_pct=2.0,
        cash=20.0, total_debt=50.0, diluted_shares=10.0,
    )
    assert converged is True
    assert abs(implied - 5.0) < 0.01


def test_fcff_dcf_paired_range_brackets_base():
    result = screener._compute_fcff_dcf(
        base_fcff=100.0, initial_growth_pct=5.0, wacc=0.09, terminal_growth_pct=2.0,
        cash=20.0, total_debt=50.0, diluted_shares=10.0, price=80.0,
    )
    assert result["value_low"] < result["intrinsic_value"] < result["value_high"]


def test_fcff_dcf_stressed_equity_value_is_zero_not_missing():
    result = screener._compute_fcff_dcf(
        base_fcff=100.0, initial_growth_pct=5.0, wacc=0.09, terminal_growth_pct=2.0,
        cash=0.0, total_debt=1400.0, diluted_shares=10.0, price=10.0,
    )
    assert result is not None
    assert result["intrinsic_value"] > 0
    assert result["value_low"] == 0.0
    assert result["value_high"] > result["intrinsic_value"]


def test_more_debt_reduces_equity_value_per_share():
    low_debt, _, _ = screener._fcff_value_per_share(100.0, 5.0, 0.09, 2.0, 20.0, 20.0, 10.0)
    high_debt, _, _ = screener._fcff_value_per_share(100.0, 5.0, 0.09, 2.0, 20.0, 80.0, 10.0)
    assert high_debt < low_debt


def test_wacc_guardrail_prevents_terminal_rate_compression():
    result = screener._apply_screen_wacc_guardrail(calculated_wacc=0.0493, risk_free_rate_pct=4.62, terminal_growth_pct=3.0)
    assert result["floor_applied"] is True
    assert abs(result["wacc"] - 0.0712) < 1e-9
    assert result["wacc"] - 0.03 >= 0.04


def test_currency_mismatch_detects_unconverted_adr_financials():
    assert screener._currency_mismatch("USD", "CNY") is True
    assert screener._currency_mismatch("usd", "USD") is False
    assert screener._currency_mismatch("USD", None) is False


def test_output_guard_accepts_healthy_dataset():
    rows = 120
    frame = _guard_frame([f"T{i}" for i in range(rows)], [50.0] * 110 + [None] * 10, [None] * 110 + ["data failure"] * 10)
    result = screener._validate_output_dataframe(frame)
    assert result["valid_rows"] == 110


def test_output_guard_rejects_mass_error_rows():
    rows = 500
    frame = _guard_frame([f"T{i}" for i in range(rows)], [50.0] * 50 + [None] * 450, [None] * 50 + ["data failure"] * 450)
    try:
        screener._validate_output_dataframe(frame)
        assert False, "Expected mass-error output to be rejected"
    except ValueError as exc:
        assert "valid scored rows" in str(exc)


def test_output_guard_rejects_duplicate_tickers():
    frame = _guard_frame(["DUP"] * 120, [50.0] * 120, [None] * 120)
    try:
        screener._validate_output_dataframe(frame)
        assert False, "Expected duplicate output to be rejected"
    except ValueError as exc:
        assert "duplicate ticker" in str(exc)


def test_output_guard_rejects_blank_tickers():
    frame = _guard_frame([None] + [f"T{i}" for i in range(119)], [50.0] * 120, [None] * 120)
    try:
        screener._validate_output_dataframe(frame)
        assert False, "Expected blank tickers to be rejected"
    except ValueError as exc:
        assert "blank ticker" in str(exc)


def test_output_guard_rejects_provider_wide_degradation():
    frame = _guard_frame([f"T{i}" for i in range(120)], [50.0] * 120, [None] * 120, finnhub_ok=[False] * 120)
    try:
        screener._validate_output_dataframe(frame)
        assert False, "Expected a provider-wide Finnhub outage to be rejected"
    except ValueError as exc:
        assert "valid Finnhub data" in str(exc)


def test_output_guard_rejects_misordered_dcf_range():
    frame = _guard_frame([f"T{i}" for i in range(120)], [50.0] * 120, [None] * 120)
    frame.loc[0, "DCF_Value_Low"] = 11.0
    try:
        screener._validate_output_dataframe(frame)
        assert False, "Expected a misordered DCF range to be rejected"
    except ValueError as exc:
        assert "misordered ranges" in str(exc)


def test_nasdaq_fetch_uses_component_list_page():
    """Regression test for the Wikipedia URL/table-column fix that unblocked this merge."""
    original = screener._wiki_tables
    seen = []

    def fake_tables(url):
        seen.append(url)
        return [pd.DataFrame({"Ticker": ["AAPL", "BRK.B"]})]

    try:
        screener._wiki_tables = fake_tables
        members = screener.fetch_nasdaq100()
    finally:
        screener._wiki_tables = original

    assert seen == ["https://en.wikipedia.org/wiki/List_of_NASDAQ-100_companies"]
    assert members == {"AAPL", "BRK-B"}


def test_dow_fetch_uses_component_list_page():
    """
    The main "Dow Jones Industrial Average" article dropped its components
    table (only a navbox survives), so the old URL matched nothing and every
    run silently fell back to the last published roster. Pin the page that
    actually carries the 30 symbols.
    """
    original = screener._wiki_tables
    seen = []

    def fake_tables(url):
        seen.append(url)
        return [pd.DataFrame({"Year": [1896]}), pd.DataFrame({"Symbol": ["MSFT", "BRK.B"]})]

    try:
        screener._wiki_tables = fake_tables
        members = screener.fetch_dow30()
    finally:
        screener._wiki_tables = original

    assert seen == ["https://en.wikipedia.org/wiki/List_of_Dow_Jones_Industrial_Average_companies"]
    assert members == {"MSFT", "BRK-B"}


def _vanguard_payload(entities):
    return type("R", (), {"status_code": 200, "headers": {"content-type": "application/json"}, "raise_for_status": lambda self: None, "json": lambda self: {"fund": {"entity": entities}}})()


def _holding(ticker, weight):
    return {"ticker": ticker, "longName": f"{ticker} Inc.", "percentWeight": weight}


def test_vanguard_pool_takes_top_100_by_weight_and_drops_dual_classes():
    """
    azqato's Growth/Value/Dividend pools are the top 100 holdings of VUG/VTV/VIG
    by portfolio weight, with a duplicate share class dropped only when its kept
    sibling is present. Mirrors his update_etf_constituents.py.
    """
    # 130 synthetic holdings in descending weight, plus GOOG right behind GOOGL.
    entities = [_holding(f"T{i:03d}", 500.0 - i) for i in range(130)]
    entities.insert(3, _holding("GOOGL", 497.5))
    entities.insert(4, _holding("GOOG", 497.4))
    # A dual class whose sibling is NOT in the fund must be kept, not dropped.
    entities.insert(5, _holding("HEI.A", 497.3))

    original = screener._HTTP_GET
    try:
        screener._HTTP_GET = lambda url, **kw: _vanguard_payload(entities)
        members = screener.fetch_growth100()
    finally:
        screener._HTTP_GET = original

    assert len(members) == 100
    assert "GOOGL" in members and "GOOG" not in members, "dual class should collapse to the kept sibling"
    assert "HEI-A" in members, "a dual class with no sibling in the fund stays"
    assert "T000" in members and "T099" not in members, "the cut must follow weight order, not ticker order"


def test_vanguard_pool_rejects_a_truncated_holdings_response():
    """A short response must abort the pool, never quietly publish a small one."""
    original = screener._HTTP_GET
    try:
        screener._HTTP_GET = lambda url, **kw: _vanguard_payload([_holding(f"T{i:03d}", 100.0 - i) for i in range(40)])
        try:
            screener.fetch_value100()
        except ValueError as exc:
            assert "unexpected raw holdings count" in str(exc), exc
        else:
            raise AssertionError("a 40-entity response should have aborted the pool")
    finally:
        screener._HTTP_GET = original


def test_every_pool_is_scored_as_its_own_cross_section():
    """
    The Azqato model is relative, so each pool has to be re-scored on its own —
    that is what makes a name comparable to azqato's per-universe views. Pin the
    pool list and the membership parser that drives it.
    """
    assert screener.INDEX_NAMES == ("S&P500", "Dow30", "Nasdaq100", "Growth100", "Value100", "Dividend100")
    assert len(screener.INDEX_FETCHERS) == len(screener.INDEX_NAMES)
    assert screener._row_indexes("S&P500, Nasdaq100") == {"S&P500", "Nasdaq100"}
    assert screener._row_indexes("S&P500,Dow30 ,  Nasdaq100") == {"S&P500", "Dow30", "Nasdaq100"}
    assert screener._row_indexes("") == set()
    assert screener._row_indexes(None) == set()


# A fully-populated get_combined_data payload for a loss-making name. The
# process_ticker tests below each copy it and override only what they exercise.
_SYNTHETIC_LOSS_MAKER = {
        "price": 10.0,
        "finnhub_ok": True,
        "market_cap_b": 5.0,
        "annual_eps": [-3.0, -2.0, -1.0],
        "annual_dividends": [],
        "ttm_eps": -1.0,
        "ttm_dps": 0.0,
        "growth_pct": 5.0,
        "current_ratio": 1.5,
        "book_value_ps": 4.0,
        "pb_ratio": 2.5,
        "long_term_debt": 10.0,
        "current_assets": 20.0,
        "current_liabilities": 15.0,
        "closes": [10.0] * 20,
        "high_52w": 12.0,
        "low_52w": 8.0,
        "az_rev_ttm": 5.0,
        "az_rev_fwd": 5.0,
        "az_eps_ttm": -10.0,
        "az_eps_fwd": -10.0,
        "az_pe_fwd": -5.0,
        "az_peg_fwd": None,
        "az_cash": 50.0,
        "az_debt": 100.0,
        "az_market_cap": 1000.0,
        "sector": "Industrials",
        "beta": 1.0,
        "price_currency": "USD",
        "financial_currency": "USD",
        "dist_52w_high": None,
        "dist_52w_low": None,
        "dist_5y_low": None,
        "weeks_since_52w_low": None,
        "weeks_since_5y_low": None,
        "short_history": False,
        "ocf": -100.0,
        "capex": -20.0,
        "interest_expense": -5.0,
        "tax_rate": 0.21,
        "total_debt": 100.0,
        "prior_total_debt": 100.0,
        "cash": 20.0,
        "equity": 40.0,
        "shares_now": 500.0,
        "shares_prev": 500.0,
        "diluted_shares": 500.0,
        "debt_equity": 2.5,
        "fcf_per_share": -0.5,
        "fcf_yield": -2.0,
        "ev_ebit": None,
        "earnings_yield": None,
        "roic": -5.0,
        "shareholder_yield": 0.0,
        "shareholder_yield_partial": True,
        "income_stmt_df": None,
        "balance_sheet_df": None,
        "cashflow_df": None,
}


def test_negative_eps_is_retained_as_worst_discount_not_a_fetch_error():
    """
    A ticker with usable price but non-positive EPS must stay visible: Error stays
    None, Lynch/Graham are marked N/A (fork's existing N/A contract, unchanged),
    but OverallScore is still computable because the WORST_DISCOUNT sentinel feeds
    the Value pillar rather than the row being silently dropped.
    """
    original = screener.get_combined_data
    synthetic = dict(_SYNTHETIC_LOSS_MAKER)

    try:
        screener.get_combined_data = lambda _ticker: synthetic
        row = screener.process_ticker("LOSS", aaa_yield=5.0, risk_free_rate=4.0)
    finally:
        screener.get_combined_data = original

    assert row.get("Error") is None
    assert row.get("EPS_TTM") is None, "usable_eps=False must not set EPS_TTM (fork's existing N/A contract)"
    assert row["Lynch_Lynch_Status"] == "N/A"
    assert row["Graham_Graham_Status"] == "N/A"
    assert row["OverallScore"] is not None, "WORST_DISCOUNT routing must still let OverallScore be computed"
    assert row["score_value"] is not None
    assert row["Valuation_Input_Warning"] == "Non-positive EPS", (
        f"the N/A must carry its reason, got {row['Valuation_Input_Warning']!r}"
    )


def test_valuation_warning_lists_every_applicable_reason():
    """
    A row that is both loss-making AND missing growth records BOTH reasons --
    not just the first one -- and a valuable row records none.
    """
    original = screener.get_combined_data
    base = dict(_SYNTHETIC_LOSS_MAKER)
    base["growth_pct"] = None
    base["annual_eps"] = [-3.0, -2.0, -1.0]  # no positive base -> CAGR uncomputable too

    healthy = dict(_SYNTHETIC_LOSS_MAKER)
    healthy["ttm_eps"] = 1.0
    healthy["annual_eps"] = [0.5, 0.7, 0.9]
    healthy["growth_pct"] = 8.0

    try:
        screener.get_combined_data = lambda _ticker: base
        both = screener.process_ticker("BOTH", aaa_yield=5.0, risk_free_rate=4.0)
        screener.get_combined_data = lambda _ticker: healthy
        ok = screener.process_ticker("OKAY", aaa_yield=5.0, risk_free_rate=4.0)
    finally:
        screener.get_combined_data = original

    assert both["Valuation_Input_Warning"] == "Non-positive EPS; Growth unavailable"
    assert ok["Valuation_Input_Warning"] is None, "a row that could be valued carries no warning"
    assert ok["Lynch_Lynch_Status"] != "N/A"


def test_trap_reasons_are_explicit_and_warning_only():
    reasons = screener._trap_reasons(
        debt_equity=screener.TRAP_MAX_DE + 1.0,
        current_ratio=screener.TRAP_MIN_CR - 0.1,
        eps_stability=0,
        fcf_per_share=-1.0,
    )
    assert reasons == ["High leverage", "Weak liquidity", "Unstable earnings", "Negative FCF"]


def test_first_weekday_snapshot_logic_handles_weekends():
    assert screener._is_first_weekday_of_month(date(2026, 7, 1)) is True
    assert screener._is_first_weekday_of_month(date(2026, 7, 2)) is False
    assert screener._is_first_weekday_of_month(date(2026, 8, 1)) is False
    assert screener._is_first_weekday_of_month(date(2026, 8, 3)) is True


def test_reverse_fcff_is_pure_without_api_credentials():
    implied, converged = screener._compute_fcff_reverse_dcf(
        price=80.0, base_fcff=100.0, wacc=0.09, terminal_growth_pct=2.0,
        cash=20.0, total_debt=50.0, diluted_shares=10.0,
    )
    assert implied is not None
    assert converged is True


def test_finnhub_preflight_rejects_empty_metric_bundle():
    original = screener.get_finnhub_metrics
    try:
        screener.get_finnhub_metrics = lambda _ticker: {}
        try:
            screener._validate_finnhub_access()
            assert False, "Expected an empty Finnhub preflight to stop the run"
        except RuntimeError as exc:
            assert "preflight returned no metrics" in str(exc)
    finally:
        screener.get_finnhub_metrics = original


def test_safe_float_rejects_non_numeric_and_non_finite():
    """
    Guards the helper directly: a broken `except` clause here is a module-level
    SyntaxError that takes the entire screener down, and every other test in the
    suite fails with the same opaque message rather than pointing at this line.
    """
    assert screener._safe_float("12.5") == 12.5
    assert screener._safe_float(0) == 0.0        # zero is a value, not a miss
    assert screener._safe_float(None) is None    # TypeError branch
    assert screener._safe_float("n/a") is None   # ValueError branch
    assert screener._safe_float(float("nan")) is None
    assert screener._safe_float(float("inf")) is None


def _seed_published_results(rows):
    """Point OUTPUT_PATH at a temp results.json holding `rows`. Returns the dir."""
    tmp = tempfile.TemporaryDirectory()
    path = Path(tmp.name) / "results.json"
    path.write_text(json.dumps({"generated_at": "2026-01-01T00:00:00Z", "rows": rows}))
    screener.OUTPUT_PATH = path
    return tmp


def test_universe_falls_back_to_last_published_members():
    """
    A Wikipedia outage must not kill the run. Membership changes slowly, so the
    last published roster is a far better outcome than no screen -- and the stale
    index is logged, never silent.
    """
    original_path = screener.OUTPUT_PATH
    tmp = _seed_published_results([
        {"Ticker": "AAPL", "Indexes": "S&P500, Nasdaq100"},
        {"Ticker": "MSFT", "Indexes": "S&P500, Dow30, Nasdaq100"},
        {"Ticker": "XOM", "Indexes": "S&P500"},
        {"Ticker": "", "Indexes": "S&P500"},          # blank tickers dropped
    ])
    try:
        def _down():
            raise RuntimeError("Wikipedia 503")

        assert screener._fetch_index_with_fallback("S&P500", _down) == {"AAPL", "MSFT", "XOM"}
        assert screener._fetch_index_with_fallback("Dow30", _down) == {"MSFT"}
        assert screener._fetch_index_with_fallback("Nasdaq100", _down) == {"AAPL", "MSFT"}
        # A live fetch that works is passed through untouched.
        assert screener._fetch_index_with_fallback("Dow30", lambda: {"KO"}) == {"KO"}
    finally:
        screener.OUTPUT_PATH = original_path
        tmp.cleanup()


def test_universe_reraises_when_no_cached_members_exist():
    """
    No seeded dataset (bootstrap run, or an index absent from it) means no
    fallback: the fetch error propagates rather than screening a partial universe.
    """
    original_path = screener.OUTPUT_PATH
    tmp = _seed_published_results([{"Ticker": "AAPL", "Indexes": "S&P500"}])
    try:
        def _down():
            raise RuntimeError("Wikipedia 503")

        # Index present in the seed but with zero members -> no silent partial run.
        try:
            screener._fetch_index_with_fallback("Dow30", _down)
            assert False, "Expected the fetch error to propagate with no cached members"
        except RuntimeError as exc:
            assert "Wikipedia 503" in str(exc)

        # Missing file entirely (bootstrap) -> same.
        screener.OUTPUT_PATH = Path(tmp.name) / "absent.json"
        assert screener._cached_index_members("S&P500") == set()
        try:
            screener._fetch_index_with_fallback("S&P500", _down)
            assert False, "Expected the fetch error to propagate with no published dataset"
        except RuntimeError as exc:
            assert "Wikipedia 503" in str(exc)
    finally:
        screener.OUTPUT_PATH = original_path
        tmp.cleanup()


def run_all():
    tests = [
        test_aggregate_total_debt_is_not_double_counted,
        test_total_debt_falls_back_to_long_plus_current,
        test_base_fcff_adds_back_after_tax_interest,
        test_screen_wacc_responds_to_beta,
        test_fcff_dcf_reverse_round_trip,
        test_fcff_dcf_paired_range_brackets_base,
        test_fcff_dcf_stressed_equity_value_is_zero_not_missing,
        test_more_debt_reduces_equity_value_per_share,
        test_wacc_guardrail_prevents_terminal_rate_compression,
        test_currency_mismatch_detects_unconverted_adr_financials,
        test_output_guard_accepts_healthy_dataset,
        test_output_guard_rejects_mass_error_rows,
        test_output_guard_rejects_duplicate_tickers,
        test_output_guard_rejects_blank_tickers,
        test_output_guard_rejects_provider_wide_degradation,
        test_output_guard_rejects_misordered_dcf_range,
        test_nasdaq_fetch_uses_component_list_page,
        test_dow_fetch_uses_component_list_page,
        test_vanguard_pool_takes_top_100_by_weight_and_drops_dual_classes,
        test_vanguard_pool_rejects_a_truncated_holdings_response,
        test_every_pool_is_scored_as_its_own_cross_section,
        test_negative_eps_is_retained_as_worst_discount_not_a_fetch_error,
        test_valuation_warning_lists_every_applicable_reason,
        test_trap_reasons_are_explicit_and_warning_only,
        test_first_weekday_snapshot_logic_handles_weekends,
        test_reverse_fcff_is_pure_without_api_credentials,
        test_finnhub_preflight_rejects_empty_metric_bundle,
        test_safe_float_rejects_non_numeric_and_non_finite,
        test_universe_falls_back_to_last_published_members,
        test_universe_reraises_when_no_cached_members_exist,
    ]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"  PASS  {test.__name__}")
        except Exception as exc:
            failed += 1
            print(f"  FAIL  {test.__name__}: {exc}")
    print(f"\n{len(tests) - failed} passed, {failed} failed")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    run_all()
