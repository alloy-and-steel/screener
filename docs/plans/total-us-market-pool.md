# Total US market pool ($1B+)

## Context
Port azqato's "Domestic" universe (every US-listed VTI holding, ~3,465) as a 7th pool, floored at $1B market cap (~1,950 names). User decisions (2026-10-01): Azqato ranks against the whole merged market (one cross-section); $1B+ floor.

## Decisions
- One merged cross-section for tier + gate; Azqato A-or-better = top 20% of the merged universe.
- Floor applies only to names whose ONLY pool is TotalUS; curated pools (S&P/Dow/Nasdaq/G/V/D) exempt.
- Floor input: Finnhub `marketCapitalization` ($M), the same number the card shows as `MarketCap_B`. Fetched first for TotalUS-only names, reused by `get_combined_data` (no second call). Unknown cap -> kept (missing is not "below").
- Rejected floor sources (measured 2026-10-01): VTI position / weight proxy (5% misclassified, drops CRNX $9B); Yahoo `yf.screen` (misses LECO $14B, CRNX, APGE).
- Finnhub spacing limiter (>= ~1s between calls): skipped names no longer get yfinance latency between Finnhub calls.
- TotalUS excluded from the per-pool `byIndex` re-score (would duplicate the merged rank).
- Cadence unchanged (weekday daily). Ledger unchanged: new names get launch-day picks.

## Approach
1. `INDEX_FETCHERS += ("TotalUS", fetch_total_market)` ([stock_screener.py](../../stock_screener.py)).
2. `run_screener`: TotalUS-only -> `get_finnhub_metrics` -> skip if cap < floor; else pass metrics into `process_ticker` -> `get_combined_data(finnhub=...)`.
3. Finnhub limiter in `get_finnhub_metrics` with a sleep/clock seam for tests.
4. Per-pool loop skips TotalUS.
5. Frontend: `INDEX_NAMES`/`INDEX_LABEL` ("Total US $1B+") in `web/src/types.ts`; Scorecard membership line hides TotalUS when another pool is present; methodology copy.
6. CLAUDE.md: seven pools, ~2,000 names, run time, floor rule.

## Verification
- `for f in tests/test_*.py; do python "$f"; done` (floor skip/keep/unknown, Finnhub reuse, limiter spacing).
- `pnpm -C web run typecheck && pnpm -C web test && pnpm -C web build`.
- Real Screen run (no API keys on the box): run time, Finnhub/yfinance error rates, row count ~1,950-2,050, publish guards pass, results.json size.
