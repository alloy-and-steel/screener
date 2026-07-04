# Screener3000 — Project Guide

## What this is

A three-system stock screener over the S&P 500, Dow 30, and Nasdaq-100. A Python
job fetches fundamentals and scores every name through **three independent
screens**; a static React SPA renders the results. Deployed to GitHub Pages on a
weekday schedule — a public, shareable URL, no account required.

The three screens (decoupled on purpose — disagreement is the signal):

- **Azqato** — pure, no-AI RELATIVE percentile model (`azqato.py`), a port of
  the live azqato screener's scoring v2 (azqato.github.io/stocks/screener.js).
  Six metrics in three pillars (Growth 60: rev TTM 10 / rev FWD 20 / EPS TTM 10 /
  EPS FWD 20; Valuation 20: PEG FWD; Balance sheet 20: cash vs debt); points
  ramp with percentile rank vs the loaded universe (top/bottom 22% clamp);
  missing data = hard zero. Score 0-100 -> rank tiers (S = top 10%, A = next
  10%, B = 20-50%, C = 50-75%, F = rest; perfect 100 = S+). Tiers are computed
  in ONE cross-sectional pass in `run_screener` after all tickers fetch — they
  are relative, so per-ticker code can't produce them. Pass (for the 3-system
  gate) = tier A or better. RSI(14) + 52-week position are scorecard display
  only, not scored.
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
- **Data sources:** yfinance (price, EPS history, dividends, and ALL azqato
  model inputs — matching azqato's own feed generator field for field: `info`
  revenueGrowth/earningsGrowth/totalCash/totalDebt/priceEpsCurrentYear/pegRatio,
  current-fiscal-year "0y" analyst estimates), Finnhub (`/stock/metric`: EPS,
  5Y growth, balance-sheet ratios, market cap), FRED (Moody's AAA yield, for
  Graham's rate adjustment), Wikipedia (universe).
- **Hosting:** GitHub Pages via GitHub Actions. Screen and deploy are SEPARATE:
  `screen.yml` (cron -> fresh data on the `data` branch) and `deploy.yml`
  (fetch that data -> build -> publish). CI gates: `ci-python.yml`, `ci-frontend.yml`.

## Data flow (and the one decision that matters)

Screen and publish are SEPARATE workflows, decoupled through a dedicated
`data` branch:

- **`screen.yml`** (cron + manual): run the screener -> `web/public/data/results.json`
  -> force-push that one file to the orphan **`data` branch** (single flat commit,
  latest-only). On success it triggers `deploy.yml` via `workflow_run`.
- **`deploy.yml`** (a `web/**` push, a successful Screen, or manual): fetch
  `results.json` from `origin/data` -> `pnpm build` -> upload `web/dist` as a Pages
  artifact -> `deploy-pages`.

**The dataset is NEVER committed to `master`.** It lives only on the isolated
`data` branch, which the `pie` superproject's gitlink never points at -- so a data
refresh never churns the submodule pointer (the original reason data was kept off
`master`; the old design committed `docs/data/results.json` to the tracked branch
and churned it daily). A frontend-only change redeploys immediately by REUSING the
last screened data; it does not re-run the ~515-call screener. Fresh data comes
from the cron screen (or a manual Screen run).

Bootstrap: the `data` branch must exist before the first deploy. Run **Screen**
once; `deploy.yml` fails loud with instructions if `origin/data` is missing.

Why `workflow_run` (not `push: [data]`): a `GITHUB_TOKEN` push emits no push
event (GitHub's loop guard), so the data-branch push cannot trigger deploy
directly -- Screen completion is the link.

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
- `.github/workflows/screen.yml` — cron + manual: run screener -> push results.json
  to the `data` branch -> trigger deploy.
- `.github/workflows/deploy.yml` — `web/**` push / Screen done / manual: fetch data
  from the `data` branch -> build -> deploy to Pages.
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
3. Actions -> General -> Workflow permissions = **read and write** (so `screen.yml`
   can push the `data` branch). The workflow's explicit `permissions: contents:
   write` already requests it; this clears any org-level read-only default.
4. Seed the data: **Run workflow** on **Screen** once -- the `data` branch must
   exist before the first deploy.

After that: the weekday cron (`0 11 * * 1-5`) refreshes data and auto-deploys (via
`workflow_run`); a `web/**` push redeploys with the last data; **Run workflow** on
**Deploy** republishes on demand. Site: `https://<owner>.github.io/screener/`.

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
- Names with no usable (positive) EPS or non-positive/uncomputable growth are
  kept **visible** with valuation N/A (Graham-defensive + Azqato still
  computed — the azqato model ranks loss-makers worst on valuation instead of
  dropping them, matching the upstream screener). Only no-price names are
  hard-excluded as error rows.
