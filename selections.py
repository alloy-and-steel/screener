"""
Selection ledger -- the price a stock had when the screener picked it.

A stock is PICKED AT LEVEL N on a run when it passes exactly N of the three
independent screens (the same gates as web/src/score.ts), N = 1, 2 or 3. The
ledger keeps, per ticker and level, the run (generated_at) and price of the
first run it sat at that level. A pick is written once and never overwritten:
dropping to another level, out of the screen, or out of the universe changes
nothing, and a stock that jumps straight from 0 to 3 screens has a level-3
pick and no level-1 or level-2 one. An error row passes 0 screens, so a failed
fetch records nothing.

The ledger is carried run to run on the `data` branch next to results.json
(screen.yml seeds it and publishes it) and is merged into each results row as
`picks` for the frontend. backfill_selections.py rebuilt it from the published
datasets that could still be recovered.

Pure: no I/O, no network. The small load/save helpers are the only file access.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

# Mirrors web/src/score.ts (AZQATO_PASS_TIERS, LYNCH_BUY, GRAHAM_BUY).
AZQATO_PASS_TIERS = frozenset({"sp", "s", "a"})
LYNCH_BUY = frozenset({"Strong Buy", "Buy"})
GRAHAM_BUY = frozenset({"Deep Buy", "Buy"})

# 1 was a single first/latest entry per stock at >= 2 screens. It can't be
# split into per-level picks, so load_ledger refuses it.
LEDGER_VERSION = 2


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
    return {"version": LEDGER_VERSION, "updated_at": None, "tickers": {}}


def update_ledger(ledger: dict, rows: list[dict], generated_at: str) -> dict:
    """Return a new ledger with one run applied. `generated_at` must be later
    than the ledger's last run: applying a run out of order would stamp an
    older price as the first pick."""
    last = ledger.get("updated_at")
    # ISO-8601 UTC ("...Z") strings order the same as the instants they name.
    if last is not None and generated_at <= last:
        raise ValueError(f"run {generated_at} is not newer than the ledger's last run {last}")

    out = copy.deepcopy(ledger)
    for r in rows:
        level = screens_passed(r)
        if level:
            # JSON object keys are strings; the level is kept as one throughout.
            out["tickers"].setdefault(r["Ticker"], {}).setdefault(str(level), {"at": generated_at, "price": r.get("Price")})
    out["updated_at"] = generated_at
    return out


def annotate_rows(rows: list[dict], ledger: dict) -> None:
    """Attach each row's picks as `picks` (None if never picked)."""
    tickers = ledger["tickers"]
    for r in rows:
        entry = tickers.get(r["Ticker"])
        r["picks"] = copy.deepcopy(entry) if entry else None


def load_ledger(path: Path) -> dict | None:
    """The ledger at `path`, or None if there is none yet (bootstrap). A file
    that exists but can't be read raises: silently starting over would stamp
    today's price as every stock's first pick."""
    if not path.exists():
        return None
    ledger = json.loads(path.read_text(encoding="utf-8"))
    if ledger.get("version") != LEDGER_VERSION or not isinstance(ledger.get("tickers"), dict):
        raise ValueError(f"{path} is not a version-{LEDGER_VERSION} selection ledger")
    return ledger


def save_ledger(path: Path, ledger: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger, separators=(",", ":"), sort_keys=True), encoding="utf-8")
