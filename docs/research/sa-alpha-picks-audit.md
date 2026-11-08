# Auditing Alpha Picks from its publicly named picks

Question (2026-11-08): rebuilt only from picks that are publicly named, how close does
Seeking Alpha's Alpha Picks (AP) record come to SA's published +294.81% (benchmark
+100.19%) at 2026-10-30? How concentrated is the gain? Is the record just momentum?
Background on the product and its rules: `docs/research/seeking-alpha-quant.md`.

Sources: pick lists and returns come from screenshots of SA's own AP Performance,
Portfolio and Closed tabs that were published on review pages: Retire Before Dad
(<https://www.retirebeforedad.com/alpha-picks-review/>, 2026-10-27, unredacted), Real
World Investor (<https://realworldinvestor.com/alpha-picks-review/>, 2026-06-12), Wall Street
Survivor (<https://www.wallstreetsurvivor.com/alpha-picks-review/>, partly redacted),
MatchMyBroker (<https://www.matchmybroker.com/tools/alpha-picks-by-seeking-alpha-review>, blurred)
and TraderHQ (<https://traderhq.com/alpha-picks-seeking-alpha-vs-seeking-alpha-premium/>,
blurred). Further sources are TraderHQ's review text, a TickerNerd image of an SA landing
page, and the Perpetual Alpha blog. That blog's homepage table
(<https://www.perpetual-alpha.com/>, captured 2026-11-08) mirrors SA's Current tab: its newest
row is MU 2025-10-15 and it still lists LRN, which SA closed on 2025-11-04, so it shows the
Current tab at some date between 2025-10-15 and 2025-11-03. The only Wayback Machine copy is
from 2025-07-13
(<http://web.archive.org/web/20250713015435/https://www.perpetual-alpha.com/>), and the CSV's
`archive_url` column marks the rows it contains. The blog also reposts SA's pick and removal
notes. A few items are search-result snippets of seekingalpha.com pages, and they are labelled
as snippets. seekingalpha.com itself returned HTTP 403 and was not fetched any other way.
Prices are from yfinance 1.8.0, factors from the Ken French data library. All of the review
sites are secondary sources, and most of them earn affiliate commissions from SA. Every figure
below is printed by `backtests/alpha_picks_audit.py`.

Reproduce (the first run downloads data; later runs read the caches in `/tmp/sa-tests/`):

    uv run --no-project --with yfinance --with pandas --with numpy --with statsmodels \
        --with pyarrow python -I backtests/alpha_picks_audit.py

`--json PATH` also writes every result to a file. A symbol Yahoo returns nothing for (TA)
gets a `.missing` marker in the cache, so later runs stay offline. The input CSV is
matched by `.gitignore`'s `*.csv` rule. It needs a `!backtests/alpha_picks_public_picks.csv`
exception in the commit that adds it, or the script cannot run from a fresh checkout.

## Answer in brief

- **SA's per-pick numbers can be reproduced from prices, using SA's own convention.** The
  rebuild uses no dividends and (H+L+C)/3 fills from mid-2024. Over 36 legs (32 picks) with a
  published return, its median error is 0.21%: 21 legs fall within 0.5% and 33 within 2%.
  Using SA's own published purchase and sell prices instead, 25 of 27 legs fall within 0.5%.
  That second test checks only the price convention, not the dates. SA's per-pick SPY column
  matches price-only SPY in 24 of 24 cases (median 0.02%). This confirms the pick dates of
  those 32 picks; FN and DY are checked only weakly, by a purchase price inside the day's
  range. The other 32 usable picks, including all 30 of unknown status, are untested.
- **SA's numbers leave out dividends and, since 2024, do not fill at the open.** This
  contradicts its help page. Of the 9 purchase prices before 2024-07-31, 8 equal the open. Of
  the 17 after, none does: all lie inside the day's range, a median 0.71% from (H+L+C)/3. The
  data place the switch between 2024-04-01 and 2024-10-15. The published +100.19% benchmark is
  within 0.5 pp of SPY's price-only return since the 2022-07-01 open (+100.69%). With
  dividends, SPY returned +112.24%.
- **The headline TWR cannot be rebuilt.** Only 66 of the 108 picks made by 2026-10-30
  are usable, and just 3 of the 16 from 2022. Before 2023-08-01 the book holds 1 to 9 stocks.
  Six are documented SA names, mostly large winners (SMCI, MOD, MHO, POWL), alongside AMPH
  (−52%) and TEX (−3%). The other three (CAAP, UBER, GRBK) come only from the survivor list
  below. That book compounds to +374.1% by 2024-10-04, against SA's +145.3%, and +681.9% over
  the full period, against SA's +294.81%. After 2024-10-04 the rebuild does not match SA
  either. Measured SA's way, it runs between −2.7 and +8.2 pp of SA at the snapshots, depending
  on the snapshot and on which close it reflects. The near-match at 2026-10-30 (+59.3% against
  SA's +60.9%) is where that drifting gap happens to land, not a sign that the two series agree.
- **Half the sample is a survivor list.** 32 of the 66 usable picks are known only because they
  were still in SA's Current tab around 2025-10-15. On 2026-09-01 the rebuild holds 54 positions
  open, while TraderHQ counts 51 active out of SA's 104 picks. So at least 3 of the picks
  modelled as held had in fact closed. The bounding variants (§3) leave the conclusions
  intact: value÷contributions runs from +97.2% to +102.5%, and the six-factor alpha with 10 or
  more holdings from +12.4% to +15.4% a year, with t never above 1.36.
- **The gain is concentrated.** In the rebuilt portfolio ($1 per pick), the top 5 picks earn
  45.8% of the net dollar gain (42.8% of the winners' gross gain), and the top 10 earn 70.1%
  (65.5%). The median pick returned +37.5%, against +30.9% for SPY bought on the same dates.
  Only 35 of 66 picks beat their own SPY leg. Capping every pick at +100% leaves +38.1%,
  against +35.6% for same-date SPY.
- **Much of it is momentum, beta and size.** Over Sep 2023 to Sep 2026, once the portfolio
  holds 10 or more stocks, the six-factor alpha is +15.4% a year (t 1.36), which is not
  significant. Over the holdings cutoffs 5–30 it runs from +5.7% to +18.9% (t 0.54–1.63). The
  loadings are momentum 0.78 (t 3.3), market 1.60 and small-cap 0.78. The full-sample alpha
  (+36.6%/yr, t 3.36) comes from the months with few holdings. October 2026 is missing from
  the factor data. In that month the rebuilt portfolio returned −12.7%, against −0.9% for its
  SPY legs.

## 1. What was collected

`backtests/alpha_picks_public_picks.csv` has 86 rows. There is one row per pick, or one
per leg where SA shows a partial sale as its own closed row (SMCI, APP, CLS and POWL). The
rows cover 72 dated picks and 10 undated names. The required columns are ticker,
pick_date, exit_date, published_return_pct, as_of and source_url. The extra columns are
leg, SA's published purchase and sell prices, SA's SPY figure, status, `survivor_table_only`
(see below), `archive_url` and notes.

| | count |
|---|---|
| Picks SA had made by 2026-10-30 (16 in 2022, then 24 a year; TraderHQ's 104 run to the 2026-08-17 pick) | 108 |
| Dated picks in the CSV | 72 |
| Usable for return math | **66** (66 of 108; also 66 of TraderHQ's 104) |
| Excluded: closed, exit date unknown | TA, META, PEP, GM, ZETA, ITRN |
| Excluded: no pick date | AMR, NUE, CVX, COP, LTHM, HLIT, RGA, GCT, GOOGL, URI |

Usable picks by pick year: 2022 3 of 16, 2023 13 of 24, 2024 17 of 24, 2025 23 of 24,
2026 10 of 20.

**Renamed tickers.** Three picks are priced under their current Yahoo symbol, which carries the
full pre-rename history:
- ATGE → CVSA. Adtalem became Covista on 2026-02-24.
- LC → HAPN. LendingClub moved to Nasdaq as Happen on 2026-06-22.
- COMM → VISN. CommScope became Vistance Networks on 2026-01-14 and has since paid $10 and $5
  special dividends.

From the pick-date open to 2026-10-30, with dividends, they returned +61.7%, −6.2% and +56.7%.
Without dividends, the way SA computes, VISN shows −59.4% at 2026-09-25 (§4).

**Status.** Only 36 of the 66 have a documented status after 2025-10-15. The other 30 are
**modelled as still held** to 2026-10-30, and §3 bounds that assumption. TEX's stated pick
date, 2023-01-16, was a market holiday, so it enters at the next session.

**Exit windows.** The 2025-07-13 archived table still lists PEP (picked 2024-01-16), GM (picked
2024-05-01, a pick date found only there) and ITRN (2025-02-18). All three are gone from the
later table, so they closed between those two states. They stay out of the base run and are
added in two exit-window variants (§3). ZETA is already absent in July.

How tickers were attached to rows:
- Most rows name the ticker outright.
- Four rows on TraderHQ's blurred Closed tab (LRN, QTWO, SFM, DXPE) are matched on pick date
  plus sector, since SA makes one pick per date.
- FN and DY are partly visible under Wall Street Survivor's redaction. They are kept because
  SA's purchase price falls inside that day's range, which is a weak check.

## 2. Are the dates right? Rebuilt vs published

**Fill prices** are SA's purchase price compared with yfinance's split-adjusted,
dividend-unadjusted prices on the entry day:

| Picks | n | Exactly the open | Median abs. gap to the open | Median abs. gap to (H+L+C)/3 | Exactly the previous close | Inside the day's range |
|---|---|---|---|---|---|---|
| before 2024-07-31 | 9 | 8 | 0.00% | 1.73% | 1 (MHO) | 8 |
| from 2024-07-31 | 17 | 0 | 4.11% | 0.71% | 1 (B) | 17 |

**MHO, the one early miss.** The pick note gives $36.23, below that day's low of $36.69.
$36.23 is exactly the 2022-09-30 close, the session before the stated 2022-10-03 pick date.
So either SA filled the launch-era pick at the previous close, or the pick took effect a
session earlier than stated. No other pre-switch purchase price equals the previous close.
B (2026-01-02) is within 0.05% of its previous close, but it is also within 0.18% of its
(H+L+C)/3, so it says nothing about the convention.

**Sell prices follow the same split.** SMCI's March 2024 partial sale is exactly the close
(91.10). Later sell prices track (H+L+C)/3, not the close: SMCI 34.22 against a close of 33.07
and (H+L+C)/3 of 34.42, and APP 709.33 against 704.09 and 709.70.

**The switch date is bracketed, not pinned.** The last fill at the open is EAT on 2024-04-01,
and the first later fill not at the open is AGX on 2024-10-15. On the sell side, the last sale
at the close is 2024-03-19 and the first later sale not at the close is 2024-10-30. AlphaYou
(secondary) says SA moved to volume-weighted prices on 2024-07-31, and the `sa` mode uses that
date. The switch date matters little:
- **Per leg,** no published leg falls between 2024-07-31 and 2024-10-15. A switch on 2024-10-15
  (`sa_late`) gives identical per-leg errors.
- **Portfolio,** TWR moves from +651.0% to +651.3% (SYF and PPC are the picks in between).

SA's help page still says opens and closes.

**Per-leg returns.** The 36 legs (32 picks) with a published return and date were rebuilt to
the same date. Error is |rebuilt growth ÷ published growth − 1|.

| Rebuild | n | Median error | Within 0.5% | Within 2% |
|---|---|---|---|---|
| **sa: no dividends, (H+L+C)/3 fills from 2024-07-31 (independent rebuild)** | 36 | **0.21%** | **21** | **33** |
| sa_late: as sa, switch at 2024-10-15 | 36 | 0.21% | 21 | 33 |
| spec: open→close, dividends reinvested (the method the task and SA's help page give) | 36 | 1.50% | 12 | 19 |
| SA's own buy and sell prices, no dividends (a check of the price convention only) | 27 | 0.00% | 25 | 25 |
| SPY, price-only, sa fills, against SA's SPY column | 24 | 0.02% | 24 | — |
| SPY, total return, open→close, against SA's SPY column | 24 | 1.52% | 7 | — |

The `sa` rebuild matches SA's figures to within 2% on 33 of 36 legs. That confirms the pick
dates of those picks. A further 2 usable picks (FN, DY) have a published purchase price inside
the entry day's range. The other 32 usable picks have no published figure, so their dates are
**untested**: all 30 of unknown status, plus OKTA and the second CLS pick. That includes the
off-schedule EZPW 2025-04-03 and MFC 2025-05-02, which §3 re-runs on SA's schedule dates.

Dividends separate the conventions on dividend payers. POWL's partial sale was published at
+900.29%. Price-only it is +898.72% (sa) or +900.11% from SA's prices, and with dividends
+924.93%. TIGO was published at +48.97%: +48.97% from SA's price, +49.89% sa, and +62.35% with
dividends. AGX was published at +356.94%, against +390.23% to spec. Most of the AGX gap is the
VWAP-style fill: the purchase price was 118.69 while the day opened at 114.00. Three legs miss
by more than 2% even SA's way:
- **TEX:** −1.21% published, −3.51% rebuilt. Its pick date was a holiday.
- **LITE:** +41.73% per TraderHQ, +36.84% rebuilt. TraderHQ's 2026-09-01 date may be loose.
- **ICHR:** −51.36% published, −52.47% rebuilt.

**SA's benchmark**, against SPY bought at the 2022-07-01 open and held, at the snapshot date's
close (D) and at the previous session's (D−1):

| SA snapshot | Source | SA AP | SA benchmark | SPY price-only, D | Gap D | Gap D−1 | SPY with dividends, D |
|---|---|---|---|---|---|---|---|
| 2024-04-17 | SA landing page (known stale) | +125.28% | +38.69% | +32.93% | −5.76 pp | −4.97 pp | +36.55% |
| 2024-10-04 | SA landing page | +145.31% | +51.82% | +52.16% | +0.34 pp | −1.03 pp | +57.29% |
| 2025-02-20 | SA help centre ("taken on February 21, 2025"; date assumed) | +136.29% | +49.41% | +62.09% | +12.68 pp | +13.36 pp | +68.12% |
| 2026-04-10 | EarnForex | +316.61% | +79.99% | +80.44% | +0.45 pp | +0.57 pp | +89.86% |
| 2026-06-09 | WallStreetZen | +421.61% | +96.50% | +95.73% | −0.77 pp | −0.19 pp | +105.96% |
| 2026-06-12 | Real World Investor | +415.28% | +95.44% | +96.98% | +1.54 pp | +0.48 pp | +107.27% |
| 2026-07-17 | MatchMyBroker (search index) | +371.06% | +99.68% | +97.39% | −2.29 pp | −0.32 pp | +108.23% |
| 2026-10-01 | Smart Money with Kai | +352.65% | +102.43% | +102.89% | +0.46 pp | +0.10 pp | +114.57% |
| 2026-10-27 | Retire Before Dad | +300.99% | +102.75% | +104.39% | +1.64 pp | +0.50 pp | +116.16% |
| 2026-10-30 | MatchMyBroker | +294.81% | +100.19% | +100.69% | +0.50 pp | +4.12 pp | +112.24% |

At D or D−1, every snapshot from October 2024 on tracks price-only SPY to within about
0.5 pp. Two snapshots fit neither date: 2024-04-17, a landing page already known to be stale
(`seeking-alpha-quant.md` §3), and the help-centre +136.29% / +49.41%, which is off by 13 pp
and so is not a February 2025 figure. Neither is used.

The check is good only to about 1–2 pp, and it cannot tell which close a figure reflects.
RBD's per-pick figures reproduce the 2026-10-27 closes exactly (STRL +488.66%, CLS +912.97%),
yet its benchmark is 1.64 pp from price-only SPY at that close and 0.50 pp at the one before.
So SA's benchmark is not exactly buy-and-hold price-only SPY. Its VWAP-style fills alone would
explain differences of this size.

**Consistency checks:**
- **SA's top-13 list.** SA's Performance tab on 2026-10-27, sorted by return, lists 13 rows
  down to +254.66%. No pick modelled as still held shows a rebuilt return above that floor
  without being in the list.
- **POWL conflict.** MatchMyBroker's Current-tab image is labelled 2026-10-13. It still
  lists the 2023 POWL pick as held at +917.64%, which is exactly the 2026-10-12 close
  measured SA's way (table above). That its other rows also match the 10-12 closes was
  checked once by hand and is not part of the script. On 2026-10-27, RBD's list shows only
  POWL's 2026-09-08 partial sale, at +900.29%. The base run keeps the remainder held. A
  variant that closes all of POWL on 2026-09-08 is reported in §3.

## 3. Portfolio vs SA's +294.81%

Construction:
- $1 per pick at entry (the entry open in spec mode). Benchmark legs put $1 into the ETF at
  the same open.
- At each documented partial sale, sell $1 of stock. This is SA's stated "winner" rule (sell
  the initial purchase amount). The ETF leg sells the same fraction of its shares.
- Close at the documented exit; otherwise hold to the 2026-10-30 close.
- Sale proceeds sit in cash at 0% for value÷contributions.
- TWR chains daily Modified-Dietz returns, with buys at the start of the day and sales at
  the close.

Every variant that was run. "Early TWR" runs from inception to 2024-10-04 and "late TWR" from
2024-10-04 to 2026-10-30. "Open 9/1" counts open positions among picks made by 2026-08-17,
against TraderHQ's 51. Alphas are monthly six-factor, per year (t, OLS). The "≥ 10" sample
starts the month after the book first holds 10 stocks.

| Variant | n | AP value/contrib | AP TWR | SPY value/contrib | Early TWR | Late TWR | Median pick | Top-5 share, net / gross | Open 9/1 | Alpha, all | Alpha, ≥ 10 | UMD, ≥ 10 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| spec (base) | 66 | +100.6% | +681.9% | +35.6% | +374.1% | +64.9% | +37.5% | 45.8 / 42.8% | 54 | +36.6% (3.36) | +15.4% (1.36) | 0.78 |
| spec, no partial sales | 66 | +98.0% | +663.3% | +35.6% | +368.1% | +63.1% | +37.5% | 45.3 / 42.3% | 54 | +35.8% (3.26) | +14.3% (1.25) | 0.77 |
| spec, POWL fully closed 2026-09-08 | 66 | +102.6% | +683.0% | +35.6% | +374.1% | +65.1% | +37.5% | 46.8 / 43.9% | 54 | +36.5% (3.36) | +15.4% (1.36) | 0.78 |
| spec, AGX + SFM winner sale at first doubling | 66 | +99.3% | +684.8% | +35.3% | +374.1% | +65.5% | +41.1% | 45.9 / 42.9% | 54 | +36.4% (3.35) | +15.4% (1.36) | 0.76 |
| spec, EZPW + MFC on schedule dates | 66 | +100.7% | +681.8% | +35.5% | +374.1% | +64.9% | +37.5% | 45.7 / 42.7% | 54 | +36.6% (3.36) | +15.4% (1.36) | 0.78 |
| spec, documented status only | 36 | +141.8% | +931.0% | +30.4% | +444.1% | +89.5% | +28.1% | 59.5 / 55.4% | 24 | +46.5% (3.41) | +23.0% (1.36) | 1.13 |
| spec, drop rows citing only the mirror's table | 41 | +130.2% | +905.2% | +30.3% | +450.8% | +82.5% | +39.3% | 56.9 / 53.1% | 29 | +45.9% (3.45) | +21.8% (1.34) | 1.17 |
| spec, drop all survivor-list picks | 34 | +139.3% | +898.1% | +29.6% | +449.7% | +81.6% | +17.3% | 64.1 / 59.4% | 22 | +46.2% (3.34) | +21.8% (1.27)¹ | 1.17 |
| spec, unknown-status picks closed 2025-10-15 | 66 | +97.2% | +685.9% | +27.2% | +374.1% | +65.8% | +29.6% | 47.3 / 44.4% | 24 | +36.5% (3.18) | +14.0% (1.15) | 0.97 |
| spec, unknown-status picks closed 2026-04-13 (cutoff + 180 d) | 66 | +102.5% | +637.9% | +29.3% | +374.1% | +55.6% | +30.4% | 44.9 / 42.2% | 24 | +35.6% (3.11) | +12.4% (1.05) | 0.96 |
| spec, + PEP/GM/ITRN closed 2025-07-14 | 69 | +96.5% | +667.2% | +34.9% | +367.2% | +64.2% | +33.2% | 45.6 / 42.6% | 54 | +35.9% (3.33) | +14.0% (1.28) | 0.77 |
| spec, + PEP/GM/ITRN closed 2025-11-03 | 69 | +97.1% | +662.0% | +35.5% | +367.2% | +63.1% | +35.6% | 45.4 / 42.4% | 54 | +35.7% (3.31) | +13.8% (1.27) | 0.77 |
| sa (no dividends, (H+L+C)/3 fills from 2024-07-31) | 66 | +94.7% | +651.0% | +32.7% | +371.4% | +59.3% | +33.5% | 47.9 / 43.8% | 54 | +35.8% (3.25) | +14.4% (1.26) | 0.78 |
| sa, switch 2024-10-15 | 66 | +94.7% | +651.3% | +32.7% | +371.6% | +59.3% | +33.5% | 47.9 / 43.8% | 54 | +35.8% (3.25) | +14.4% (1.26) | 0.78 |
| **SA published, 2026-10-30, all 108 picks** | 108 | — | **+294.81%** | — | **+145.3%** | **+60.9%** | — | — | 51 (TraderHQ) | — | — | — |

¹ This sample starts 2023-11-15 and dips to 9 holdings once. Every other ≥ 10 sample stays at
10 or more throughout.

Notes on the variants:
- **SPY TWR** is +119.9% in every spec variant (+109.2% sa). The rebuilt SPY legs start at
  the first entry (2022-10-03), not at SA's 2022-07-01, so the inception rows are not like
  for like on the benchmark side. Measured SA's way, the rebuilt SPY legs gain +58.4% to
  2024-10-04, against SA's +51.8%.
- **The winner-sale variant** sells $1 at the first close at 2× the entry: SFM on 2025-01-31
  and AGX on 2025-06-05. That is the earliest date the "winner" label can apply. SA's rule
  sells only after a further 180 days at Hold, so any real sale came later.

Rebuilt TWR from 2024-10-04 (SA's landing-page snapshot, the first after coverage fills in)
to each later snapshot, against SA's growth implied by its own since-inception figures:

| To snapshot | SA AP | Rebuilt sa, D | Gap, D | Rebuilt sa, D−1 | Gap, D−1 | Gap spec, D |
|---|---|---|---|---|---|---|
| 2026-04-10 | +69.8% | +78.0% | +8.2 pp | +75.4% | +5.6 pp | +11.4 pp |
| 2026-06-09 | +112.6% | +111.0% | −1.6 pp | +115.8% | +3.1 pp | +3.7 pp |
| 2026-06-12 | +110.1% | +118.3% | +8.2 pp | +115.2% | +5.1 pp | +13.8 pp |
| 2026-07-17 | +92.0% | +91.2% | −0.9 pp | +92.6% | +0.6 pp | +4.5 pp |
| 2026-10-01 | +84.5% | +86.2% | +1.7 pp | +83.3% | −1.3 pp | +7.4 pp |
| 2026-10-27 | +63.5% | +65.5% | +2.0 pp | +60.8% | −2.7 pp | +7.7 pp |
| 2026-10-30 | +60.9% | +59.3% | −1.6 pp | +67.8% | +6.9 pp | +4.0 pp |

The rebuilt book's day-to-day moves are large enough that one session shifts the gap by up to
8.5 pp,
and the SPY check above cannot say which session a third-party figure shows. Measured SA's way,
the rebuild sits between −2.7 and +8.2 pp of SA over this period, more often above than below,
with no stable sign. Measured to spec it sits +2.8 to +13.8 pp above (dividends included). So
the rebuilt book tracks SA's moves roughly once coverage fills in, but it does not reproduce
SA's level, and the near-match at 2026-10-30 is one point on a drifting gap.

Consecutive snapshots at their stated dates give the same picture (only the first pair passes
the SPY check at D on both ends):
- **2026-04-10 → 2026-06-09:** SA +25.2%, rebuilt sa +18.5%.
- **2026-06-12 → 2026-07-17:** SA −8.6%, rebuilt sa −12.4%.
- **2026-10-01 → 2026-10-27:** SA −11.4%, rebuilt sa −11.1%.

**Open positions against TraderHQ.** On 2026-09-01, among picks made by 2026-08-17, the base
rebuild holds 54 positions open out of 66. TraderHQ's trade-log analysis has SA at 51 active
and 53 closed out of 104. Even if all 38 picks missing here were closed, at least 3 of the picks
modelled as held must actually have closed. If the 6 missing 2026 picks were still open (an
assumption), at least 9 must have. Of the 54, 30 are of unknown status. As a base rate, 3 of the
41 picks in the 2025-07-13 table (PEP, GM, ITRN) were gone from it about three months later. The
two "unknown closed" variants are the bounds: they close all 30 unknown-status picks, leaving 24
open, well below TraderHQ's 51. The truth lies between, and every headline measure stays inside
the ranges in the variant table.

**Why the rebuilt portfolio misses +294.81%:**

1. **Different quantities.** SA reports a time-weighted return. Value÷contributions
   (+100.6%) measures the average dollar, so the two must not be compared. Wall Street
   Survivor's "94% vs 28%" is a third quantity again, the simple mean per pick.
2. **Missing picks, and which ones are missing.** The rebuilt book holds 1 stock at the start
   and does not reach 10 until 2023-08-01. Before that it holds 9 picks:
   - Big documented winners: MHO +230%, SMCI +352%, MOD +350%, POWL +792%.
   - Losers: TEX −3% and AMPH −52%.
   - Three names known only from the survivor list: CAAP +118%, UBER +74% and GRBK +6%.

   Compounded, these give +374.1% to 2024-10-04, against SA's +145.3%. Most of the 13 missing
   2022 picks and 11 missing 2023 picks left the portfolio without a public record. The sample
   keeps the names that either were still held in October 2025 or were big enough winners to
   be shown.
3. **The survivor list.** 32 of the 66 usable picks enter only because they were in SA's
   Current tab around 2025-10-15. Of these, 25 cite only the mirror's table and 7 cite a pick
   note for a name in it. By pick year they are 2023 5 of 13, 2024 12 of 17 and 2025 15 of 23.
   Picks that closed before then are present only when a removal note or a screenshot happens
   to survive. For returns up to October 2025 this conditioning biases upward, since a pick
   that drew a Sell rating and was removed at a loss is less likely to be in the sample. But
   the other half is selected even harder: it is RBD's top-13 list sorted by return, plus
   removal notes. The survivor-list picks average +59.4% (median +45.2%), against +139.3%
   (median +17.3%) for the rest. So dropping them raises every result (table rows "drop …").
   Adding the three picks known to have dropped out between July and October 2025 lowers
   value÷contributions by 3.5–4.1 pp and the ≥ 10 alpha by 1.4–1.6 pp.
4. **What the missing picks earned, implied.** Take Wall Street Survivor's per-year means
   as of 2026-09-25 (secondary; method not documented). The 40 picks missing here would
   have averaged +47.7% each, against +121.7% for the 66 present. By year: 2022 +58.8%,
   2023 +97.6%, 2024 +19.3%. The 2025 row cannot be reconciled: its one missing pick would
   need −26.6% with a same-date S&P of −39.8%. That points to 2025 picks of unknown status
   having closed earlier than this model holds them.
5. **Partial sales and conventions are small.** Ignoring partial sales moves
   value÷contributions by 2.6 pp. SA's no-dividend, VWAP-style convention moves it by
   5.9 pp; the run does not split that between dividends and fills.
6. **Weights.** On 2026-10-27, SA's Holding % for seven recent picks is a median 0.83 of the
   rebuilt weights. Measured in units of a new pick's stake, SA's book is therefore about 20%
   larger than the rebuilt one. That is less than 42 more picks would add if they were all
   still held, which is consistent with the open-count check.

## 4. Concentration

These figures use the spec base portfolio: 66 picks, a net gain of $66.38 on $66 (the winners'
gross gain is $70.97), 45 winners and 21 losers.

| | value |
|---|---|
| Top 1 pick | 13.5% of the net gain, 12.6% of the gross (CLS 2023-10-16, +895.6% including the partial sale) |
| Top 3 | 33.0% / 30.9% (+ POWL 2023-05-15 +792.0%, APP 2023-11-15 +506.0%) |
| Top 5 | 45.8% / 42.8% (+ STRL 2023-08-01 +454.1%, AGX 2024-10-15 +390.2%) |
| Top 10 | 70.1% / 65.5% (+ MU 2025-10-15 +360.2%, SMCI +351.6%, MOD +350.1%, EAT 2024 +314.0%, CLS 2024 +237.1%) |
| Median pick | +37.46% (mean +100.57%) |
| Same-date SPY per pick | median +30.92%, mean +35.57%; picks beating their SPY leg: 35 of 66 |
| Without the top 5 | +59.02% value/contrib (same-date SPY +32.82%); TWR +483.7% (SPY +120.0%); median +32.93% |
| Every pick capped at +100% | +38.09% value/contrib; the net gain shrinks 62.1%, the gross gain 58.1% |
| By evidence | documented status +141.83% mean (n 36), unknown status +51.07% (n 30); survivor-list only +59.44% (n 32), other +139.29% (n 34) |

Across the variants in §3, the top-5 share of the net gain runs from 44.9% to 64.1%.
The worst picks were ICHR 2026 (−63.0%), LRN (−52.9%), AMPH (−51.8%), FN (−39.4%), DY
(−37.3%) and PYPL (−35.0%). The record is a handful of 4- to 10-baggers on top of a pick
distribution whose middle sits a few points above the market. TraderHQ found that a +100% cap
cuts total gains by 61.5%. This rebuild reproduces that in direction and size: 62.1% of the net
gain.

Pick-year cohorts, SA's convention, as of 2026-09-25, beside Wall Street Survivor's table
for all picks:

| Year | n here | Mean here | Median | Win rate | Same-date SPY | WSS n | WSS mean | WSS S&P | WSS win rate |
|---|---|---|---|---|---|---|---|---|---|
| 2022 | 3 | +314.6% | +349.1% | 100% | +54.8% | 16 | +106.8% | +29.2% | 75% |
| 2023 | 13 | +303.6% | +85.7% | 77% | +64.6% | 24 | +209.2% | +46.8% | 79% |
| 2024 | 17 | +102.6% | +47.6% | 76% | +38.3% | 24 | +78.3% | +30.0% | 71% |
| 2025 | 23 | +62.8% | +36.9% | 78% | +24.2% | 24 | +59.1% | +21.5% | 75% |
| 2026 | 10 | −4.7% | −4.1% | 40% | +9.6% | 18 | — | — | — |

Every cohort that WSS reports is higher here, which is the selection bias of §3 shown
directly. In this convention VISN counts at −59.4%, because SA's no-dividend method treats its
$15 of special dividends as a loss.

## 5. Is it just momentum?

The monthly series is the rebuilt spec base portfolio's TWR. The regression is excess
return on Fama-French 5 plus UMD (Ken French monthly and daily files, which end
2026-09). Alpha is per year (monthly × 12, daily × 252). t-statistics are given as OLS /
Newey-West, and loadings carry their OLS t-statistic.

| Sample | Series | n | Alpha/yr | t | Mkt | SMB | HML | RMW | CMA | UMD | R² |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Oct 2022 – Sep 2026, monthly | AP | 48 | +36.6% | 3.36 / 2.88 | 1.45 (6.5) | 1.27 (3.4) | −0.66 (−1.7) | 0.01 | −0.64 (−1.4) | 0.69 (3.3) | 0.723 |
| same, daily | AP | 1002 | +29.3% | 2.79 / 3.00 | 1.48 | 0.76 (9.8) | −0.12 | −0.11 | −0.30 (−3.4) | 0.68 (16.1) | 0.664 |
| Sep 2023 – Sep 2026 (≥ 10 holdings), monthly | AP | 37 | **+15.4%** | **1.36 / 1.36** | 1.60 (6.2) | 0.78 (2.1) | −0.30 | −0.21 | −0.16 | **0.78 (3.3)** | 0.804 |
| Aug 2023 – Sep 2026, daily | AP | 795 | +14.3% | 1.36 / 1.51 | 1.36 | 0.67 (8.8) | −0.09 | −0.27 (−3.3) | 0.04 | 0.82 (16.8) | 0.718 |

**Holdings-cutoff sensitivity** (monthly, six factors; the sample starts the month after the
book first holds k stocks, and the book never falls below k afterwards):

| k | First held | Months | Alpha/yr | t OLS / HAC | Mkt | SMB | UMD | R² |
|---|---|---|---|---|---|---|---|---|
| 5 | 2023-05-01 | 40 | +18.9% | 1.63 / 1.61 | 1.71 | 0.74 | 0.72 | 0.784 |
| 10 | 2023-08-01 | 37 | +15.4% | 1.36 / 1.36 | 1.60 | 0.78 | 0.78 | 0.804 |
| 15 | 2023-11-15 | 34 | +14.9% | 1.20 / 1.29 | 1.66 | 0.71 | 0.79 | 0.780 |
| 20 | 2024-04-01 | 29 | +5.7% | 0.54 / 0.56 | 1.50 | 0.82 | 0.64 | 0.840 |
| 25 | 2024-07-15 | 26 | +9.9% | 0.86 / 0.92 | 1.50 | 0.95 | 0.64 | 0.851 |
| 30 | 2024-11-15 | 22 | +6.5% | 0.58 / 0.53 | 1.56 | 0.59 | 0.75 | 0.885 |

Smaller models on the full monthly sample give the following alphas:
- CAPM: +26.7% a year (t 2.18), R² 0.542.
- Market + UMD: +24.9% (t 2.08), with UMD 0.41 (t 1.9).
- FF5: +35.3% (t 2.92).

The same-date ETF portfolios use the same dates and partial-sale fractions, holding the ETF
instead of the pick:

| Benchmark | Value/contrib | TWR | Monthly FF6 alpha/yr, all (t) | Monthly FF6 alpha/yr, ≥ 10 holdings (t) | UMD loading, ≥ 10 | AP − ETF per month, all (t) | AP − ETF per month, from 2023-09 (t) |
|---|---|---|---|---|---|---|---|
| AP | +100.6% | +681.9% | +36.6% (3.36) | +15.4% (1.36) | 0.78 | — | — |
| SPY | +35.6% | +119.9% | +0.2% (0.37) | −0.2% (−0.28) | 0.01 | +3.06% (2.75) | +1.93% (1.61) |
| SPMO | +53.3% | +175.8% | +4.0% (0.93) | +7.3% (1.34) | 0.45 | +2.49% (2.28) | +0.96% (1.00) |
| MTUM | +40.5% | +122.5% | −0.6% (−0.17) | +0.5% (0.11) | 0.64 | +2.94% (2.77) | +1.47% (1.55) |
| QMOM | +21.7% | +64.3% | −9.2% (−1.70) | −5.8% (−0.81) | 0.37 | +3.58% (3.59) | +2.06% (2.18) |
| XMMO | +23.0% | +96.1% | −0.6% (−0.11) | +0.2% (0.03) | 0.42 | +3.22% (3.56) | +1.93% (2.34) |

What this shows:
- **Momentum explains part of it, not all.** AP's UMD loading (0.68–0.82) is larger than
  any momentum ETF's. With market beta near 1.5 and a small-cap tilt it gives AP an R² of
  0.66–0.80. That fits the paper's finding that the Quant Rating loads mostly on momentum
  (`seeking-alpha-quant.md` §5).
- **The alpha is not robust.** It is significant only when the 2022–23 months with 1–9
  holdings are included. Once 5 or more names are held, alpha runs from +5.7% to +18.9% a
  year, and no cutoff reaches t 2. The bounding variants in §3 stay at +12.4% to +23.0%
  (t 1.05–1.36). It is also flattered by missing October 2026, when AP returned −12.7%.
- **Against momentum ETFs, AP is ahead on point estimates** in every pairing. From 2023-09,
  only the QMOM (t 2.18) and XMMO (t 2.34) spreads clear t = 2. The spreads to SPMO (t 1.00)
  and MTUM (t 1.55) do not. The factor model prices SPY, SPMO, MTUM and XMMO near zero, which
  gives some confidence in it. QMOM is the exception: −6% to −11% a year, with |t| up to 2.2
  (daily, all months: −10.7%, t −2.03 / −2.20).
- **Verdict.** Within the limits below, the public record is consistent with a high-beta,
  small-cap, momentum-loaded stock picker that caught several extreme winners in 2023. It
  is not evidence of factor-adjusted skill.

## Verdict

- **The published per-pick numbers are real and reproducible** for the 32 picks that carry
  one. But they are computed without dividends, and with VWAP-style fills since some date
  between April and October 2024. Both differ from SA's help page. The benchmark's missing
  dividends cost it about 12 pp at 2026-10-30.
- **The since-inception +294.81% cannot be audited from public data.** 42 of the 108 picks
  are missing, and they skew toward 2022–23 and toward picks that left the portfolio without a
  public record. Half of the usable sample is a survivor list. After October 2024 the rebuild
  moves with SA but sits −3 to +8 pp from it depending on the snapshot. The 2026-10-30
  near-match is not a reconciliation.
- **The record rests on a few names.** Five picks earn 46% of the net dollar gain. The
  typical pick beats SPY bought on the same day by a few points, and a +100% cap brings the
  whole book close to the same-date SPY's level.
- **Is it "just momentum"?** Mostly beta, size and momentum. Factor-adjusted alpha after
  2023 is not distinguishable from zero under any holdings cutoff or bounding variant.
- **For this screener:** nothing here argues for ingesting Alpha Picks. The
  rating-approximation route in `seeking-alpha-quant.md` §7 remains the only compliant
  option.

## Biases and limits

- **Survivor-list selection.** This is the largest structural bias. 32 of the 66 usable picks
  are in the sample only because they were still held around 2025-10-15 (CSV column
  `survivor_table_only`). For returns before then the bias is upward. The rest of the sample is
  selected even harder on outcome (SA's top-13 by return, reviewers' named winners), so
  dropping the survivor list raises the results rather than lowering them. Neither half is a
  random draw. The three picks known to have left the list between July and October 2025
  lower the results when added (§3).
- **Coverage.** 66 of 108 picks are usable, and only 3 of the 16 from 2022. Six dated picks
  are excluded because they closed on unknown dates: TA (acquired by BP, delisted), META, PEP,
  GM, ZETA and ITRN. Three of them, PEP, GM and ITRN, have a known three-month exit window and
  are used in variants. ATGE, LC and COMM were not delisted but renamed, and are included.
- **Unknown status.** 30 of the 66 picks have no documented status after about 2025-10-15
  and are modelled as held to 2026-10-30. TraderHQ's open count shows at least 3 of them, and
  probably more, had closed by 2026-09-01. The two bounding variants close all 30 at 2025-10-15
  or at 2026-04-13. The unknown-status picks average +51.1% against +141.8% for documented
  ones, so keeping only documented-status picks raises the result (+141.8%).
- **Dates.** Pick dates come from SA screenshots, TraderHQ, and the Perpetual Alpha blog's
  copies of SA notes. 32 usable picks have no published price or return to test their date
  against. For TEX, EZPW (2025-04-03) and MFC (2025-05-02) the blog date is not on SA's
  1st/15th schedule. Moving EZPW and MFC to 2025-04-01 and 2025-05-01 changes
  value÷contributions by 0.1 pp. For AMPH, ANF, MHO and TEX, the exit date is the date of the
  removal note. MHO's published purchase price is the close of the session before its stated
  pick date.
- **Partial sales.** These are documented for SMCI, APP, CLS and POWL, but the quantities
  are not. Each is modelled as selling the initial $1, SA's stated winner rule; SMCI's March
  2024 sale may instead have been the 15%→10% trim. SFM's and AGX's closed rows both carry a
  "Winner" tag, so an earlier sale of the initial amount is possible for both. The
  winner-sale variant costs 1.3 pp of value÷contributions. POWL's remainder is uncertain
  (§2). Proceeds earn 0%, whereas SA says trim proceeds are spread across the other holdings.
- **Prices.** yfinance adjusted series are restated after the fact. (H+L+C)/3 is a proxy for
  VWAP, not the real thing. Costs, taxes and slippage are ignored. The daily Modified-Dietz
  TWR assumes buys at the open and sales at the close. The renamed tickers' history comes from
  the successor symbol, and VISN's spin-off-era special dividends are handled only by Yahoo's
  adjustment factor.
- **Regressions.** The samples are short: 22–48 months, or 795–1,002 days. The early months
  hold 1–9 stocks. October 2026, a −12.7% month, is not covered by the factor files. The
  series is built from the biased subset. Every variant that was run is reported, and no
  parameter was tuned. The holdings cutoff (10) and the bounding dates were set before the
  results were seen. The other cutoffs were added on review and are all shown.
- **Snapshot dates.** SA shows the previous close, and third-party pages rarely say which close
  a figure reflects. Both D and D−1 are shown. SA's benchmark differs from buy-and-hold
  price-only SPY by up to about 1.6 pp even on a date the per-pick figures pin down (RBD,
  2026-10-27), so the SPY check cannot settle a one-day ambiguity.
- **Sources are secondary, and the record is notional.** Most review sites earn affiliate
  commissions. SA says AP is not run with real money and is not an audited GIPS product.

## Review notes

Defects raised on review, and what was done about each:
- **Snapshot gaps.** The review's rebuilt-minus-SA gaps for EarnForex, WallStreetZen,
  MatchMyBroker and Kai (+7.0, +6.5, +2.9 and +1.7 pp) do not reproduce exactly. They used the
  previous session's close and the 63-pick sample. This run, with 66 picks, gives +5.6, +3.1,
  +0.6 and −1.3 pp at D−1, and +8.2, −1.6, −0.9 and +1.7 pp at D. The point stands: the
  2026-10-30 match is an endpoint coincidence.
- **The SPY check.** The review used it to rank snapshot dates. RBD's case shows it cannot do
  that at the 1–2 pp level, so no snapshot is chosen or dropped on a gap under 2 pp.
- **Direction of the survivor bias.** The review called it upward. It is upward relative to the
  population, but the remaining sample is more selected still, so removing the survivor list
  raises the results (§3 item 3).
- **The `.gitignore` exception.** Not added. That file is outside this task's write scope
  (see Reproduce).
