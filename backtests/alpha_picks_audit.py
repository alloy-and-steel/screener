"""Audit Seeking Alpha's Alpha Picks record from its publicly named picks.

Reads backtests/alpha_picks_public_picks.csv (one row per pick, or per leg when
SA shows a partial close as its own row), rebuilds each pick from yfinance
prices and reports:

  1. coverage, and SA's purchase price against the pick-date open, the day's
     (H+L+C)/3 and the previous close (are the dates right? which fill does SA use?),
  2. rebuilt vs published per-pick returns,
  3. an equal-dollar portfolio (value vs contributions, and a time-weighted
     return) against SA's published +294.81% / +100.19% at 2026-10-30, the gap
     to every dated SA snapshot, the open-position count against TraderHQ's,
     and a table of sensitivity / bounding variants,
  4. concentration of the dollar gain,
  5. a Fama-French 5-factor + momentum regression of the portfolio's returns,
     its sensitivity to the holdings cutoff, and the same-date benchmark
     swapped from SPY to SPMO / MTUM / QMOM / XMMO.

Price conventions ("modes"):
  spec     - the method the task and SA's help page state: buy at the pick-date
             open, sell at the exit-date close, auto_adjust=True prices
             (dividends reinvested) for both legs.
  sa       - what SA's published per-pick numbers turn out to use (sections 1-2):
             split-adjusted prices without dividends; before 2024-07-31 the open /
             close, from 2024-07-31 the day's (High+Low+Close)/3 as a stand-in
             for the VWAP SA reportedly switched to.
  sa_late  - as sa, with the switch at 2024-10-15 (the data only bracket it).

Reproduce (network on first run; later runs read the caches):

  uv run --no-project --with yfinance --with pandas --with numpy \
      --with statsmodels --with pyarrow python -I backtests/alpha_picks_audit.py

Downloads are treated as untrusted data: prices are cached as parquet under
--cache (a ticker Yahoo returns nothing for gets a .missing marker, so later
runs do not go back to the network), Ken French zips under --ff-dir, and the
CSVs inside the zips are only parsed. Missing data is NaN/None and excluded,
never zero.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
DEFAULT_CSV = HERE / "alpha_picks_public_picks.csv"
END = pd.Timestamp("2026-10-30")          # SA's published figure is as of this close
INCEPTION = pd.Timestamp("2022-06-30")    # SA measures from the 2022-07-01 open
PRICE_START = "2022-06-01"
PRICE_END = "2026-11-07"                  # exclusive
BENCHMARKS = ["SPY", "SPMO", "MTUM", "QMOM", "XMMO"]
SA_PUBLISHED = {"alpha_picks_pct": 294.81, "sp500_pct": 100.19, "as_of": "2026-10-30"}
# Renamed tickers: the CSV keeps the symbol SA used at the pick; prices come from
# the current Yahoo symbol, which carries the full pre-rename history.
#   ATGE -> CVSA  Adtalem renamed Covista, NYSE, 2026-02-24
#                 (https://www.businesswire.com/news/home/20260205325750/en)
#   LC   -> HAPN  LendingClub moved to Nasdaq as Happen, 2026-06-22
#                 (https://lendingclub.gcs-web.com/news-releases/news-release-details/lendingclub-transfer-listing-nasdaq-new-ticker-symbol-hapn)
#   COMM -> VISN  CommScope became Vistance Networks, 2026-01-14
#                 (https://www.businesswire.com/news/home/20260112514830/en)
YF_SYMBOL = {"ATGE": "CVSA", "LC": "HAPN", "COMM": "VISN"}
# TraderHQ counts 104 picks in its 2026-09-01 data (16+24+24+24+16 by year, i.e.
# through the 2026-08-17 pick), 51 active and 53 closed. Two a month adds Sep 1,
# Sep 15, Oct 1 and Oct 15:
TOTAL_PICKS_TRADERHQ, TRADERHQ_LAST_PICK = 104, pd.Timestamp("2026-08-17")
TRADERHQ_ASOF, TRADERHQ_ACTIVE, TRADERHQ_CLOSED = pd.Timestamp("2026-09-01"), 51, 53
TRADERHQ_2026_PICKS = 16
TOTAL_PICKS_AT_END = 108
TOTAL_BY_YEAR = {2022: 16, 2023: 24, 2024: 24, 2025: 24, 2026: 20}
# Dated snapshots of SA's since-inception Total Return: (date, AP %, benchmark %,
# source). Each is taken as of that date's close (SA shows the previous close).
# Sources and caveats in docs/research/seeking-alpha-quant.md section 6 and the
# audit doc. Section 3 prints each one's benchmark against price-only SPY.
SA_SNAPSHOTS = [
    ("2022-06-30", 0.0, 0.0, "inception"),
    ("2024-04-17", 125.28, 38.69, "SA landing page (known stale)"),
    ("2024-10-04", 145.31, 51.82, "SA landing page"),
    ("2025-02-20", 136.29, 49.41, "SA help centre screenshot 'taken on February 21, 2025' (date assumed)"),
    ("2026-04-10", 316.61, 79.99, "EarnForex ('as of April 10, 2026')"),
    ("2026-06-09", 421.61, 96.50, "WallStreetZen ('as of June 9, 2026')"),
    ("2026-06-12", 415.28, 95.44, "Real World Investor (page modified 2026-06-12)"),
    ("2026-07-17", 371.06, 99.68, "MatchMyBroker, per search index"),
    ("2026-10-01", 352.65, 102.43, "Smart Money with Kai (page 'Last updated October 1, 2026')"),
    ("2026-10-27", 300.99, 102.75, "Retire Before Dad"),
    ("2026-10-30", 294.81, 100.19, "MatchMyBroker ('to 30 October 2026')"),
]
SNAPSHOT_BASE = pd.Timestamp("2024-10-04")  # first snapshot after coverage fills in
SPY_CHECK_TOL_PP = 1.0                      # snapshot flagged if its benchmark is further than this from price-only SPY
# SA "Holding %" column, Portfolio > Current, as of 2026-10-27 (Retire Before Dad fig. 8).
SA_HOLDING_PCT_20261027 = {"B": 0.69, "TIGO": 1.06, "W": 0.92, "PARR": 1.26,
                           "INCY": 1.00, "MU": 3.61, "TTMI": 1.29}
# Lowest return among the 13 rows of SA's Performance tab sorted by return on
# 2026-10-27 (RBD fig. 11): any other pick had a lower return that day.
SA_TOP13_FLOOR_PCT_20261027 = 254.66
# Wall Street Survivor's per-year table of all picks, "thru Saturday 09/26/2026":
# year -> (picks, mean return %, mean same-date S&P %, % profitable).
WSS_ASOF = pd.Timestamp("2026-09-25")
WSS_COHORTS = {2022: (16, 106.8, 29.2, 75), 2023: (24, 209.2, 46.8, 79), 2024: (24, 78.3, 30.0, 71),
               2025: (24, 59.1, 21.5, 75), 2026: (18, None, None, None)}
WSS_ALL = (106, 93.8, 27.9, 72)
# VWAP-style fills: AlphaYou (secondary) dates the switch 2024-07-31. SA's own
# prices only bracket it (section 1b), so a later switch is run as a variant.
SWITCH_OF = {"sa": pd.Timestamp("2024-07-31"), "sa_late": pd.Timestamp("2024-10-15")}
VWAP_SWITCH = SWITCH_OF["sa"]
# The Perpetual Alpha Current-tab mirror: live table newest row 2025-10-15, still
# lists LRN (closed 2025-11-04); archived copy of 2025-07-13 (captured 01:54 UTC,
# so it shows at least the 2025-07-11 state).
STATUS_CUTOFF = pd.Timestamp("2025-10-15")
ARCHIVE_STATE, LIVE_STATE_LATEST = pd.Timestamp("2025-07-11"), pd.Timestamp("2025-11-03")
# Held in the 2025-07-13 archive, absent from the live table: closed in between.
EXIT_WINDOW_PICKS = ["PEP 2024-01-16", "GM 2024-05-01", "ITRN 2025-02-18"]
# Off-schedule pick dates from blog post dates, and SA's 1st/15th schedule date.
SCHEDULE_DATES = {"EZPW 2025-04-03": pd.Timestamp("2025-04-01"), "MFC 2025-05-02": pd.Timestamp("2025-05-01")}
# Closed rows tagged Winner without a documented partial sale.
WINNER_TAG_NO_TRIM = ["SFM 2024-06-17", "AGX 2024-10-15"]
FF_URLS = {
    "ff5_monthly": "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_5_Factors_2x3_CSV.zip",
    "mom_monthly": "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Momentum_Factor_CSV.zip",
    "ff5_daily": "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_5_Factors_2x3_daily_CSV.zip",
    "mom_daily": "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Momentum_Factor_daily_CSV.zip",
}
FACTORS = ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "UMD"]
BATCH = 200
MIN_POSITIONS_FOR_REGRESSION = 10
POSITION_CUTOFFS = [5, 10, 15, 20, 25, 30]


# =========================================================================== data

def fetch_prices(tickers: list[str], cache: Path, adjusted: bool) -> dict[str, pd.DataFrame]:
    """Daily OHLC per (CSV) ticker, fetched under its current Yahoo symbol and
    cached as parquet. adjusted=True is auto_adjust=True (Open and Close scaled
    by the same dividend+split factor); adjusted=False is Yahoo's
    split-adjusted, dividend-unadjusted OHLC. A symbol Yahoo returns nothing
    for gets a .missing marker (delete it to retry)."""
    tag = "adj" if adjusted else "raw"
    cache.mkdir(parents=True, exist_ok=True)
    out: dict[str, pd.DataFrame] = {}
    missing = []
    for t in tickers:
        sym = YF_SYMBOL.get(t, t)
        p = cache / f"{sym}_{tag}.parquet"
        if p.exists():
            out[t] = pd.read_parquet(p)
        elif not (cache / f"{sym}_{tag}.missing").exists():
            missing.append(t)
    if missing:
        import yfinance as yf
        yf.set_tz_cache_location(str(cache / "yf_tz"))
        for i in range(0, len(missing), BATCH):
            batch = missing[i:i + BATCH]
            syms = [YF_SYMBOL.get(t, t) for t in batch]
            df = yf.download(syms, start=PRICE_START, end=PRICE_END, auto_adjust=adjusted,
                             group_by="ticker", progress=False, threads=True, actions=False)
            for t, sym in zip(batch, syms):
                sub = None
                if isinstance(df.columns, pd.MultiIndex):
                    if sym in df.columns.get_level_values(0):
                        sub = df[sym]
                else:
                    sub = df
                if sub is not None:
                    sub = sub[["Open", "High", "Low", "Close"]].dropna(how="any")
                if sub is None or sub.empty:
                    (cache / f"{sym}_{tag}.missing").write_text(f"no data from yfinance on {pd.Timestamp.now().date()}\n")
                    continue
                sub.index = pd.to_datetime(sub.index).tz_localize(None)
                sub.to_parquet(cache / f"{sym}_{tag}.parquet")
                out[t] = sub
    return out


def _read_french_csv(raw: bytes, daily: bool) -> pd.DataFrame:
    """First data block of a Ken French CSV, percent -> decimal."""
    rows, header = [], None
    for line in raw.decode("latin-1").splitlines():
        cells = [c.strip() for c in line.split(",")]
        if header is None:
            if len(cells) > 1 and cells[0] == "" and cells[1]:
                header = cells[1:]
            continue
        key = cells[0]
        if not (key.isdigit() and len(key) == (8 if daily else 6)):
            if rows:
                break
            continue
        rows.append([key] + cells[1:1 + len(header)])
    df = pd.DataFrame(rows, columns=["date"] + header)
    df["date"] = pd.to_datetime(df["date"], format="%Y%m%d" if daily else "%Y%m")
    df = df.set_index("date").apply(pd.to_numeric, errors="coerce") / 100.0
    if not daily:
        df.index = df.index.to_period("M")
    return df


def fetch_french(ff_dir: Path) -> dict[str, pd.DataFrame]:
    ff_dir.mkdir(parents=True, exist_ok=True)
    out = {}
    for key, url in FF_URLS.items():
        p = ff_dir / (key + ".zip")
        if not p.exists():
            with urllib.request.urlopen(url, timeout=60) as r:  # fixed https URL
                p.write_bytes(r.read())
        with zipfile.ZipFile(p) as z:
            name = [n for n in z.namelist() if n.lower().endswith(".csv")][0]
            out[key] = _read_french_csv(z.read(name), daily=key.endswith("daily"))
    return out


# =========================================================================== picks

def _f(x):
    x = (x or "").strip()
    return float(x) if x else None


def _d(x):
    x = (x or "").strip()
    return pd.Timestamp(x) if x else None


@dataclass
class Leg:
    ticker: str
    pick_date: pd.Timestamp | None
    exit_date: pd.Timestamp | None
    published_pct: float | None
    as_of: pd.Timestamp | None
    source: str
    leg: str                      # full | trim | remainder
    pub_buy: float | None
    pub_sell: float | None
    pub_spy: float | None
    status: str                   # open | closed | unknown | closed_exit_unknown
    survivor_only: bool           # only evidence: the ~2025-10-15 Current-tab mirror
    notes: str


def load_legs(path: Path) -> list[Leg]:
    with open(path, newline="") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        if r["survivor_table_only"].strip() not in ("yes", "no"):
            raise SystemExit(f"bad survivor_table_only for {r['ticker']}: {r['survivor_table_only']!r}")
    return [Leg(r["ticker"].strip(), _d(r["pick_date"]), _d(r["exit_date"]),
                _f(r["published_return_pct"]), _d(r["as_of"]), r["source_url"].strip(),
                r["leg"].strip(), _f(r["published_purchase_price"]),
                _f(r["published_sell_price"]), _f(r["published_spy_pct"]),
                r["status"].strip(), r["survivor_table_only"].strip() == "yes", r["notes"].strip())
            for r in rows]


@dataclass
class Pick:
    ticker: str
    pick_date: pd.Timestamp
    legs: list[Leg] = field(default_factory=list)
    excluded: str | None = None
    entry: pd.Timestamp | None = None

    @property
    def label(self) -> str:
        return f"{self.ticker} {self.pick_date.date()}"

    @property
    def trim_leg(self) -> Leg | None:
        return next((lg for lg in self.legs if lg.leg == "trim"), None)

    @property
    def final_exit(self) -> pd.Timestamp | None:
        """Exit of the last-held shares; None if still held."""
        final = [lg for lg in self.legs if lg.leg != "trim"]
        return final[0].exit_date if final else self.trim_leg.exit_date

    @property
    def status_known(self) -> bool:
        return all(lg.status in ("open", "closed") for lg in self.legs)

    @property
    def survivor_only(self) -> bool:
        return all(lg.survivor_only for lg in self.legs)

    @property
    def homepage_only(self) -> bool:
        return all(lg.source == "https://www.perpetual-alpha.com/" for lg in self.legs)

    @property
    def date_tested(self) -> bool:
        """A published purchase price or a dated published return exists."""
        return any(lg.pub_buy is not None or (lg.published_pct is not None and lg.as_of is not None)
                   for lg in self.legs)


def group_picks(legs: list[Leg]) -> tuple[list[Pick], list[Leg]]:
    picks: dict[tuple, Pick] = {}
    undated = []
    for lg in legs:
        if lg.pick_date is None:
            undated.append(lg)
            continue
        picks.setdefault((lg.ticker, lg.pick_date), Pick(lg.ticker, lg.pick_date)).legs.append(lg)
    return sorted(picks.values(), key=lambda p: (p.pick_date, p.ticker)), undated


def on_or_after(idx: pd.DatetimeIndex, d: pd.Timestamp):
    i = idx.searchsorted(d, side="left")
    return idx[i] if i < len(idx) else None


def on_or_before(idx: pd.DatetimeIndex, d: pd.Timestamp):
    i = idx.searchsorted(d, side="right") - 1
    return idx[i] if i >= 0 else None


# =========================================================================== prices per mode

def _vwap_proxy(mode: str, d: pd.Timestamp) -> bool:
    return mode in SWITCH_OF and d >= SWITCH_OF[mode]


def buy_px(df: pd.DataFrame, d: pd.Timestamp, mode: str) -> float:
    r = df.loc[d]
    if _vwap_proxy(mode, d):
        return float((r["High"] + r["Low"] + r["Close"]) / 3.0)
    return float(r["Open"])


def sell_px(df: pd.DataFrame, d: pd.Timestamp, mode: str) -> float:
    r = df.loc[d]
    if _vwap_proxy(mode, d):
        return float((r["High"] + r["Low"] + r["Close"]) / 3.0)
    return float(r["Close"])


def leg_return(df: pd.DataFrame, entry: pd.Timestamp, d: pd.Timestamp, mode: str, closed: bool):
    """Return from the entry to d: the exit fill if the leg closed on d, else the close."""
    d2 = on_or_before(df.index, d)
    if d2 is None or d2 < entry:
        return None
    exit_price = sell_px(df, d2, mode) if closed else float(df.loc[d2, "Close"])
    return exit_price / buy_px(df, entry, mode) - 1.0


# =========================================================================== portfolio

@dataclass
class Position:
    label: str
    ticker: str
    pick_date: pd.Timestamp
    entry: pd.Timestamp
    trim_date: pd.Timestamp | None
    exit_date: pd.Timestamp | None       # None = held at END


def plan_positions(picks: list[Pick], cal_of: dict, trims: str = "initial", exit_over: dict | None = None,
                   entry_over: dict | None = None, trim_over: dict | None = None) -> list[Position]:
    """trims='initial': at a documented partial close sell $1 of stock (SA's
    'winner' rule: sell the initial purchase amount). trims='none': ignore
    partial closes. exit_over: {label: final exit date}; entry_over: {label:
    entry date}; trim_over: {label: date of an undocumented $1 sale}."""
    exit_over, entry_over, trim_over = exit_over or {}, entry_over or {}, trim_over or {}
    out = []
    for p in picks:
        idx = cal_of[p.ticker]
        tl = p.trim_leg
        has_remainder = any(lg.leg == "remainder" for lg in p.legs)
        trim_date = on_or_before(idx, tl.exit_date) if (trims == "initial" and tl and has_remainder) else None
        if p.label in trim_over:
            trim_date = trim_over[p.label]
        ex = exit_over.get(p.label, p.final_exit)
        if p.label in exit_over and tl is not None and ex == tl.exit_date:
            trim_date = None                      # whole position closed on the trim date
        exit_d = on_or_before(idx, ex) if ex is not None and ex <= END else None
        entry = on_or_after(idx, entry_over[p.label]) if p.label in entry_over else p.entry
        out.append(Position(p.label, p.ticker, p.pick_date, entry, trim_date, exit_d))
    return out


def simulate(positions: list[Position], prices: dict, mode: str, mirror: str | None = None) -> dict:
    """$1 per pick. With mirror=<ETF>, each position holds that ETF over the same
    dates instead (same buy day, same sell days, same fraction sold at a trim)."""
    cal = prices["SPY"].index
    cal = cal[(cal >= min(p.entry for p in positions)) & (cal <= END)]
    hold_val = pd.DataFrame(0.0, index=cal, columns=range(len(positions)))
    buys = pd.Series(0.0, index=cal)
    procs = pd.Series(0.0, index=cal)
    per = []
    for j, pos in enumerate(positions):
        own = prices[pos.ticker]
        src = prices[mirror] if mirror else own
        close = src["Close"].reindex(cal).ffill()
        shares = 1.0 / buy_px(src, pos.entry, mode)
        sh = pd.Series(shares, index=cal)
        sh[cal < pos.entry] = 0.0
        proceeds = 0.0
        if pos.trim_date is not None:
            own_val = sell_px(own, pos.trim_date, mode) / buy_px(own, pos.entry, mode)
            frac = min(1.0, 1.0 / own_val) if own_val > 0 else 0.0
            sold = shares * frac
            p_ = sold * sell_px(src, pos.trim_date, mode)
            procs.loc[pos.trim_date] += p_
            proceeds += p_
            sh[cal >= pos.trim_date] = shares - sold
        if pos.exit_date is not None:
            rem = sh.loc[pos.exit_date]
            p_ = rem * sell_px(src, pos.exit_date, mode)
            procs.loc[pos.exit_date] += p_
            proceeds += p_
            sh[cal >= pos.exit_date] = 0.0
        buys.loc[pos.entry] += 1.0
        hold_val[j] = sh * close
        end_val = proceeds + hold_val[j].iloc[-1]
        per.append({"label": pos.label, "ticker": pos.ticker, "entry": pos.entry,
                    "return": end_val - 1.0})
    H = hold_val.sum(axis=1)
    Hprev = H.shift(1).fillna(0.0)
    denom = Hprev + buys
    # Buys happen at (about) the open, sales at the close: Modified-Dietz per day.
    daily = (H + procs - Hprev - buys) / denom.where(denom > 0)
    return {"daily": daily.dropna(), "holdings": H, "cash": procs.cumsum(),
            "contrib": buys.cumsum(), "per_pick": pd.DataFrame(per), "hold_val": hold_val,
            "n_open": (hold_val > 0).sum(axis=1)}


def summarize(sim: dict) -> dict:
    v = (sim["holdings"].iloc[-1] + sim["cash"].iloc[-1]) / sim["contrib"].iloc[-1] - 1
    pp = sim["per_pick"]["return"]
    return {"value_over_contrib": v, "twr": float((1 + sim["daily"]).prod() - 1),
            "avg": float(pp.mean()), "median": float(pp.median()), "n": int(len(pp))}


def twr_between(daily: pd.Series, a: pd.Timestamp, b: pd.Timestamp) -> float:
    s = daily[(daily.index > a) & (daily.index <= b)]
    return float((1 + s).prod() - 1)


def open_on(pos: list[Position], d: pd.Timestamp, last_pick: pd.Timestamp) -> int:
    """Positions picked by last_pick with shares still held after the close of d."""
    return sum(1 for p in pos if p.pick_date <= last_pick and p.entry <= d
               and (p.exit_date is None or p.exit_date > d))


def concentration(per_pick: pd.DataFrame) -> dict:
    pp = per_pick.sort_values("return", ascending=False).reset_index(drop=True)
    g = pp["return"]
    net, gross = float(g.sum()), float(g[g > 0].sum())
    return {"pp": pp, "net": net, "gross": gross,
            "net_share": {k: float(g.iloc[:k].sum() / net) for k in (1, 3, 5, 10)},
            "gross_share": {k: float(g.iloc[:k].sum() / gross) for k in (1, 3, 5, 10)}}


def value_asof(pos: Position, own: pd.DataFrame, src: pd.DataFrame, d: pd.Timestamp, mode: str) -> float:
    """Value on date d of $1 put into pos (or, with src=an ETF, into that ETF over
    the same dates): trim proceeds + sale proceeds + remaining shares at d's close."""
    d = on_or_before(src.index, d)
    shares = 1.0 / buy_px(src, pos.entry, mode)
    val = 0.0
    if pos.trim_date is not None and pos.trim_date <= d:
        own_val = sell_px(own, pos.trim_date, mode) / buy_px(own, pos.entry, mode)
        frac = min(1.0, 1.0 / own_val) if own_val > 0 else 0.0
        val += shares * frac * sell_px(src, pos.trim_date, mode)
        shares *= 1 - frac
    if pos.exit_date is not None and pos.exit_date <= d:
        return val + shares * sell_px(src, pos.exit_date, mode)
    return val + shares * float(src.loc[d, "Close"])


# =========================================================================== regressions

def regress(y: pd.Series, X: pd.DataFrame, per_year: int, hac_lags: int) -> dict:
    import statsmodels.api as sm
    Xc = sm.add_constant(X)
    ols = sm.OLS(y, Xc).fit()
    hac = sm.OLS(y, Xc).fit(cov_type="HAC", cov_kwds={"maxlags": hac_lags})
    a = float(ols.params["const"])
    return {"n": int(ols.nobs), "alpha": a, "alpha_annual": a * per_year,
            "t_ols": float(ols.tvalues["const"]), "t_hac": float(hac.tvalues["const"]),
            "loadings": {k: (float(ols.params[k]), float(ols.tvalues[k])) for k in X.columns},
            "r2": float(ols.rsquared), "start": str(y.index.min()), "end": str(y.index.max())}


def monthly(daily: pd.Series) -> pd.Series:
    return (1 + daily).groupby(daily.index.to_period("M")).prod() - 1


def ff6_monthly(daily: pd.Series, fac_m: pd.DataFrame, start: pd.Timestamp | None = None) -> dict:
    """Monthly six-factor regression; with start, months after start's month only."""
    if start is not None:
        daily = daily[daily.index >= start]
    r = monthly(daily)
    if start is not None:
        r = r[r.index > start.to_period("M")]   # drop the partial first month
    j = pd.concat([r.rename("r"), fac_m], axis=1, join="inner").dropna()
    return regress(j["r"] - j["RF"], j[FACTORS], 12, 3)


def first_with(n_open: pd.Series, k: int):
    s = n_open[n_open >= k]
    return None if s.empty else s.index.min()


def pct(x, nd=2):
    return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{100 * x:+.{nd}f}%"


# =========================================================================== main

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    ap.add_argument("--cache", type=Path, default=Path("/tmp/sa-tests/cache"))
    ap.add_argument("--ff-dir", type=Path, default=Path("/tmp/sa-tests/ff"))
    ap.add_argument("--json", type=Path, default=None, help="optional JSON dump of the results")
    args = ap.parse_args()

    legs = load_legs(args.csv)
    picks, undated = group_picks(legs)
    tickers = sorted({p.ticker for p in picks} | set(BENCHMARKS))
    adj = fetch_prices(tickers, args.cache, adjusted=True)
    raw = fetch_prices(tickers, args.cache, adjusted=False)
    for b in BENCHMARKS:
        if b not in adj or b not in raw:
            raise SystemExit(f"benchmark {b} has no price data; refusing to continue")
    out: dict = {}
    print("=" * 78)
    print(f"ALPHA PICKS PUBLIC-PICKS AUDIT   end date {END.date()}")
    print("=" * 78)

    # ------------------------------------------------------------ 1. coverage
    for p in picks:
        if p.ticker in adj and p.ticker in raw:
            p.entry = on_or_after(adj[p.ticker].index, p.pick_date)
        if any(lg.status == "closed_exit_unknown" for lg in p.legs):
            p.excluded = "closed, exit date not published"
        elif p.ticker not in adj or p.ticker not in raw:
            p.excluded = "no yfinance price data"
        elif p.entry is None or p.entry > END:
            p.excluded = "no price on/after the pick date"
    for p in picks:      # partly-redacted names must be confirmed by SA's purchase price
        if p.excluded or "redaction" not in " ".join(lg.notes for lg in p.legs):
            continue
        b = p.legs[0].pub_buy
        r = raw[p.ticker].loc[p.entry]
        if b is None or not (r["Low"] * 0.995 <= b <= r["High"] * 1.005):
            p.excluded = f"redacted name not confirmed: SA price {b} outside the day's range"
    used = [p for p in picks if not p.excluded]
    by_year = pd.Series([p.pick_date.year for p in used]).value_counts().sort_index()
    print(f"\n[1] COVERAGE  rows {len(legs)}, dated picks {len(picks)}, undated rows {len(undated)}")
    print(f"  usable dated picks: {len(used)} of {TOTAL_PICKS_AT_END} made by {END.date()} "
          f"({sum(p.pick_date <= TRADERHQ_LAST_PICK for p in used)} of the {TOTAL_PICKS_TRADERHQ} "
          f"in TraderHQ's count through {TRADERHQ_LAST_PICK.date()})")
    print("  by year (usable / total):",
          ", ".join(f"{y}: {int(by_year.get(y, 0))}/{n}" for y, n in TOTAL_BY_YEAR.items()))
    print(f"  renamed tickers priced under their current symbol: "
          f"{', '.join(f'{a}->{b}' for a, b in YF_SYMBOL.items())}")
    unknown = [p for p in used if not p.status_known]
    print(f"  status after {STATUS_CUTOFF.date()} documented for "
          f"{sum(p.status_known for p in used)} of {len(used)}; the other {len(unknown)} are modelled as open")
    surv = [p for p in used if p.survivor_only]
    home = [p for p in used if p.homepage_only]
    print(f"  picks whose only evidence is the ~{STATUS_CUTOFF.date()} Current-tab mirror (survivor list): "
          f"{len(surv)} of {len(used)} ({len(home)} cite only the mirror's table, "
          f"{len(surv) - len(home)} a pick note for a name in it)")
    print("    by year:", ", ".join(f"{y}: {sum(p.pick_date.year == y for p in surv)}/{int(by_year.get(y, 0))}"
                                   for y in TOTAL_BY_YEAR))
    src_kind = pd.Series(["survivor list" if p.survivor_only else
                          ("published price or return" if any(lg.pub_buy is not None or lg.published_pct is not None for lg in p.legs)
                           else "other") for p in used]).value_counts()
    print("  usable picks by kind of evidence:", {k: int(v) for k, v in src_kind.items()})
    for p in picks:
        if p.excluded:
            print(f"  excluded {p.label}: {p.excluded}")
    print("  excluded (no pick date):", ", ".join(lg.ticker for lg in undated))
    moved = [p.label for p in used if p.entry != p.pick_date]
    print("  pick date not a trading day, entry at the next session:", moved or "none")
    tested = [p for p in used if p.date_tested]
    print(f"  pick dates testable against a published price or return: {len(tested)} of {len(used)}; untested: "
          f"{', '.join(p.label for p in used if not p.date_tested)}")
    out["coverage"] = {"usable": len(used), "by_year": {int(k): int(v) for k, v in by_year.items()},
                       "excluded": {p.label: p.excluded for p in picks if p.excluded},
                       "undated": [lg.ticker for lg in undated], "survivor_only": len(surv),
                       "homepage_only": len(home), "unknown_status": len(unknown), "date_tested": len(tested)}

    # ------------------------------------------------------------ 1b. purchase price check
    print(f"\n[1b] SA PURCHASE PRICE vs yfinance split-adjusted, dividend-unadjusted prices on the entry day")
    print(f"  {'pick':17s} {'SA buy':>9s} {'open':>9s} {'low':>9s} {'high':>9s} {'(H+L+C)/3':>9s} {'prev cls':>9s} "
          f"{'vs open':>8s} {'vs (H+L+C)/3':>12s} {'vs prev':>8s}")
    rows = []
    for p in used:
        b = next((lg.pub_buy for lg in p.legs if lg.pub_buy), None)
        if b is None:
            continue
        df = raw[p.ticker]
        r = df.loc[p.entry]
        prev = df["Close"].iloc[df.index.get_loc(p.entry) - 1]
        typ = (r["High"] + r["Low"] + r["Close"]) / 3
        inr = r["Low"] * 0.995 <= b <= r["High"] * 1.005
        rows.append({"pick": p.label, "entry": p.entry, "after": p.entry >= VWAP_SWITCH, "vs_open": b / r["Open"] - 1,
                     "vs_typ": b / typ - 1, "vs_prev": b / prev - 1, "in_range": bool(inr)})
        print(f"  {p.label:17s} {b:9.2f} {r['Open']:9.2f} {r['Low']:9.2f} {r['High']:9.2f} {typ:9.2f} {prev:9.2f} "
              f"{100 * (b / r['Open'] - 1):+7.2f}% {100 * (b / typ - 1):+11.2f}% {100 * (b / prev - 1):+7.2f}%"
              f"{'' if inr else '  outside range'}")
    chk = pd.DataFrame(rows)
    for flag, g in chk.groupby("after"):
        print(f"  picks {'on/after' if flag else 'before'} {VWAP_SWITCH.date()}: n={len(g)}; median |vs open| "
              f"{100 * g.vs_open.abs().median():.2f}%, median |vs (H+L+C)/3| {100 * g.vs_typ.abs().median():.2f}%; "
              f"exactly the open (<0.1%): {int((g.vs_open.abs() < 0.001).sum())}; exactly the previous close (<0.1%): "
              f"{int((g.vs_prev.abs() < 0.001).sum())}; in day's range {int(g.in_range.sum())}/{len(g)}")
    at_open = chk[chk.vs_open.abs() < 0.001]
    not_open = chk[(chk.vs_open.abs() >= 0.001) & (chk.entry > at_open.entry.max())]
    print(f"  switch bracket from purchase prices: last fill at the open {at_open.entry.max().date()}, "
          f"first later fill not at the open {not_open.entry.min().date()}")
    print("  SA sell price vs the exit day's close and (H+L+C)/3:")
    sells = []
    for p in used:
        for lg in p.legs:
            if lg.pub_sell is None or lg.exit_date is None:
                continue
            d = on_or_before(raw[p.ticker].index, lg.exit_date)
            r = raw[p.ticker].loc[d]
            typ = (r["High"] + r["Low"] + r["Close"]) / 3
            sells.append((d, abs(lg.pub_sell / r["Close"] - 1) < 0.001))
            print(f"    {p.label:17s} {lg.leg:9s} sold {lg.exit_date.date()} at {lg.pub_sell:8.2f}: close {r['Close']:8.2f} "
                  f"({100 * (lg.pub_sell / r['Close'] - 1):+.2f}%), (H+L+C)/3 {typ:8.2f} ({100 * (lg.pub_sell / typ - 1):+.2f}%)")
    last_close = max(d for d, ok in sells if ok)
    first_not = min(d for d, ok in sells if not ok and d > last_close)
    print(f"  switch bracket from sell prices: last sale at the close {last_close.date()}, "
          f"first later sale not at the close {first_not.date()}")
    out["purchase_check"] = chk.drop(columns="entry").to_dict("records")

    # ------------------------------------------------------------ 2. per-leg comparison
    print("\n[2] REBUILT vs PUBLISHED, per leg, to the published as_of close (or the exit)")
    print("    spec = open->close, dividends reinvested;  sa = no dividends, (H+L+C)/3 fills from 2024-07-31;")
    print("    sa_px = SA's own purchase/sell price where published, no dividends (tests the price convention only)")
    print(f"  {'pick':17s} {'leg':9s} {'as_of':10s} {'published':>10s} {'spec':>10s} {'sa':>10s} {'sa_px':>10s} "
          f"{'SPY pub':>8s} {'SPY sa':>8s} {'SPY spec':>8s}")
    cmp_rows = []
    for p in used:
        for lg in p.legs:
            if lg.published_pct is None or lg.as_of is None:
                continue
            closed = lg.exit_date is not None and lg.exit_date <= lg.as_of
            d = lg.exit_date if closed else lg.as_of
            spec = leg_return(adj[p.ticker], p.entry, d, "spec", closed)
            sa = leg_return(raw[p.ticker], p.entry, d, "sa", closed)
            sa_late = leg_return(raw[p.ticker], p.entry, d, "sa_late", closed)
            sa_px = None
            if lg.pub_buy:
                if closed and lg.pub_sell:
                    sa_px = lg.pub_sell / lg.pub_buy - 1
                elif not closed:
                    sa_px = raw[p.ticker].loc[on_or_before(raw[p.ticker].index, d), "Close"] / lg.pub_buy - 1
            spy_sa = leg_return(raw["SPY"], p.entry, d, "sa", closed)
            spy_spec = leg_return(adj["SPY"], p.entry, d, "spec", closed)
            row = {"pick": p.label, "leg": lg.leg, "as_of": str(lg.as_of.date()), "published": lg.published_pct,
                   "spec": spec, "sa": sa, "sa_late": sa_late, "sa_px": sa_px, "spy_pub": lg.pub_spy,
                   "spy_sa": spy_sa, "spy_spec": spy_spec}
            cmp_rows.append(row)
            f = lambda x: "" if x is None else f"{100 * x:+9.2f}%"
            print(f"  {p.label:17s} {lg.leg:9s} {row['as_of']:10s} {lg.published_pct:+9.2f}% {f(spec):>10s} "
                  f"{f(sa):>10s} {f(sa_px):>10s} {'' if lg.pub_spy is None else f'{lg.pub_spy:+7.2f}%':>8s} "
                  f"{f(spy_sa):>8s} {f(spy_spec):>8s}")
    cdf = pd.DataFrame(cmp_rows)

    def err(col, ref="published", scale=100.0):
        s = cdf.dropna(subset=[col, ref])
        e = ((1 + s[col]) / (1 + s[ref] / scale) - 1).abs()
        return len(s), float(e.median()), int((e < 0.005).sum()), int((e < 0.02).sum()), len({x for x in s["pick"]})
    for col in ("spec", "sa", "sa_late", "sa_px"):
        n, med, w05, w2, npk = err(col)
        print(f"  {col:7s}: n={n} legs ({npk} picks), median |growth error| {100 * med:.2f}%, "
              f"within 0.5%: {w05}, within 2%: {w2}")
    for col in ("spy_sa", "spy_spec"):
        n, med, w05, w2, _ = err(col, "spy_pub")
        print(f"  SPY {col[4:]:4s}: n={n}, median |growth error| vs SA's SPY column {100 * med:.2f}%, within 0.5%: {w05}")
    out["per_leg"] = cmp_rows

    # ------------------------------------------------------------ 2b. consistency with SA's top-13 list
    d27 = pd.Timestamp("2026-10-27")
    in_top = {(lg.ticker, lg.pick_date) for p in used for lg in p.legs
              if lg.as_of == d27 and (lg.published_pct or 0) >= SA_TOP13_FLOOR_PCT_20261027}
    viol = []
    for p in used:
        if (p.ticker, p.pick_date) in in_top or (p.final_exit is not None and p.final_exit <= d27):
            continue
        r = leg_return(raw[p.ticker], p.entry, d27, "sa", False)
        if r is not None and 100 * r > SA_TOP13_FLOOR_PCT_20261027:
            viol.append((p.label, round(100 * r, 1)))
    print(f"\n[2b] picks modelled as held on {d27.date()} with a rebuilt return above SA's top-13 floor "
          f"({SA_TOP13_FLOOR_PCT_20261027}%) but missing from SA's list: {viol or 'none'}")
    out["top13_conflicts"] = viol

    # ------------------------------------------------------------ 3. portfolios
    ff = fetch_french(args.ff_dir)
    mm = ff["mom_monthly"].rename(columns=lambda c: "UMD" if c.lower().startswith("mom") else c)
    dm = ff["mom_daily"].rename(columns=lambda c: "UMD" if c.lower().startswith("mom") else c)
    fac_m = ff["ff5_monthly"].join(mm[["UMD"]], how="inner")
    fac_d = ff["ff5_daily"].join(dm[["UMD"]], how="inner")

    cal_of = {t: adj[t].index for t in adj}
    by_label = {p.label: p for p in picks}
    known = [p for p in used if p.status_known]
    window = [by_label[x] for x in EXIT_WINDOW_PICKS]
    for p in window:
        if p.entry is None:
            raise SystemExit(f"{p.label}: no price data for the exit-window variant")
    unk_close = lambda d: {p.label: d for p in unknown}
    # Winner-tag sale: sell $1 at the first close at >= 2x the entry open (the
    # earliest date the 'winner' label can apply; SA's rule sells only after a
    # further 180 days at Hold, so the real sale, if any, was later).
    winner_trim = {}
    for lbl in WINNER_TAG_NO_TRIM:
        p = by_label[lbl]
        df = adj[p.ticker]
        s = df["Close"][(df.index >= p.entry) & (df.index <= (p.final_exit or END))]
        hit = s[s >= 2.0 * df.loc[p.entry, "Open"]]
        winner_trim[lbl] = None if hit.empty else hit.index.min()
    print(f"\n[3] PORTFOLIO: $1 per pick at entry, held to exit, sale proceeds kept as 0% cash")
    print("  winner-tag sale dates (first close >= 2x entry, spec prices):",
          {k: (None if v is None else str(v.date())) for k, v in winner_trim.items()})
    winner_trim = {k: v for k, v in winner_trim.items() if v is not None}
    variants = {
        "spec (base)": (used, "spec", "initial", {}, {}, {}),
        "spec, no trims": (used, "spec", "none", {}, {}, {}),
        "spec, POWL fully closed 2026-09-08": (used, "spec", "initial", {"POWL 2023-05-15": pd.Timestamp("2026-09-08")}, {}, {}),
        "spec, AGX+SFM winner sale": (used, "spec", "initial", {}, {}, winner_trim),
        "spec, EZPW+MFC on schedule dates": (used, "spec", "initial", {}, SCHEDULE_DATES, {}),
        "spec, documented status only": (known, "spec", "initial", {}, {}, {}),
        "spec, drop table-cited rows": ([p for p in used if not p.homepage_only], "spec", "initial", {}, {}, {}),
        "spec, drop survivor-list picks": ([p for p in used if not p.survivor_only], "spec", "initial", {}, {}, {}),
        f"spec, unknown closed {STATUS_CUTOFF.date()}": (used, "spec", "initial", unk_close(STATUS_CUTOFF), {}, {}),
        f"spec, unknown closed {(STATUS_CUTOFF + pd.Timedelta(days=180)).date()}":
            (used, "spec", "initial", unk_close(STATUS_CUTOFF + pd.Timedelta(days=180)), {}, {}),
        f"spec, +PEP/GM/ITRN closed {on_or_after(cal_of['SPY'], ARCHIVE_STATE + pd.Timedelta(days=1)).date()}":
            (used + window, "spec", "initial", {p.label: on_or_after(cal_of[p.ticker], ARCHIVE_STATE + pd.Timedelta(days=1)) for p in window}, {}, {}),
        f"spec, +PEP/GM/ITRN closed {LIVE_STATE_LATEST.date()}":
            (used + window, "spec", "initial", {p.label: LIVE_STATE_LATEST for p in window}, {}, {}),
        "sa (no dividends, VWAP proxy)": (used, "sa", "initial", {}, {}, {}),
        "sa, VWAP switch 2024-10-15": (used, "sa_late", "initial", {}, {}, {}),
    }
    sims_all = {}
    vt = []
    for name, (ps, mode, trims, eo, en, to) in variants.items():
        prices = adj if mode == "spec" else raw
        pos = plan_positions(ps, cal_of, trims, eo, en, to)
        sims = {"AP": simulate(pos, prices, mode)}
        for b in (BENCHMARKS if name == "spec (base)" else ["SPY"]):
            sims[b] = simulate(pos, prices, mode, mirror=b)
        sims_all[name] = (pos, sims)
        m, ms = summarize(sims["AP"]), summarize(sims["SPY"])
        c = concentration(sims["AP"]["per_pick"])
        d = sims["AP"]["daily"]
        f10 = first_with(sims["AP"]["n_open"], MIN_POSITIONS_FOR_REGRESSION)
        r_all = ff6_monthly(d, fac_m)
        r_10 = ff6_monthly(d, fac_m, f10)
        row = {"variant": name, "n": m["n"], "vc": m["value_over_contrib"], "twr": m["twr"],
               "spy_vc": ms["value_over_contrib"], "spy_twr": ms["twr"],
               "twr_early": twr_between(d, INCEPTION, SNAPSHOT_BASE), "twr_late": twr_between(d, SNAPSHOT_BASE, END),
               "median": m["median"], "top5_net": c["net_share"][5], "top5_gross": c["gross_share"][5],
               "open_thq": open_on(pos, TRADERHQ_ASOF, TRADERHQ_LAST_PICK),
               "alpha_all": r_all["alpha_annual"], "t_all": r_all["t_ols"],
               "alpha_10": r_10["alpha_annual"], "t_10": r_10["t_ols"], "umd_10": r_10["loadings"]["UMD"][0],
               "first10": str(f10.date()), "min_after10": int(sims["AP"]["n_open"][sims["AP"]["n_open"].index >= f10].min())}
        vt.append(row)
        out.setdefault("portfolio", {})[name] = {"AP": m, "SPY": ms, "row": row}
    print(f"  {'variant':40s} {'n':>3s} {'AP v/c':>8s} {'AP TWR':>8s} {'SPY v/c':>8s} {'SPY TWR':>8s} "
          f"{'TWR->24-10-04':>13s} {'TWR 24-10-04->':>14s} {'median':>7s} {'top5 net/gross':>14s} "
          f"{'open 9/1':>8s} {'a all (t)':>13s} {'a >=10 (t)':>13s} {'UMD10':>6s} {'>=10 from':>10s} {'min':>4s}")
    for r in vt:
        print(f"  {r['variant']:40s} {r['n']:3d} {pct(r['vc'], 1):>8s} {pct(r['twr'], 1):>8s} {pct(r['spy_vc'], 1):>8s} "
              f"{pct(r['spy_twr'], 1):>8s} {pct(r['twr_early'], 1):>13s} {pct(r['twr_late'], 1):>14s} "
              f"{pct(r['median'], 1):>7s} {100 * r['top5_net']:6.1f}/{100 * r['top5_gross']:4.1f}% {r['open_thq']:8d} "
              f"{100 * r['alpha_all']:+6.1f}({r['t_all']:+.2f}) {100 * r['alpha_10']:+6.1f}({r['t_10']:+.2f}) "
              f"{r['umd_10']:6.2f} {r['first10']:>10s} {r['min_after10']:4d}")
    print(f"  SA published, {SA_PUBLISHED['as_of']}: Alpha Picks {SA_PUBLISHED['alpha_picks_pct']:+.2f}%, "
          f"benchmark {SA_PUBLISHED['sp500_pct']:+.2f}% (time-weighted, {TOTAL_PICKS_AT_END} picks)")

    pos, sims = sims_all["spec (base)"]
    print("  base, same-date benchmark portfolios: " + "; ".join(
        f"{b} value/contrib {pct(summarize(sims[b])['value_over_contrib'], 1)}, TWR {pct(summarize(sims[b])['twr'], 1)}"
        for b in BENCHMARKS))
    n_open = sims["AP"]["n_open"]
    first10 = first_with(n_open, MIN_POSITIONS_FOR_REGRESSION)
    print(f"  base positions held: {int(n_open.iloc[0])} at the start, first >= {MIN_POSITIONS_FOR_REGRESSION} on "
          f"{first10.date()} (never below afterwards: {int(n_open[n_open.index >= first10].min()) >= MIN_POSITIONS_FOR_REGRESSION}), "
          f"{int(n_open.iloc[-1])} at {END.date()}")
    early = [p for p in pos if p.entry < first10]
    print(f"  base book before {first10.date()} ({len(early)} picks): " + ", ".join(
        f"{p.label} {pct(float(sims['AP']['per_pick'].set_index('label').loc[p.label, 'return']), 0)}"
        f"{' [survivor list]' if by_label[p.label].survivor_only else ''}" for p in early))

    # open-position count vs TraderHQ
    o = open_on(pos, TRADERHQ_ASOF, TRADERHQ_LAST_PICK)
    n_thq = sum(p.pick_date <= TRADERHQ_LAST_PICK for p in used)
    n26 = sum(p.pick_date.year == 2026 and p.pick_date <= TRADERHQ_LAST_PICK for p in used)
    print(f"\n  OPEN COUNT on {TRADERHQ_ASOF.date()} (picks through {TRADERHQ_LAST_PICK.date()}): rebuilt base {o} open of "
          f"{n_thq}; TraderHQ {TRADERHQ_ACTIVE} active / {TRADERHQ_CLOSED} closed of {TOTAL_PICKS_TRADERHQ}")
    print(f"    -> at least {max(0, o - TRADERHQ_ACTIVE)} of the picks modelled as open must have closed "
          f"(if all {TOTAL_PICKS_TRADERHQ - n_thq} missing picks were closed)")
    print(f"    -> at least {max(0, o + TRADERHQ_2026_PICKS - n26 - TRADERHQ_ACTIVE)} if the {TRADERHQ_2026_PICKS - n26} missing "
          f"2026 picks were still open (an assumption)")
    print(f"    modelled-open picks with unknown status: {sum(1 for p in pos if not by_label[p.label].status_known)}")
    held_july = 41  # rows in the archived 2025-07-13 table
    print(f"    base rate: {len(EXIT_WINDOW_PICKS)} of the {held_july} picks held on {ARCHIVE_STATE.date()} were gone from the "
          f"table by ~{STATUS_CUTOFF.date()} (about three months)")
    out["open_count"] = {"rebuilt": o, "traderhq_active": TRADERHQ_ACTIVE, "n_rebuilt": n_thq}

    # dated SA snapshots. A third-party "as of D" may show D's close or, since SA
    # shows the previous close, the session before D: both are printed.
    print("\n  SA BENCHMARK vs SPY bought at the 2022-07-01 open and held (price-only / with dividends),")
    print("  at the snapshot date's close and at the previous session's close")
    spy_raw, spy_adj = raw["SPY"], adj["SPY"]
    o_raw, o_adj = spy_raw.loc["2022-07-01", "Open"], spy_adj.loc["2022-07-01", "Open"]
    prev_session = lambda d: spy_raw.index[spy_raw.index.get_loc(d) - 1]
    snaps = []
    for d, a, b, src in SA_SNAPSHOTS:
        d = pd.Timestamp(d)
        if d == INCEPTION:
            snaps.append((d, a, b, src, True))
            continue
        gaps = {}
        for dd in (d, prev_session(d)):
            po = spy_raw.loc[dd, "Close"] / o_raw - 1
            tr = spy_adj.loc[dd, "Close"] / o_adj - 1
            gaps[dd] = 100 * po - b
            out.setdefault("spy_bh", []).append({"snapshot": str(d.date()), "close": str(dd.date()), "sa": b,
                                                 "price_only": po, "total": tr})
        ok = abs(gaps[d]) <= SPY_CHECK_TOL_PP
        snaps.append((d, a, b, src, ok))
        po_d = spy_raw.loc[d, "Close"] / o_raw - 1
        tr_d = spy_adj.loc[d, "Close"] / o_adj - 1
        pv = prev_session(d)
        print(f"    {d.date()}: SA benchmark {b:+7.2f}%   SPY price-only {pct(po_d):>8s} (gap {gaps[d]:+5.2f} pp; "
              f"at {pv.date()} {gaps[pv]:+5.2f} pp)   SPY total return {pct(tr_d):>8s}"
              f"{'' if ok else '   FAILS the check at D'}   [{src}]")

    sa_sims = sims_all["sa (no dividends, VWAP proxy)"][1]
    base_snap = next(s for s in snaps if s[0] == SNAPSHOT_BASE)
    print(f"\n  REBUILT vs SA, TWR from {SNAPSHOT_BASE.date()} to each later snapshot (SA's growth from its own figures),")
    print("  measured to the snapshot date's close (D) and to the previous session's close (D-1)")
    print(f"  {'snapshot':10s} {'close':10s} {'SPY gap':>8s} {'SA AP':>8s} {'AP sa':>8s} {'gap sa':>8s} {'AP spec':>8s} "
          f"{'gap spec':>8s} | {'SA bench':>8s} {'SPY sa':>8s}")
    sub = []
    d0, a0, b0 = base_snap[:3]
    for d1, a1, b1, src, ok in snaps:
        if d1 <= SNAPSHOT_BASE:
            continue
        for dd in (d1, prev_session(d1)):
            po = spy_raw.loc[dd, "Close"] / o_raw - 1
            row = {"from": str(d0.date()), "snapshot": str(d1.date()), "to": str(dd.date()),
                   "spy_gap_pp": 100 * po - b1,
                   "sa_ap": (1 + a1 / 100) / (1 + a0 / 100) - 1, "sa_bm": (1 + b1 / 100) / (1 + b0 / 100) - 1,
                   "ap_spec": twr_between(sims["AP"]["daily"], d0, dd), "ap_sa": twr_between(sa_sims["AP"]["daily"], d0, dd),
                   "spy_sa": twr_between(sa_sims["SPY"]["daily"], d0, dd)}
            sub.append(row)
            print(f"  {row['snapshot'] if dd == d1 else '':10s} {row['to']:10s} {row['spy_gap_pp']:+7.2f}p "
                  f"{pct(row['sa_ap'], 1):>8s} {pct(row['ap_sa'], 1):>8s} {100 * (row['ap_sa'] - row['sa_ap']):+7.1f}pp "
                  f"{pct(row['ap_spec'], 1):>8s} {100 * (row['ap_spec'] - row['sa_ap']):+7.1f}pp | "
                  f"{pct(row['sa_bm'], 1):>8s} {pct(row['spy_sa'], 1):>8s}")
    print(f"  inception -> {SNAPSHOT_BASE.date()}: SA AP {pct(a0 / 100, 1)}, rebuilt sa "
          f"{pct(twr_between(sa_sims['AP']['daily'], INCEPTION, d0), 1)}, spec {pct(twr_between(sims['AP']['daily'], INCEPTION, d0), 1)}; "
          f"SA bench {pct(b0 / 100, 1)}, rebuilt SPY sa {pct(twr_between(sa_sims['SPY']['daily'], INCEPTION, d0), 1)} "
          f"(the rebuilt legs start at the first entry, not 2022-07-01)")
    out["subperiods"] = sub

    hv = sims["AP"]["hold_val"]
    d27i = on_or_before(hv.index, d27)
    tot = hv.loc[d27i].sum()
    print(f"\n  Weight check {d27i.date()}: rebuilt holding % vs SA's Holding % (RBD fig. 8)")
    wr = []
    for j, ps in enumerate(pos):
        if ps.ticker in SA_HOLDING_PCT_20261027 and ps.entry >= pd.Timestamp("2025-10-01"):
            w = 100 * hv.loc[d27i, j] / tot
            wr.append((ps.ticker, w, SA_HOLDING_PCT_20261027[ps.ticker]))
            print(f"    {ps.ticker:5s} rebuilt {w:5.2f}%   SA {SA_HOLDING_PCT_20261027[ps.ticker]:5.2f}%")
    if wr:
        print(f"    median SA/rebuilt {np.median([s / w for _, w, s in wr]):.2f}")
    out["weights"] = wr

    # ------------------------------------------------------------ 4. concentration
    c = concentration(sims["AP"]["per_pick"])
    pp, g = c["pp"], c["pp"]["return"]
    print(f"\n[4] CONCENTRATION (spec base, $1 per pick): {len(g)} picks, net gain ${c['net']:.2f}, "
          f"gross gain of the winners ${c['gross']:.2f}, winners {int((g > 0).sum())}, losers {int((g <= 0).sum())}")
    prev_k = 0
    for k in (1, 3, 5, 10):
        added = ", ".join(f"{lbl} {pct(r, 1)}" for lbl, r in zip(pp["label"].iloc[prev_k:k], g.iloc[prev_k:k]))
        print(f"  top {k:2d}: {100 * c['net_share'][k]:5.1f}% of the net gain, {100 * c['gross_share'][k]:5.1f}% of the gross gain"
              f"   ({'' if k == 1 else '+ '}{added})")
        prev_k = k
    print(f"  median pick {pct(g.median())}, mean pick {pct(g.mean())}")
    print("  worst:", ", ".join(f"{lbl} {pct(r, 1)}" for lbl, r in zip(pp["label"].iloc[-6:], g.iloc[-6:])))
    top5 = set(pp["label"].iloc[:5])
    ex = [p_ for p_ in pos if p_.label not in top5]
    ex_ap, ex_spy = simulate(ex, adj, "spec"), simulate(ex, adj, "spec", mirror="SPY")
    ex_m, ex_s = summarize(ex_ap), summarize(ex_spy)
    print(f"  without the top 5: value/contrib {pct(ex_m['value_over_contrib'])} (same-date SPY {pct(ex_s['value_over_contrib'])}), "
          f"TWR {pct(ex_m['twr'], 1)} (SPY {pct(ex_s['twr'], 1)}), median {pct(ex_m['median'])}")
    cap = g.clip(upper=1.0)
    print(f"  every pick capped at +100%: value/contrib {pct(cap.mean())}; net gain ${cap.sum():.2f} vs ${c['net']:.2f} "
          f"({100 * (1 - cap.sum() / c['net']):.1f}% smaller); gross gain ${cap[cap > 0].sum():.2f} vs ${c['gross']:.2f} "
          f"({100 * (1 - cap[cap > 0].sum() / c['gross']):.1f}% smaller)")
    spy_pp = sims["SPY"]["per_pick"]["return"]
    print(f"  same-date SPY per pick: mean {pct(spy_pp.mean())}, median {pct(spy_pp.median())}; "
          f"picks beating their SPY leg: {int((sims['AP']['per_pick']['return'] > spy_pp).sum())}/{len(spy_pp)}")
    pr = sims["AP"]["per_pick"].set_index("label")["return"]
    for grp, sel in (("documented status", [p.label for p in used if p.status_known]),
                     ("unknown status", [p.label for p in used if not p.status_known]),
                     ("survivor-list only", [p.label for p in used if p.survivor_only]),
                     ("other evidence", [p.label for p in used if not p.survivor_only])):
        print(f"  mean pick, {grp:18s}: {pct(float(pr.loc[sel].mean()))} (n {len(sel)}, median {pct(float(pr.loc[sel].median()))})")
    out["concentration"] = {"net_share": c["net_share"], "gross_share": c["gross_share"], "median": float(g.median()),
                            "mean": float(g.mean()), "ex_top5": ex_m, "ex_top5_spy": ex_s, "capped_mean": float(cap.mean()),
                            "per_pick": pp[["label", "return"]].to_dict("records")}

    # ------------------------------------------------------------ 4b. cohorts vs Wall Street Survivor
    print(f"\n[4b] PICK-YEAR COHORTS, sa mode (SA's displayed convention), as of {WSS_ASOF.date()} close,")
    print("     against Wall Street Survivor's table for all picks (secondary; 'thru Saturday 09/26/2026')")
    print(f"  {'year':4s} {'n':>3s} {'of':>3s} {'mean':>8s} {'median':>8s} {'win':>5s} {'SPY mean':>9s} | "
          f"{'WSS n':>5s} {'WSS mean':>9s} {'WSS SPY':>8s} {'WSS win':>7s}")
    pos_sa = plan_positions(used, cal_of, "initial")
    coh = []
    for ps in pos_sa:
        if ps.entry > WSS_ASOF:
            continue
        ap_v = value_asof(ps, raw[ps.ticker], raw[ps.ticker], WSS_ASOF, "sa")
        spy_v = value_asof(ps, raw[ps.ticker], raw["SPY"], WSS_ASOF, "sa")
        coh.append({"year": ps.entry.year, "label": ps.label, "ret": ap_v - 1, "spy": spy_v - 1})
    coh = pd.DataFrame(coh)
    for y, gdf in coh.groupby("year"):
        w = WSS_COHORTS[y]
        fw = lambda x, f: "n/a" if x is None else format(x, f) + "%"
        print(f"  {y:4d} {len(gdf):3d} {w[0]:3d} {pct(gdf.ret.mean(), 1):>8s} "
              f"{pct(gdf.ret.median(), 1):>8s} {100 * (gdf.ret > 0).mean():4.0f}% {pct(gdf.spy.mean(), 1):>9s} | "
              f"{w[0]:5d} {fw(w[1], '+.1f'):>9s} {fw(w[2], '+.1f'):>8s} {fw(w[3], '.0f'):>7s}")
    w = WSS_ALL
    print(f"  all  {len(coh):3d} {w[0]:3d} {pct(coh.ret.mean(), 1):>8s} {pct(coh.ret.median(), 1):>8s} "
          f"{100 * (coh.ret > 0).mean():4.0f}% {pct(coh.spy.mean(), 1):>9s} | {w[0]:5d} {w[1]:+8.1f}% {w[2]:+7.1f}% {w[3]:6.0f}%")
    print("  implied mean of the picks missing here, if WSS's means are right (WSS n*mean - ours) / missing:")
    for y, gdf in list(coh.groupby("year")) + [("all", coh)]:
        w = WSS_ALL if y == "all" else WSS_COHORTS[y]
        if w[1] is None or w[0] <= len(gdf):
            continue
        miss = (w[0] * w[1] / 100 - gdf.ret.sum()) / (w[0] - len(gdf))
        miss_spy = (w[0] * w[2] / 100 - gdf.spy.sum()) / (w[0] - len(gdf))
        print(f"    {y}: {w[0] - len(gdf)} missing picks, implied mean {pct(miss, 1)} (implied same-date S&P {pct(miss_spy, 1)})")
    out["cohorts"] = coh.to_dict("records")

    # ------------------------------------------------------------ 5. factor regressions
    print(f"\n[5] FAMA-FRENCH 5 + MOMENTUM. Ken French data end: monthly {fac_m.index.max()}, "
          f"daily {fac_d.index.max().date()} (October 2026 is not in the library yet)")
    starts = {"all": None, f">={MIN_POSITIONS_FOR_REGRESSION} positions": first10}
    reg = {}
    for sname, sstart in starts.items():
        for freq in ("monthly", "daily"):
            print(f"\n  {freq} excess returns, sample '{sname}'  [alpha %/yr (t OLS / t HAC); loadings (t)]")
            print(f"  {'series':6s} {'n':>4s} {'alpha':>7s} {'t':>12s}  " + "".join(f"{c:>14s}" for c in FACTORS) + f" {'R2':>6s}")
            for s, sim in sims.items():
                dr = sim["daily"]
                if freq == "monthly":
                    res = ff6_monthly(dr, fac_m, sstart)
                else:
                    if sstart is not None:
                        dr = dr[dr.index >= sstart]
                    j = pd.concat([dr.rename("r"), fac_d], axis=1, join="inner").dropna()
                    res = regress(j["r"] - j["RF"], j[FACTORS], 252, 5)
                reg[f"{sname}|{freq}|{s}"] = res
                ld = "".join(f"{res['loadings'][c][0]:+6.2f}({res['loadings'][c][1]:+5.1f})" for c in FACTORS)
                print(f"  {s:6s} {res['n']:4d} {100 * res['alpha_annual']:+6.1f}% {res['t_ols']:+5.2f}/{res['t_hac']:+5.2f}  {ld} {res['r2']:6.3f}")
            print(f"  sample {res['start']} .. {res['end']}")
    print("\n  Holdings-cutoff sensitivity, AP monthly six-factor (sample starts the month after the book first holds k)")
    print(f"  {'k':>3s} {'from':10s} {'min held after':>14s} {'n':>3s} {'alpha/yr':>9s} {'t OLS':>6s} {'t HAC':>6s} {'Mkt':>5s} {'SMB':>5s} {'UMD':>5s} {'R2':>5s}")
    for k in POSITION_CUTOFFS:
        fk = first_with(n_open, k)
        res = ff6_monthly(sims["AP"]["daily"], fac_m, fk)
        reg[f"cutoff|{k}"] = res
        L = res["loadings"]
        print(f"  {k:3d} {str(fk.date()):10s} {int(n_open[n_open.index >= fk].min()):14d} {res['n']:3d} "
              f"{100 * res['alpha_annual']:+8.1f}% {res['t_ols']:+6.2f} {res['t_hac']:+6.2f} {L['Mkt-RF'][0]:5.2f} "
              f"{L['SMB'][0]:5.2f} {L['UMD'][0]:5.2f} {res['r2']:5.3f}")
    j = pd.concat([monthly(sims["AP"]["daily"]).rename("r"), fac_m], axis=1, join="inner").dropna()
    print("\n  AP monthly, all months, smaller models:")
    for name, cs in (("CAPM", ["Mkt-RF"]), ("Mkt+UMD", ["Mkt-RF", "UMD"]), ("FF5", FACTORS[:5])):
        r = regress(j["r"] - j["RF"], j[cs], 12, 3)
        reg[f"AP_{name}"] = r
        extra = f", UMD {r['loadings']['UMD'][0]:+.2f} (t {r['loadings']['UMD'][1]:+.1f})" if "UMD" in cs else ""
        print(f"    {name:8s} alpha {100 * r['alpha_annual']:+.1f}%/yr (t {r['t_ols']:+.2f} OLS, {r['t_hac']:+.2f} HAC), "
              f"R2 {r['r2']:.3f}{extra}")
    print("\n  AP minus the same-date benchmark portfolio, monthly TWR difference (all months to Oct 2026)")
    apm = monthly(sims["AP"]["daily"])
    for b in BENCHMARKS:
        d = (apm - monthly(sims[b]["daily"])).dropna()
        t = d.mean() / (d.std(ddof=1) / math.sqrt(len(d)))
        reg[f"spread|{b}"] = {"mean": float(d.mean()), "t": float(t), "n": int(len(d))}
        print(f"    AP - {b:5s}: {100 * d.mean():+.2f}%/month ({100 * 12 * d.mean():+.1f}%/yr), t {t:+.2f}, n {len(d)}, "
              f"AP ahead in {int((d > 0).sum())}")
    print(f"  same, from {first10.to_period('M') + 1} (>= {MIN_POSITIONS_FOR_REGRESSION} positions held all month)")
    for b in BENCHMARKS:
        d = (apm - monthly(sims[b]["daily"])).dropna()
        d = d[d.index > first10.to_period("M")]
        t = d.mean() / (d.std(ddof=1) / math.sqrt(len(d)))
        reg[f"spread10|{b}"] = {"mean": float(d.mean()), "t": float(t), "n": int(len(d))}
        print(f"    AP - {b:5s}: {100 * d.mean():+.2f}%/month ({100 * 12 * d.mean():+.1f}%/yr), t {t:+.2f}, n {len(d)}, "
              f"AP ahead in {int((d > 0).sum())}")
    m_oct = apm.get(pd.Period("2026-10", "M"))
    print(f"  AP October 2026 (not in the regressions): {pct(m_oct)}; SPY leg "
          f"{pct(monthly(sims['SPY']['daily']).get(pd.Period('2026-10', 'M')))}")
    out["regressions"] = reg

    if args.json:
        args.json.write_text(json.dumps(out, default=str, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
