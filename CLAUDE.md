# Screener3000 — Project Guide

## What this is

A three-system stock screener over the S&P 500, Dow 30, and Nasdaq-100, plus a
4th **informational** composite score. A Python job fetches fundamentals and
scores every name through **three independent screens** (the pass/fail gate);
a static React SPA renders the results. Deployed to GitHub Pages on a weekday
schedule — a public, shareable URL, no account required.

This repo is a fork of `VoxMachina1/graham-screener` (`git remote -v` /
`GET /repos/alloy-and-steel/screener` shows `parent`). Upstream diverged into
its own "v2.0 Methodology Expansion" (a 4-pillar `OverallScore` engine, sector
+ cheap-factor data, Piotroski/Altman distress signals, a screen-grade
FCFF/WACC DCF, `stats.json`, monthly snapshots) with a different frontend
(vanilla `docs/` dashboard + a GSD `.planning/` tree) and CI/branch model. That
scoring/data logic was hand-ported into this fork (not a `git merge` — the two
trees only share 6 file paths and the frontends are incompatible by design;
this fork kept its own Vite/React `web/`, `azqato.py`, and decoupled
`data`-branch CI). Upstream's `OverallScore` was wired in as an **additional,
non-gating** layer to preserve this fork's "three independent systems,
disagreement is the signal" design — see the `Overall` bullet below.

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

**Overall (informational, not gated)** — a 4th, absolute 0-100 composite
(`overall_score()` in `stock_screener.py`), ported from upstream's v2.0
methodology expansion. Does NOT feed `combinedVerdict`/`passesAll`
(`web/src/score.ts` is unchanged) — shown as a separate `Overall` column group
and a Scorecard panel only. Four renormalized-over-present pillars:
**Value 35%** (Lynch/Graham discount + FCF/earnings/shareholder yield +
distance from 52w/5y low + DCF discount), **Quality 30%** (Graham
DefensiveScore, debt/equity, current ratio, ROIC), **Growth 20%** (growth
level + stability), **Safety 15%** (Piotroski F-Score, Altman Z'', reused
Quality leverage/liquidity signals). Discount bands are rate-relativized by
the live AAA yield. A present-but-terrible input (the `WORST_DISCOUNT`
sentinel, negative D/E, non-positive growth, negative DCF discount) scores 0;
a genuinely-absent input is skipped (averaged over what's present); Piotroski/
Altman absent -> neutral 50.0 each (not skipped) so sector-excluded names
don't inherit an inflated Safety from the rest. Sector-gated: Financial
Services/Real Estate skip DCF, Financial Services also skips Altman/EV-EBIT/
earnings-yield (`_sector_allows`). All `SCORE_*`/`PILLAR_WEIGHTS`/`DCF_*`
band constants are `[ASSUMED]` first-pass estimates — monitor `stats.json`'s
`score_distribution`/`pillar_averages` before tuning them.

## Stack

- **Backend:** Python 3.14. `stock_screener.py` (pipeline + OverallScore
  engine), `azqato.py` (pure scoring, unit-testable), `monitor.py` (falsifier
  checks). Deps in `requirements.txt` (requests, pandas, fredapi,
  python-dotenv, lxml, yfinance, scipy — scipy is only for
  `_compute_fcff_reverse_dcf`'s `brentq` root-finder).
- **Frontend:** Vite 6 + React 19 + TypeScript 5.7 + Tailwind v4
  (`@tailwindcss/vite`, `@theme` tokens) + TanStack Table v8 / Virtual v3, under
  `web/`. Package manager **pnpm 11**.
- **Data sources:** yfinance (price, EPS history, dividends, ALL azqato model
  inputs — matching azqato's own feed generator field for field: `info`
  revenueGrowth/earningsGrowth/totalCash/totalDebt/priceEpsCurrentYear/pegRatio,
  current-fiscal-year "0y" analyst estimates — plus, for the Overall engine:
  sector/beta/currency from `.info`, 5y weekly history for price-distance
  signals, and raw cashflow/income/balance-sheet statements for the Phase 6
  factors + Piotroski/Altman/DCF), Finnhub (`/stock/metric`: EPS, 5Y growth
  — a WHOLE-NUMBER percent, e.g. 11.79 == 11.79%, verified against the live
  API; do NOT rescale by 100, that was upstream's bug — balance-sheet ratios,
  market cap), FRED (Moody's AAA yield for Graham's rate adjustment + 10-year
  Treasury `DGS10` for the DCF's cost of equity), Wikipedia (universe).
- **Hosting:** GitHub Pages via GitHub Actions. Screen and deploy are SEPARATE:
  `screen.yml` (cron -> fresh data on the `data` branch) and `deploy.yml`
  (fetch that data -> build -> publish). CI gates: `ci-python.yml` (compile +
  import smoke + `tests/test_*.py`), `ci-frontend.yml`.

## Data flow (and the one decision that matters)

Screen and publish are SEPARATE workflows, decoupled through a dedicated
`data` branch:

- **`screen.yml`** (cron + manual): offline `tests/test_*.py` pre-flight ->
  run the screener -> `web/public/data/results.json` + `stats.json` (universe
  aggregate stats: score distribution, sector breakdown, coverage — for future
  monitoring, no dedicated UI page yet) -> force-push those files to the
  orphan **`data` branch** (single flat commit, latest-only). On the first
  weekday of the month, also copies `results.json` into
  `web/public/data/snapshots/{date}.json` and updates its `index.json`
  manifest -- BEFORE force-pushing, prior snapshot files are pulled forward
  from `origin/data` (a shallow clone; GitHub doesn't support
  `git archive --remote`) so they survive each run's flat-commit reset. On
  success it triggers `deploy.yml` via `workflow_run`.
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

- `stock_screener.py` — universe -> fetch -> score -> `write_json`. Entry
  point. Also holds the `overall_score()` engine + its `SCORE_*`/`PILLAR_
  WEIGHTS`/`DCF_*` constants, the Phase 6 factor helpers (`_compute_fcf_
  yield`, `_compute_ev_ebit`, `_compute_roic`, `_compute_shareholder_yield`,
  `_compute_price_signals`), the Phase 7 distress/DCF helpers (`_compute_
  piotroski`, `_compute_altman_z`, the `_compute_fcff_*`/`_estimate_screen_
  wacc` FCFF/WACC stack), and `_validate_output_dataframe`/`_compute_stats`.
- `azqato.py` — `wilder_rsi`, `pct_of_52w_range`, `azqato_profile` (pure).
- `monitor.py` — falsifier / drift checks.
- `tests/test_*.py` — offline regression suite (vanilla `assert`, no pytest,
  no network) covering the OverallScore engine, Phase 6 factors, Piotroski/
  Altman, the FCFF DCF stack, the output-validation guard, and the KO
  Lynch/Graham formula fixture. Run individually (`python tests/test_X.py`)
  or via the CI/pre-flight loop (`for f in tests/test_*.py; do python "$f"; done`).
- `web/src/` — SPA. `score.ts` (verdicts — Azqato/Lynch/Graham gate only,
  Overall is deliberately NOT here), `columns.tsx` (grid, incl. `g_overall`),
  `DataTable.tsx`, `Scorecard.tsx` (incl. `OverallPanel`), `format.tsx`,
  `Toolbar.tsx`, `MethodologyDialog.tsx`, `App.tsx`.
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
  yfinance --with scipy python stock_screener.py`.) It writes
  `web/public/data/results.json` and `web/public/data/stats.json`.
- **Tests:** `for f in tests/test_*.py; do python "$f"; done` (or the ephemeral
  `uv run` form above, per file) — offline, no API keys needed beyond the
  dummy values each test file sets itself.
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
  `_validate_output_dataframe` (also called from `write_json`, also aborting)
  adds richer checks on top: required columns present, no blank/duplicate
  tickers, >= 60% of rows valid-and-scored, >= 60% with live Finnhub data,
  >= 100 rows with a complete FCFF DCF whose value range/WACC/terminal-value
  share are internally consistent.

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
