"""Offline tests for data-fetch robustness: HTTP retries, backoff, and the per-ticker crash guard."""

import os
import sys

os.environ.setdefault("FRED_API_KEY", "test")
os.environ.setdefault("FINNHUB_API_KEY", "test")

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import pandas as pd
import requests

import stock_screener as screener


class _FakeResponse:
    def __init__(self, status_code, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.headers = headers or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")


def _run_with_fake_http(responses, fn):
    """Swap screener._HTTP_GET for a scripted fake; returns (result, calls, sleeps)."""
    calls = []
    sleeps = []
    script = list(responses)

    def fake_get(url, **kwargs):
        calls.append(url)
        step = script.pop(0)
        if isinstance(step, Exception):
            raise step
        return step

    orig_get, orig_sleep = screener._HTTP_GET, screener._RETRY_SLEEP
    screener._HTTP_GET = fake_get
    screener._RETRY_SLEEP = sleeps.append
    try:
        return fn(), calls, sleeps
    finally:
        screener._HTTP_GET, screener._RETRY_SLEEP = orig_get, orig_sleep


def test_http_get_retries_connection_error_then_succeeds():
    ok = _FakeResponse(200, {"metric": {"epsAnnual": 5.0}})
    resp, calls, sleeps = _run_with_fake_http(
        [requests.ConnectionError("reset"), ok],
        lambda: screener._http_get_with_retries("https://x.test", what="test"),
    )
    assert resp is ok
    assert len(calls) == 2
    assert len(sleeps) == 1 and sleeps[0] > 0


def test_http_get_retries_on_429_and_honours_retry_after():
    ok = _FakeResponse(200)
    resp, calls, sleeps = _run_with_fake_http(
        [_FakeResponse(429, headers={"Retry-After": "7"}), ok],
        lambda: screener._http_get_with_retries("https://x.test", what="test"),
    )
    assert resp is ok
    assert len(calls) == 2
    assert sleeps == [7.0]


def test_http_get_retry_after_is_capped():
    ok = _FakeResponse(200)
    _, _, sleeps = _run_with_fake_http(
        [_FakeResponse(429, headers={"Retry-After": "9999"}), ok],
        lambda: screener._http_get_with_retries("https://x.test", what="test"),
    )
    assert sleeps == [screener.RETRY_AFTER_CAP]


def test_http_get_floors_a_negative_retry_after():
    ok = _FakeResponse(200)
    _, _, sleeps = _run_with_fake_http(
        [_FakeResponse(429, headers={"Retry-After": "-5"}), ok],
        lambda: screener._http_get_with_retries("https://x.test", what="test"),
    )
    assert sleeps == [0.0]


def test_http_get_does_not_retry_client_errors():
    not_found = _FakeResponse(404)
    resp, calls, sleeps = _run_with_fake_http(
        [not_found],
        lambda: screener._http_get_with_retries("https://x.test", what="test"),
    )
    assert resp is not_found
    assert len(calls) == 1 and sleeps == []


def test_http_get_returns_last_retryable_response_when_exhausted():
    bad = _FakeResponse(503)
    resp, calls, _ = _run_with_fake_http(
        [_FakeResponse(503), _FakeResponse(503), bad],
        lambda: screener._http_get_with_retries("https://x.test", what="test", attempts=3),
    )
    assert resp is bad
    assert len(calls) == 3


def test_http_get_raises_last_error_when_exhausted():
    raised = None
    try:
        _run_with_fake_http(
            [requests.ConnectionError("a"), requests.Timeout("b"), requests.Timeout("final")],
            lambda: screener._http_get_with_retries("https://x.test", what="test", attempts=3),
        )
    except requests.Timeout as exc:
        raised = exc
    assert raised is not None and "final" in str(raised)


def test_finnhub_metrics_survive_transient_429():
    ok = _FakeResponse(200, {"metric": {"epsAnnual": 6.1}})
    metrics, calls, _ = _run_with_fake_http(
        [_FakeResponse(429, headers={"Retry-After": "1"}), ok],
        lambda: screener.get_finnhub_metrics("AAPL"),
    )
    assert metrics == {"epsAnnual": 6.1}
    assert len(calls) == 2


def test_finnhub_metrics_empty_after_exhausted_retries():
    metrics, calls, _ = _run_with_fake_http(
        [requests.ConnectionError("x")] * screener.RETRY_ATTEMPTS,
        lambda: screener.get_finnhub_metrics("AAPL"),
    )
    assert metrics == {}
    assert len(calls) == screener.RETRY_ATTEMPTS


def test_vanguard_names_a_bot_challenge_instead_of_a_json_decode_error():
    html_shell = _FakeResponse(200, headers={"content-type": "text/html;charset=utf-8"})
    html_shell.raise_for_status = lambda: None
    raised = None
    try:
        _run_with_fake_http([html_shell], lambda: screener._fetch_vanguard_top_holdings("VUG"))
    except ValueError as exc:
        raised = exc
    assert raised is not None and "non-JSON" in str(raised) and "text/html" in str(raised)


def test_call_with_retries_recovers_then_raises_when_exhausted():
    sleeps = []
    attempts = {"n": 0}

    def flaky():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RuntimeError("transient")
        return 42

    orig_sleep = screener._RETRY_SLEEP
    screener._RETRY_SLEEP = sleeps.append
    try:
        assert screener._call_with_retries(flaky, what="flaky", attempts=3) == 42
        assert attempts["n"] == 3
        assert len(sleeps) == 2 and sleeps[1] > sleeps[0]  # exponential backoff

        raised = None
        try:
            screener._call_with_retries(lambda: (_ for _ in ()).throw(RuntimeError("always")), what="doomed", attempts=2)
        except RuntimeError as exc:
            raised = exc
        assert raised is not None and "always" in str(raised)
    finally:
        screener._RETRY_SLEEP = orig_sleep


def test_yf_price_and_info_recover_from_one_transient_failure_each():
    calls = {"fast_info": 0, "info": 0}

    class FakeTicker:
        def __init__(self, ticker):
            pass

        @property
        def fast_info(self):
            calls["fast_info"] += 1
            if calls["fast_info"] == 1:
                raise RuntimeError("transient fast_info outage")
            return type("FI", (), {"last_price": 123.45})()

        @property
        def info(self):
            calls["info"] += 1
            if calls["info"] == 1:
                raise RuntimeError("transient info outage")
            return {"sector": "Technology", "revenueGrowth": 0.10, "totalCash": 5.0, "totalDebt": 2.0, "marketCap": 1e9}

        income_stmt = None
        dividends = None
        cashflow = None
        balance_sheet = None
        earnings_estimate = None
        revenue_estimate = None

        def history(self, **kwargs):
            return pd.DataFrame()

    sleeps = []
    orig_ticker, orig_sleep = screener.yf.Ticker, screener._RETRY_SLEEP
    screener.yf.Ticker = FakeTicker
    screener._RETRY_SLEEP = sleeps.append
    try:
        d = screener.get_yf_price_and_history("FAKE")
    finally:
        screener.yf.Ticker, screener._RETRY_SLEEP = orig_ticker, orig_sleep

    assert d["price"] == 123.45
    assert d["sector"] == "Technology"
    assert d["az_rev_ttm"] == 10.0 and d["az_cash"] == 5.0
    assert calls["fast_info"] == 2 and calls["info"] == 2
    assert len(sleeps) == 2  # one backoff for the price, one for info


def test_run_screener_survives_one_ticker_crash():
    universe = pd.DataFrame(
        {"ticker": ["GOODCO", "BOOM", "OTHERCO"], "indexes": ["S&P500", "S&P500", "S&P500"]}
    )

    def fake_process(ticker, aaa_yield, risk_free_rate=None):
        if ticker == "BOOM":
            raise KeyError("surprise shape from provider")
        return {
            "Ticker": ticker,
            "Error": None,
            "Provider_Finnhub_OK": True,
            "azqato": {
                "revTTM": 5.0, "revFwd": 6.0, "epsTTM": 7.0, "epsFwd": 8.0,
                "peFwd": 20.0, "pegFwd": 1.5, "cash": 10.0, "debt": 5.0,
                "marketCap": 1e9,
            },
        }

    orig = screener.process_ticker
    screener.process_ticker = fake_process
    try:
        df = screener.run_screener(universe, aaa_yield=5.0)
    finally:
        screener.process_ticker = orig

    assert len(df) == 3
    boom = df[df["Ticker"] == "BOOM"].iloc[0]
    assert str(boom["Error"]).startswith("Processing failed")
    assert boom["Provider_Finnhub_OK"] == False  # noqa: E712 — numpy bool
    good = df[df["Ticker"] == "GOODCO"].iloc[0]
    assert good["Error"] is None or pd.isna(good["Error"])
    assert good["azqato"]["score"] is not None


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  PASS {name}")
            except Exception as exc:
                failures += 1
                print(f"  FAIL {name}: {exc!r}")
    if failures:
        sys.exit(1)
    print("test_fetch_robustness: all tests passed")
