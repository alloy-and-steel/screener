# Wealthmatica as the 4th gating system

## Context
Systematize Wealthmatica's recurring financial checklist (research: [docs/research/wealthmatica.md](../research/wealthmatica.md)) into a 4th pass/fail system alongside Azqato / Lynch / Graham. User decisions (2026-10-05): pass = 7 of 9 checks, no growth gate; judge only on the checks that apply; fresh 4-level pick ledger, old 3-level one archived (not shown); default card view = passes 3 of 4.

## Decisions
- Inputs: the annual `income_stmt` / `cashflow` / `balance_sheet` frames already fetched in `get_yf_price_and_history` (newest-first) + Yahoo `info` totalCash/totalDebt (the Azqato cash/debt inputs). No new API calls.
- Nine checks (thresholds `[ASSUMED]`, constants in `wealthmatica.py`):
  1. revenue growth >= 15% (FY0 vs FY1)
  2. growth re-accelerating (g0 > g1) or g0 >= 25%
  3. FCF > 0 and above prior year
  4. FCF - SBC > 0
  5. share count change <= +2% YoY
  6. gross margin down <= 1 pt YoY
  7. operating margin up YoY
  8. diluted EPS up YoY and (positive, or loss narrowed)
  9. cash >= debt
- A check whose inputs are absent is N/A, not failed (banks: no gross profit / operating income; WMT/VZ/AEP: no SBC row). Pass = >= 6 applicable AND passed >= ceil(7/9 x applicable). Fewer than 6 applicable -> verdict N/A (not a pass).
- Row field `wealthmatica`: per-check value + pass (true/false/null), `passed`, `applicable`, `pass`.
- Ledger: `LEDGER_VERSION = 3`, levels 1-4, new file `web/public/data/picks.json`, row field `picks4` (an old cached shell must not read 4-level picks as 3-level). `selections.json` (v2) carried forward untouched on the data branch, no longer read. `backfill_selections.py` deleted (replays v2 only; git keeps it).
- screen.yml seed rule: picks.json present -> seed; absent but selections.json present -> first v3 run, start fresh; data branch with neither -> error.
- Frontend: `passesAll` = all 4; combined green at 4; pass floor 0-4, default 3; card/scorecard verdict block for Wealthmatica with the nine checks as drivers.
- Publish guard: >= 100 rows with a non-N/A Wealthmatica verdict.

## Approach
1. `wealthmatica.py` (pure, like `azqato.py`): `wealthmatica_profile(inc, cf, bs, cash, debt) -> dict`. Tests first: `tests/test_wealthmatica.py`.
2. `stock_screener.py`: `process_ticker` sets `row["wealthmatica"]`; `_validate_output_dataframe` guard; `_compute_stats` pass count; `SELECTIONS_PATH` -> picks.json.
3. `selections.py`: 4th gate in `screens_passed`, v3, `picks4`; update `tests/test_selections.py` (gate-diff test reads the new TS rule).
4. Delete `backfill_selections.py`.
5. `screen.yml`: seed/publish picks.json; carry selections.json forward; guard per seed rule.
6. Web: `types.ts`, `score.ts`, `selection.ts`, `prefs.ts`, `filters.ts`, `FilterBar.tsx`, `StockCard.tsx`, `Scorecard.tsx`, `MethodologyDialog.tsx`, `App.tsx`; tests beside them.
7. CLAUDE.md: four systems, checklist, ledger v3, picks.json; remove backfill references.

## Verification
- `for f in tests/test_*.py; do python "$f"; done`
- `pnpm -C web run typecheck && pnpm -C web test && pnpm -C web build`
- Live sample: `wealthmatica_profile` on ~20 real tickers via yfinance (picks, controls, banks, no-SBC names), compared against the research run.
- UNVERIFIED until the next Screen run: full-universe pass counts, the publish guard on real data, first v3 ledger bootstrap on the data branch.
