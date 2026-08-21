# Screener3000 — Project Guide

## What this is

A three-system stock screener over six pools — the S&P 500, Dow 30, Nasdaq-100,
and (from azqato) Growth 100 / Value 100 / Dividend 100, the top-100 holdings by
weight of VUG / VTV / VIG — merged into ONE deduplicated universe (~523 names),
plus a 4th **informational** composite score. A Python job fetches fundamentals and
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

Synced with upstream through `e71db99` (2026-08-10). Everything upstream has
published since `a8cf842` (2026-07-16) is `chore: update screener results` data
commits (upstream commits its dataset to `master`; this fork keeps it on `data`
by design). `a8cf842` itself and `d36a503` are vanilla-`docs/`-dashboard changes
with no React analogue. To re-check for drift:
`git fetch upstream && git log upstream/master --oneline -- . ':(exclude)docs/data'`.

A full function-by-function comparison against `upstream/master:stock_screener.py`
(2026-08-10) found the fork at parity or ahead everywhere. Deliberately NOT
ported, and why:

- `_compute_discounted_earnings_*` — upstream itself marks it "not an FCFF/FCFE
  DCF, does not feed the DCF value sub-score"; this fork carries the real
  FCFF/WACC DCF and keeps a leaner output.
- `growth_pct = round(growth_pct * 100, 4)` in `get_combined_data` — upstream
  still rescales Finnhub's already-whole-number `epsGrowth5Y` by 100.
- `combined_score` averaging a missing framework as a real 0% discount — this
  fork averages over the present legs only.
- `datetime.utcnow()` (deprecated) in `write_json` / `_compute_stats`.
- `row["Error"] = "No EPS"` early-return — this fork keeps unvaluable names
  visible with valuation N/A (financial-integrity rules below).
- `graham_metrics`' `min(VA, VB)` and the D/E defensive criterion — this fork
  uses the canonical 1974 formula and Graham's own long-term-debt-vs-working-
  capital / 3-year-average-EPS-growth checks.
- `overall_score(coverage_fraction=...)` — vestigial upstream, unused there.

Ported in the 2026-08-10 sync: `Valuation_Input_Warning` (every reason a row's
Lynch/Graham valuation is N/A, surfaced in the Scorecard) and the separate
`SCORE_DCF_DISCOUNT_*` band constants (same numbers as `SCORE_DISC_BANDS`, kept
apart so a Lynch/Graham recalibration can't silently move the DCF sub-score).

**azqato upstream** (`Azqato/stocks`, `screener.js` + `scripts/fetch_screener_
data.py`): `azqato.py` is a faithful port of the live STOCK model, now at
**scoring v3, "four even pillars"** — the metric weights were rebalanced
upstream (see the Azqato bullet below) and re-ported 2026-08-21. `CLAMP_Q`, tie
handling, tier cuts, the sentinel ranks, and the feed-generator field
definitions are all still verified against the live file. Everything else
published since is inapplicable by design: the MAG 10 toggle (v3.36.0), the ETF
reweighting (v3.37.0), and the v4.0.0 vanilla-HTML redesign. His **ETFs**
(v3.33.0) and **International** (v3.34.x) universes are deliberately NOT
screened here: ETFs are scored by a wholly different technicals-only model with
no EPS for Lynch/Graham to value, and International is local-exchange listings
(`005930.KS`, `7203.T`) that the Finnhub free tier doesn't cover — two of this
fork's three systems would have nothing to score them with, so they could never
clear the gate. His **Growth/Value/Dividend 100** pools ARE screened (see
`INDEX_FETCHERS`). Still unported: upstream's `grossMargin`/`netMargin` feed
fields, which no current metric reads. Adopted from it: the v3.37.2 stale-data
lesson — `Toolbar.tsx`'s freshness threshold is a week, not 3 days, since a
weekday cron leaves Friday's data legitimately ~3 days old on Monday morning.
To re-check: `git clone --filter=blob:none https://github.com/Azqato/stocks`
then `git log --oneline -- screener.js scripts/fetch_screener_data.py`.

The three screens (decoupled on purpose — disagreement is the signal):

- **Azqato** — pure, no-AI RELATIVE percentile model (`azqato.py`), a port of
  the live azqato screener's scoring v3 (azqato.github.io/stocks/screener.js).
  Six metrics in FOUR evenly weighted 25-point pillars (TTM 25: rev TTM 10 /
  EPS TTM 15; FWD 25: rev FWD 10 / EPS FWD 15; Valuation 25: PEG FWD; Balance
  sheet 25: cash vs debt) — trailing growth counts the same as forward
  estimates, EPS outweighs revenue inside both growth pillars; points
  ramp with percentile rank vs the loaded universe (top/bottom 22% clamp);
  missing data = hard zero. Score 0-100 -> rank tiers (S = top 10%, A = next
  10%, B = 20-50%, C = 50-75%, F = rest; perfect 100 = S+). Tiers are computed
  in ONE cross-sectional pass in `run_screener` after all tickers fetch — they
  are relative, so per-ticker code can't produce them. Pass (for the 3-system
  gate) = tier A or better. RSI(14) + 52-week position are scorecard display
  only, not scored. **Because the model is relative, the peer set IS part of
  the score**: azqato's own site loads one pool at a time, so the same name can
  sit two tiers apart there. `run_screener` therefore also re-scores each pool
  as its own cross-section into `azqato.byIndex` (score + tier only) — for the
  Scorecard's "rank inside each pool" panel and nothing else. The grid, the
  tier, and the gate all read the merged cross-section; measured on the
  2026-08-20 dataset, Nasdaq-100 names move a mean 12.8 points (65% change
  tier) between the two, so never conflate them.
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
  shallow-clone `origin/data` and seed the previous `results.json` (so
  `get_universe`'s constituent fallback has a last-known roster; the file is
  gitignored on `master`, so without the seed the fallback is a no-op) ->
  run the screener -> `web/public/data/results.json` + `stats.json` (universe
  aggregate stats: score distribution, sector breakdown, coverage — for future
  monitoring, no dedicated UI page yet) -> force-push those files to the
  orphan **`data` branch** (single flat commit, latest-only). On the first
  weekday of the month, also copies `results.json` into
  `web/public/data/snapshots/{date}.json` and updates its `index.json`
  manifest -- BEFORE force-pushing, prior snapshot files are pulled forward
  from that same `origin/data` clone (GitHub doesn't support
  `git archive --remote`) so they survive each run's flat-commit reset. The
  publish step also refuses to push if `generated_at` still matches the seeded
  copy -- proof the run produced fresh data rather than republishing the seed.
  On success it triggers `deploy.yml` via `workflow_run`.
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
  point. `get_universe` walks `INDEX_FETCHERS` (the six pools, in membership
  order) and wraps each fetch in `_fetch_index_with_fallback`, which on failure
  falls back to that pool's membership in the last published `results.json`
  (`_cached_index_members`) and logs a warning; with no cached members it
  re-raises rather than screening a partial universe. S&P/Dow/Nasdaq come from
  Wikipedia component-list pages (the parent index articles no longer carry a
  symbols table — both fetches are pinned by regression tests); Growth/Value/
  Dividend come from Vanguard's fund-profile holdings API via
  `_fetch_vanguard_top_holdings`, top 100 by weight, dual share classes
  collapsed, with a raw-count band so a truncated response aborts instead of
  quietly shrinking a pool. Also holds the `overall_score()` engine + its `SCORE_*`/`PILLAR_
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
