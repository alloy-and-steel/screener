# Alpha Picks rules on a momentum-only rating: a 2015–2026 backtest

Question (2026-11-08): if Seeking Alpha's Quant Rating is cut down to the one part that can
be rebuilt from prices alone, its momentum factor, and Alpha Picks' published rules run on
top of it, what does the result look like over 2015–2026? And how does it compare with the
real Alpha Picks record from 2022-07-01?

Sources: `docs/research/seeking-alpha-quant.md` (the rules, the rating's bucket shares, the
Guo-Jame-Markov results, and the real Alpha Picks figures); the screener's dataset on the
`data` branch (`generated_at` 2026-11-06T19:17:39Z, 1,994 rows); yfinance 1.8.0 daily
prices, 2013-01-02..2026-11-06; and the Ken French data library's monthly
`F-F_Research_Data_5_Factors_2x3`, `F-F_Momentum_Factor` and `F-F_ST_Reversal_Factor`
files, 1963-07..2026-09
(<https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html>). Every number
below was printed by one run of `backtests/sa_momentum_backtest.py` (command at the end).
The exceptions are the real Alpha Picks figures and the paper's figures, which are quoted
from the research doc, and the two splice dates, which come from SEC filings (cited in
the Prices section).

## Answer in brief

- **Against SPY the emulator wins on time-weighted return (TWR). Against the universe it
  picks from, the result is mixed.** From 2015-01-02 to 2026-10-30 the three main variants
  returned +401.6% to +606.4% of TWR. SPY returned +344.4% and the equal-weight (EW)
  universe +415.0%. That puts the emulator +12.9% to +58.9% ahead of SPY and −2.6% to
  +37.2% against the EW universe. Across all 15 rule and selector variants the range was
  +0.1% to +58.9% against SPY and −13.7% to +37.2% against the EW universe.
- **The EW universe's own lead over SPY accounts for between a third and all of the
  emulator's lead, depending on the variant.** The universe is today's survivors, and the EW universe of those names beat SPY
  on its own. Its lead accounts for this share of each variant's log excess return over SPY:
  - 2015–2026: 122% for the score selector (it trailed the EW universe), 36% for the
    streak selector, 32% for the calendar-day score variant, and 44% and 53% for the random
    medians.
  - 2022–2026: 39% to 54% for the main variants (35% to 77% across all variants), and 61%
    and 82% for the random medians.

  The EW universe understates survivorship for this book. It measures the bias for the
  average name, while a high-beta momentum book loses the most from the missing delisted
  crash-outs. So the unexplained remainder is not evidence that the rating works.
- **It does not reproduce the real Alpha Picks.** From 2022-07-01 to 2026-10-30, the real
  portfolio returned +294.81% against +100.19% for its SPY benchmark, a margin of +97.2%.
  The emulator's TWR margin over SPY was +26.9% to +39.9% in the main variants, and +18.2%
  to +44.4% across all variants. The 95th percentile of 500 random selections reached
  +62.9% (trading-day streak) and +69.4% (calendar).
- **The paper's result does not reappear here.** The comparable figure is the six-factor
  alpha of Strong Buy minus Strong Sell. The paper found +1.52%/month (t 3.50). Here it is:
  - −0.77% (t −1.44) on the splice-masked data;
  - −0.03% (t −0.11) with each month winsorized at 1%/99%;
  - +0.04% (t 0.12) on the paper's own window, formation months Dec 2015 to Nov 2022.

  The raw mean spread is null under every treatment. It is +0.00% (t 0.01) winsorized and
  −0.10% (t −0.25) between the bucket medians. Universe-wide alpha is consistent with
  survivorship: +0.24%/month (t 3.31) for Hold, +0.45% (t 6.52) for the whole rated
  universe, and +0.19% (t 2.30) for the EW benchmark. Strong Sell's alpha stays at +1.63%
  (t 3.44) after a short-term-reversal control.
- **There is no significant factor alpha over 2015–2026.** The emulator's FF5 + momentum
  alpha was +0.17%/month (t 0.46) with the score selector and +0.27% (t 0.86) with the
  streak selector. It is a high-beta momentum book: market beta 1.29–1.48, SMB 0.68–0.77,
  momentum 0.44–0.48. Its worst drawdown, −51.7% to −54.2% across the main variants, ran
  from Nov 2021 to Jun–Jul 2022. SPY's was −33.7%.
- **The proxy is less sticky than SA's rating.** All 7 of the real exact-dated picks that
  are in this universe were proxy Strong Buys on their pick day. Only 2 of them (SMCI,
  LRN) had a 75-trading-day streak. APP also qualified under the calendar-day rule.

## Method

### Universe

The universe is the 1,994 rows of today's dataset. 3 rows with an `Error` are dropped, and
so are 6 with no sector (ASPSW, ASPSZ, FISV, LION, NIQ, SQFTW). That leaves 1,985 names,
and all of them returned prices. Rows are sorted by ticker. The dataset's own row order is
today's OverallScore (the review measured a rank correlation of 1.0), so a tie-break on row position would leak 2026 fundamentals into past
picks. Sectors are the dataset's Yahoo sectors as of today. Peer-set sizes run from 61
(Utilities) to 327 (Financial Services). 23 rows have no `MarketCap_B` or `Price`. They
are rated but can never pass the cap filter: a missing value stays missing and is not
treated as 0.

### Prices

yfinance is called with `auto_adjust=False, actions=True` from 2013-01-01, 200 tickers per
batch, and the results are cached as parquet. Starting in 2013 means the 252-day rating
warm-up and a 75-day streak are both complete before the first 2015 pick day. In this run
every one of the 284 pick days in the 2015 window had a pick, the first on 2015-01-02.
Three price series are built from the download:
- **Total-return prices** are `Adj Close` and `Open × Adj Close / Close`. The run checked
  these against `auto_adjust=True` for SPY, AAPL and NVDA over 2015–2026. The largest
  relative difference was 2.2e-16.
- **Nominal price**, for the > $10 filter, is Yahoo's `Close` with splits undone. Yahoo's
  `auto_adjust=False` close is already split-adjusted. For NVDA on 2024-06-07 it reads
  120.89, while the traded price was 1,208.88. Using Yahoo's close as-is would change 117 of
  the 4,814 pick-day flags that are eligible under either basis. 103 would be eligible only
  under the nominal price, and 14 only under Yahoo's close.
- **Approximate cap** is current shares (`MarketCap_B / Price`) × Yahoo's split-adjusted
  close. This departs from the brief, which said "× nominal price". Current shares are
  post-split, so multiplying them by an unsplit price would overstate a split name's past
  cap by the split ratio.

**Verified splices are masked.** For two names the series before a date belongs to a
different security, so those days are set to missing. They are not repaired.
- **CHRD.** Oasis Petroleum's old equity was cancelled before the open on 2020-11-20, when
  the new shares began trading
  ([8-K](https://www.sec.gov/Archives/edgar/data/1486159/000148615920000115/oasemergencereleasefil.htm)).
  Yahoo joins the two series, which reads as a +30,991% month (adjusted close 0.0669 →
  20.7893) with a +25,733% day on 2020-11-20.
- **IVT.** InvenTrust was a non-traded REIT until its NYSE listing on 2021-10-12. Yahoo's
  pre-listing series ignores the 2021-08-05 1-for-10 reverse split
  ([10-K FY2021](https://www.sec.gov/Archives/edgar/data/1307748/000130774822000021/ivtp-20211231.htm)).

The raw, unmasked series is kept for the "splices in" comparison rows. Other extreme
months were checked and left in (see the paper-style check).

The trading calendar is SPY's.

### Rating proxy

Each day the proxy is built in five steps:
1. Total-return momentum over 63, 126, 189 and 252 trading days, with no skip month.
2. A percentile rank of each window within the name's sector.
3. The average of the four ranks.
4. A re-rank of that average within the sector.
5. A cut into buckets by SA's observed shares: top 9.5% Strong Buy, next 10.4% Buy, bottom
   8% Strong Sell, next 8% Sell, and the rest Hold.

A name is unrated until it has 252 trading days of history. SA updates "before the market
opens", so on day t the backtest acts on the rating computed from closes through t−1.

### Alpha Picks rules

| Rule | Implementation |
|---|---|
| Pick days | First trading day of each month, and the 15th or the next trading day |
| Strong Buy streak | ≥ 75 consecutive trading days rated Strong Buy (main run). Variant: ≥ 75 calendar days elapsed since the streak began |
| Price | nominal close of t−1 > $10 |
| Size | 63-trading-day mean of the approximate cap, through t−1, > $500M |
| Cooldown | not picked in the prior 365 calendar days. A name still held can be picked again after that, which adds to the position |
| No REITs | Sector ≠ Real Estate |
| No ADRs | The ADR proxy used by `alphapicks.py`: the dataset's `DCF_Currency_Mismatch` is true. Only 4 names are flagged: ASML, CCEP, FER and PDD. A foreign issuer that reports in USD is not caught. Variant: ADRs allowed |
| Selector | `score`: highest re-ranked composite, then the average percentile, then ticker. `streak`: longest trading-day streak, then the re-ranked score, then the average percentile, then ticker. `random`: uniform over the eligible names, 500 seeds (20261108 + k) |
| Entry | $1 at the pick day's adjusted open |
| Exit | rating Sell or Strong Sell: sell everything at that day's close. Hold for more than 180 calendar days in a row: sell at that day's close, unless the position is a winner |
| Winner | close ≥ 2× the first entry price of the current position. Main run: a winner is never sold at Hold. Variant: the documented partial sale, described below the table |
| Trim | at each close, a position above 15% of the book is cut to 10%, and the proceeds are split equally across the other holdings. **[ASSUMED]** only with ≥ 10 holdings, described below the table. Variants: from 7 holdings, and no trim |
| Exit cash | withdrawn and held at 0%. It is never reinvested |

**The documented winner rule.** The research doc (§2, retirebeforedad, secondary) says a
winner held at Hold for more than 180 days sells only its original purchase amount, and
that this repeats every further 180 days. The variant sells $1 per pick into the current
position, and the clock restarts at each sale. If the position is worth no more than that,
it is sold out. `alphapicks.py` implements the same rule.

**Why the trim waits for 10 holdings.** With fewer than 7 names an equal-weight book
already has every position above 15%, so 7 is the mechanical minimum. Below 10 names an
equal weight sits above the 10% target, so the trim would cut a winner below an average
position. The trim was inactive for the first 102 trading days of the 2015 window (score
selector; 92 for streak) and the first 95 of the 2022 window, until 2022-11-15. From 7
holdings those counts fall to 69, 61 and 64.

**The score selector is mostly a sector-leader selector.** The re-ranked score is 1.0 for
the top name of each sector. 184 of the 284 trading-rule picks (248 under the calendar
rule) were sector leaders, and the top score was tied on 78 pick days (179 calendar). Those
ties go to the average percentile. After that a tie fell to the ticker on 3 pick days, all
of them in the calendar score run. The streak selector's top key was tied on 18 days, and
no tie reached the ticker. Dropping the average-percentile step moved the streak run's TWR
from +567.6% to +564.6%.

### Metrics

- **Value/contrib** = (holdings + exit cash) ÷ dollars contributed, minus 1. Exit cash
  earns nothing and the benchmarks never sell, so this measure penalizes the emulator.
- **TWR** is the chain-linked time-weighted return, with each day split at the open (where
  new money comes in) and at the close (where exits leave). This is the closest analogue to
  SA's S&P-computed time-weighted figure. The TWR CAGR clock starts at the first pick.
- **vs SPY / vs EW** = (1 + TWR) ÷ (1 + benchmark TWR) − 1. The benchmark is bought on the
  same pick days the run actually picked on.
- **EW share** = ln(EW ÷ SPY) ÷ ln(run ÷ SPY), on TWR. It is the part of the run's log
  excess over SPY that the EW universe's own lead over SPY accounts for, and it is left
  undefined when the run beat SPY by less than 1%. For the random runs it is the median EW
  gap divided by the median log excess.
- **IRR** is money-weighted. Contributions count as outflows; exits and terminal holdings
  count as inflows.
- **Max DD** is measured on the TWR index.
- **Win rate** is the share of picks whose price return from entry to exit (or to the
  2026-10-30 close) is above 0.
- **Top-5 share** is the five tickers' share of total dollar P&L, with trims, winner sales
  and redistributions counted per ticker.

Benchmarks put the same $1 into SPY, or into the equal-weight universe, at the open of each
pick date. The equal-weight universe is $1 spread over every name with an open that day,
then held without rebalancing.

## Does the proxy behave like SA's rating?

| Check | Proxy | SA / paper |
|---|---|---|
| Bucket shares (SB / B / H / S / SS) | 9.86% / 10.38% / 64.11% / 7.98% / 7.67% | 9.49 / 10.44 / 64 / 8 / 8 |
| Strong Buy names per day | 155 of 1,573 rated | about 380–400 of about 5,600 (UNVERIFIED Cress quote) |
| Strong Buy still Strong Buy after 1 / 21 / 252 trading days | 91.3% / 63.4% / 13.0% | 95% / 64% / 18% (day, month, year) |
| Strong Buy after a year: Hold / Sell / Strong Sell | 57.2% / 8.7% / 10.3% | 57.61% / 8.02% / 4.41% |

The month-scale churn matches. Over one day and one year the proxy is less sticky, and it
sends more Strong Buys all the way to Strong Sell. SA's fundamental factors presumably
dampen that.

The real picks with exact dates, rated by the proxy on their pick day. Price and cap are as
of the previous close.

| Ticker | Pick date | Proxy rating | Streak (trading / calendar days) | Nominal close | 63-day approx cap | Eligible (75 trading / 75 calendar) |
|---|---|---|---|---|---|---|
| SMCI | 2022-11-15 | Strong Buy | 146 / 209 | $81.93 | $4,105.7M | yes / yes |
| POWL | 2023-05-15 | Strong Buy | 109 / 159 | $53.85 | $499.1M | no / no (cap, $0.9M under the line) |
| AMPH | 2023-07-03 | Strong Buy | 14 / 20 | $57.47 | $1,835.5M | no / no |
| CLS | 2023-10-16 | not in universe | – | – | – | – |
| APP | 2023-11-15 | Strong Buy | 68 / 96 | $42.80 | $12,172.3M | no / yes |
| LRN | 2025-06-02 | Strong Buy | 140 / 207 | $151.39 | $5,726.7M | yes / yes |
| MU | 2025-10-15 | Strong Buy | 10 / 13 | $187.06 | $156,207.7M | no / no |
| ICHR | 2026-07-01 | Strong Buy | 25 / 35 | $112.28 | $2,493.9M | no / no |

None of them is in Real Estate or flagged as an ADR. On those dates the trading-rule pool
held 8–27 names. The median pool across all pick days was 11–15 names under the trading-day
rule and 22–28 under the calendar rule.

## Results, 2015-01-02..2026-10-30

SPY's total return, from the 2015-01-02 open to the 2026-10-30 close, was +344.4% (+266.2%
price only). All 284 pick days had a pick, so every benchmark is bought on all 284 dates.

| Streak | Selector | Variant | Value/contrib | TWR | TWR CAGR | vs SPY | vs EW | EW share | IRR | Max DD | Win rate | Median pick | Top-5 share |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| trading | score | **main** | +39.0% | +401.6% | +14.6% | +12.9% | −2.6% | 122% | +20.1% | −51.8% | 51% | +2.8% | 35% |
| trading | score | trim off | +36.3% | +344.7% | +13.4% | +0.1% | −13.7% | n/a | +19.4% | −52.9% | 51% | +2.8% | 34% |
| trading | score | trim from 7 | +39.1% | +403.3% | +14.6% | +13.3% | −2.3% | 119% | +20.3% | −51.8% | 51% | +2.8% | 35% |
| trading | score | winner partial sale | +39.8% | +413.2% | +14.8% | +15.5% | −0.4% | 102% | +20.5% | −52.5% | 51% | +2.8% | 34% |
| trading | score | ADRs allowed | +39.2% | +407.1% | +14.7% | +14.1% | −1.5% | 112% | +20.2% | −52.6% | 52% | +2.9% | 35% |
| trading | streak | **main** | +32.7% | +567.6% | +17.4% | +50.2% | +29.6% | 36% | +19.4% | −51.7% | 49% | −0.9% | 43% |
| trading | streak | trim off | +30.3% | +474.7% | +15.9% | +29.3% | +11.6% | 57% | +18.9% | −52.3% | 49% | −0.9% | 46% |
| trading | streak | trim from 7 | +32.8% | +567.3% | +17.4% | +50.2% | +29.6% | 36% | +19.5% | −51.7% | 49% | −0.9% | 42% |
| trading | streak | winner partial sale | +33.2% | +588.3% | +17.7% | +54.9% | +33.6% | 34% | +19.9% | −50.2% | 49% | −0.9% | 42% |
| trading | streak | ADRs allowed | +32.3% | +546.6% | +17.1% | +45.5% | +25.6% | 39% | +19.2% | −52.6% | 49% | −0.9% | 43% |
| trading | streak, no avg-percentile tie-break | – | +32.7% | +564.6% | +17.4% | +49.5% | +29.0% | 37% | +19.4% | −51.7% | 49% | −0.9% | 43% |
| trading | random, median (p5 / p95) | main | +33.4% (+24.5 / +41.7) | +522.2% (+324.0 / +782.0) | | +40.0% (−4.6 / +98.5) | +20.8% (−17.7 / +71.3) | 44% | +19.4% (+15.7 / +23.0) | −48.4% (−53.5 / −42.1) | 50.0% | −0.0% | 39.0% |
| calendar | score | **main** | +45.7% | +606.4% | +18.0% | +58.9% | +37.2% | 32% | +23.0% | −54.2% | 50% | −0.9% | 35% |
| calendar | score | winner partial sale | +45.3% | +592.2% | +17.8% | +55.7% | +34.4% | 33% | +23.0% | −54.1% | 50% | −0.9% | 36% |
| calendar | streak | main | +32.7% | +567.6% | +17.4% | +50.2% | +29.6% | 36% | +19.4% | −51.7% | 49% | −0.9% | 43% |
| calendar | streak | winner partial sale | +33.2% | +588.3% | +17.7% | +54.9% | +33.6% | 34% | +19.9% | −50.2% | 49% | −0.9% | 42% |
| calendar | random, median (p5 / p95) | main | +31.6% (+23.2 / +43.4) | +486.6% (+302.5 / +755.0) | | +32.0% (−9.4 / +92.4) | +13.9% (−21.9 / +66.0) | 53% | +18.7% (+14.9 / +22.9) | −46.2% (−51.7 / −40.8) | 51.1% | +0.8% | 40.0% |

The calendar-rule streak runs match the trading-rule streak runs exactly. The longest
trading-day streak was the longest calendar streak on every pick day.

| Benchmark, $1 on each of the 284 pick dates | Value/contrib | TWR | TWR CAGR | IRR | Max DD |
|---|---|---|---|---|---|
| SPY | +155.8% | +344.4% | +13.4% | +15.0% | −33.7% (2020-02-19 → 2020-03-23) |
| EW universe, splices masked | +166.2% | +415.0% | +14.9% | +15.6% | −39.8% (2020-02-20 → 2020-03-23) |
| EW universe, raw (splices in) | +170.2% | +425.4% | +15.1% | +15.8% | −39.8% |

What the tables show:
- **Random selection beat SPY on TWR in 93% of runs** under the trading-day rule (86%
  under the calendar rule). It beat the EW universe in 80% (68%). On value/contrib it
  beat SPY in 0% of runs, because exit cash sits idle.
- **The selector matters as much as the rules.** The three main variants span +401.6% to
  +606.4%, and the random p5–p95 band spans +302.5% to +782.0%. Random's median TWR
  (+522.2%) beat the score selector (+401.6%) but not the streak selector (+567.6%).
- **The trim helped in all four comparisons**, counting the 2022 window: here +12.9%
  against +0.1% relative to SPY for score, and +50.2% against +29.3% for streak. Starting
  it at 7 holdings instead of 10 changed little in this window (+13.3%, +50.2%).
- **The documented winner partial sale cut both ways.** It made 8 to 11 sales per run. It
  raised TWR for the two trading-rule runs (+413.2% against +401.6%, +588.3% against
  +567.6%) and lowered it for the calendar score run (+592.2% against +606.4%).
- **The ADR filter also cut both ways.** Allowing the 4 proxy ADRs raised the score run
  (+407.1% against +401.6%) and lowered the streak run (+546.6% against +567.6%). The
  review of the first version found PDD among the picks when ADRs were allowed. This run
  printed the picked ADR names only for the main variants, where there are none.
- **The worst drawdown was the 2021–22 momentum unwind.** It began on 2021-11-02 to
  2021-11-08 and bottomed on 2022-06-17 or 2022-07-06, depending on the variant.
- **The five largest dollar P&Ls:** for score, ENPH, FIVN, DAVE, STRL and BLDR; for
  streak, FIVN, SHOP, STRL, NVDA and SMCI; for calendar score, FIVN, ENPH, FRPT, DAVE and
  TSLA. None of them is a masked splice.
- **The book held 25.9–28.4 names on average**, and 27–30 picks were still open at the
  end.

## Results, 2022-07-01..2026-10-30, against the real Alpha Picks

This is a fresh run with no cooldown history. Ratings and streaks from before 2022-07-01
still count, since SA's ratings existed then. All 104 pick days had a pick.

SPY's total return from the 2022-07-01 open to the 2026-10-30 close was +112.2%, and +100.7%
on price alone. SA published +100.19% for its benchmark. SA's figures are "as of the
previous close", and it is not known which close the 2026-10-30 snapshot used. To the
2026-10-29 close, SPY's total return was +116.1% and its price return +104.3%. One day
moves SPY by 3.6 points, seven times the gap between SA's figure and SPY's price return.
So the closeness of the price return to SA's figure says nothing about whether SA's
benchmark includes dividends (UNVERIFIED either way).

| Streak | Selector | Variant | Value/contrib | TWR | vs SPY | vs EW | EW share | IRR | Max DD | Win rate | Top-5 share |
|---|---|---|---|---|---|---|---|---|---|---|---|
| trading | score | **main** | +40.9% | +169.4% | +26.9% | +11.5% | 54% | +29.7% | −37.2% (2026-05-28 → 2026-10-23) | 56% | 59% |
| trading | score | trim off | +36.5% | +151.0% | +18.2% | +3.9% | 77% | +26.8% | −38.2% | 56% | 51% |
| trading | score | trim from 7 | +41.0% | +170.0% | +27.2% | +11.8% | 54% | +29.7% | −37.2% | 56% | 59% |
| trading | score | winner partial sale | +41.6% | +173.3% | +28.8% | +13.1% | 51% | +30.3% | −37.0% | 56% | 60% |
| trading | score | ADRs allowed | +40.9% | +169.4% | +26.9% | +11.5% | 54% | +29.7% | −37.2% | 56% | 59% |
| trading | streak | **main** | +37.8% | +197.0% | +39.9% | +22.9% | 39% | +29.7% | −37.9% (2024-12-04 → 2025-04-04) | 59% | 51% |
| trading | streak | trim off | +33.2% | +174.9% | +29.5% | +13.8% | 50% | +26.6% | −37.7% | 59% | 44% |
| trading | streak | trim from 7 | +39.5% | +206.5% | +44.4% | +26.9% | 35% | +31.1% | −38.0% | 59% | 54% |
| trading | streak | winner partial sale | +37.7% | +194.7% | +38.9% | +22.0% | 39% | +29.7% | −37.9% | 59% | 51% |
| trading | streak | ADRs allowed | +37.8% | +197.0% | +39.9% | +22.9% | 39% | +29.7% | −37.9% | 59% | 51% |
| trading | streak, no avg-percentile tie-break | – | +37.8% | +197.0% | +39.9% | +22.9% | 39% | +29.7% | −37.9% | 59% | 51% |
| trading | random, median (p5 / p95) | main | +33.5% (+22.8 / +47.7) | +162.8% (+105.7 / +245.7) | +23.8% (−3.1 / +62.9) | +8.8% (−14.8 / +43.1) | 61% | +25.7% (+18.8 / +33.0) | −34.9% (−38.5 / −31.2) | 51.9% | 58.0% |
| calendar | score | **main** | +45.7% | +196.5% | +39.7% | +22.7% | 39% | +31.5% | −34.8% (2026-05-28 → 2026-10-30) | 49% | 56% |
| calendar | score | winner partial sale | +45.6% | +195.0% | +39.0% | +22.1% | 39% | +31.4% | −35.1% | 49% | 56% |
| calendar | streak | main | +37.8% | +197.0% | +39.9% | +22.9% | 39% | +29.7% | −37.9% | 59% | 51% |
| calendar | random, median (p5 / p95) | main | +32.0% (+19.0 / +49.5) | +148.5% (+82.2 / +259.6) | +17.1% (−14.2 / +69.4) | +2.9% (−24.6 / +48.9) | 82% | +24.6% (+16.0 / +34.8) | −33.6% (−37.5 / −29.8) | 51.9% | 61.4% |
| SPY | – | – | +48.7% | +112.2% | – | – | – | +18.7% | −18.8% (2025-02-19 → 2025-04-08) | – | – |
| EW universe | – | – | +60.3% | +141.6% | – | – | – | +22.3% | −23.8% (2024-11-29 → 2025-04-08) | – | – |
| **Real Alpha Picks** (secondary snapshot) | – | – | – | **+294.81%** | **+97.2%** vs its own +100.19% | – | – | – | – | 66% (TraderHQ, 2026-09-01) | – |

The masked splices predate this window, so the raw and masked EW universes agree here
(+141.6%).

What the table shows:
- **Random selection beat SPY on TWR in 92% of runs** under the trading-day rule (79%
  under the calendar rule). It beat the EW universe in 71% (56%).
- **The emulator fell well short of Alpha Picks' margin over SPY.** Its best variant
  reached +44.4%, against the real portfolio's +97.2%. No random run up to the 95th
  percentile came near either. The missing piece is the four fundamental factors, the real
  selector, or both. This test cannot say which.
- **The score selector's worst drawdown has the same timing as the real portfolio's
  slide.** It ran from 2026-05-28 to late October. The research doc puts Alpha Picks' fall
  at about 24% from Jun 9 to Oct 30.
- **Three of the top five were real picks.** For score the top five by dollar P&L were
  DAVE, STRL, VST, SMCI and MOD. For streak they were STRL, NVDA, SMCI, VST and MOD. STRL,
  SMCI and MOD were also real Alpha Picks, but only SMCI is in the real top five (APP, CLS,
  SMCI, POWL, MU; research doc §6). The overlap is drawn from a universe of today's
  survivors, so hindsight inflates it.

## Paper-style check: monthly bucket sort

Names are sorted by the proxy at each month-end close and equal-weighted within each
bucket, then held one month. The sample runs from Jan 2015 to Oct 2026, 142 months. Four
data treatments are reported side by side:
- **Masked:** the main data, with the two verified splices masked.
- **Raw:** splices left in, with ratings recomputed on the raw data.
- **Upside trim:** each name-month above +300% dropped. This is a one-sided trim, not a
  splice filter.
- **Winsorized:** each month's rated cross-section clipped at its 1st and 99th
  percentiles.

| Bucket, mean monthly (t) | Masked | Raw (splices in) | Upside trim > +300% | Winsorized 1/99 | Median of monthly medians (masked) | Avg names |
|---|---|---|---|---|---|---|
| Strong Buy | +2.01% (3.96) | +2.02% (3.97) | +1.87% (3.80) | +1.65% (3.39) | +1.41% | 158 |
| Buy | +1.57% (3.55) | +1.57% (3.55) | +1.57% (3.55) | +1.45% (3.33) | +1.21% | 166 |
| Hold | +1.29% (2.92) | +1.29% (2.91) | +1.28% (2.89) | +1.21% (2.74) | +1.04% | 1,024 |
| Sell | +1.60% (2.82) | +1.60% (2.79) | +1.56% (2.78) | +1.37% (2.48) | +1.10% | 127 |
| Strong Sell | +2.72% (3.33) | +4.61% (2.14) | +2.02% (2.82) | +1.65% (2.41) | +1.08% | 123 |
| Rated universe | +1.53% (3.28) | +1.67% (3.21) | +1.45% (3.12) | +1.32% (2.87) | | |
| **SB − SS** | **−0.71% (−1.14)** | **−2.60% (−1.31)** | **−0.15% (−0.30)** | **+0.00% (0.01)** | | |
| SB median − SS median | −0.10% (−0.25) | −0.10% (−0.24) | | | | |

By sub-period, SB − SS:

| Return months | Masked | Raw | Upside trim | Winsorized | SB minus rated universe (masked) |
|---|---|---|---|---|---|
| 2015-01..2018-12 | −0.93% (t −0.73) | −0.94% (−0.74) | +0.23% (0.39) | +0.31% (0.58) | +0.29% (1.01) |
| 2019-01..2022-12 | −0.24% (−0.27) | −5.81% (−1.02) | +0.00% (0.00) | +0.09% (0.11) | +0.63% (1.38) |
| 2023-01..2026-10 | −0.97% (−0.92) | −0.97% (−0.92) | −0.69% (−0.69) | −0.40% (−0.44) | +0.54% (1.03) |
| **Paper's window**, 2016-01..2022-12 (formation Dec 2015 to Nov 2022) | −0.12% (−0.20) | −3.30% (−1.01) | +0.01% (0.02) | +0.07% (0.13) | +0.52% (1.77) |

The upside trim dropped 24 name-months: 4 from Strong Buy, 6 from Hold, 2 from Sell and 12
from Strong Sell. The run printed all 28 raw name-months above +300%, with the largest
one-day move in each. Only the two masked names are verified splices: CHRD (+25,733% on
2020-11-20) and IVT (+908% on 2021-09-24).

The other 26 were not verified either way. Several are well-known real moves, such as
GME (+1,625%, rated Strong Buy) and AMC (Strong Sell) in Jan 2021, and RGTI (Strong Buy) in
the Dec 2024 quantum rally. In all, 4 of the 26 were Strong Buys, so the upside trim
removes real Strong Buy winners along with any bad data.

One name is suspect but unverified, so it was left in: ADTI, at +5,700% in Jun 2015 and
+322% to +342% in two later months. Its Yahoo series sits flat for weeks between jumps, and
it has no market cap in today's data, so it can never be picked. It still sits in the
Consumer Defensive peer set, the EW universe and the Strong Sell bucket.

The paper's equal-weight figures for comparison: Strong Buy six-factor alpha +0.90% (t
4.50), Strong Sell −0.62% (t −1.65), long-short +1.52% (t 3.50). The proxy's Strong Buys
beat the rated universe by 0.3–0.6% a month, though never significantly. Its Strong
Sells did not underperform under any treatment.

## Factor regressions (monthly)

Coefficients are shown with OLS t-statistics in brackets. "t HAC" uses Newey-West
standard errors with 3 lags. The dependent variable is the excess return over RF, except
for SB − SS. FF6 means FF5 + Mom. The sort rows use the masked data unless they say
otherwise.

| Series | Factors | Months | Alpha/month | t | t HAC | Mkt-RF | SMB | HML | RMW | CMA | Mom | ST_Rev | R² |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Emulator 2015–26, score | FF6 | 140 | +0.17% | 0.46 | 0.50 | 1.48 (17.2) | 0.68 (4.6) | −0.43 (−3.2) | −0.47 (−3.0) | 0.01 (0.0) | 0.44 (4.5) | | 0.78 |
| Emulator 2015–26, streak | FF6 | 140 | +0.27% | 0.86 | 0.94 | 1.29 (16.9) | 0.77 (5.8) | −0.33 (−2.7) | −0.24 (−1.7) | −0.25 (−1.4) | 0.48 (5.5) | | 0.79 |
| Emulator 2022–26, score | FF6 | 50 | +0.68% | 0.83 | 0.80 | 1.42 (7.4) | 0.67 (1.9) | −0.70 (−1.9) | −0.34 (−1.2) | 0.12 (0.3) | 0.81 (4.0) | | 0.71 |
| Emulator 2022–26, streak | FF6 | 50 | +1.39% | 2.02 | 2.01 | 1.12 (7.0) | 1.06 (3.6) | −0.63 (−2.0) | −0.02 (−0.1) | −0.10 (−0.3) | 0.77 (4.6) | | 0.72 |
| SPY benchmark (sanity) | FF6 | 140 | −0.01% | −0.43 | −0.49 | 0.99 (172.4) | −0.11 (−11.4) | 0.02 (2.4) | 0.05 (4.7) | 0.02 (1.6) | 0.01 (0.8) | | 1.00 |
| EW universe benchmark | FF6 | 140 | +0.19% | 2.30 | 2.50 | 1.06 (52.6) | 0.58 (16.8) | 0.08 (2.5) | −0.03 (−0.9) | −0.08 (−1.7) | 0.13 (5.5) | | 0.97 |
| Sort: Strong Buy | FF6 | 141 | +0.84% | 4.71 | 4.06 | 1.10 (25.8) | 0.87 (11.8) | 0.05 (0.7) | −0.12 (−1.6) | −0.04 (−0.4) | 0.49 (10.1) | | 0.89 |
| Sort: Hold | FF6 | 141 | +0.24% | 3.31 | 4.05 | 0.98 (55.9) | 0.54 (17.9) | 0.19 (6.7) | 0.06 (1.8) | −0.03 (−0.8) | −0.04 (−1.9) | | 0.98 |
| Sort: Strong Sell | FF6 | 141 | +1.61% | 3.40 | 3.06 | 1.26 (11.0) | 1.17 (6.0) | −0.07 (−0.4) | 0.00 (0.0) | −0.11 (−0.4) | −0.43 (−3.3) | | 0.71 |
| Sort: rated universe | FF6 | 141 | +0.45% | 6.52 | 6.99 | 1.02 (61.3) | 0.64 (22.4) | 0.15 (5.5) | 0.02 (0.7) | −0.04 (−0.9) | −0.01 (−0.5) | | 0.98 |
| Sort: SB − SS | FF6 | 141 | −0.77% | −1.44 | −1.29 | −0.16 (−1.2) | −0.30 (−1.3) | 0.12 (0.6) | −0.13 (−0.5) | 0.07 (0.2) | 0.93 (6.3) | | 0.36 |
| Sort: Strong Buy | FF6 + ST_Rev | 141 | +0.82% | 4.73 | 4.05 | 1.12 (26.6) | 0.89 (12.4) | 0.06 (0.9) | −0.09 (−1.2) | −0.09 (−0.9) | 0.45 (9.1) | −0.17 (−3.0) | 0.90 |
| Sort: Hold | FF6 + ST_Rev | 141 | +0.25% | 3.40 | 4.32 | 0.97 (55.3) | 0.53 (17.8) | 0.18 (6.6) | 0.05 (1.5) | −0.02 (−0.4) | −0.03 (−1.4) | 0.04 (1.8) | 0.98 |
| Sort: Strong Sell | FF6 + ST_Rev | 141 | +1.63% | 3.44 | 3.18 | 1.23 (10.7) | 1.15 (5.8) | −0.09 (−0.5) | −0.03 (−0.1) | −0.05 (−0.2) | −0.39 (−2.9) | 0.19 (1.2) | 0.71 |
| Sort: rated universe | FF6 + ST_Rev | 141 | +0.46% | 6.58 | 7.22 | 1.02 (60.3) | 0.64 (22.2) | 0.14 (5.4) | 0.02 (0.5) | −0.03 (−0.7) | −0.00 (−0.1) | 0.03 (1.2) | 0.98 |
| Sort: SB − SS | FF6 + ST_Rev | 141 | −0.81% | −1.53 | −1.39 | −0.11 (−0.9) | −0.26 (−1.2) | 0.16 (0.8) | −0.06 (−0.3) | −0.03 (−0.1) | 0.84 (5.5) | −0.36 (−2.0) | 0.38 |
| Sort, paper window: Strong Buy | FF6 | 84 | +0.82% | 3.74 | 3.50 | 1.09 (21.1) | 0.96 (9.7) | 0.09 (1.2) | −0.02 (−0.2) | −0.05 (−0.4) | 0.56 (8.0) | | 0.91 |
| Sort, paper window: SB − SS | FF6 | 84 | +0.04% | 0.12 | 0.13 | −0.36 (−4.0) | 0.31 (1.8) | 0.20 (1.5) | 0.37 (1.9) | −0.39 (−1.9) | 1.06 (8.7) | | 0.66 |
| Sort, raw: Strong Sell | FF6 | 141 | +3.48% | 1.86 | 2.22 | 1.97 (4.4) | 1.85 (2.4) | −0.93 (−1.3) | −1.00 (−1.2) | 1.64 (1.6) | −1.68 (−3.3) | | 0.34 |
| Sort, raw: SB − SS | FF6 | 141 | −2.64% | −1.42 | −1.70 | −0.87 (−1.9) | −0.98 (−1.3) | 0.98 (1.4) | 0.88 (1.1) | −1.68 (−1.6) | 2.17 (4.2) | | 0.24 |
| Sort, upside trim: Strong Sell | FF6 | 141 | +0.87% | 3.81 | 3.83 | 1.29 (23.5) | 0.84 (8.9) | 0.01 (0.1) | −0.14 (−1.4) | −0.09 (−0.7) | −0.57 (−9.1) | | 0.91 |
| Sort, upside trim: SB − SS | FF6 | 141 | −0.17% | −0.57 | −0.57 | −0.20 (−2.8) | −0.04 (−0.3) | 0.06 (0.5) | 0.05 (0.4) | −0.03 (−0.2) | 1.02 (12.1) | | 0.64 |
| Sort, winsorized: Strong Sell | FF6 | 141 | +0.51% | 2.73 | 2.73 | 1.26 (27.8) | 0.81 (10.4) | 0.03 (0.4) | −0.13 (−1.6) | −0.03 (−0.3) | −0.54 (−10.4) | | 0.93 |
| Sort, winsorized: SB − SS | FF6 | 141 | −0.03% | −0.11 | −0.11 | −0.18 (−2.8) | −0.01 (−0.1) | 0.05 (0.5) | 0.04 (0.3) | −0.07 (−0.5) | 0.97 (13.2) | | 0.68 |

What the regressions show:
- **The factor data parses correctly.** The SPY sanity row gives beta 0.99, R² 1.00 and no
  alpha.
- **The emulator is a high-beta momentum and small-cap tilt.** Its momentum loading is
  significant in every run. Its alpha is significant only in the 50-month streak run (t
  2.02). That is one of four emulator regressions, on a short sample.
- **The proxy does rank on momentum.** The long-short spread loads 0.93–1.06 on Mom in
  the FF6 regressions of the masked, upside-trimmed, winsorized and paper-window sorts.
  Once that loading is accounted for, nothing is left under any data treatment, and nothing
  is left on the paper's window either (+0.04%, t 0.12).
- **The pattern is consistent with survivorship, though it does not prove it.** Every
  long-only series earns positive six-factor alpha: Hold +0.24%/month (t 3.31), the whole
  rated universe +0.45% (t 6.52), and the EW benchmark +0.19% (t 2.30). Strong Sell's alpha
  is the largest. The obvious alternative is one-month reversal, since the proxy has no
  skip month. The ST_Rev control does not support it: Strong Sell's loading is 0.19
  (t 1.2), and its alpha stays at +1.63% (t 3.44). Winsorizing cuts Strong Sell's alpha to
  +0.51% (t 2.73), so a few extreme rebounds carry much of it. A universe of names that
  were still listed in 2026 would produce exactly this pattern.

## Verdict

Run on prices alone, Alpha Picks' mechanical rules produce a concentrated, high-beta
momentum portfolio. It beat SPY on time-weighted return in both windows, but the
comparison is tilted in its favour, because the universe it picks from is today's
survivors. Against the equal-weight universe of those survivors the result ranges from
−13.7% to +37.2% over 12 years, depending on the selector and rule reading. The EW
universe's lead over SPY accounts for between about a third and all of the emulator's
lead over SPY. That EW gap understates survivorship for a momentum book, so the remainder
cannot be credited to the rating. Six-factor alpha is indistinguishable from zero over the
full period, and drawdowns run 1.5–2× SPY's.

The emulator does not reproduce Alpha Picks' 2022–2026 margin over SPY, which was +97.2%.
The emulator's best variant reached +44.4%. The paper's Strong Buy over Strong Sell spread
does not appear on this universe either: not on the full sample, not on the paper's own
window, and not under any of the four data treatments. Two things cannot be separated here:
what the momentum factor adds, and what SA's other four factors and its unpublished
selector add. Nothing here supports adding a momentum-only SA proxy to this screener as a
source of alpha. As a timeliness tilt, it would duplicate what Azqato's growth legs and the
52-week display already show.

## Biases and limits

- **Survivorship.** The universe is today's 1,985 names. For the Total US pool that means
  today's $1B+ names. Delisted, acquired and shrunken names are missing. The measured
  symptoms:
  - the EW universe beat SPY (TWR +415.0% against +344.4%, and +141.6% against +112.2%);
  - every long-only bucket, Hold and Strong Sell included, earned positive six-factor
    alpha;
  - the Strong Sell bucket held most of the extreme rebounds.

  The bias inflates every absolute return here and works against any short-side or spread
  test. The EW-vs-SPY gap is a lower bound on it for a momentum book.
- **Cap approximation.** Past cap is today's share count × the split-adjusted price. That
  misses buybacks and issuance. A name that issued heavily (a SPAC, a dilutive biotech) is
  overstated in the past, and a heavy buyer back is understated. POWL's real 2023 pick
  failed here at the $500M line: its approximate cap was $499.1M. Names with no cap or price
  in today's data (23) are never eligible.
- **Today's sectors.** Each name's current Yahoo sector is applied to all 12 years. Yahoo's
  taxonomy is not GICS. "Real Estate" stands in for "is a REIT". Sector peer sets of
  61–327 names are not SA's sector sets out of about 5,600.
- **The ADR proxy is narrow.** Only 4 names are flagged. A foreign issuer that reports in
  USD passes as a US common stock.
- **No costs.** There are no commissions, spreads, slippage or taxes. Fills are at the
  exact open and close. SA's picks may post mid-session (research doc, UNVERIFIED), so the
  open fill may not have been obtainable.
- **Momentum only.** SA's rating has five factors, a cap rule, a size and risk adjustment,
  and hidden weights. This proxy has one factor with four equally weighted windows, and
  the bucket shares are matched by construction. The paper's 0.50 momentum loading leaves
  most of the rating's variation unexplained.
- **The selector is unknown.** SA does not say how it chooses one name from the eligible
  pool. The three main variants spread full-period TWR from +401.6% to +606.4%, and the
  random runs from +302.5% to +782.0% at p5/p95. The selector moves the result at least as
  much as the choice of streak rule does.
- **Rule readings that are ours.**
  - Trading-day and calendar-day streaks (both run).
  - The Hold clock resets on Buy or Strong Buy.
  - In the main run winners are exempt from the 180-day Hold exit, following the brief. The
    research doc's partial-sale rule is run as a variant. A winner is judged against the
    first entry of the position.
  - The trim applies only with ≥ 10 holdings (7 run as a variant).
  - Exit cash is withdrawn rather than reinvested.
  - A re-pick of a held name adds to the position.
  - One pick per pick day.
- **Benchmark method.** SA's benchmark convention (dividends or not, which close) is
  unknown. SPY's figure moves 3.6 points between the 2026-10-29 and 2026-10-30 closes, so
  SA's +100.19% cannot settle the question. The comparison with the real portfolio's +97.2%
  margin uses SA's own pair of figures, so it does not depend on the answer.
- **Data quality.** Yahoo splices corporate actions. Two verified splices (CHRD, IVT) are
  masked everywhere: ratings, emulator, EW benchmark and bucket sort. ADTI is suspect,
  unverified and left in. Masking moves the full-period EW universe from +425.4% to +415.0%.
  No masked or suspect name is among the emulator's top P&L names. A separate exploration
  (not part of the script) also saw one-day misprints around reverse splits (ASTH 2015,
  QUBT 2018) and flat stale prints (SUPN, Nov 2022). They are left in.
- **One dataset, one day.** The `data` branch is force-pushed daily, and yfinance revises
  history, so a later run will use a different universe and slightly different prices.

## Notes: the review of the first version and what changed

The first version was reviewed on 2026-11-08. Each defect, and how it was handled:

- **Benchmarks on mismatched dates (major): fixed.** The relative columns now use
  benchmarks bought on each run's own pick days, and the TWR CAGR clock starts at the first
  pick. Prices now start in 2013, so the 2015 window has a pick on all 284 pick days from
  2015-01-02. The first version's window effectively began in April or May 2015.
- **"Almost all of the edge is survivorship" overstated (major): fixed.** Each variant now
  reports the EW share of its log excess over SPY. The range is 32% to 122%. The doc also
  states that the EW gap is a lower bound for a momentum book.
- **Tie-break on row order, which carried today's OverallScore (minor): fixed.** The
  universe is sorted by ticker, the order is asserted, and the selectors tie-break on it.
  The streak selector now breaks ties on the average percentile before the ticker. Its
  sensitivity to that step is reported (+567.6% vs +564.6%), and so is the sector-leader
  share of picks.
- **The "+300% = splices" label (minor): fixed.** The variant is renamed an upside outlier
  trim, all 28 name-months are printed, and symmetric winsorization and the median spread
  are added. Only verified splices are masked.
- **CHRD in the EW benchmark (minor): fixed.** CHRD and IVT are masked everywhere. The EW
  universe is reported with and without them.
- **No ADR filter (minor): fixed.** The `alphapicks.py` proxy is in the eligibility mask,
  with an ADRs-allowed variant.
- **Winner exemption vs the documented partial sale (minor): fixed.** The partial sale is
  run as a variant and the research doc's rule is cited.
- **Trim threshold justification (minor): fixed.** One stated reason, a 7-holding variant,
  and the trim-inactive days are reported.
- **Numbers not printed by the script (minor): fixed.** The script now prints the sector
  sizes, the per-filter values for each real pick, every name-month above +300% with its
  prices, and the yfinance version. The splice dates come from the cited SEC filings.
- **No test of the survivorship claim (minor): fixed.** Hold, rated-universe and EW
  regressions are added, and so is the ST_Rev control. The conclusion is now worded as
  "consistent with".
- **SPY end-date fragility (minor): fixed.** Both end dates are reported, and the dividend
  inference is dropped.
- **Top-five overlap overstated (minor): fixed** as suggested.
- **Raw spread compared with the paper's alpha (minor): fixed.** The six-factor SB − SS
  alpha is compared with the paper's, and the paper's window is added.
- **Price-basis count mixed two directions (minor): fixed.** Both directions and the union
  are printed.

No defect was rejected. One reviewer figure differs here for a stated reason: the reviewer
counted top-score ties on 212 of 276 pick days. This doc counts them on 78 of 284, because
it counts ties only within the pool that remains after the cooldown, which is the tie the
selector actually faces.

## Reproduce

From the repo root:

```
uv run --no-project --with yfinance --with pandas --with numpy --with statsmodels \
    --with pyarrow python -I backtests/sa_momentum_backtest.py
```

The script reads `origin/data:web/public/data/results.json` through `git show`. It caches
prices in `/tmp/sa-tests/cache/` and the Ken French zips in `/tmp/sa-tests/ff/`. It prints
every table in this document as markdown, and writes the raw numbers to
`/tmp/sa-tests/out/results.json`. A cold start downloads 10 price batches; in a trial run
with `--mc-runs 2`, downloading and building the context took 141 s. The full run, from
cache, took 1,253 s, most of it the Monte Carlo (4 × 500 runs). Use
`--mc-runs N` to shorten it and `--seed` to change the seeds. This document comes from the
2026-11-08 run on the 2026-11-06 dataset. Its output is saved at
`/tmp/sa-tests/out/run_final.md`.
