#!/usr/bin/env python3
"""Momentum-only emulator of Seeking Alpha's Alpha Picks, backtested 2015-2026.

What it does (doc: docs/research/sa-momentum-backtest.md):

1. Universe = the screener's latest dataset on the `data` branch (today's names,
   so survivorship-biased by construction). Rows with an Error, or with no
   sector, are dropped; rows are sorted by ticker so that no tie-break carries
   the dataset's row order (which is today's OverallScore).
2. Daily prices from yfinance, 2013-01-01..2026-11-06, cached as parquet. Two
   verified corporate-action splices (SPLICES) have the pre-splice series
   masked; the raw series is kept for the with-splice comparison rows.
3. Rating proxy, daily: 3M/6M/9M/12M total-return momentum (63/126/189/252
   trading days, no skip month), percentile-ranked within sector, averaged,
   re-ranked within sector, cut into SA's observed bucket shares.
4. Alpha Picks rules on the 1st trading day of each month and the 15th (or the
   next trading day): Strong Buy streak, price > $10, approx 3-month average cap
   > $500M, 365-day cooldown, no Real Estate, no ADR (proxy). Three selectors.
   Exits on Sell/Strong Sell, Hold > 180 days (winners exempt, or the
   documented partial sale as a variant), 15%->10% trim.
5. Benchmarks: the same dollars into SPY and into the equal-weight universe on
   each pick date the emulator actually picked on. Paper-style monthly bucket
   sort and FF5+Momentum (+ short-term reversal) regressions.

Run (from the repo root):

    uv run --no-project --with yfinance --with pandas --with numpy \
        --with statsmodels --with pyarrow python -I backtests/sa_momentum_backtest.py

Downloads go to /tmp/sa-tests/ (prices cached in /tmp/sa-tests/cache/, Ken
French zips in /tmp/sa-tests/ff/); a second run works from the cache. Results
are printed as markdown and also written to /tmp/sa-tests/out/results.json.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
WORK = Path("/tmp/sa-tests")
CACHE = WORK / "cache"
FF_DIR = WORK / "ff"
OUT = WORK / "out"

# 2013 so that a 252-day rating warm-up plus a 75-day streak are complete
# before the first 2015 pick day.
PRICE_START = "2013-01-01"
PRICE_END_EXCLUSIVE = "2026-11-07"  # yfinance `end` is exclusive -> last day 2026-11-06
BATCH = 200

WINDOWS = (63, 126, 189, 252)  # 3M / 6M / 9M / 12M in trading days
MIN_HISTORY = 252  # trading days of history before a name is rated

# SA's observed rating distribution (Guo-Jame-Markov 2026, Table 1).
SHARE_SB, SHARE_B, SHARE_S, SHARE_SS = 0.095, 0.104, 0.08, 0.08
SS, SELL, HOLD, BUY, SB = 1, 2, 3, 4, 5  # 0 = unrated
LABEL = {SS: "Strong Sell", SELL: "Sell", HOLD: "Hold", BUY: "Buy", SB: "Strong Buy"}

STREAK_MIN = 75  # "Strong Buy ... for at least 75 consecutive days"
MIN_PRICE = 10.0
MIN_CAP_M = 500.0
CAP_AVG_DAYS = 63  # "3-month average market capitalization"
COOLDOWN_DAYS = 365
HOLD_MAX_DAYS = 180
WINNER_MULT = 2.0
TRIM_TRIGGER, TRIM_TARGET = 0.15, 0.10
# [ASSUMED] The trim is mechanically possible from 7 holdings (below that an
# equal-weight book already has every name above 15%). We require 10 because
# below 10 names an equal weight is above the 10% target, so the trim would cut
# the winner below an average position. 7 is run as a variant.
TRIM_MIN_HOLDINGS = 10
TRIM_MIN_VARIANT = 7
# [ASSUMED] Upside outlier trim for the paper-style sort only: name-months above
# +300% are dropped. This is NOT a splice filter -- most such months are real
# moves (GME Jan 2021). Reported beside the other variants, never instead.
UPSIDE_TRIM_RET = 3.0
WINSOR_PCT = (1.0, 99.0)  # symmetric cross-sectional winsorization, robustness check
# Corporate-action splices verified against primary sources: the series before
# the date belongs to a different security, so it is masked (set missing).
SPLICES = {
    "CHRD": ("2020-11-20", "Oasis Petroleum's old equity was cancelled at its Chapter 11 exit; "
                           "new shares traded from 2020-11-20 (8-K, sec.gov/Archives/edgar/data/1486159/"
                           "000148615920000115)"),
    "IVT": ("2021-10-12", "non-traded REIT before its NYSE listing on 2021-10-12; Yahoo's pre-listing "
                          "series ignores the 2021-08-05 1-for-10 reverse split (FY2021 10-K)"),
}
EXCLUDED_SECTOR = "Real Estate"

PERIODS = {
    "2015-01-01..2026-10-30": ("2015-01-01", "2026-10-30"),
    "2022-07-01..2026-10-30": ("2022-07-01", "2026-10-30"),
}

# Exact-dated real Alpha Picks from docs/research/seeking-alpha-quant.md section 3.
REAL_PICKS = [
    ("SMCI", "2022-11-15"), ("POWL", "2023-05-15"), ("AMPH", "2023-07-03"),
    ("CLS", "2023-10-16"), ("APP", "2023-11-15"), ("LRN", "2025-06-02"),
    ("MU", "2025-10-15"), ("ICHR", "2026-07-01"),
]

FF_URLS = {
    "ff5": "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_5_Factors_2x3_CSV.zip",
    "mom": "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Momentum_Factor_CSV.zip",
    "strev": "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_ST_Reversal_Factor_CSV.zip",
}
FF6 = ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "Mom"]
PAPER_WINDOW = ("2016-01", "2022-12")  # return months for formation Dec 2015 .. Nov 2022


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


# ---------------------------------------------------------------- universe

def load_universe() -> pd.DataFrame:
    raw = subprocess.run(
        ["git", "-C", str(REPO), "show", "origin/data:web/public/data/results.json"],
        check=True, capture_output=True,
    ).stdout
    data = json.loads(raw)
    rows = pd.DataFrame(data["rows"])[["Ticker", "Sector", "MarketCap_B", "Price", "Error",
                                       "DCF_Currency_Mismatch"]]
    info = {"generated_at": data["generated_at"], "rows": len(rows)}
    rows = rows[rows["Error"].isna()]
    info["non_error"] = len(rows)
    no_sector = rows["Sector"].isna() | (rows["Sector"].astype(str).str.strip() == "")
    info["no_sector_dropped"] = sorted(rows.loc[no_sector, "Ticker"])
    rows = rows[~no_sector].drop_duplicates("Ticker").sort_values("Ticker").reset_index(drop=True)
    info["kept"] = len(rows)
    return rows, info


# ---------------------------------------------------------------- prices

def _batch_path(tickers: list[str]) -> Path:
    h = hashlib.sha1((",".join(tickers) + PRICE_START + PRICE_END_EXCLUSIVE).encode()).hexdigest()[:12]
    return CACHE / f"batch_{h}.parquet"


def download_prices(tickers: list[str]) -> dict[str, pd.DataFrame]:
    """Open / Close (split-adjusted) / Adj Close / Stock Splits, wide frames."""
    import yfinance as yf

    CACHE.mkdir(parents=True, exist_ok=True)
    yf.set_tz_cache_location(str(CACHE / "yf-tz"))
    fields = ["Open", "Close", "Adj Close", "Stock Splits"]
    parts = {f: [] for f in fields}
    tickers = sorted(tickers)
    for k in range(0, len(tickers), BATCH):
        chunk = tickers[k:k + BATCH]
        path = _batch_path(chunk)
        if path.exists():
            df = pd.read_parquet(path)
        else:
            log(f"downloading batch {k // BATCH + 1} ({len(chunk)} tickers)")
            got = yf.download(chunk, start=PRICE_START, end=PRICE_END_EXCLUSIVE,
                              auto_adjust=False, actions=True, progress=False,
                              group_by="column", threads=True)
            cols = {}
            for f in fields:
                sub = got[f] if f in got.columns.get_level_values(0) else pd.DataFrame(index=got.index)
                for t in chunk:
                    cols[f"{f}|{t}"] = sub[t] if t in sub.columns else pd.Series(np.nan, index=got.index)
            df = pd.DataFrame(cols, index=got.index)
            df.index = pd.to_datetime(df.index).tz_localize(None)
            df.to_parquet(path)
            time.sleep(2)
        for f in fields:
            sub = df[[c for c in df.columns if c.startswith(f + "|")]]
            sub.columns = [c.split("|", 1)[1] for c in sub.columns]
            parts[f].append(sub)
    return {f: pd.concat(parts[f], axis=1).sort_index() for f in fields}


def check_auto_adjust_equivalence() -> dict:
    """Adjusted open is built as Open * AdjClose / Close. Check it equals auto_adjust=True."""
    path = CACHE / "auto_adjust_check.parquet"
    if not path.exists():
        import yfinance as yf
        yf.set_tz_cache_location(str(CACHE / "yf-tz"))
        a = yf.download(["SPY", "AAPL", "NVDA"], start="2015-01-01", end="2026-11-07",
                        auto_adjust=True, progress=False, group_by="column")
        b = yf.download(["SPY", "AAPL", "NVDA"], start="2015-01-01", end="2026-11-07",
                        auto_adjust=False, progress=False, group_by="column")
        df = pd.concat({"aa_open": a["Open"], "aa_close": a["Close"], "open": b["Open"],
                        "close": b["Close"], "adj": b["Adj Close"]}, axis=1)
        df.columns = [f"{x}|{y}" for x, y in df.columns]
        df.index = pd.to_datetime(df.index).tz_localize(None)
        df.to_parquet(path)
    df = pd.read_parquet(path)
    out = {}
    for t in ["SPY", "AAPL", "NVDA"]:
        derived = df[f"open|{t}"] * df[f"adj|{t}"] / df[f"close|{t}"]
        rel_open = (derived / df[f"aa_open|{t}"] - 1).abs().max()
        rel_close = (df[f"adj|{t}"] / df[f"aa_close|{t}"] - 1).abs().max()
        out[t] = {"max_rel_err_open": float(rel_open), "max_rel_err_close": float(rel_close)}
    return out


# ---------------------------------------------------------------- ratings

def sector_rank(frame: pd.DataFrame, groups: dict[str, list[int]]) -> np.ndarray:
    out = np.full(frame.shape, np.nan)
    vals = frame.values
    for cols in groups.values():
        out[:, cols] = pd.DataFrame(vals[:, cols]).rank(axis=1, pct=True, method="average").values
    return out


def bucket(p: np.ndarray) -> np.ndarray:
    r = np.zeros(p.shape, dtype=np.int8)
    ok = ~np.isnan(p)
    r[ok] = HOLD
    r[ok & (p > 1 - SHARE_SB)] = SB
    r[ok & (p <= 1 - SHARE_SB) & (p > 1 - SHARE_SB - SHARE_B)] = BUY
    r[ok & (p <= SHARE_SS + SHARE_S)] = SELL
    r[ok & (p <= SHARE_SS)] = SS
    return r


def compute_ratings(adj_rank: pd.DataFrame, groups) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    T = adj_rank.shape[0]
    valid = adj_rank.notna().values
    first = np.where(valid.any(axis=0), valid.argmax(axis=0), T + 10**6)
    hist_ok = (np.arange(T)[:, None] >= first[None, :] + MIN_HISTORY) & valid
    pcts = []
    for w in WINDOWS:
        mom = adj_rank / adj_rank.shift(w) - 1.0
        mom = mom.where(hist_ok)
        pcts.append(sector_rank(mom, groups))
    avg = np.mean(np.stack(pcts), axis=0)  # NaN where unrated
    rerank = sector_rank(pd.DataFrame(avg), groups)
    return bucket(rerank), rerank, avg


def run_lengths(mask: np.ndarray) -> np.ndarray:
    """Per column, length of the current True run ending at each row."""
    out = np.zeros(mask.shape, dtype=np.int32)
    run = np.zeros(mask.shape[1], dtype=np.int32)
    for t in range(mask.shape[0]):
        run = np.where(mask[t], run + 1, 0)
        out[t] = run
    return out


# ---------------------------------------------------------------- metrics

def irr(flows: list[tuple[pd.Timestamp, float]]) -> float | None:
    """Annual money-weighted return; flows signed from the investor's side."""
    t0 = flows[0][0]
    yrs = np.array([(d - t0).days / 365.25 for d, _ in flows])
    amt = np.array([a for _, a in flows])

    def npv(r):
        return float(np.sum(amt / (1.0 + r) ** yrs))

    lo, hi = -0.99, 20.0
    if npv(lo) * npv(hi) > 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        if npv(lo) * npv(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def max_drawdown(index: np.ndarray) -> float:
    peak = np.maximum.accumulate(index)
    return float(np.min(index / peak - 1.0))


def drawdown_dates(index: np.ndarray, dates) -> tuple[str, str]:
    peak = np.maximum.accumulate(index)
    trough = int(np.argmin(index / peak - 1.0))
    top = int(np.argmax(index[:trough + 1]))
    return str(dates[top].date()), str(dates[trough].date())


# ---------------------------------------------------------------- context

class Ctx:
    pass


def split_factor_future(splits: pd.DataFrame | pd.Series):
    """Product of split ratios strictly after each date (undoes Yahoo's split adjustment)."""
    s = splits.fillna(0.0).replace(0.0, 1.0)
    return s.iloc[::-1].cumprod().iloc[::-1].shift(-1).fillna(1.0)


def ew_units(c: Ctx, adj_open: np.ndarray, close_ff: np.ndarray, open_ff: np.ndarray,
             open_valid: np.ndarray) -> tuple[dict, dict]:
    """Equal-weight universe: $1 spread over every name trading at that pick day's open."""
    unit_close, unit_open = {}, {}
    close0 = np.nan_to_num(close_ff)
    open0 = np.nan_to_num(open_ff)
    for p in c.pick_days:
        ok = open_valid[p]
        sh = np.where(ok, 1.0 / ok.sum() / np.where(ok, adj_open[p], 1.0), 0.0)
        unit_close[p] = close0 @ sh
        unit_open[p] = open0 @ sh
    return unit_close, unit_open


def build_context(args) -> Ctx:
    c = Ctx()
    uni, c.uni_info = load_universe()
    tickers = list(uni["Ticker"])
    px = download_prices(tickers + ["SPY"])
    spy_close = px["Adj Close"]["SPY"]
    dates = spy_close.dropna().index
    dates = dates[(dates >= PRICE_START) & (dates < PRICE_END_EXCLUSIVE)]
    for f in px:
        px[f] = px[f].reindex(dates)
    c.dates = dates
    T = len(dates)

    have = px["Adj Close"][tickers].notna().any(axis=0)
    c.no_price = sorted(have.index[~have])
    uni = uni[uni["Ticker"].isin(have.index[have])].reset_index(drop=True)
    tickers = list(uni["Ticker"])
    assert tickers == sorted(tickers), "universe must be in ticker order (the final tie-break)"
    c.uni = uni
    c.tickers = np.array(tickers)
    N = len(tickers)
    log(f"{N} tickers with prices, {T} trading days {dates[0].date()}..{dates[-1].date()}")

    close_raw = px["Close"][tickers]  # Yahoo close: split-adjusted, not dividend-adjusted
    adj_raw = px["Adj Close"][tickers]
    opn_raw = px["Open"][tickers]
    splits = px["Stock Splits"][tickers]
    nominal = close_raw * split_factor_future(splits)  # the price that actually printed that day

    c.split_check = {
        "NVDA_2024-06-07_yahoo_close": float(close_raw.loc["2024-06-07", "NVDA"]),
        "NVDA_2024-06-07_nominal": float(nominal.loc["2024-06-07", "NVDA"]),
    }
    assert c.split_check["NVDA_2024-06-07_nominal"] > 1000, "split un-adjustment failed"

    # Raw (unmasked) total-return series, kept only for the with-splice comparison rows.
    adj_open_raw = (opn_raw * adj_raw / close_raw).values
    c.raw_adj_close = adj_raw.values

    # Mask verified splices: the series before the date is a different security.
    mask = pd.DataFrame(False, index=dates, columns=tickers)
    c.splice_info = {}
    for tk, (d, why) in SPLICES.items():
        if tk in mask.columns:
            mask.loc[mask.index < pd.Timestamp(d), tk] = True
            c.splice_info[tk] = {"masked_before": d, "days_masked": int(mask[tk].sum()), "why": why}
    close_raw = close_raw.mask(mask)
    adj = adj_raw.mask(mask)
    opn = opn_raw.mask(mask)
    nominal = nominal.mask(mask)

    c.adj_open = (opn * adj / close_raw).values
    c.adj_close = adj.values
    c.close_ff = adj.ffill().values
    c.open_valid = ~np.isnan(c.adj_open)
    c.close_valid = ~np.isnan(c.adj_close)

    sectors = uni["Sector"].values
    groups = {s: list(np.flatnonzero(sectors == s)) for s in sorted(set(sectors))}
    c.sectors = sectors
    c.sector_sizes = {s: len(v) for s, v in groups.items()}
    rating_close, rerank, avg = compute_ratings(adj.ffill(limit=5), groups)
    c.rating_close = rating_close
    c.rating_close_raw = compute_ratings(adj_raw.ffill(limit=5), groups)[0]
    # SA updates before the open from the previous close: on day t we act on
    # the rating computed from data through close t-1.
    c.R = np.vstack([np.zeros((1, N), np.int8), rating_close[:-1]])
    c.score = np.vstack([np.full((1, N), np.nan), rerank[:-1]])
    c.score2 = np.vstack([np.full((1, N), np.nan), avg[:-1]])

    sb_run = run_lengths(c.R == SB)
    hold_run = run_lengths(c.R == HOLD)
    tidx = np.arange(T)
    day_num = np.array([(d - dates[0]).days for d in dates])
    c.day_num = day_num
    sb_start = np.clip(tidx[:, None] - sb_run + 1, 0, T - 1)
    hold_start = np.clip(tidx[:, None] - hold_run + 1, 0, T - 1)
    c.sb_run = sb_run
    c.sb_cal = np.where(sb_run > 0, day_num[:, None] - day_num[sb_start], -1)
    c.hold_cal = np.where(hold_run > 0, day_num[:, None] - day_num[hold_start], -1)
    del sb_start, hold_start

    # Filters, all known before day t's open (data through t-1).
    shares_b = (uni["MarketCap_B"] / uni["Price"]).astype(float).values  # NaN if either missing
    cap_m = close_raw.values * shares_b[None, :] * 1000.0
    cap3m = pd.DataFrame(cap_m).rolling(CAP_AVG_DAYS, min_periods=CAP_AVG_DAYS).mean().values
    c.cap_prev = np.vstack([np.full((1, N), np.nan), cap3m[:-1]])
    c.nom_prev = np.vstack([np.full((1, N), np.nan), nominal.values[:-1]])
    yah_prev = np.vstack([np.full((1, N), np.nan), close_raw.values[:-1]])
    c.sector_ok = (sectors != EXCLUDED_SECTOR)
    # ADR proxy, the same rule as alphapicks._is_adr_proxy: the DCF found a
    # reporting currency different from the trading currency. Missing = not ADR.
    c.adr = (uni["DCF_Currency_Mismatch"] == True).values  # noqa: E712 (None -> False)
    with np.errstate(invalid="ignore"):
        base_noadr = (c.R == SB) & (c.cap_prev > MIN_CAP_M) & c.sector_ok[None, :] & c.open_valid
        base = base_noadr & ~c.adr[None, :]
        c.elig = {
            "75 trading days": base & (c.nom_prev > MIN_PRICE) & (sb_run >= STREAK_MIN),
            "75 calendar days": base & (c.nom_prev > MIN_PRICE) & (c.sb_cal >= STREAK_MIN),
        }
        c.elig_adr_allowed = base_noadr & (c.nom_prev > MIN_PRICE) & (sb_run >= STREAK_MIN)
        alt = base & (yah_prev > MIN_PRICE) & (sb_run >= STREAK_MIN)
    c.cap_missing = int(np.isnan(shares_b).sum())

    # Pick days: first trading day of each month, and the 15th or next trading day.
    s = pd.Series(np.arange(T), index=dates)
    first = s.groupby([dates.year, dates.month]).min().values
    mid = []
    for (y, m), grp in s.groupby([dates.year, dates.month]):
        after = grp[grp.index.day >= 15]
        if len(after):
            mid.append(int(after.iloc[0]))
    c.pick_days = np.array(sorted(set(first.tolist()) | set(mid)))
    pd_mask = np.zeros(T, bool)
    pd_mask[c.pick_days] = True
    e = c.elig["75 trading days"]
    c.price_basis = {
        "eligible only under the nominal price": int(np.sum((e & ~alt)[pd_mask])),
        "eligible only under Yahoo's split-adjusted close": int(np.sum((alt & ~e)[pd_mask])),
        "eligible under either (union)": int(np.sum((e | alt)[pd_mask])),
    }

    spy_fut = split_factor_future(px["Stock Splits"]["SPY"])
    c.spy_open = (px["Open"]["SPY"] * px["Adj Close"]["SPY"] / px["Close"]["SPY"]).values
    c.spy_close = px["Adj Close"]["SPY"].ffill().values
    c.spy_nom_open = (px["Open"]["SPY"] * spy_fut).values
    c.spy_nom_close = (px["Close"]["SPY"] * spy_fut).values

    open_ff = np.where(c.open_valid, c.adj_open, np.vstack([c.close_ff[:1], c.close_ff[:-1]]))
    c.open_ff = open_ff
    c.ew_unit_close, c.ew_unit_open = ew_units(c, c.adj_open, c.close_ff, open_ff, c.open_valid)
    # Same benchmark on the raw (splice-included) series, for comparison only.
    raw_close_ff = adj_raw.ffill().values
    raw_open_valid = ~np.isnan(adj_open_raw)
    raw_open_ff = np.where(raw_open_valid, adj_open_raw, np.vstack([raw_close_ff[:1], raw_close_ff[:-1]]))
    c.ew_raw = ew_units(c, adj_open_raw, raw_close_ff, raw_open_ff, raw_open_valid)
    del raw_close_ff, raw_open_ff, adj_open_raw
    return c


# ---------------------------------------------------------------- simulation

def simulate(c: Ctx, start_i: int, end_i: int, elig: np.ndarray, selector: str,
             rng=None, trim: bool = True, trim_min: int = TRIM_MIN_HOLDINGS,
             hold_rule: str = "exempt") -> dict:
    """hold_rule: "exempt" = a winner is never sold at Hold (the brief's reading);
    "partial" = a winner more than 180 days at Hold sells its original purchase
    amount ($1 per pick into the current position), the clock restarting at each
    such sale (research doc section 2, retirebeforedad; as alphapicks.py)."""
    assert hold_rule in ("exempt", "partial")
    N = len(c.tickers)
    shares = np.zeros(N)
    entry = np.full(N, np.nan)
    cost = np.zeros(N)  # pick dollars into the current position
    wsold = np.full(N, -10**9)  # day_num of the last winner sale in the current position
    cin = np.zeros(N)
    cout = np.zeros(N)
    last_pick = np.full(N, -10**9)
    day_num = c.day_num
    picks = []  # [ticker_idx, pick_t, entry_px, exit_t, exit_px]
    open_recs = {}
    flows = []
    realized = 0.0
    contrib = 0.0
    twr = 1.0
    twr_idx = np.full(end_i + 1, np.nan)
    value = np.full(end_i + 1, np.nan)
    nheld = np.zeros(end_i + 1, int)
    pick_set = set(int(p) for p in c.pick_days if start_i <= p <= end_i)
    used_picks = []
    empty_pool = 0
    pool_sizes = []
    ties_top = ties_ticker = 0
    winner_sales = 0
    vprev = 0.0
    for t in range(start_i, end_i + 1):
        held = np.flatnonzero(shares > 0)
        vopen = float(shares[held] @ c.open_ff[t, held]) if len(held) else 0.0
        r1 = vopen / vprev - 1.0 if vprev > 0 else 0.0
        inflow = 0.0
        if t in pick_set:
            cand = elig[t] & (day_num[t] - last_pick > COOLDOWN_DAYS)
            idx = np.flatnonzero(cand)
            pool_sizes.append(len(idx))
            if len(idx) == 0:
                empty_pool += 1
            else:
                # Final tie-break is the ticker: the universe is in ticker order (asserted).
                if selector == "score":
                    keys = (-c.score[t, idx], -c.score2[t, idx])
                elif selector == "streak":
                    keys = (-c.sb_run[t, idx].astype(float), -c.score[t, idx], -c.score2[t, idx])
                elif selector == "streak-no-score2":  # tie-break sensitivity variant
                    keys = (-c.sb_run[t, idx].astype(float), -c.score[t, idx])
                if selector in ("score", "streak", "streak-no-score2"):
                    order = np.lexsort((idx,) + keys[::-1])
                    i = int(idx[order[0]])
                    if len(idx) > 1:
                        top = keys[0] == keys[0][order[0]]
                        ties_top += int(top.sum() > 1)
                        allk = np.all([k == k[order[0]] for k in keys], axis=0)
                        ties_ticker += int(allk.sum() > 1)
                else:
                    i = int(rng.choice(idx))
                px = c.adj_open[t, i]
                if shares[i] == 0:
                    entry[i] = px
                shares[i] += 1.0 / px
                cin[i] += 1.0
                cost[i] += 1.0
                contrib += 1.0
                inflow = 1.0
                last_pick[i] = day_num[t]
                flows.append((c.dates[t], -1.0))
                used_picks.append(t)
                open_recs.setdefault(i, []).append(len(picks))
                picks.append([i, t, px, None, None])
        vclose = float(np.nan_to_num(shares) @ np.nan_to_num(c.close_ff[t]))
        basev = vopen + inflow
        r2 = vclose / basev - 1.0 if basev > 0 else 0.0
        twr *= (1 + r1) * (1 + r2)

        held = np.flatnonzero(shares > 0)
        if len(held):
            codes = c.R[t, held]
            cl = c.adj_close[t, held]
            ok = c.close_valid[t, held]
            sell = ok & ((codes == SELL) | (codes == SS))
            hold_el = c.hold_cal[t, held]
            if hold_rule == "partial":
                hold_el = np.minimum(hold_el, day_num[t] - wsold[held])
            with np.errstate(invalid="ignore"):
                over = ok & (codes == HOLD) & (hold_el > HOLD_MAX_DAYS)
                winner = cl >= WINNER_MULT * entry[held]
            stale = over & ~winner
            full_exit = list(held[sell | stale])
            if hold_rule == "partial":
                for i in held[over & winner]:
                    val = shares[i] * c.adj_close[t, i]
                    if val <= cost[i]:
                        full_exit.append(i)
                        continue
                    shares[i] *= 1.0 - cost[i] / val
                    realized += cost[i]
                    cout[i] += cost[i]
                    flows.append((c.dates[t], cost[i]))
                    wsold[i] = day_num[t]
                    winner_sales += 1
            for i in full_exit:
                proceeds = shares[i] * c.adj_close[t, i]
                realized += proceeds
                cout[i] += proceeds
                flows.append((c.dates[t], proceeds))
                for r in open_recs.pop(i, []):
                    picks[r][3] = t
                    picks[r][4] = c.adj_close[t, i]
                shares[i] = 0.0
                entry[i] = np.nan
                cost[i] = 0.0
                wsold[i] = -10**9
            held = np.flatnonzero(shares > 0)
            if trim and len(held) >= trim_min:
                for _ in range(10):
                    px_t = c.close_ff[t, held]
                    vals = shares[held] * px_t
                    tot = vals.sum()
                    over_w = np.flatnonzero(vals > TRIM_TRIGGER * tot)
                    if len(over_w) == 0:
                        break
                    for k in over_w:
                        i = held[k]
                        excess = shares[i] * px_t[k] - TRIM_TARGET * tot
                        shares[i] -= excess / px_t[k]
                        cout[i] += excess
                        others = np.delete(np.arange(len(held)), k)
                        per = excess / len(others)
                        shares[held[others]] += per / px_t[others]
                        cin[held[others]] += per
        vprev = float(np.nan_to_num(shares) @ np.nan_to_num(c.close_ff[t]))
        twr_idx[t] = twr
        value[t] = vprev + realized
        nheld[t] = int((shares > 0).sum())

    held_val = shares * np.nan_to_num(c.close_ff[end_i])
    pnl = cout + held_val - cin
    for r in picks:
        if r[3] is None:
            r[4] = c.close_ff[end_i, r[0]]
    first = used_picks[0] if used_picks else start_i
    nh = nheld[first:end_i + 1]
    return {
        "picks": picks, "flows": flows, "contrib": contrib, "value_end": value[end_i],
        "holdings_end": float(held_val.sum()), "twr_idx": twr_idx, "value": value,
        "nheld": nheld, "pnl": pnl, "used_picks": used_picks, "empty_pool": empty_pool,
        "pool_sizes": pool_sizes, "start_i": start_i, "end_i": end_i,
        "ties_top": ties_top, "ties_ticker": ties_ticker, "winner_sales": winner_sales,
        "trim_inactive_days": int((nh < trim_min).sum()) if trim else None,
        "trim_first_active": (str(c.dates[first + int(np.argmax(nh >= trim_min))].date())
                              if trim and (nh >= trim_min).any() else None),
    }


def benchmark(c: Ctx, used_picks: list[int], start_i: int, end_i: int, kind: str) -> dict:
    T = end_i + 1
    vclose = np.zeros(T)
    vopen = np.zeros(T)
    inflow = np.zeros(T)
    for p in used_picks:
        if kind == "SPY":
            u_c = c.spy_close / c.spy_open[p]
            u_o = np.where(np.isnan(c.spy_open), np.r_[c.spy_close[:1], c.spy_close[:-1]], c.spy_open) / c.spy_open[p]
        elif kind == "EW universe":
            u_c, u_o = c.ew_unit_close[p], c.ew_unit_open[p]
        elif kind == "EW universe, raw (splices in)":
            u_c, u_o = c.ew_raw[0][p], c.ew_raw[1][p]
        else:
            raise ValueError(kind)
        vclose[p:T] += u_c[p:T]
        vopen[p + 1:T] += u_o[p + 1:T]
        inflow[p] += 1.0
    twr = 1.0
    idx = np.full(T, np.nan)
    for t in range(start_i, T):
        vp = vclose[t - 1] if t > start_i else 0.0
        r1 = vopen[t] / vp - 1.0 if vp > 0 else 0.0
        b = vopen[t] + inflow[t]
        r2 = vclose[t] / b - 1.0 if b > 0 else 0.0
        twr *= (1 + r1) * (1 + r2)
        idx[t] = twr
    flows = [(c.dates[p], -1.0) for p in used_picks] + [(c.dates[end_i], float(vclose[end_i]))]
    contrib = float(len(used_picks))
    return {"value_end": float(vclose[end_i]), "contrib": contrib, "twr_idx": idx, "flows": flows,
            "used_picks": list(used_picks)}


def summarize(c: Ctx, res: dict, is_bench: bool = False) -> dict:
    """The clock (TWR CAGR, drawdown, average holdings) starts at the first pick."""
    end_i = len(res["twr_idx"]) - 1
    first = int(res["used_picks"][0])
    tw = res["twr_idx"][first:]
    assert not np.isnan(tw).any()
    out = {
        "value_over_contrib": res["value_end"] / res["contrib"] - 1.0,
        "twr": float(tw[-1] - 1.0),
        "irr": irr(res["flows"] + ([] if is_bench else [(c.dates[end_i], res["holdings_end"])])),
        "max_dd_twr": max_drawdown(tw),
        "dd_dates": drawdown_dates(tw, c.dates[first:end_i + 1]),
        "twr_cagr": float(tw[-1] ** (365.25 / max((c.dates[end_i] - c.dates[first]).days, 1)) - 1.0),
        "contrib": res["contrib"],
        "first_pick": str(c.dates[first].date()),
    }
    if not is_bench:
        rets = np.array([r[4] / r[2] - 1.0 for r in res["picks"]])
        pnl = res["pnl"]
        tot = pnl.sum()
        top = np.argsort(-pnl)[:5]
        out.update({
            "n_picks": len(res["picks"]),
            "n_names": len(set(r[0] for r in res["picks"])),
            "win_rate": float(np.mean(rets > 0)) if len(rets) else None,
            "median_pick_ret": float(np.median(rets)) if len(rets) else None,
            "mean_pick_ret": float(np.mean(rets)) if len(rets) else None,
            "top5_share": float(pnl[top].sum() / tot) if tot > 0 else None,
            "top5": [(c.tickers[i], float(pnl[i])) for i in top],
            "empty_pool_days": res["empty_pool"],
            "median_pool": float(np.median(res["pool_sizes"])) if res["pool_sizes"] else None,
            "avg_holdings": float(np.mean(res["nheld"][first:])),
            "open_at_end": int(sum(1 for r in res["picks"] if r[3] is None)),
            "ties_top": res["ties_top"], "ties_ticker": res["ties_ticker"],
            "winner_sales": res["winner_sales"], "trim_inactive_days": res["trim_inactive_days"],
            "trim_first_active": res["trim_first_active"],
            "picked_names": sorted(set(c.tickers[r[0]] for r in res["picks"])),
            # re-ranked score 1.0 = the top name of its sector on the average percentile
            "picks_sector_leader": int(sum(1 for r in res["picks"] if c.score[r[1], r[0]] == 1.0)),
        })
    return out


def vs_bench(m: dict, spy: dict, ew: dict) -> None:
    """Relative TWR against date-matched benchmarks, and the share of the log
    excess over SPY that the EW universe's own lead over SPY accounts for."""
    m["twr_vs_spy"] = (1 + m["twr"]) / (1 + spy["twr"]) - 1
    m["twr_vs_ew"] = (1 + m["twr"]) / (1 + ew["twr"]) - 1
    m["log_excess_spy"] = math.log1p(m["twr_vs_spy"])
    m["log_ew_gap"] = math.log((1 + ew["twr"]) / (1 + spy["twr"]))
    # Undefined when the run barely beat SPY (a share of ~0 is not informative).
    m["ew_share_of_excess"] = m["log_ew_gap"] / m["log_excess_spy"] if m["log_excess_spy"] > 0.01 else None


# ---------------------------------------------------------------- paper check

def month_ends(dates: pd.DatetimeIndex) -> np.ndarray:
    s = pd.Series(np.arange(len(dates)), index=dates)
    return s.groupby([dates.year, dates.month]).max().values


def paper_sort(c: Ctx, adj_close: np.ndarray | None = None, ratings: np.ndarray | None = None,
               mode: str = "plain") -> pd.DataFrame:
    """mode: "plain"; "upside" drops name-months above UPSIDE_TRIM_RET; "winsor"
    clips each month's rated cross-section at WINSOR_PCT."""
    me = month_ends(c.dates)
    rows = []
    adjc = pd.DataFrame(c.adj_close if adj_close is None else adj_close).ffill(limit=5).values
    rats = c.rating_close if ratings is None else ratings
    for a, b in zip(me[:-1], me[1:]):
        d = c.dates[b]
        if d < pd.Timestamp("2015-01-01") or d > pd.Timestamp("2026-10-31"):
            continue
        r = adjc[b] / adjc[a] - 1.0
        rat = rats[a]
        row = {"month": d.to_period("M")}
        keep = ~np.isnan(r)
        if mode == "upside":
            with np.errstate(invalid="ignore"):
                keep &= ~(r > UPSIDE_TRIM_RET)
        elif mode == "winsor":
            ok = keep & (rat > 0)
            lo, hi = np.percentile(r[ok], WINSOR_PCT)
            r = np.clip(r, lo, hi)
        for code, lab in LABEL.items():
            m = (rat == code) & keep
            row[lab] = float(np.mean(r[m])) if m.any() else np.nan
            row[lab + "_n"] = int(m.sum())
            row[lab + "_med"] = float(np.median(r[m])) if m.any() else np.nan
            row[lab + "_dropped"] = int(np.sum((rat == code) & ~np.isnan(r) & ~keep))
        m = (rat > 0) & keep
        row["Rated universe"] = float(np.mean(r[m])) if m.any() else np.nan
        rows.append(row)
    df = pd.DataFrame(rows).set_index("month")
    df = df[df["Strong Buy"].notna()]  # a formation month before the first rating
    df["SB-SS"] = df["Strong Buy"] - df["Strong Sell"]
    df["SB-SS median"] = df["Strong Buy_med"] - df["Strong Sell_med"]
    return df


def big_months(c: Ctx, adj_close: np.ndarray, ratings: np.ndarray) -> list[dict]:
    """Every name-month above UPSIDE_TRIM_RET in the sort window, with its largest one-day move."""
    me = month_ends(c.dates)
    adjc = pd.DataFrame(adj_close).ffill(limit=5).values
    out = []
    for a, b in zip(me[:-1], me[1:]):
        d = c.dates[b]
        if d < pd.Timestamp("2015-01-01") or d > pd.Timestamp("2026-10-31"):
            continue
        with np.errstate(invalid="ignore", divide="ignore"):
            r = adjc[b] / adjc[a] - 1.0
            for j in np.flatnonzero(r > UPSIDE_TRIM_RET):
                seg = adjc[a + 1:b + 1, j] / adjc[a:b, j] - 1.0
                k = int(np.nanargmax(seg))
                out.append({"month": str(d.to_period("M")), "ticker": str(c.tickers[j]),
                            "rating": LABEL.get(int(ratings[a, j]), "unrated"), "ret": float(r[j]),
                            "px_from": float(adjc[a, j]), "px_to": float(adjc[b, j]),
                            "max_1d": float(seg[k]), "max_1d_date": str(c.dates[a + 1 + k].date()),
                            "masked_splice": str(c.tickers[j]) in SPLICES})
    return out


def churn(c: Ctx) -> dict:
    R = c.rating_close
    out = {}
    for lag, lab in [(1, "1 day"), (21, "21 days"), (252, "252 days")]:
        a, b = R[:-lag], R[lag:]
        m = (a == SB) & (b > 0)
        out[lab] = float(np.mean(b[m] == SB))
    m = (R[:-252] == SB) & (R[252:] > 0)
    out["after 252: dist"] = {LABEL[k]: float(np.mean(R[252:][m] == k)) for k in LABEL}
    rated = R[R > 0]
    out["bucket shares"] = {LABEL[k]: float(np.mean(rated == k)) for k in LABEL}
    out["avg SB per day"] = float(np.mean(np.sum(R == SB, axis=1)[MIN_HISTORY + 1:]))
    out["avg rated per day"] = float(np.mean(np.sum(R > 0, axis=1)[MIN_HISTORY + 1:]))
    return out


# ---------------------------------------------------------------- Ken French

def load_ff() -> pd.DataFrame:
    FF_DIR.mkdir(parents=True, exist_ok=True)
    frames = []
    for key, url in FF_URLS.items():
        path = FF_DIR / f"{key}.zip"
        if not path.exists():
            with urllib.request.urlopen(url, timeout=60) as resp:
                path.write_bytes(resp.read())
        with zipfile.ZipFile(path) as z:
            name = [n for n in z.namelist() if n.lower().endswith(".csv")][0]
            text = z.read(name).decode("latin-1")
        header, recs = None, []
        for line in text.splitlines():
            parts = [p.strip() for p in line.split(",")]
            if header is None and len(parts) > 1 and parts[0] == "" and any(p for p in parts[1:]):
                header = parts[1:]
                continue
            if header is not None and len(parts[0]) == 6 and parts[0].isdigit():
                recs.append([parts[0]] + parts[1:])
            elif header is not None and recs and parts[0] == "":
                break  # end of the monthly block
        df = pd.DataFrame(recs, columns=["ym"] + header)
        df.index = pd.PeriodIndex(pd.to_datetime(df.pop("ym"), format="%Y%m"), freq="M")
        frames.append(df.astype(float) / 100.0)
    ff = pd.concat(frames, axis=1, join="inner")
    ff.columns = [x.strip() for x in ff.columns]
    return ff


def regress(y: pd.Series, ff: pd.DataFrame, excess: bool = True, factors: list[str] = FF6) -> dict:
    import statsmodels.api as sm
    df = pd.concat([y.rename("y"), ff], axis=1, join="inner").dropna()
    yy = df["y"] - (df["RF"] if excess else 0.0)
    X = sm.add_constant(df[factors])
    ols = sm.OLS(yy, X).fit()
    hac = sm.OLS(yy, X).fit(cov_type="HAC", cov_kwds={"maxlags": 3})
    return {
        "months": int(len(df)), "first": str(df.index[0]), "last": str(df.index[-1]),
        "alpha_m": float(ols.params["const"]), "alpha_t": float(ols.tvalues["const"]),
        "alpha_t_hac3": float(hac.tvalues["const"]), "r2": float(ols.rsquared),
        "betas": {k: (float(ols.params[k]), float(ols.tvalues[k])) for k in X.columns if k != "const"},
    }


def monthly_from_index(c: Ctx, idx: np.ndarray, first_pick: int) -> pd.Series:
    me = month_ends(c.dates)
    me = me[me < len(idx)]
    s = pd.Series(idx[me], index=c.dates[me].to_period("M"))
    s = s[s.index > c.dates[first_pick].to_period("M")].dropna()
    full = pd.Series(idx[me], index=c.dates[me].to_period("M"))
    prev = full.shift(1)
    return (full / prev - 1.0).loc[s.index]


# ---------------------------------------------------------------- report

def px_spy_nominal(c: Ctx, start_i: int, end_i: int) -> float:
    return c.spy_nom_close[end_i] / c.spy_nom_open[start_i] - 1.0


def pct(x, d=1):
    return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{100 * x:+.{d}f}%"


def tstat(s: pd.Series) -> float:
    s = s.dropna()
    return float(s.mean() / (s.std(ddof=1) / math.sqrt(len(s))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mc-runs", type=int, default=500)
    ap.add_argument("--seed", type=int, default=20261108)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    import yfinance
    c = build_context(args)
    log(f"context built in {time.time() - t0:.0f}s")
    results = {"yfinance": yfinance.__version__, "universe": c.uni_info, "no_price": c.no_price,
               "split_check": c.split_check, "auto_adjust_check": check_auto_adjust_equivalence(),
               "cap_missing": c.cap_missing, "price_basis": c.price_basis, "sector_sizes": c.sector_sizes,
               "splices": c.splice_info, "adr_proxy": sorted(c.tickers[c.adr].tolist())}
    print("# SA momentum emulator - run output\n")
    print(f"yfinance {yfinance.__version__}; pandas {pd.__version__}; numpy {np.__version__}")
    print(f"universe: {json.dumps(c.uni_info)}")
    print(f"tickers with prices: {len(c.tickers)}; no price data: {c.no_price}")
    print(f"trading days: {len(c.dates)} ({c.dates[0].date()}..{c.dates[-1].date()})")
    print(f"sector sizes: {json.dumps(c.sector_sizes)}")
    print(f"split check: {c.split_check}")
    print(f"auto_adjust equivalence: {results['auto_adjust_check']}")
    print(f"rows with no MarketCap_B/Price (never cap-eligible): {c.cap_missing}")
    print(f"ADR proxy (DCF_Currency_Mismatch), never eligible: {results['adr_proxy']}")
    print(f"masked splices: {json.dumps(c.splice_info)}")
    print(f"price-filter basis, pick-day eligibility flags (75 trading days): {json.dumps(c.price_basis)}")

    ch = churn(c)
    results["churn"] = ch
    print("\n## Rating proxy calibration\n")
    print(f"bucket shares of rated name-days: {json.dumps({k: round(v, 4) for k, v in ch['bucket shares'].items()})}")
    print(f"avg rated per day {ch['avg rated per day']:.0f}, avg Strong Buy per day {ch['avg SB per day']:.0f}")
    print(f"Strong Buy retained after 1 day {pct(ch['1 day'])}, 21 days {pct(ch['21 days'])}, 252 days {pct(ch['252 days'])}")
    print(f"Strong Buy after 252 days: {json.dumps({k: round(v, 4) for k, v in ch['after 252: dist'].items()})}")

    print("\n## Real Alpha Picks on their pick date (proxy view, filters as of close t-1)\n")
    print("| Ticker | Pick date | In universe | Proxy rating | SB streak (trading) | SB streak (calendar) | Nominal close t-1 | 63-day approx cap t-1 ($M) | Sector ok | ADR proxy | Eligible (75 trading) | Eligible (75 calendar) | Trading-rule pool |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    realrows = []
    for tk, d in REAL_PICKS:
        t = int(np.searchsorted(c.dates, pd.Timestamp(d)))
        pool = int(c.elig["75 trading days"][t].sum())
        if tk not in set(c.tickers):
            print(f"| {tk} | {d} | no | - | - | - | - | - | - | - | - | - | {pool} |")
            realrows.append({"ticker": tk, "date": d, "in_universe": False})
            continue
        i = int(np.flatnonzero(c.tickers == tk)[0])
        row = {"ticker": tk, "date": d, "in_universe": True, "rating": LABEL.get(int(c.R[t, i]), "unrated"),
               "sb_td": int(c.sb_run[t, i]), "sb_cal": int(max(c.sb_cal[t, i], 0)),
               "nominal_prev": float(c.nom_prev[t, i]), "cap3m_prev_m": float(c.cap_prev[t, i]),
               "sector_ok": bool(c.sector_ok[i]), "adr": bool(c.adr[i]),
               "elig_td": bool(c.elig["75 trading days"][t, i]), "elig_cal": bool(c.elig["75 calendar days"][t, i])}
        realrows.append(row)
        yn = lambda b: "yes" if b else "no"
        print(f"| {tk} | {d} | yes | {row['rating']} | {row['sb_td']} | {row['sb_cal']} | {row['nominal_prev']:.2f} | "
              f"{row['cap3m_prev_m']:.1f} | {yn(row['sector_ok'])} | {yn(row['adr'])} | {yn(row['elig_td'])} | {yn(row['elig_cal'])} | {pool} |")
    results["real_picks"] = realrows

    ff = load_ff()
    results["ff_range"] = (str(ff.index[0]), str(ff.index[-1]))
    print(f"\nKen French factors loaded: {ff.index[0]}..{ff.index[-1]}, columns {list(ff.columns)}")

    tr = "75 trading days"
    variants = []  # (streak rule, elig, selector, variant label, kwargs)
    for sel in ("score", "streak"):
        variants += [
            (tr, c.elig[tr], sel, "main", {}),
            (tr, c.elig[tr], sel, "trim off", {"trim": False}),
            (tr, c.elig[tr], sel, f"trim from {TRIM_MIN_VARIANT} holdings", {"trim_min": TRIM_MIN_VARIANT}),
            (tr, c.elig[tr], sel, "winner partial sale at Hold", {"hold_rule": "partial"}),
            (tr, c.elig_adr_allowed, sel, "ADRs allowed", {}),
        ]
    variants.append((tr, c.elig[tr], "streak-no-score2", "streak, then score only", {}))
    for sel in ("score", "streak"):
        variants += [
            ("75 calendar days", c.elig["75 calendar days"], sel, "main", {}),
            ("75 calendar days", c.elig["75 calendar days"], sel, "winner partial sale at Hold", {"hold_rule": "partial"}),
        ]

    sims = {}
    results["runs"] = {}
    for pname, (ps, pe) in PERIODS.items():
        start_i = int(np.searchsorted(c.dates, pd.Timestamp(ps)))
        end_i = int(np.searchsorted(c.dates, pd.Timestamp(pe), side="right") - 1)
        all_days = [int(p) for p in c.pick_days if start_i <= p <= end_i]
        print(f"\n## Period {pname} (sim days {c.dates[start_i].date()}..{c.dates[end_i].date()}, {len(all_days)} pick days)\n")
        spy_all = summarize(c, benchmark(c, all_days, start_i, end_i, "SPY"), True)
        for e_lab in (pe, "2026-10-29"):
            e_i = int(np.searchsorted(c.dates, pd.Timestamp(e_lab), side="right") - 1)
            tr_ret = c.spy_close[e_i] / c.spy_open[start_i] - 1.0
            nom = float(px_spy_nominal(c, start_i, e_i))
            results["runs"][f"{pname}|spy_buy_hold_to_{e_lab}"] = {"total": float(tr_ret), "price_only": nom}
            print(f"SPY buy-and-hold from the {c.dates[start_i].date()} open to the {c.dates[e_i].date()} close: "
                  f"total return {pct(tr_ret)}, price only {pct(nom)}")
        if pname.startswith("2022"):
            ap_, apb = 2.9481, 1.0019  # real Alpha Picks vs its SPY benchmark to 2026-10-30 (seeking-alpha-quant.md section 6)
            print(f"\nReal Alpha Picks to 2026-10-30: +294.81% vs SPY benchmark +100.19% -> relative {pct((1 + ap_) / (1 + apb) - 1)}")
        print("\nRelative columns use benchmarks bought on the run's own pick dates. EW share = ln(EW/SPY) / ln(run/SPY), "
              "the part of the run's log excess over SPY that the EW universe's lead over SPY accounts for.\n")
        print("| Streak rule | Selector | Variant | Picks | Names | First pick | Value/contrib | TWR | TWR CAGR | vs SPY TWR | vs EW TWR | EW share | IRR | Max DD (TWR) | Win rate | Median pick | Top-5 share | Avg holdings | Empty-pool days | Median pool | Ties: top key / to ticker | Picks that were sector leaders | Trim-inactive days (first active) | Winner sales |")
        print("|" + "---|" * 24)
        for sname, elig, sel, vlab, kw in variants:
            res = simulate(c, start_i, end_i, elig, sel, **kw)
            m = summarize(c, res)
            spy = summarize(c, benchmark(c, res["used_picks"], start_i, end_i, "SPY"), True)
            ew = summarize(c, benchmark(c, res["used_picks"], start_i, end_i, "EW universe"), True)
            vs_bench(m, spy, ew)
            m["spy_matched"], m["ew_matched"] = spy["twr"], ew["twr"]
            key = f"{pname}|{sname}|{sel}|{vlab}"
            sims[key] = res
            results["runs"][key] = m
            share = "n/a (excess < 1%)" if m["ew_share_of_excess"] is None else f"{100 * m['ew_share_of_excess']:.0f}%"
            trim_txt = "-" if m["trim_inactive_days"] is None else f"{m['trim_inactive_days']} ({m['trim_first_active']})"
            print(f"| {sname} | {sel} | {vlab} | {m['n_picks']} | {m['n_names']} | {m['first_pick']} | "
                  f"{pct(m['value_over_contrib'])} | {pct(m['twr'])} | {pct(m['twr_cagr'])} | {pct(m['twr_vs_spy'])} | {pct(m['twr_vs_ew'])} | {share} | "
                  f"{pct(m['irr'])} | {pct(m['max_dd_twr'])} ({m['dd_dates'][0]} -> {m['dd_dates'][1]}) | "
                  f"{pct(m['win_rate'], 0).lstrip('+')} | {pct(m['median_pick_ret'])} | "
                  f"{pct(m['top5_share'], 0).lstrip('+')} | {m['avg_holdings']:.1f} | {m['empty_pool_days']} | {m['median_pool']:.0f} | "
                  f"{m['ties_top']} / {m['ties_ticker']} | {m['picks_sector_leader']} | {trim_txt} | {m['winner_sales']} |")
        print("\nMatched benchmarks and top P&L names (main variants):\n")
        for sname, elig, sel, vlab, kw in variants:
            if vlab != "main":
                continue
            m = results["runs"][f"{pname}|{sname}|{sel}|{vlab}"]
            adr_picked = sorted(set(m["picked_names"]) & set(results["adr_proxy"]))
            print(f"- {sname} / {sel}: SPY on its dates {pct(m['spy_matched'])}, EW on its dates {pct(m['ew_matched'])}; "
                  f"top 5 by P&L ($ per $1 pick): {', '.join(f'{t} ({v:+.2f})' for t, v in m['top5'])}; "
                  f"open at end {m['open_at_end']}; ADR-proxy names picked {adr_picked}")

        print("\n| Streak rule | Random x N: median (p5 / p95) | Picks | Value/contrib | TWR | vs SPY TWR | vs EW TWR | IRR | Max DD | Win rate | Median pick | Top-5 share |")
        print("|---|---|---|---|---|---|---|---|---|---|---|---|")
        mc_notes = []
        for sname in c.elig:
            elig = c.elig[sname]
            mc = []
            t1 = time.time()
            for k in range(args.mc_runs):
                rng = np.random.default_rng(args.seed + k)
                res = simulate(c, start_i, end_i, elig, "random", rng=rng)
                m = summarize(c, res)
                spy = summarize(c, benchmark(c, res["used_picks"], start_i, end_i, "SPY"), True)
                ew = summarize(c, benchmark(c, res["used_picks"], start_i, end_i, "EW universe"), True)
                vs_bench(m, spy, ew)
                m["minus_spy_voc"] = m["value_over_contrib"] - spy["value_over_contrib"]
                mc.append(m)
            log(f"MC {pname} {sname}: {args.mc_runs} runs in {time.time() - t1:.0f}s")
            keys = ["value_over_contrib", "twr", "twr_vs_spy", "twr_vs_ew", "irr", "max_dd_twr", "win_rate",
                    "median_pick_ret", "top5_share", "minus_spy_voc", "log_excess_spy", "log_ew_gap"]
            q = {k: np.nanpercentile([np.nan if x[k] is None else x[k] for x in mc], [5, 50, 95]).tolist() for k in keys}
            q["n_picks"] = float(np.median([x["n_picks"] for x in mc]))
            q["beat_spy_share"] = float(np.mean([x["minus_spy_voc"] > 0 for x in mc]))
            q["beat_spy_twr_share"] = float(np.mean([x["twr_vs_spy"] > 0 for x in mc]))
            q["beat_ew_twr_share"] = float(np.mean([x["twr_vs_ew"] > 0 for x in mc]))
            q["ew_share_of_median_excess"] = q["log_ew_gap"][1] / q["log_excess_spy"][1] if q["log_excess_spy"][1] > 0.01 else None
            results["runs"][f"{pname}|{sname}|random-MC"] = q
            fmt = lambda k: f"{pct(q[k][1])} ({pct(q[k][0])} / {pct(q[k][2])})"
            print(f"| {sname} | x{args.mc_runs} | {q['n_picks']:.0f} | {fmt('value_over_contrib')} | {fmt('twr')} | {fmt('twr_vs_spy')} | {fmt('twr_vs_ew')} | "
                  f"{fmt('irr')} | {fmt('max_dd_twr')} | {fmt('win_rate')} | {fmt('median_pick_ret')} | {fmt('top5_share')} |")
            share = q["ew_share_of_median_excess"]
            mc_notes.append(f"- {sname} random: runs beating SPY on value/contrib {pct(q['beat_spy_share'], 0).lstrip('+')}, "
                            f"on TWR {pct(q['beat_spy_twr_share'], 0).lstrip('+')}; beating the EW universe on TWR "
                            f"{pct(q['beat_ew_twr_share'], 0).lstrip('+')}; median EW gap ln {q['log_ew_gap'][1]:.3f} vs median log excess "
                            f"{q['log_excess_spy'][1]:.3f} -> EW share {'n/a' if share is None else f'{100 * share:.0f}%'}")
        print("\n" + "\n".join(mc_notes))

        base = sims[f"{pname}|{tr}|score|main"]
        print("\n| Benchmark (same $1 on each pick date) | Pick dates | First | Value/contrib | TWR | TWR CAGR | IRR | Max DD (TWR) |")
        print("|---|---|---|---|---|---|---|---|")
        for kind in ("SPY", "EW universe", "EW universe, raw (splices in)"):
            for lab, days in (("all pick dates", all_days), ("score-selector dates", base["used_picks"])):
                b = benchmark(c, days, start_i, end_i, kind)
                m = summarize(c, b, True)
                results["runs"][f"{pname}|bench|{kind}|{lab}"] = m
                print(f"| {kind} | {lab} ({len(days)}) | {m['first_pick']} | {pct(m['value_over_contrib'])} | {pct(m['twr'])} | {pct(m['twr_cagr'])} | {pct(m['irr'])} | "
                      f"{pct(m['max_dd_twr'])} ({m['dd_dates'][0]} -> {m['dd_dates'][1]}) |")

    # Paper-style bucket sort
    results["paper_sort"] = {}
    sorts = {
        "splices masked": paper_sort(c),
        "raw data (splices in)": paper_sort(c, c.raw_adj_close, c.rating_close_raw),
        f"upside outlier trim (name-months > +{UPSIDE_TRIM_RET:.0%} dropped)": paper_sort(c, mode="upside"),
        f"winsorized {WINSOR_PCT[0]:.0f}/{WINSOR_PCT[1]:.0f} per month": paper_sort(c, mode="winsor"),
    }
    subperiods = (("2015-01", "2018-12"), ("2019-01", "2022-12"), ("2023-01", "2026-10"), PAPER_WINDOW)
    for sname_, ps_df in sorts.items():
        results["paper_sort"][sname_] = {}
        print(f"\n## Paper-style check ({sname_}): month-end sort, equal weight, held one month\n")
        print(f"months: {ps_df.index[0]}..{ps_df.index[-1]} ({len(ps_df)})\n")
        print("| Bucket | Mean monthly | t | Median of monthly cross-section medians | Annualized (geometric) | Cumulative | Avg names | Name-months dropped |")
        print("|---|---|---|---|---|---|---|---|")
        for col in ["Strong Buy", "Buy", "Hold", "Sell", "Strong Sell", "Rated universe", "SB-SS", "SB-SS median"]:
            s = ps_df[col].dropna()
            mean = s.mean()
            ts = tstat(s)
            g = np.prod(1 + s)
            cum = float(g - 1)
            ann = float(g ** (12 / len(s)) - 1) if g > 0 else float("nan")
            n = ps_df[col + "_n"].mean() if col + "_n" in ps_df else float("nan")
            med = float(ps_df[col + "_med"].median()) if col + "_med" in ps_df else float("nan")
            drop = int(ps_df[col + "_dropped"].sum()) if col + "_dropped" in ps_df else None
            results["paper_sort"][sname_][col] = {"mean": mean, "t": ts, "ann": ann, "cum": cum, "median": med, "dropped": drop}
            print(f"| {col} | {pct(mean, 2)} | {ts:.2f} | {pct(med, 2)} | {pct(ann)} | {pct(cum, 0)} | "
                  f"{'' if math.isnan(n) else f'{n:.0f}'} | {'' if drop is None else drop} |")
        print("\n| Sub-period (return months) | Months | Strong Buy mean | Strong Sell mean | SB-SS mean | SB-SS t | SB minus rated universe | t |")
        print("|---|---|---|---|---|---|---|---|")
        for lo, hi in subperiods:
            sub = ps_df.loc[pd.Period(lo, "M"):pd.Period(hi, "M")]
            ls = sub["SB-SS"]
            ex = sub["Strong Buy"] - sub["Rated universe"]
            tl, te = tstat(ls), tstat(ex)
            results["paper_sort"][sname_][f"{lo}..{hi}"] = {"sb": sub["Strong Buy"].mean(), "ss": sub["Strong Sell"].mean(),
                                                           "ls": ls.mean(), "ls_t": tl, "ex": ex.mean(), "ex_t": te}
            print(f"| {lo}..{hi} | {len(sub)} | {pct(sub['Strong Buy'].mean(), 2)} | {pct(sub['Strong Sell'].mean(), 2)} | "
                  f"{pct(ls.mean(), 2)} | {tl:.2f} | {pct(ex.mean(), 2)} | {te:.2f} |")

    bm = big_months(c, c.raw_adj_close, c.rating_close_raw)
    results["big_months_raw"] = bm
    print(f"\n## Name-months above +{UPSIDE_TRIM_RET:.0%} (raw data, rating at formation)\n")
    print("| Month | Ticker | Rating | Return | Adj close from -> to | Largest one-day move (date) | Masked as a verified splice |")
    print("|---|---|---|---|---|---|---|")
    for r in bm:
        print(f"| {r['month']} | {r['ticker']} | {r['rating']} | {pct(r['ret'], 0)} | {r['px_from']:.4f} -> {r['px_to']:.4f} | "
              f"{pct(r['max_1d'], 0)} ({r['max_1d_date']}) | {'yes' if r['masked_splice'] else 'no'} |")

    print("\n## Factor regressions (monthly; alpha per month)\n")
    print("| Series | Factors | Months | Alpha/month | t (OLS) | t (HAC 3) | Mkt-RF | SMB | HML | RMW | CMA | Mom | ST_Rev | R2 |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    results["regressions"] = {}

    def show(name, y, excess=True, factors=FF6):
        r = regress(y, ff, excess=excess, factors=factors)
        lab = "FF6" if factors == FF6 else "FF6+ST_Rev"
        results["regressions"][f"{name} [{lab}]"] = r
        b = r["betas"]
        cells = " | ".join(f"{b[k][0]:.2f} ({b[k][1]:.1f})" if k in b else "" for k in FF6 + ["ST_Rev"])
        print(f"| {name} | {lab} | {r['months']} ({r['first']}..{r['last']}) | {pct(r['alpha_m'], 2)} | {r['alpha_t']:.2f} | "
              f"{r['alpha_t_hac3']:.2f} | {cells} | {r['r2']:.2f} |")

    for p in PERIODS:
        for s in ("score", "streak"):
            res = sims[f"{p}|{tr}|{s}|main"]
            show(f"emulator {p} {tr} {s}", monthly_from_index(c, res["twr_idx"], res["used_picks"][0]))
    pstart = int(np.searchsorted(c.dates, pd.Timestamp("2015-01-01")))
    pend = int(np.searchsorted(c.dates, pd.Timestamp("2026-10-30"), side="right") - 1)
    pdays = [int(p) for p in c.pick_days if pstart <= p <= pend]
    for kind in ("SPY", "EW universe"):
        b = benchmark(c, pdays, pstart, pend, kind)
        show(f"{kind} benchmark, all 2015 pick dates", monthly_from_index(c, b["twr_idx"], pdays[0]))
    ps_df = sorts["splices masked"]
    pw = ps_df.loc[pd.Period(PAPER_WINDOW[0], "M"):pd.Period(PAPER_WINDOW[1], "M")]
    for factors in (FF6, FF6 + ["ST_Rev"]):
        for col in ("Strong Buy", "Hold", "Strong Sell", "Rated universe"):
            show(f"sort (splices masked): {col}", ps_df[col], factors=factors)
        show("sort (splices masked): SB-SS (no RF)", ps_df["SB-SS"], excess=False, factors=factors)
    show(f"sort (splices masked), paper window {PAPER_WINDOW[0]}..{PAPER_WINDOW[1]}: Strong Buy", pw["Strong Buy"])
    show(f"sort (splices masked), paper window {PAPER_WINDOW[0]}..{PAPER_WINDOW[1]}: SB-SS (no RF)", pw["SB-SS"], excess=False)
    for sname_ in list(sorts)[1:]:
        show(f"sort ({sname_}): Strong Sell", sorts[sname_]["Strong Sell"])
        show(f"sort ({sname_}): SB-SS (no RF)", sorts[sname_]["SB-SS"], excess=False)

    def clean(o):
        if isinstance(o, dict):
            return {str(k): clean(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [clean(v) for v in o]
        if isinstance(o, (np.floating, np.integer, np.bool_)):
            return o.item()
        return o

    (OUT / "results.json").write_text(json.dumps(clean(results), indent=1, default=str))
    log(f"done in {time.time() - t0:.0f}s; results in {OUT / 'results.json'}")


if __name__ == "__main__":
    main()
