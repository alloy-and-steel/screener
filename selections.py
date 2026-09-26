"""
Selection ledger -- the price a stock had when the screener picked it.

A stock is SELECTED on a run when it passes at least SELECTION_MIN_PASS of the
three independent screens (the same gates as web/src/score.ts). The ledger
keeps, per ticker:

  first    -- the run (generated_at) and price it was first seen selected.
              Written once, never overwritten.
  latest   -- the run and price of its most recent entry: equal to `first`
              until it drops out and comes back, then moved to the re-entry.
              A run where the stock is an error row changes nothing.
  selected -- whether the most recent run had it selected.

The ledger is carried run to run on the `data` branch next to results.json
(screen.yml seeds it and publishes it) and is merged into each results row as
`selection` for the frontend. backfill_selections.py rebuilt it from the
published datasets that could still be recovered.

Pure: no I/O, no network. The small load/save helpers are the only file access.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

SELECTION_MIN_PASS = 2

# Mirrors web/src/score.ts (AZQATO_PASS_TIERS, LYNCH_BUY, GRAHAM_BUY).
AZQATO_PASS_TIERS = frozenset({"sp", "s", "a"})
LYNCH_BUY = frozenset({"Strong Buy", "Buy"})
GRAHAM_BUY = frozenset({"Deep Buy", "Buy"})

LEDGER_VERSION = 1


def screens_passed(row: dict) -> int:
    if row.get("Error"):
        return 0
    az = row.get("azqato") or {}
    return (
        (az.get("tier") in AZQATO_PASS_TIERS)
        + (row.get("Lynch_Lynch_Status") in LYNCH_BUY)
        + (row.get("Graham_Graham_Status") in GRAHAM_BUY)
    )


def empty_ledger() -> dict:
    return {"version": LEDGER_VERSION, "min_pass": SELECTION_MIN_PASS, "updated_at": None, "tickers": {}}


def update_ledger(ledger: dict, rows: list[dict], generated_at: str) -> dict:
    """Return a new ledger with one run applied. `generated_at` must be later
    than the ledger's last run: applying a run twice (or out of order) would
    record a drop-out that never happened as a re-entry."""
    if ledger.get("min_pass") != SELECTION_MIN_PASS:
        raise ValueError(f"ledger was built with min_pass={ledger.get('min_pass')}, code uses {SELECTION_MIN_PASS}")
    last = ledger.get("updated_at")
    # ISO-8601 UTC ("...Z") strings order the same as the instants they name.
    if last is not None and generated_at <= last:
        raise ValueError(f"run {generated_at} is not newer than the ledger's last run {last}")

    out = copy.deepcopy(ledger)
    tickers = out["tickers"]
    now = {r["Ticker"]: r for r in rows if screens_passed(r) >= SELECTION_MIN_PASS}
    # An error row is a failed fetch, not a verdict: we don't know whether the
    # stock still passes, so its entry is left exactly as it was. Treating it
    # as a drop-out would log a fake re-entry at the next clean run.
    unknown = {r["Ticker"] for r in rows if r.get("Error")}

    for t, entry in tickers.items():
        if t not in now and t not in unknown:
            entry["selected"] = False

    for t, r in now.items():
        mark = {"at": generated_at, "price": r.get("Price")}
        entry = tickers.get(t)
        if entry is None:
            tickers[t] = {"first": mark, "latest": dict(mark), "selected": True}
        elif not entry["selected"]:
            entry["latest"] = mark
            entry["selected"] = True

    out["updated_at"] = generated_at
    return out


def annotate_rows(rows: list[dict], ledger: dict) -> None:
    """Attach each row's ledger entry as `selection` (None if never selected)."""
    tickers = ledger["tickers"]
    for r in rows:
        entry = tickers.get(r["Ticker"])
        r["selection"] = copy.deepcopy(entry) if entry else None


def load_ledger(path: Path) -> dict | None:
    """The ledger at `path`, or None if there is none yet (bootstrap). A file
    that exists but can't be read raises: silently starting over would stamp
    today's price as every stock's first entry."""
    if not path.exists():
        return None
    ledger = json.loads(path.read_text(encoding="utf-8"))
    if ledger.get("version") != LEDGER_VERSION or not isinstance(ledger.get("tickers"), dict):
        raise ValueError(f"{path} is not a version-{LEDGER_VERSION} selection ledger")
    return ledger


def save_ledger(path: Path, ledger: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger, separators=(",", ":"), sort_keys=True), encoding="utf-8")
