# Screens from Nobel laureates and award-winning investors

Question (2026-10-09): which stock-screening rules come from Nobel laureates or other
well-recognised academics and investors, what exactly are they, does the evidence
survive publication, and which could become a screen alongside Azqato / Lynch / Graham /
Wealthmatica with the data the pipeline already fetches?

Method: three research passes — academics, practitioners, and an inventory of
`stock_screener.py`'s inputs. Formulas and thresholds come from the original papers,
shareholder letters, or the investor's own article wherever it could be read.
**UNVERIFIED** marks anything confirmed only through a secondary source (mostly book
passages and paywalled papers). AAII's "guru screens" are AAII's interpretation and are
labelled secondary.

Post-publication decay uses four sources:
- McLean & Pontiff 2016 ([PDF](https://www.gwern.net/doc/economics/2016-mclean.pdf)):
  across 97 predictors, long-short returns fall 26% out of sample and 58% after
  publication.
- Hou, Xue & Zhang, "Replicating Anomalies" ([NBER w23394](https://www.nber.org/papers/w23394)),
  "HXZ" below: NYSE breakpoints, value-weighted, 1967–2014; 65% of 452 anomalies are
  insignificant at |t| < 1.96.
- "CZ calc": means computed from Chen & Zimmermann's open replication data
  ([openassetpricing.com](https://www.openassetpricing.com/), release 2025.10, through
  Dec 2024), in-sample vs calendar years after publication. Monthly long-short %.
- Factor files from [Ken French](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html)
  and AQR ([QMJ](https://www.aqr.com/Insights/Datasets/Quality-Minus-Junk-Factors-Monthly), BAB).
  These are raw returns, not alphas.

## Answer in brief

- **Nobel laureates left almost no per-stock screens.** Markowitz and Sharpe built
  portfolio theory. Shiller's CAPE is a market-level gauge and needs 10 years of earnings
  (we hold 3–4). Merton's model is a default probability, not a return signal. Fama's
  value and profitability factors are the only laureate rules that rank individual stocks,
  and value has been close to zero in large caps since 2005.
- **The rules that are computable here and still worked after publication** are all
  "profitable and cheap" rules: Novy-Marx gross profitability (GP/A), Greenblatt's
  Magic Formula, and O'Shaughnessy's Value Composite. Each one ranks the universe, like
  Azqato, rather than passing or failing a single stock.
- **Recommended fifth screen: a "profitable value" rank**, either Novy-Marx (GP/A rank +
  book-to-market rank) or Greenblatt (ROC rank + EBIT/EV rank). Novy-Marx has the better
  evidence: tested in the largest 500 stocks, and no decay after 2013. Greenblatt is the
  better-known name and costs least to build, because `_compute_ev_ebit` already exists.
  Neither is in the gate today. The Overall score's Value and Quality pillars use
  overlapping inputs, but Overall is informational only.
- **One finding about existing code:** `_compute_piotroski` departs from Piotroski's
  paper in four ways (see [Piotroski](#piotroski-f-score-jar-2000--already-implemented)).

## Summary

| Rule | Who / recognition | Type | Computable now | After publication |
|---|---|---|---|---|
| Value B/M, profitability RMW, investment CMA, size | Fama (Nobel 2013) & French | Ranking | Yes | HML ~0 since 2005; RMW 0.18 (t 0.9) and CMA −0.08 since 2014; size gone |
| CAPE | Shiller (Nobel 2013) | Market-level | No (needs 10y EPS) | n/a |
| Mean-variance, CAPM | Markowitz, Sharpe (Nobel 1990) | Not a stock screen | n/a | n/a |
| Long-term losers | Thaler (Nobel 2017), De Bondt | Ranking | Yes | Negative since 2005 |
| Distance to default | Merton (Nobel 1997) | Absolute probability | Yes | Distress sorts insignificant (HXZ) |
| Gross profitability GP/A | Novy-Marx | Ranking | Yes | **1.02 %/mo, t 2.7, 2014–24** |
| Quality Minus Junk | Asness, Frazzini, Pedersen (AQR) | Ranking | Partly | ~0 raw since 2019 |
| Momentum | Jegadeesh & Titman | Ranking | Yes | 0.13 %/mo since 2005 |
| Accruals | Sloan | Ranking | Partly | 0.10 %/mo (t 1.0) |
| M-score | Beneish | Absolute (−1.78) | Mostly | No post-2013 test found |
| G-score | Mohanram | Score vs industry | Partly | 0.55 (t 2.7) CZ calc; insignificant in HXZ |
| Betting Against Beta | Frazzini & Pedersen | Ranking, levered | Partly | 0.41 (t 1.98) since 2014; leverage-driven |
| F-score | Piotroski | Absolute score | Yes (built) | 0.59 (t 1.2) after 2000 |
| Owner earnings, ROE tests | Buffett (Presidential Medal of Freedom 2011) | Pass/fail | Partly (needs 5–10y) | Alpha explained by BAB + QMJ |
| Magic Formula | Greenblatt | Ranking | **Yes** | Weakened since 2000; still alpha in 1963–2022 |
| Value Composite, Cornerstone | O'Shaughnessy | Ranking / filter + rank | Yes | VC top decile 17.3% vs 11.1% (1963–2012); Cornerstone funds lagged live |
| Price/sales | Ken Fisher | Pass/fail | Yes | Low P/E beat low P/S (1987) |
| Total return ratio | John Neff | Ratio | Yes | Only AAII's live version tested |
| Contrarian low multiple | Dreman | Rank, then pass/fail | Yes | Low-multiple premium widely replicated |
| 15 points / 16 rules | Philip Fisher, Templeton | Qualitative | Proxies only | n/a |
| — | Munger, Pabrai | No published screen | n/a | n/a |

## Nobel laureates

### Fama (Nobel 2013) & French: value, size, profitability, investment

Definitions are from French's data library
([variables](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/variable_definitions.html),
[size × B/M](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/six_portfolios.html),
[size × OP](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/six_portfolios_me_op.html)):

- **Book equity (BE)** = stockholders' equity + deferred taxes and investment tax credit
  − preferred stock. **B/M** = BE for the fiscal year ending in t−1 ÷ market equity in
  December of t−1.
- **Operating profitability (OP)** = (revenue − COGS − interest − SG&A) ÷ BE.
- **Investment (Inv)** = growth in total assets from t−2 to t−1.
- **Sort:** each June, split by NYSE median size, then by NYSE 30th/70th percentiles of
  the factor. Hold July to June. Negative-BE firms are excluded.

Reported effect, 1963–2012 ([5-factor paper draft](https://www.johnhcochrane.com/s/FF_Five_Factor.pdf),
JFE 2015), %/month: SMB 0.29, HML 0.38, RMW 0.26, CMA 0.33. **Among big stocks only**
(our universe): HML 0.21 (t 1.67), RMW 0.19 (t 1.94), CMA 0.22 (t 2.00). The paper finds
HML redundant once RMW and CMA are in the model.

Decay (French factor file): HML 0.38 for 1963–91, 0.17 (t 1.1) after mid-1992, −0.03
since 2005. Since 2014, RMW 0.18 (t 0.9) and CMA −0.08. Fama & French's "The Value
Premium" ([SSRN 3525096](https://papers.ssrn.com/abstract=3525096)) has the big-value
premium falling from 0.36 to 0.05 %/mo; numbers read through the
[Chicago Booth Review summary](https://www.chicagobooth.edu/review/value-stock-premium-shrinking).

Computable: yes. Equity, revenue, gross profit and total assets are in the annual frames.
Percentiles over our ~2,000 names stand in for NYSE breakpoints.

### Shiller (Nobel 2013): CAPE

Real price ÷ 10-year average real earnings, following Graham & Dodd's "not less than five
years, preferably seven or ten" ([Campbell & Shiller, NBER w8221](https://www.nber.org/papers/w8221)).
It is defined and tested on the S&P Composite to forecast 10-year market returns. A
per-stock version (Anderson & Brooks 2006, [JBFA](https://research-information.bris.ac.uk/en/publications/the-long-term-price-earnings-ratio/))
finds 8-year average earnings roughly double the value spread in UK stocks; the exact
figure is UNVERIFIED (truncated abstract). **Not computable:** we hold 3–4 years of EPS.

### Markowitz & Sharpe (Nobel 1990)

No per-stock screen exists. These are portfolio-construction and pricing theories. Sharpe
says his ratio is for "a zero investment strategy" and "does not take correlations into
account" ([Sharpe 1994](https://web.stanford.edu/~wfsharpe/art/sr/sr.htm)). The only
stock-level descendant is beta, whose empirical form is Betting Against Beta (below).

### Thaler (Nobel 2017) and Kahneman (Nobel 2002): long-term losers

Kahneman has no stock rule; De Bondt & Thaler cite his work with Tversky as motivation.
Rule ([JF 1985](https://breesefine7110.tulane.edu/wp-content/uploads/sites/16/2015/10/Debondt-and-Thaler.pdf)):
sum each stock's monthly return in excess of the market over 36 months; buy the bottom 35
("losers"), hold 36 months. Losers minus winners: 24.6% over three years (t 2.20), mostly
in Januaries and years 2–3.

Decay (CZ calc): 0.78 %/mo in sample, 0.48 after 1985, **−0.20 since 2005**. Computable
from 5y weekly prices; ranking. Not recommended.

### Merton (Nobel 1997): distance to default

Equity is a call option on firm value. The usable "naive" version (Bharath & Shumway,
RFS 2008, [author's slides](https://web-docs.stern.nyu.edu/salomon/docs/Credit2006/T_Shumway.pdf)):

- V = market cap + F, where F = current debt + ½ long-term debt; T = 1.
- σ_V = [E/V]·σ_E + [F/V]·(0.05 + 0.25·σ_E); μ = the stock's prior-year return.
- DD = [ln(V/F) + (μ − σ_V²/2)] ÷ σ_V; default probability = N(−DD).

It forecasts default, not returns: HXZ find failure-probability, O-score and Altman Z
sorts all insignificant. Computable from market cap, debt and 1y daily prices. It
duplicates what Altman Z'' already does for the Overall score's Safety pillar.

## Highly cited academics

### Novy-Marx: gross profitability (JFE 2013)

GP/A = (revenue − COGS) ÷ total assets. Financials excluded; rebalanced each June
([accepted manuscript](https://www.johnhcochrane.com/s/Novy_marx_OSoV.pdf)).

- 1963–2010, top minus bottom quintile: 0.31 %/mo (t 2.49); Fama-French 3-factor alpha
  0.52 (t 4.49).
- **It works in the largest 500 stocks.** Ranking them on GP/A rank + B/M rank, long the
  top 150 and short the bottom 150, earned 0.62 %/mo with a Sharpe ratio of 0.74.
- Decay (CZ calc): 0.30 in sample, **1.02 (t 2.7) for 2014–2024**.
- Caveat (HXZ): GP/A is significant (0.38, t 2.62), but scaled by lagged assets it is not
  (0.16, t 1.04). They argue it is partly the investment effect.

Computable: yes. Gross profit and total assets are already read for Piotroski and
Wealthmatica.

### Asness, Frazzini & Pedersen: Quality Minus Junk (RAST 2019)

[Paper appendix](https://research-api.cbs.dk/ws/portalfiles/portal/60211462/lasse_heje_pedersen_et_al_quality_minus_junk_publishersversion.pdf).
Each input becomes the z-score of its cross-sectional rank; a missing input is dropped,
not zeroed. Quality is the z-score of the sum of three parts:

- **Profitability**: gross profit/assets, ROE, ROA, cash flow/assets, gross margin, low
  accruals.
- **Growth**: five-year change in those same measures, per share.
- **Safety**: low beta, low leverage, Ohlson O-score, Altman Z (1968 form), low ROE
  volatility.

US 1957–2016: alphas 39 / 51 / 60 bp/mo (CAPM / FF3 / 4-factor). Decay (AQR file): raw
0.36 %/mo over the sample, **0.01 since 2019**; post-publication alpha UNVERIFIED.
Computable: profitability yes; growth no (needs 5 years); safety mostly; beta needs a
market series we don't fetch.

### Jegadeesh & Titman: momentum (JF 1993)

[Paper](https://floridapsc.com/library/filings/2013/07457-2013/Support/Gulf's%20response%20to%20OPC's%201st%20POD,%20No.%2057/Jegadeesh%20and%20Titman%201993%20(140-167).pdf):
rank on past 3–12 month returns, buy the top decile. The 12-month formation earned
1.31 %/mo, or 1.49 with a one-week skip. "12-1" is the Fama-French convention
([UMD](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/det_mom_factor.html)),
not the original.

Decay (French UMD): 0.82 for 1965–89, 0.37 after 1993, **0.13 since 2005**. Momentum also
crashes in rebounds after declines (Daniel & Moskowitz, [NBER w20439](https://www.nber.org/papers/w20439)).
Computable now: the weekly close at t−5 ÷ the close at t−53 − 1, if
`get_yf_price_and_history` kept the 5y weekly series (it currently discards it).

### Sloan: accruals (Accounting Review 1996)

[Paper](https://www.cuhk.edu.hk/acy2/workshop/June2009Wasley/1996TAR).pdf):

- Accruals = (ΔCA − Δcash) − (ΔCL − Δshort-term debt − Δtaxes payable) − depreciation,
  divided by average total assets.
- Lowest minus highest decile: 10.4% in year 1 (t 4.71).

Decay: "no longer reliably positive" (Green, Hand & Soliman 2011,
[doi](https://doi.org/10.1287/mnsc.1110.1320)); CZ calc 0.69 in sample, **0.10 (t 1.0)
after 1996**. The cash-flow form, (net income − CFO) ÷ total assets, is computable; it is
already Piotroski's F4.

### Beneish: M-score (FAJ 1999)

M = −4.84 + 0.920·DSRI + 0.528·GMI + 0.404·AQI + 0.892·SGI + 0.115·DEPI − 0.172·SGAI
+ 4.679·TATA − 0.327·LVGI. Above −1.78 flags a likely earnings manipulator.

- The coefficients and cutoff were confirmed only through
  [CFA Institute's tutorial](https://rpc.cfainstitute.org/blogs/enterprising-investor/2013/detetecting-earnings-manipulation-and-fraud-a-light-tutorial-on-probit-analysis).
  The [original paper](https://rpc.cfainstitute.org/research/financial-analysts-journal/1999/the-detection-of-earnings-manipulation)
  is paywalled, so the index definitions are UNVERIFIED.
- Beneish, Lee & Nichols ([FAJ 2013](https://rpc.cfainstitute.org/research/financial-analysts-journal/2013/earnings-manipulation-and-expected-returns))
  find higher M-scores earn lower returns in every size, value and momentum decile. No
  test after 2013 was found.

Mostly computable from two years of statements. Receivables, PP&E and SG&A rows are not
read today. Not meaningful for banks. Best used as a red flag, not a screen.

### Mohanram: G-score (RAST 2005)

Eight binary signals for the lowest-B/M (growth) quintile, most compared with the
industry median: ROA, cash-flow ROA, CFO > net income, low earnings and sales variability
(16 quarters), and R&D, capex and advertising intensity
([doi](https://doi.org/10.1007/s11142-005-1526-4), paywalled; definitions from HXZ
Appendix A.4.26). Decay: CZ calc 1.10 in sample, 0.55 (t 2.7) after 2005. HXZ's
all-stock sort is insignificant (0.27, t 1.35). **Partly computable:** we have no
16-quarter history and no advertising line.

### Frazzini & Pedersen: Betting Against Beta (JFE 2014)

[Paper](https://pages.stern.nyu.edu/~lpederse/papers/BettingAgainstBeta.pdf):

- β = ρ·σ_i/σ_m, shrunk toward 1 (0.6·β + 0.4).
- Split at the median beta. Lever the low-beta leg up to beta 1 and the high-beta leg
  down.
- Four-factor alpha 0.55 %/mo, 1926–2012.

Decay (AQR file): 0.68 through 2012, 0.41 (t 1.98) since 2014. **The alpha comes from the
leverage.** An unlevered sort shows no raw spread (CZ calc −0.01), and BAB puts outsized
weight on micro-caps (Novy-Marx & Velikov,
[JFE 2022](https://ideas.repec.org/a/eee/jfinec/v143y2022i1p80-106.html)). Not usable as
a long-only pass/fail screen.

### Piotroski: F-score (JAR 2000) — already implemented

[Paper](https://www.ivey.uwo.ca/media/3775523/value_investing_the_use_of_historical_financial_statement_information.pdf), §2.3:

- **Nine signals:** ROA > 0, CFO > 0, ΔROA > 0, CFO > ROA, falling long-term debt ÷
  average assets, rising current ratio, no equity issued, rising gross margin, rising
  asset turnover. ROA, CFO and turnover are scaled by beginning-of-year assets.
- **Universe:** only the highest B/M quintile, 1976–96. Scores of 8–9 are high, 0–1 low.
- **Effect:** high minus low 23.0%/yr. **The benefit is confined to the smaller
  two-thirds by market cap and is weak among the largest firms.**
- **Decay:** CZ calc 1.05 in sample, 0.59 (t 1.2) after 2000; HXZ all-stock 0.29
  (t 1.06).

`_compute_piotroski` (`stock_screener.py:1295`) differs from the paper:

- It scores every name, not only high-B/M ones.
- ΔROA and asset turnover use end-of-year assets, not beginning-of-year.
- The leverage test divides this year's LTD by average assets but last year's by
  year-end assets.
- It returns a partial count when some signals are missing. The paper required complete
  data.

These affect only the Overall score's Safety pillar, which is informational, not the gate.

## Practitioners

### Buffett (Presidential Medal of Freedom, [2011](https://obamawhitehouse.archives.gov/blog/2011/02/15/watch-live-president-obama-honors-presidential-medal-freedom-recipients))

From the shareholder letters (primary):

- **Owner earnings** ([1986](https://www.berkshirehathaway.com/letters/1986.html)):
  reported earnings + depreciation, depletion, amortisation and other non-cash charges −
  the average capital spending needed to keep competitive position and unit volume. He
  says that last part "must be a guess."
- **Acquisition criteria** (1986): "demonstrated consistent earning power", "good returns
  on equity while employing little or no debt", simple businesses, management in place,
  no turnarounds. There is no number for "good". The [2014 letter](https://www.berkshirehathaway.com/letters/2014ltr.pdf)
  raises the size test to $75M of pre-tax earnings.
- **The one numeric ROE bar he endorsed** ([1987](https://www.berkshirehathaway.com/letters/1987.html)):
  a Fortune study's tests of "an average return on equity of over 20% in the ten years
  ... and no year worse than 15%". 25 of 1,000 companies passed, and 24 of those 25 beat
  the S&P 500. That result is in sample.
- **The $1 test** (1983): each dollar retained should create at least a dollar of market
  value, "on a five-year rolling basis."

Evidence: "Buffett's Alpha" (Frazzini, Kabiller & Pedersen, FAJ 2018,
[SSRN 3197185](https://papers.ssrn.com/abstract=3197185)) finds Berkshire's alpha becomes
insignificant after controlling for BAB and QMJ. It is leveraged cheap, safe, quality
stocks.

**Partly computable.** Owner earnings works with total capex standing in for maintenance
capex. The 10-year ROE test and the 5-year $1 test need history we don't keep; a 3–4
year version would be our approximation, not Buffett's rule. AAII's "Buffett: Hagstrom"
screen ([AAII](https://www.aaii.com/stockideas/article/486662-combining-quality-and-value-with-the-buffet-hagstrom-screen))
adds thresholds Buffett never set, such as ROE above 15% in each of 3 years.

### Greenblatt: Magic Formula

- **Return on capital** = EBIT ÷ (net working capital + net fixed assets).
- **Earnings yield** = EBIT ÷ enterprise value.
- Rank every name on each, add the two ranks, buy the lowest sums.
- Definitions are from *The Little Book That Beats the Market* (2005), appendix: wording
  UNVERIFIED. Secondary sources say working capital excludes excess cash and fixed assets
  exclude goodwill.
- The [FAQ](https://www.magicformulainvesting.com/Home/Faqs) (primary): no financials or
  utilities; US-listed; "over $1 billion" suggested; at least 20 stocks held about a year.

Evidence:

- Greenblatt's backtest: 30.8%/yr vs 12.4% for 1988–2004
  ([AAII](https://www.aaii.com/stockideas/article/99688-greenblatts-magic-formula-for-beating-the-market)).
- Larkin's 1998–2006 replication: 23.9%/yr ([CXO](https://www.cxoadvisory.com/?p=2290)).
- Gray & Carlisle, *Quantitative Value*: **EBIT/EV alone beat the two-factor formula**
  ([CFA review](https://blogs.cfainstitute.org/investor/2013/04/09/book-review-quantitative-value);
  book figures UNVERIFIED).
- Schwartz & Hanauer 2025 (SSRN 5043197, [summary](https://quantpedia.com/out-of-sample-test-of-formula-investing-strategies/)):
  significant alpha over 1963–2022 from value + quality, weaker since 2000.
- AAII's live version: 6.4%/yr vs 7.5% for the S&P 500 (price) since 1998
  ([AAII performance](https://www.aaii.com/stock-screens/performance)).

**Computable: yes.**
- `_compute_ev_ebit` already gives EBIT/EV, set to None for Financial Services.
- Return on capital needs a net PP&E reader; the row is in `balance_sheet_df` but no
  label constant reads it.
- Our ≥$1B universe meets the size guidance.

### O'Shaughnessy: *What Works on Wall Street*

- **Value Composite** (his own [AAII Journal article, 2013](https://www.aaii.com/files/journal/pdf/what-works-key-new-findings-on-stock-selection.pdf)):
  - Factors: price/sales, P/E, EBITDA/EV, FCF/EV, shareholder yield.
  - Each factor gets a 1–100 percentile. At least 3 factors must be present; missing ones
    are ignored. Sum and split into deciles.
  - Top decile 17.3%/yr vs 11.1% for all stocks, 1963–2012.
- **Trending Value:** top VC decile, then the 25 best 6-month price changes. Book rule
  UNVERIFIED; secondary sources report 21.2% vs 11.2% for 1964–2009.
- **Cornerstone Growth** ([Hennessy prospectus, SEC 2004](https://www.sec.gov/Archives/edgar/data/0001017953/000089706904002090/cmw1065.txt)):
  - Filter: EPS above last year, price/sales < 1.5, positive 3- and 6-month relative
    strength.
  - Then buy the 50 best one-year price gains.
- **Live evidence:** the Cornerstone funds' results from 2000 to 2013 were close to their
  benchmarks against 15–18% in the backtests
  ([CXO](https://cxoadvisory.com/fundamental-valuation/out-of-sample-test-of-what-works-on-wall-street-oshaughnessys-cornerstone-strategies)).

**Computable:** yes. EBITDA needs a D&A reader. Shareholder yield already exists.

### Ken Fisher: price/sales

*Super Stocks* (1984): avoid price/sales above 1.5; "super stocks" are at 0.75 or below.
Thresholds from secondary sources ([Validea](https://blog.validea.com/?p=12824)),
UNVERIFIED. Senchack & Martin
([FAJ 1987](https://rpc.cfainstitute.org/research/financial-analysts-journal/1987/the-relative-performance-of-the-psr-and-per-investment-strategies))
found low P/S beat the market but low P/E beat low P/S in 68% of quarters. Computable;
absolute.

### John Neff: total return ratio

(EPS growth % + dividend yield %) ÷ P/E. His goal was a ratio of 2: "total return —
growth rate plus yield — of twice the P/E we paid" (via
[Novel Investor](https://novelinvestor.com/wise-words-from-john-neff/); book UNVERIFIED).
He wanted growth above 7% but below about 20%, and a P/E 50–60% of the market's. Ran
Vanguard Windsor 1964–95 at 13.7%/yr vs ~10.6% for the market (secondary).

Computable from Finnhub 5y growth, yield and P/E, but it is close to a
dividend-adjusted PEG, which the Lynch screen already is. AAII's version returned
13.7%/yr vs 7.5% since 1998, the best of these. That is one of dozens of AAII screens,
picked after the fact.

### David Dreman: contrarian

*Contrarian Investment Strategies* (1998), UNVERIFIED, per
[Validea](https://blog.validea.com/?p=8148):

- Take the bottom 20% of the largest 1,500 stocks on P/E, price/cash flow, price/book or
  price/dividend.
- Then require: ROE in the top third, current ratio > 2, pretax margin ≥ 8%, debt/equity
  < 20%, earnings growth above the S&P's, and a sustainable dividend.

Computable. The pass conditions overlap heavily with Graham's defensive checks.

### Qualitative only

- **Philip Fisher's 15 points** (1958) are questions about management, R&D and sales
  organisation, with no numbers. AAII's proxy screen adds thresholds Fisher never wrote
  ([AAII](https://www.aaii.com/journal/article/the-philip-fisher-approach-to-screening-common-stocks-for-uncommon-profits)).
- **Templeton's 16 rules** ([Franklin Templeton](https://franklintempleton.com/forms-literature/download/TL-R16))
  have no numeric criteria.
- **Munger and Pabrai** published no screen. Pabrai says he looks at 52-week lows, low
  P/E and P/B lists, and "Joel Greenblatt's Magic Formula ... on a daily basis"
  ([Graham & Doddsville, 2008](https://business.columbia.edu/sites/default/files-efs/imce-uploads/Graham%20And%20Doddsville%20-%20Issue%204%20Summer%202008.pdf)).

## Fit with this screener

**Data:** everything the recommended rules need is already fetched. The three annual
frames are kept whole on the fund dict (`income_stmt_df`, `balance_sheet_df`,
`cashflow_df`), so a new row label is a label constant, not a new request.

- Missing readers: net PP&E (Greenblatt), D&A (EBITDA, Sloan), receivables and SG&A
  (Beneish).
- Momentum needs the 5y weekly closes, which `_compute_price_signals` currently reduces
  and discards.
- About 4 annual periods are available. Rules that need 5–10 years (CAPE, Buffett's ROE
  record, QMJ growth, Templeton's proxy) are out of reach.

**Shape:** the surviving rules are all rankings. A pass would need a cut, such as the top
decile or top two deciles of the composite rank, computed in one cross-sectional pass in
`run_screener` like `azqato_score_all`. Where that cut sits is our choice, not the
author's; Novy-Marx and O'Shaughnessy used quintiles and deciles.

**Cost of a fifth screen:** it touches the gate in both languages (`selections.py`,
`score.ts`, a drift test that diffs them), bumps the selection ledger to v4 (`picks5`,
new file name, a seed step in `screen.yml`), widens the pass filter to 5 levels, changes
card and scorecard layout, and adds methodology text. `docs/plans/wealthmatica-fourth-system.md`
is the checklist from the last time a system was added.

## Recommendation

1. **Fifth screen: profitable value, Novy-Marx form.** Rank the universe on GP/A and on
   book-to-market; sum the ranks; pass = top quintile. Exclude Financial Services, as the
   paper did. It has the strongest post-publication record of anything computable here
   and was tested on the largest 500 stocks.
2. **Alternative with the famous name: Greenblatt's Magic Formula.** ROC rank + EBIT/EV
   rank, excluding Financial Services and Utilities. It has the same economic content.
   Its public live record (AAII) lags the market, and EBIT/EV alone did as well in
   replication.
3. **Not as screens:**
   - Momentum and long-term reversal: dead since 2005.
   - Accruals and size: decayed.
   - BAB: only works with leverage.
   - CAPE and Buffett's 10-year tests: not enough history.
   - Fisher and Templeton: qualitative.
4. **Cheap informational additions, not gates:** Beneish M-score as a red flag beside
   `Trap_Reasons`, and Neff's total return ratio as a Scorecard line.
5. **Piotroski:** align `_compute_piotroski`'s denominators and missing-data handling with
   the paper. This is a separate fix.
