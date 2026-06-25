# Screener3000 — Project Guide

## What this is

A three-system stock screener over the S&P 500, Dow 30, and Nasdaq-100. A Python
job fetches fundamentals and scores every name through **three independent
screens**; a static React SPA renders the results. Deployed to GitHub Pages on a
weekday schedule — a public, shareable URL, no account required.

The three screens (decoupled on purpose — disagreement is the signal):

- **Azqato** — pure, no-AI 8-band growth + technical-entry screen; binary
  pass/fail (`azqato.py`). Pass = clears >= 6 of 8 bands.
- **Lynch** — growth at a reasonable price (PEG / fair-value bands).
- **Graham** — rate-adjusted intrinsic value + 8 defensive balance-sheet checks.

The default grid shows only names that clear **all three**; relax the filter to
see 2/1/any. Each name also has a full scorecard (per-system verdicts + drivers,
RSI gauge, 52-week-range bar).

## Stack

- **Backend:** Python 3.14. `stock_screener.py` (pipeline), `azqato.py` (pure
  scoring, unit-testable), `monitor.py` (falsifier checks). Deps in
  `requirements.txt` (requests, pandas, fredapi, python-dotenv, lxml, yfinance).
- **Frontend:** Vite 6 + React 19 + TypeScript 5.7 + Tailwind v4
  (`@tailwindcss/vite`, `@theme` tokens) + TanStack Table v8 / Virtual v3, under
  `web/`. Package manager **pnpm 11**.
- **Data sources:** yfinance (price, EPS history, dividends), Finnhub
  (`/stock/metric`: EPS, 5Y growth, margins, balance-sheet ratios, market cap),
  FRED (Moody's AAA yield, for Graham's rate adjustment), Wikipedia (universe).
- **Hosting:** GitHub Pages via GitHub Actions (`.github/workflows/deploy.yml`).

## Data flow (and the one decision that matters)

Weekday Action: run screener -> writes `web/public/data/results.json` -> `pnpm build`
-> upload `web/dist` as a Pages artifact -> `deploy-pages`.

**The dataset is NEVER committed.** It is generated fresh in CI and shipped inside
the Pages build artifact. This is deliberate: the old design committed
`docs/data/results.json` every run, which churned the submodule gitlink in the
`pie` superproject daily. Do not reintroduce a committed dataset.

`results.json` shape: a flat row per ticker. Lynch/Graham keys are
**double-prefixed** (`Graham_Graham_Status`, `Lynch_Lynch_Status`) because
`process_ticker` does `row.update({f"Graham_{k}": v ...})` over an
already-prefixed dict. The frontend reads those exact keys (`web/src/score.ts`,
`format.tsx`). Don't "fix" the prefix without updating the frontend in the same diff.

## Layout

- `stock_screener.py` — universe -> fetch -> score -> `write_json`. Entry point.
- `azqato.py` — `wilder_rsi`, `pct_of_52w_range`, `azqato_profile` (pure).
- `monitor.py` — falsifier / drift checks.
- `web/src/` — SPA. `score.ts` (verdicts), `columns.tsx` (grid), `DataTable.tsx`,
  `Scorecard.tsx`, `format.tsx`, `Toolbar.tsx`, `MethodologyDialog.tsx`, `App.tsx`.
- `.github/workflows/deploy.yml` — cron + manual: run screener -> build -> deploy.
- `.github/workflows/ci-python.yml` — on `**.py` change: compile + import smoke.
- `.github/workflows/ci-frontend.yml` — on `web/**` change: typecheck + build.
- `diagnose_finnhub.py`, `diagnose_yfinance.py` — ad-hoc data-source probes.

## Local development

- **Screener:** create `.env` with `FRED_API_KEY` and `FINNHUB_API_KEY`, then
  `pip install -r requirements.txt && python stock_screener.py`. (Inside the `pie`
  superproject you can also run it with an ephemeral `uv run --no-project --with
  requests --with pandas --with fredapi --with python-dotenv --with lxml --with
  yfinance python stock_screener.py`.) It writes `web/public/data/results.json`.
- **Frontend:** `pnpm -C web install` then `pnpm -C web dev` ->
  `http://localhost:7273/screener/`. Port 7273 is fixed (`strictPort`); the
  `/screener/` base path matches the GitHub Pages repo name.
- **Typecheck:** `pnpm -C web run typecheck`. **Build:** `pnpm -C web build`.

## Deploy (GitHub Actions -> Pages)

One-time repo setup (operator, in repo Settings):

1. Add Actions secrets `FRED_API_KEY` and `FINNHUB_API_KEY`.
2. Pages -> Source = **"GitHub Actions"** (not "Deploy from a branch").

Then it runs on the weekday cron (`0 11 * * 1-5`) or via **Run workflow**
(`workflow_dispatch`). Site: `https://<owner>.github.io/screener/`.

## Financial-integrity rules (non-negotiable — this is financial data)

- **None, never 0**, for missing data. Zero is a valid financial value (flat
  position, zero growth); a missing input is `None` and surfaces as a dash in the
  UI, never zero.
- **Never fabricate** a value to keep the pipeline moving. The screen previously
  floored non-positive growth to +1% — that invented positive fair values and
  false Buys. Don't. A name we can't value stays visible with valuation **N/A**.
- **Fail loud.** Catch only at system boundaries (data fetch / API), surface the
  failure, don't silently swallow it.
- **Publish guard.** `write_json` aborts (exit 1) unless there are >= 100
  non-error rows **and** >= 100 rows carrying a real valuation — so a fetch outage
  or a growth-feed outage can't silently publish a degraded `results.json`.

## Gotchas

- **`.gitignore` ignores `*.json`.** Any JSON that must be tracked needs an
  explicit `!path` exception (see `web/package.json`, `web/tsconfig.json`).
  `web/public/data/results.json` is intentionally NOT excepted — it stays ignored.
- **pnpm must be 10+** (the workspace `allowBuilds` allowlist that lets
  esbuild / `@tailwindcss/oxide` run their native build scripts is a pnpm 10+
  feature). CI pins pnpm 11; build locally with the same.
- **52-week range + RSI use `auto_adjust=False`** (nominal prices) so they share
  a basis with the raw `fast_info` last price and the Finviz/azqato convention.
- **Finnhub free tier is 60 req/min** (~515 calls/run). yfinance latency paces it
  under the limit; the publish guard covers a rate-limit-induced degraded run.
- Names with non-positive or uncomputable growth are kept **visible** with
  valuation N/A (Graham-defensive + Azqato still computed). Only no-usable-EPS /
  no-price names are hard-excluded as error rows.
