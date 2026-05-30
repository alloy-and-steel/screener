# Lynch & Graham Screener — GitHub Pages Migration

## What This Is

A daily-automated value stock screener that applies Peter Lynch and Benjamin Graham valuation frameworks across the S&P 500, Dow 30, and Nasdaq-100 universe (~550 tickers). Results are published as a public interactive web dashboard hosted on GitHub Pages, updated automatically each weekday via GitHub Actions.

## Core Value

A public, shareable URL that shows today's Lynch/Graham buy signals — no Google account, no friction, just open the link.

## Requirements

### Validated

These exist and work in the current codebase:

- ✓ Fetch S&P 500, Dow 30, Nasdaq-100 constituents dynamically from Wikipedia — existing
- ✓ Fetch current Moody's AAA corporate bond yield from FRED — existing
- ✓ Fetch price, EPS history, and dividends from yfinance — existing
- ✓ Fetch current EPS, growth CAGR, and balance sheet ratios from Finnhub — existing
- ✓ Compute Lynch PEG/PEGY metrics and buy/hold/avoid signals — existing
- ✓ Compute Graham intrinsic value (Version A and B) and price bands — existing
- ✓ Score stocks against Graham defensive investor 8-point checklist — existing
- ✓ Blend Lynch and Graham signals into a combined score, sorted best-first — existing
- ✓ Run full pipeline on GitHub Actions schedule (weekdays, 6am ET) — existing

### Active

The migration target — what we're building:

- [ ] GitHub Actions job writes screener results as `results.json` committed to the repo
- [ ] GitHub Actions job auto-pushes the updated data file after each run
- [ ] GitHub Pages hosts an interactive dashboard at the project's Pages URL
- [ ] Dashboard: sortable, filterable results table with all signal columns
- [ ] Dashboard: traffic-light color coding (green/yellow/red) on signal cells
- [ ] Dashboard: Top 20 buy signals summary view
- [ ] Dashboard: methodology documentation page (Lynch/Graham formulas, signal definitions)
- [ ] Remove all Google dependencies (gspread, google-auth, service account credentials, GSHEET_* secrets)
- [ ] Remove Tiingo dead config (TIINGO_API_KEYS, TIINGO_DELAY_SEC misleading constant)

### Out of Scope

- Server-side rendering or a backend — fully static, no server
- Real-time or intraday data updates — daily schedule is sufficient
- User accounts or authentication on the website — public, open access
- Historical trend charts or multi-run comparisons — current run only
- Keeping Google Sheets as a parallel output — full migration, not dual-write
- Mobile-native app — responsive web is sufficient

## Context

The existing `stock_screener.py` is a mature single-file Python script (~1,217 lines) with the full pipeline already working. The migration is primarily an **output layer swap**: replace `push_to_gsheets()` with a JSON writer, add a static web frontend, and wire it into GitHub Pages.

Key facts from the codebase map:
- All Google output logic is isolated in `push_to_gsheets()` and its private helpers (`_apply_color_coding`, `_write_docs_tab`, `_write_markdown_tab`)
- The color coding config (`SIGNAL_COLORS`) and docs content (`DOCS_CONTENT`) already exist and can be reused in the frontend
- GitHub Actions workflow (`screener.yml`) already runs on the target schedule — needs only output and push changes
- No test suite exists — valuation math is production-proven but untested

## Constraints

- **Platform**: GitHub Pages (static hosting only — no server, no database)
- **Data freshness**: Weekday daily updates via existing Actions schedule
- **Python backend**: Keep existing Python pipeline; only swap the output target
- **Zero new credentials**: The new setup must not require any new API keys or service accounts
- **Git-friendly**: results.json committed to the repo so data is versioned

## Key Decisions

| Decision | Rationale | Outcome |
|---|---|---|
| Commit results.json to repo | Eliminates all external dependencies; data versioned in git; Pages can serve it statically | — Pending |
| Full Google removal (not dual-write) | User motivation is to eliminate all Google friction; keeping Sheets adds maintenance burden | — Pending |
| Static frontend (no framework required) | Simpler deployment; no build step needed for Pages; vanilla JS + a table library is sufficient | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-29 after initialization*
