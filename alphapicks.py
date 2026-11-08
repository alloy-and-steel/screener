"""
Alpha Picks emulator -- a forward test of Seeking Alpha's published rules.

Applies the Alpha Picks rules that Seeking Alpha publishes on its help center
(docs/research/seeking-alpha-quant.md section 2) to this screener's own
SA-style rating (saquant.py), one screener run at a time, and keeps the
result as a ledger on the `data` branch next to picks.json. It cannot be
backfilled -- past runs' fundamentals and estimates were never saved -- so
its record starts on its first run, and its first pick comes once a stock
has held Strong Buy for 75 business days.

Rules, and where each comes from:
  - Two picks a month: a slot opens on the 1st (slot "a") and on the 15th
    (slot "b"); the first run in a slot that finds an eligible stock fills
    it. (help center: first trading day, and the 15th or the next one)
  - Eligible: rated Strong Buy today and for at least 75 consecutive
    business days, today included [the help center does not say trading or
    calendar; Mon-Fri here, holidays not removed], price > $10, market cap >
    $500M [SA: 3-month average; the screener has today's], not a REIT [by
    Yahoo industry], not an ADR [proxy: price and financials in different
    currencies, which misses ADRs that report in dollars], not picked in the
    past 365 days, not already held. (help center)
  - Among the eligible, the highest SA-style score. [ASSUMED: SA does not say
    how it chooses]
  - Entry: PICK_DOLLARS at the run's price; the benchmark buys the same
    dollars of SPY at the run's SPY price (SA: "an equal amount of SPY on the
    pick date"). The run's price stands in for SA's opening price.
  - Exit at the run's price when the rating is Sell or Strong Sell, or after
    more than 180 days at Hold (help center). A winner -- price at least
    twice the entry -- is not sold out at Hold: each further 180 days there
    it sells only its original purchase amount [secondary sources; SA's own
    wording varies, see the research doc]. A sale sells the same fraction of
    the position's SPY lot.
  - A held stock that leaves the data (delisted, acquired, dropped from the
    universe) for more than GONE_EXIT_DAYS is closed at its last price
    [ASSUMED: SA exits on M&A; we cannot see why it left].
  - A position above 15% of the portfolio is cut back to 10%, the proceeds
    spread equally over the other holdings [secondary sources and one SA
    webinar snippet], once the portfolio holds at least 10 names [ASSUMED:
    with fewer, a 10% target sits below an equal weight and a trim pushes the
    others toward 15%]. The SPY lots are not trimmed.

Missing data is a gap, not a verdict: a run where a stock is missing or
unrated leaves its streak and position as they were (a streak unseen for more
than STREAK_GAP_DAYS lapses). A run with no SPY price makes no pick and no
sale, so every lot's benchmark leg is priced on the day it trades. Prices are
nominal and dividends are left out on both sides (SA reinvests them), and a
split after entry shows as a false drop, as in the picks.json ledger.

Pure: no I/O, no network. The small load/save helpers are the only file access.
"""

from __future__ import annotations

import copy
import json
from datetime import date, timedelta
from pathlib import Path

from saquant import HOLD, RATINGS

LEDGER_VERSION = 1
ROW_FIELD = "alphaPicks"

PICK_DOLLARS = 1000.0
STREAK_BUSINESS_DAYS = 75
MIN_PRICE = 10.0
MIN_MARKET_CAP_B = 0.5
COOLDOWN_DAYS = 365
HOLD_EXIT_DAYS = 180  # more than this many days at Hold -> exit
WINNER_MULTIPLE = 2.0
TRIM_ABOVE = 0.15
TRIM_TO = 0.10
# [ASSUMED] Trims apply only from this many holdings: below 1 / TRIM_TO an
# equal-weight portfolio already sits above 15% per name, and trimming would
# churn every holding on every run.
TRIM_MIN_HOLDINGS = round(1 / TRIM_TO)
STREAK_GAP_DAYS = 10  # [ASSUMED] a streak unseen longer than this lapses
GONE_EXIT_DAYS = 14  # [ASSUMED] a held stock missing longer than this is closed

STRONG_BUY = RATINGS[0]
SELLS = frozenset(RATINGS[-2:])


def empty_ledger() -> dict:
    return {
        "version": LEDGER_VERSION,
        "started_at": None,
        "updated_at": None,
        "streaks": {},
        "slots": [],
        "open": [],
        "closed": [],
        "trims": [],
        "last_picked": {},
    }


def _slot(day: date) -> str:
    return f"{day:%Y-%m}-{'a' if day.day < 15 else 'b'}"


def _business_days(since: str, day: date) -> int:
    """Mon-Fri days from `since` (counted) up to `day` (not counted)."""
    start = date.fromisoformat(since)
    if day <= start:
        return 0
    weeks, extra = divmod((day - start).days, 7)
    return weeks * 5 + sum(1 for i in range(extra) if (start.weekday() + i) % 7 < 5)


def _streak_days(since: str, day: date) -> int:
    """Business days in a streak that began on `since` and is still on at `day`, both counted."""
    return _business_days(since, day + timedelta(days=1))


def _qualifies_on(since: str) -> date:
    """The first day a streak that began on `since` reaches STREAK_BUSINESS_DAYS."""
    d = date.fromisoformat(since)
    while _streak_days(since, d) < STREAK_BUSINESS_DAYS:
        d += timedelta(days=1)
    return d


def _rating(row: dict) -> str | None:
    return (row.get("saQuant") or {}).get("rating")


def _usable_price(v) -> bool:
    return isinstance(v, (int, float)) and v > 0


def _is_reit(row: dict) -> bool:
    return str(row.get("Industry") or "").upper().startswith("REIT")


def _is_adr_proxy(row: dict) -> bool:
    return row.get("DCF_Currency_Mismatch") is True


def update_ledger(ledger: dict, rows: list[dict], generated_at: str, spy_price: float | None) -> dict:
    """Return a new ledger with one run applied. `generated_at` must be later
    than the ledger's last run. With `spy_price` None the run only updates
    streaks and trims: a pick or a sale needs a benchmark price that day."""
    last = ledger.get("updated_at")
    if last is not None and generated_at <= last:
        raise ValueError(f"run {generated_at} is not newer than the ledger's last run {last}")
    out = copy.deepcopy(ledger)
    day = date.fromisoformat(generated_at[:10])
    today = day.isoformat()
    by_ticker = {r["Ticker"]: r for r in rows if not r.get("Error")}
    if out["started_at"] is None:
        out["started_at"] = generated_at
    spy_ok = _usable_price(spy_price)

    # 1. Rating streaks: kept while the rating repeats, restarted when it
    #    changes, untouched by a gap (missing or unrated), lapsed after a long one.
    streaks = {}
    for t, prev in out["streaks"].items():
        if (day - date.fromisoformat(prev["seen"])).days <= STREAK_GAP_DAYS:
            streaks[t] = prev
    for t, r in by_ticker.items():
        rating = _rating(r)
        if rating is None:
            continue
        prev = streaks.get(t)
        since = prev["since"] if prev and prev["rating"] == rating else today
        streaks[t] = {"rating": rating, "since": since, "seen": today}
    out["streaks"] = streaks

    # 2. Sales, at today's price, for positions whose rating says so.
    still_open = []
    for pos in out["open"]:
        r = by_ticker.get(pos["ticker"])
        price = r.get("Price") if r else None
        if _usable_price(price):
            pos["last_price"] = price
            pos["last_seen"] = today
        if spy_ok:
            pos = _apply_exit_rules(out, pos, _rating(r) if r and _usable_price(price) else None, streaks.get(pos["ticker"]), day, spy_price)
        if pos is not None:
            still_open.append(pos)
    out["open"] = still_open

    # 3. Trim: anything above 15% of the portfolio back to 10%.
    _trim(out, today)

    # 4. Pick: one per slot, the best-scoring eligible Strong Buy.
    slot = _slot(day)
    if slot not in out["slots"] and spy_ok:
        held = {p["ticker"] for p in out["open"]}
        eligible = []
        for t, r in by_ticker.items():
            s = streaks.get(t)
            score = (r.get("saQuant") or {}).get("score")
            if not s or s["rating"] != STRONG_BUY or s["seen"] != today or score is None:
                continue
            if _streak_days(s["since"], day) < STREAK_BUSINESS_DAYS:
                continue
            price, cap_b = r.get("Price"), r.get("MarketCap_B")
            if not (_usable_price(price) and price > MIN_PRICE):
                continue
            if not (isinstance(cap_b, (int, float)) and cap_b > MIN_MARKET_CAP_B):
                continue
            if _is_reit(r) or _is_adr_proxy(r) or t in held:
                continue
            last_pick = out["last_picked"].get(t)
            if last_pick and (day - date.fromisoformat(last_pick)).days < COOLDOWN_DAYS:
                continue
            eligible.append((-score, t))
        if eligible:
            t = min(eligible)[1]
            price = by_ticker[t]["Price"]
            out["open"].append({
                "ticker": t,
                "slot": slot,
                "at": today,
                "price": price,
                "shares": PICK_DOLLARS / price,
                "cost": PICK_DOLLARS,
                "spy_price": spy_price,
                "spy_shares": PICK_DOLLARS / spy_price,
                "last_price": price,
                "last_seen": today,
                "winner_sold_at": None,
            })
            out["slots"].append(slot)
            out["last_picked"][t] = today

    out["updated_at"] = generated_at
    return out


def _sell(ledger: dict, pos: dict, fraction: float, price: float, spy_price: float, today: str, reason: str) -> None:
    """Record the sale of `fraction` of a position (and of its SPY lot) and shrink it."""
    ledger["closed"].append({
        "ticker": pos["ticker"],
        "slot": pos["slot"],
        "at": pos["at"],
        "price": pos["price"],
        "exit_at": today,
        "exit_price": price,
        "fraction": fraction,
        "proceeds": pos["shares"] * fraction * price,
        "spy_price": pos["spy_price"],
        "spy_exit_price": spy_price,
        "spy_proceeds": pos["spy_shares"] * fraction * spy_price,
        "reason": reason,
    })
    pos["shares"] *= 1.0 - fraction
    pos["spy_shares"] *= 1.0 - fraction


def _apply_exit_rules(ledger: dict, pos: dict, rating: str | None, streak: dict | None, day: date, spy_price: float) -> dict | None:
    """Apply the sell rules to one position; the position if any of it is still held, else None."""
    today = day.isoformat()
    if rating is None:
        if (day - date.fromisoformat(pos["last_seen"])).days > GONE_EXIT_DAYS:
            _sell(ledger, pos, 1.0, pos["last_price"], spy_price, today, "gone")
            return None
        return pos
    price = pos["last_price"]
    if rating in SELLS:
        _sell(ledger, pos, 1.0, price, spy_price, today, "sell")
        return None
    if rating != HOLD:
        return pos
    clock_start = max(streak["since"], pos.get("winner_sold_at") or streak["since"])
    if (day - date.fromisoformat(clock_start)).days <= HOLD_EXIT_DAYS:
        return pos
    if price < WINNER_MULTIPLE * pos["price"]:
        _sell(ledger, pos, 1.0, price, spy_price, today, "hold180")
        return None
    value = pos["shares"] * price
    if value <= pos["cost"]:
        _sell(ledger, pos, 1.0, price, spy_price, today, "winner_sale")
        return None
    _sell(ledger, pos, pos["cost"] / value, price, spy_price, today, "winner_sale")
    pos["winner_sold_at"] = today
    return pos


def _trim(ledger: dict, today: str) -> None:
    for _ in range(len(ledger["open"])):
        values = {p["ticker"]: p["shares"] * p["last_price"] for p in ledger["open"]}
        total = sum(values.values())
        if total <= 0 or len(values) < TRIM_MIN_HOLDINGS:
            return
        big = max(values, key=values.get)
        if values[big] <= TRIM_ABOVE * total:
            return
        freed = values[big] - TRIM_TO * total
        others = [p for p in ledger["open"] if p["ticker"] != big]
        for p in ledger["open"]:
            if p["ticker"] == big:
                p["shares"] -= freed / p["last_price"]
            else:
                p["shares"] += freed / len(others) / p["last_price"]
        ledger["trims"].append({"ticker": big, "at": today, "from_pct": round(values[big] / total * 100, 2), "to_pct": TRIM_TO * 100})


def summary(ledger: dict, rows: list[dict], spy_price: float | None) -> dict:
    """Portfolio totals for the frontend: dollars in vs value now, for the
    picks and for the same-dollars SPY benchmark."""
    prices = {r["Ticker"]: r.get("Price") for r in rows}
    spy = spy_price if _usable_price(spy_price) else None
    picks = len(ledger["slots"])
    invested = picks * PICK_DOLLARS
    value = sum(p["shares"] * (prices.get(p["ticker"]) if _usable_price(prices.get(p["ticker"])) else p["last_price"]) for p in ledger["open"])
    value += sum(c["proceeds"] for c in ledger["closed"])
    spy_value = None
    if spy:
        spy_value = sum(p["spy_shares"] * spy for p in ledger["open"]) + sum(c["spy_proceeds"] for c in ledger["closed"])
    first_eligible = None
    for s in ledger["streaks"].values():
        if s["rating"] == STRONG_BUY:
            d = _qualifies_on(s["since"]).isoformat()
            first_eligible = min(first_eligible, d) if first_eligible else d
    return {
        "startedAt": ledger["started_at"],
        "picks": picks,
        "open": len(ledger["open"]),
        "closed": sum(1 for c in ledger["closed"] if c["fraction"] == 1.0),
        "invested": invested,
        "value": value if picks else None,
        "returnPct": (value / invested - 1.0) * 100.0 if picks else None,
        "spyReturnPct": (spy_value / invested - 1.0) * 100.0 if picks and spy_value is not None else None,
        "strongBuyStreaks": sum(1 for s in ledger["streaks"].values() if s["rating"] == STRONG_BUY),
        "streakBusinessDays": STREAK_BUSINESS_DAYS,
        "firstEligibleOn": first_eligible,
        "holdings": [
            {"ticker": p["ticker"], "at": p["at"], "price": p["price"]} for p in ledger["open"]
        ],
    }


def annotate_rows(rows: list[dict], ledger: dict, generated_at: str) -> None:
    """Attach each row's streak and open position as ROW_FIELD (None when the
    ledger knows nothing about the ticker)."""
    day = date.fromisoformat(generated_at[:10])
    positions = {p["ticker"]: p for p in ledger["open"]}
    for r in rows:
        t = r["Ticker"]
        s = ledger["streaks"].get(t)
        p = positions.get(t)
        if not s and not p:
            r[ROW_FIELD] = None
            continue
        r[ROW_FIELD] = {
            "streak": {"rating": s["rating"], "since": s["since"], "businessDays": _streak_days(s["since"], day)} if s else None,
            "position": {"at": p["at"], "price": p["price"], "slot": p["slot"]} if p else None,
        }


def load_ledger(path: Path) -> dict | None:
    """The ledger at `path`, or None if there is none yet (bootstrap). A file
    that exists but can't be read raises: starting over would silently erase
    the forward test's history."""
    if not path.exists():
        return None
    ledger = json.loads(path.read_text(encoding="utf-8"))
    if ledger.get("version") != LEDGER_VERSION or not isinstance(ledger.get("streaks"), dict):
        raise ValueError(f"{path} is not a version-{LEDGER_VERSION} Alpha Picks emulator ledger")
    return ledger


def save_ledger(path: Path, ledger: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger, separators=(",", ":"), sort_keys=True), encoding="utf-8")

