# Seeking Alpha Quant Ratings and Alpha Picks

Question (2026-11-08): can this screener use Seeking Alpha (SA) Quant Ratings or Alpha
Picks, either by ingesting them or by rebuilding an approximation from the data the
pipeline already fetches? What are the rules, what is public, and what does outside
evidence say about whether the ratings work?

Sources: SA's help center (help.seekingalpha.com), about.seekingalpha.com (Terms of Use,
feeds, ratings-performance and academic-research pages), subscriptions.seekingalpha.com
landing pages, and the author-hosted PDFs of the University of Kentucky paper
(russelljame.com), all fetched 2026-11-08. seekingalpha.com article and symbol pages, SSRN
and about.seekingalpha.com/products returned HTTP 403 to automated fetches. That was
respected: no user-agent spoofing and no workarounds. SA's own robots.txt also disallows
archive.org crawlers, so archived copies of seekingalpha.com are sparse.
help.seekingalpha.com pages are archived and were used. Quotes from SA articles and webinar
transcripts come from **search-result snippets** and are labelled that way. Reviews,
affiliate pages and forums are labelled **secondary**. Every claim below was checked
twice: once in a sweep, once in a verification pass. Only claims that came back confirmed
or corrected are stated as fact, and corrected claims use the corrected text. Claims that
could not be checked are listed under UNVERIFIED.

## Answer in brief

- **No compliant feed exists.** SA has no documented API, data-licensing product or
  ratings feed. The Terms of Use limit content to personal, non-commercial use and ban
  scraping and redistribution. Every "Seeking Alpha API" is an unaffiliated wrapper, and the
  best known of them advertises getting past SA's bot defence. The data underneath is
  licensed from S&P Global, and S&P's terms are separate and also say "internal use only".
  Showing SA ratings or picks on a public GitHub Pages site would need written consent from
  SA, and probably from S&P as well. Without consent, the only compliant option is a link
  to SA's page for each ticker.
- **The rules are partly public.** The help center publishes the Alpha Picks entry filters,
  the sell rule and the performance method. The Quant Rating's scale, five factors, cap
  rule and update cadence are public. Its weights, grade bands, full metric list and
  size/risk adjustment are not.
- **Outside evidence is real but modest.** Guo, Jame and Markov find a long-short spread
  of 1.20–1.52%/month in six-factor alpha over 2016–2022. They also find it is comparable
  to a generic 118-anomaly composite and loads mostly on momentum. A random forest trained
  on 59 SA-style inputs reproduces the rating at a correlation of 0.70 and earns similar
  alpha.
- **Alpha Picks' headline return is concentrated and volatile.** Per secondary trackers,
  five picks carry most of the gain. The since-inception figure fell from about +422% (June
  2026) to +295% (30 Oct 2026). SA says the record is not audited GIPS-compliant and is not
  run with real money.
- **An approximation is buildable for four of the five factors** from data we already
  fetch or can fetch from yfinance. EPS Revisions can be measured today but has no free
  history. A backtest of the approximation would be biased by look-ahead, survivorship and
  weight-fitting (§7).

## 1. Is there an API?

### Verdict

No publicly documented SA API or data-licensing product could be found. It is not in the
Terms, in the 288-URL help-center sitemap, on the about site or on the feeds page. This is
an absence-of-evidence finding: about.seekingalpha.com/products returned 403 and was not
checked. SA does distribute some content through partners. Its transcripts page says "links
to our transcripts appear on our partners' websites". For ratings, the only route the Terms
name is consent: "please contact Seeking Alpha to obtain written consent"
(<https://about.seekingalpha.com/terms>, §5). None of the RSS feeds has a rating field.

### Terms of Use (<https://about.seekingalpha.com/terms>, "Updated: May 2, 2021", footer © 2024)

| Section | What it says (verbatim) | Bearing on this project |
|---|---|---|
| §5 Copyright | "You may access and use the Content ... solely for your personal, non-commercial use." | A public site is outside personal use. |
| §5 | "If you are interested in reprinting, republishing or distributing content from Seeking Alpha, please contact Seeking Alpha to obtain written consent." | The only sanctioned route. |
| §5 | "You may link to any content on the Site." | A per-ticker link-out is allowed. |
| §6 User Conduct | "Use any robot, spider, site search/retrieval application, or other manual or automatic device or process to download, retrieve, index, \"data mine\", \"scrape\", \"harvest\" ..." | Rules out scraping. |
| §6 | "You may not use, copy, display, sell, license, de-compile, republish, upload, post, transmit, distribute, create derivative works or otherwise exploit Content ... without our prior written permission." | Rules out displaying ratings. |
| §6 | "You may only maintain a single account; You may never share your account user name or password ..." | Rules out a shared bot account. |
| §18 S&P Services | "The S&P Services are being provided for your internal use only ... without prior written approval of S&P." S&P "may enforce its rights against you as the third-party beneficiary". | A second clearance, from S&P. |
| §19 GICS | "You agree not to redistribute the Global Industry Classification Standard Service" | SA's sector labels are GICS. |
| §20 Subscriptions | "Unless we notify you in writing otherwise, you are not permitted to share Content available through your Subscriptions." | Alpha Picks content. |
| §22 | "Seeking Alpha's Very Bullish recommendations are generated daily by a systematic quantitative model with no human intervention." | Ratings change daily, so any copy goes stale fast. |
| §23 Marketplace/Advisory | "... any release of specific investment recommendations, is strictly prohibited." | This sits in a paragraph about marketing promotions and does not name Alpha Picks. Applying it to Alpha Picks is an inference. |

Related pages:
- The newsletter disclaimer says content is "licensed solely for your individual use as a
  subscriber" (<https://help.seekingalpha.com/newsletter-disclaimer>).
- The market-data page says: "Fundamentals, estimates, and Wall Street analyst ratings are
  provided by S&P Global Market Intelligence." It credits backtests to "ClariFI, S&P Global
  Market Intelligence LLC", and adds: "You may not copy or redistribute information provided
  by Seeking Alpha. ... Reproduction of any information ... including ratings ... is
  prohibited except with the prior written permission of the relevant party"
  (<https://help.seekingalpha.com/basic/where-do-you-source-your-market-data-from>).
- A subscription "cannot be shared with other users or across multiple email addresses"
  (<https://help.seekingalpha.com/basic/can-i-share-my-subscription-across-more-than-one-email-address>).

### Official channels, none of which is a ratings feed

- **RSS.** <https://about.seekingalpha.com/feeds> links 19 feeds: per-ticker
  (`/api/sa/combined/{T}.xml`), `feed.xml`, `market_currents`, and several topic, country
  and sector feeds. The AAPL feed returned 30 items, 14 articles and 16 news items, with
  `sa:author_name` and `sa:stock` fields and no rating field. It says: "Use of this feed is
  limited to personal, non-commercial use ... Publishing this feed for public or commercial
  use ... is prohibited" (<https://seekingalpha.com/api/sa/combined/AAPL.xml>).
- **Rating alerts.** A help-page snapshot from 2025-09-10 says: "Choose the Rating Type:
  Quant, SA Author, or Wall Street. ... Choose the Delivery option ie Email or Mobile"
  (<https://web.archive.org/web/20250910055357/https://help.seekingalpha.com/premium/how-do-i-set-up-or-edit-rating-alerts-for-a-stock>).
  The live page now describes price alerts. Either way the alerts go to one personal account.
- **Alpha Picks alerts.** "Subscribers are notified when new stock picks are added to the
  portfolio" (<https://help.seekingalpha.com/how-does-alpha-picks-handle-changes-in-stock-ratings>).
  No delivery channel is named. A standalone iOS app, "Alpha Picks: Stock Ideas" (seller
  Seeking Alpha Ltd., v1.0 2026-03-11, v1.7.1 2026-10-26, in-app purchase "Alpha Picks
  $499.00"), mentions no export (<https://apps.apple.com/app/id6758436545>).
- **Broker linking** is inbound only: "the changes from your broker will be updated
  automatically on a daily basis"
  (<https://help.seekingalpha.com/premium/how-can-i-link-my-seeking-alpha-portfolio-with-my-broker>).
  The aggregators are Plaid and SnapTrade. A portfolio can be downloaded as .xlsx by hand.
- **Institutional history.** In 2014 SA Pro carried "an annual license fee of $8,200",
  "targeted at hedge funds and other institutional investors". That bought article access,
  not data (secondary, <https://www.waterstechnology.com/management-strategy/2340379/seeking-alpha-mulls-breaking-out-research-platform-into-separate-subscriptions>).

### Unofficial wrappers and scrapers (secondary; none is licensed)

| Listing | Publisher | Ratings endpoints | Free / top tier | Notes |
|---|---|---|---|---|
| <https://rapidapi.com/apidojo/api/seeking-alpha> | Api Dojo (created 2020-05-20) | `get-factor-grades`, `get-metric-grades`, `get-quant-rating-histories` (Deprecated), `get-ratings` (Deprecated) | $0/500 req/mo; $500/1,000,000 | "SA now have PerimeterX as bot defender ... Our API has already included feature that helps you to overcome the layer". This is access-control evasion. |
| <https://rapidapi.com/tipsters/api/seeking-alpha-finance> | Tipsters CO (2022-10-16) | `metric-grades`, `rating/histories`, `rating/relative`, `author-ratings` | $0/500; $599/1,000,000 | Copies SA's marketing text and states no affiliation. |
| <https://rapidapi.com/belchiorarkad-FqvHs2EDOtP/api/seeking-alpha-api> | Pinto Studio (2024-03-27) | ratings data | 200 free; $495/1,500,000 | "This API is not affiliated with, endorsed by, or connected to Seeking Alpha." Success rate 69%. |
| <https://apify.com/bovi/seeking-alpha-scraper> | bovi | `quant_overall_rank`, `quant_sector_rank` | — | "Uses Seeking Alpha's internal v3 API ... rotates to a fresh RESIDENTIAL IP per ticker on any block". |

None of the three RapidAPI listings has an Alpha Picks endpoint: a search of each for
"alpha-picks", "alpha_picks" and "Alpha Picks" found nothing. On GitHub,
`AG3NTZ3R0/seeking-alpha` "is **not** affiliated, endorsed, or vetted by Seeking Alpha"
(last code push 2022-03-14). `polo2444172276/SeekingAlphaQuant` is a replication attempt
(see §5). `seekingalpha.com/robots.txt` disallows the whole site for GPTBot, ClaudeBot,
CCBot, archive.org_bot and others. Robots rules grant no license either way.

## 2. Alpha Picks mechanics

Started 2022-07-01 by "Steven Cress from the Quant Team at Seeking Alpha and Joel Hancock"
(<https://help.seekingalpha.com/when-was-alpha-picks-started-and-by-whom>).

### Cadence

"We pick two 'Strong Buy' rated stocks per month. One pick is added on the first trading
day of the month, and the other is added on the 15th of the month or the closest trading
day after it" (<https://help.seekingalpha.com/when-are-the-picks-added-to-the-alpha-picks-portfolio>).
SA's pages give no time of day.

### Entry filters (all primary, <https://help.seekingalpha.com/what-criteria-does-alpha-picks-use-to-select-its-top-performers>)

| Rule | Verbatim |
|---|---|
| Strong Buy streak | "Stocks must have a \"Strong Buy\" quant rating for at least 75 consecutive days" (calendar or trading days is not stated) |
| Security type | "Must be a U.S. common stock (no ADRs)" |
| No REITs | "Cannot be a REIT" |
| Size | "3-month average market capitalization greater than $500M" |
| Price | "Stock price greater than $10" |
| Cooldown | "Has not been recommended in the past year" |
| Ranking | "ranks stocks based on five factors: value, growth, profitability, EPS revisions, and momentum" |

SA does not publish how two names are chosen from the eligible pool. Sector concentration
is allowed: "The Alpha Picks portfolio may be concentrated in sectors experiencing the
greatest improvement in fundamentals"
(<https://help.seekingalpha.com/what-specific-economic-indicators-does-alpha-picks-consider>).

### Exit, trim and winner rules

| Rule | Status | Source |
|---|---|---|
| Removed when the rating becomes Sell, or "When a stock no longer scores well on fundamentals, valuation, and momentum (relative to the sector)" | primary | <https://help.seekingalpha.com/how-does-alpha-picks-handle-changes-in-stock-ratings> |
| "If a stock is rated 'Hold' for more than 180 days, its rating is automatically changed to \"Sell\"." | primary | same page; also <https://subscriptions.seekingalpha.com/lp_alpha-picks_sub_new> |
| "Alpha Picks outlines specific criteria for when to sell or reduce your position in a stock." The criteria are not listed. | primary | <https://help.seekingalpha.com/what-kind-of-performance-updates-and-analysis-does-alpha-picks-provide-1> |
| Exit on Sell **or Strong Sell**, on an M&A event, or on a merger of equals | secondary | <https://www.retirebeforedad.com/alpha-picks-review/>, <https://www.matchmybroker.com/tools/alpha-picks-by-seeking-alpha-review> ("Rating drops to Sell or Strong Sell, immediate exit") |
| "Winner" = "when it doubles from the purchase price". A winner at Hold for 180 days sells only the original purchase amount, and this repeats each further 180 days. Winners fully exit only on Sell, Strong Sell or M&A. | secondary | retirebeforedad |
| A position reaching 15% is "reduced to 10%", and "proceeds are distributed on an equal-weighted basis among the other holdings" | secondary, plus an SA snippet | retirebeforedad; TraderHQ; Wall Street Survivor. Search snippet of a July 2024 SA webinar: "Once the stock is in excess of 15%, we cut the position back to 10%". In the same webinar SMCI "became 20% of our portfolio". A second check could not reproduce this snippet. |
| "Subscribers get notified via email when a position is closed or reduced in the portfolio." | secondary | retirebeforedad |

### Sizing

No SA page reachable without login states the initial size. New subscribers are told to
buy "at least 5 'Strong Buy' rated Alpha Picks" or "the entire portfolio using the
allocations in the 'Portfolio' tab"
(<https://help.seekingalpha.com/i-am-new-to-alpha-picks-how-can-i-get-started>). Weights
drift: "Winners dominate the performance of the portfolio as they become larger positions"
(<https://help.seekingalpha.com/how-does-the-buy-and-hold-approach-of-alpha-picks-impact-long-term-investments-1>).
The benchmark buys an equal amount of SPY on each pick date, which suggests equal entry
notional, but that is an inference. Real World Investor (secondary) says positions are 2–4%
of holdings (<https://realworldinvestor.com/alpha-picks-review/>).

### Performance method

From <https://help.seekingalpha.com/how-is-the-alpha-picks-performance-calculated>:
- Measured from 2022-07-01, "buying every Alpha Pick on the pick date using the opening
  price".
- Closed picks use "the closing price of the sell date".
- The benchmark is "buying an equal amount of SPY on the pick date using the opening
  price".
- "Dividends are reinvested."
- "Total Return is as of the previous close."

From <https://subscriptions.seekingalpha.com/premium-getting-started_cs/ap>:
- "Seeking Alpha and Alpha Picks employ S&P Global, an independent 3rd party, to calculate
  the returns", as time-weighted returns "consistent with" GIPS.
- "Alpha Picks is not an investment product run with real money, nor is it an audited
  GIPS compliant investment product."

### Sibling quant portfolios

| | Alpha Picks | PRO Quant Portfolio (PQP) | Quant Growth & Income (QG&I) |
|---|---|---|---|
| Launch | 2022-07-01 | performance from 2025-06-02; announced 2025-06-17 ([press release](https://www.silicon.co.uk/press-release/seeking-alpha-launches-pro-quant-portfolio-delivering-weekly-stock-ideas-powered-by-market-beating1-quantitative-system)) | "calculated starting from June 3, 2026" ([help](https://help.seekingalpha.com/how-is-the-quant-growth-income-performance-calculated)) |
| Size | open-ended (help page: "over 30 stocks", undated) | "typically holds 30 positions selected from Seeking Alpha's top-rated 'Strong Buy' stocks" ([lp](https://subscriptions.seekingalpha.com/lp_pro_pqp)) | "no more than 30 stocks" ([help](https://help.seekingalpha.com/what-is-the-quant-growth-income-portfolio-qgi)) |
| Cadence | 2 a month | "rebalances weekly", 2–3 trades a week | "Trades every 2 weeks on Wednesdays", published "at 1:00 p.m. ET" ([help](https://help.seekingalpha.com/how-can-new-subscribers-invest-with-the-quant-growth-income-portfolio)) |
| Universe | US common stock, no ADRs or REITs, >$500M, >$10 | US stocks and ADRs, small and micro caps, "no minimum share price" ([comparison](https://subscriptions.seekingalpha.com/lp_subscriptions_pro-ap-comparison/)) | dividend payers, Strong Buy or Buy "for a certain amount of consecutive days", "average market cap ≥ $400M"; ADRs, REITs and small caps allowed ([help](https://help.seekingalpha.com/what-criteria-does-quant-growth-income-use-to-select-its-top-performers)) |
| Benchmark | equal SPY per pick date | Equal Weighted S&P 500 | VYM total return |
| Fill price | pick-date open / sell-date close | not stated | "volume-weighted average price on the purchase date and sell date" |

**Price.** SA's 2024 notice says "your subscription will renew automatically at $399/year"
(<https://about.seekingalpha.com/alpha-picks-subscription-price-update>). The 2026 landing
page shows "$499 $449/year"
(<https://subscriptions.seekingalpha.com/lp_alpha-picks_sitewide_sale_2026_aff/>). "We don't
offer free trials for Alpha Picks" (help center).

## 3. What is public

**What a free user gets.** "Free users can read one Premium article per month", plus
portfolios, real-time alerts and basic tools
(<https://help.seekingalpha.com/can-i-access-seeking-alphas-content-without-a-subscription>).
Quant Ratings and Factor Grades "are displayed on symbol pages for paying subscribers", and
the user must be logged in "as a paying subscriber or in free trial"
(<https://help.seekingalpha.com/premium/quant-ratings-and-factor-grades-faq>). Alpha Picks is
a separate product from Premium
(<https://help.seekingalpha.com/what-is-the-difference-between-sa-premium-and-alpha-picks>).
"Alpha Picks subscribers get access to all stock picks (over 30 stocks) ... on day 1"
(<https://help.seekingalpha.com/how-do-i-access-the-managed-model-portfolios-offered-by-alpha-picks>).
None of the 17 help articles on Alpha Picks mentions picks being released to the public
after a delay. Nobody here checked what a logged-out browser sees on the portfolio page.

**Public landing pages** show headline returns only and name no tickers. Their copy is stale
and contradicts itself: "Performance calculated from day of launch July 1, 2022, until April
17, 2024" sits beside "Performance since 7/1/2022 (381 days)"
(<https://subscriptions.seekingalpha.com/lp_alpha-picks_sitewide_sale_2026/>). The only pick
they mention is unnamed: "a homebuilder stock in March 2023, which appreciated 100%". The
help page on performance since inception is a screenshot "taken on February 21, 2025".

**Named picks found in openly reachable sources.** Returns are as of the snapshot date
shown. They move a lot between snapshots.

| Ticker | Pick date | Return (as of) | Source |
|---|---|---|---|
| AMR | 2022-07 (one of the first) | "up 142%" (2024-07-12) | SA webinar "Inside Alpha Picks", search snippet |
| NUE | 2022-07 | closed "up almost 60%" | same snippet |
| SMCI | 2022-11-15 | +968.59%, sold (TraderHQ); "picked at $85 and sold above $900" (MMB) | TraderHQ, MatchMyBroker (secondary) |
| MOD | 2022 | +348.42% (2026-09-01) | TraderHQ (secondary) |
| POWL | 2023-05-15 | "up 163%" (2024-07, SA snippet); +1,194.36% (2026-08-13, MMB); +886.62% (2026-09-01, TraderHQ) | mixed |
| AMPH | 2023-07-03 | −52.32% | TraderHQ (secondary) |
| CLS | 2023-10-16, picked twice ("+632.8% average across two recommendations") | +1,166.59% (2026-09-01); +1,013.04% (2026-08-13) | TraderHQ, MMB, [HTMW](https://www.howthemarketworks.com/advanced/charts-and-patterns/seeking-alpha-alpha-picks-review/) (secondary) |
| APP | 2023-11-15 | +1,571.37% (2026-09-01) | TraderHQ (secondary) |
| EAT | 2024 | +345.85% | TraderHQ (secondary) |
| STRL | not given | +927.31% (2026-08-13). First in an October 2026 allocation screenshot at 7.40%, so likely open | MMB (secondary) |
| LRN | 2025-06-02 | −54.42% | TraderHQ (secondary) |
| MU | 2025-10-15 | +402.58% | TraderHQ (secondary) |
| TTMI | late 2025 | +101.59% | TraderHQ (secondary) |
| LITE | 2026 | +41.73% | TraderHQ (secondary) |
| ICHR | 2026-07-01 | −51.36% | TraderHQ (secondary) |

The TraderHQ figures are "TraderHQ analysis of the published trade log (data as of
September 1, 2026)", 104 picks with 51 active and 53 closed, and it calls itself "not a
third-party audit"
(<https://traderhq.com/alpha-picks-by-seeking-alpha-review-stock-market-insights-best-investment-newsletters/>).
MatchMyBroker's screenshots have tickers "obscured". Position counts disagree between
sources: TheStockDork says "about 20 active positions" (2026-07-24), and TraderHQ says 51
active (2026-09-01). CRDO appears on an SA landing page
(<https://subscriptions.seekingalpha.com/lp_alpha-picks_sub_crdo_ppc>) without being called
a pick. InvestorPlace's "Alpha Picks: 3 Solid Stocks" uses the phrase generically and is not
SA's service.

## 4. The Quant Rating

### Stated rules (primary)

| Topic | Verbatim | Source |
|---|---|---|
| Scale | "a score (from 1.0 to 5.0, where 1.0 is Strong Sell and 5.0 is Strong Buy)". Labels: Strong Sell, Sell, Hold, Buy, Strong Buy. | <https://help.seekingalpha.com/premium/what-are-quant-ratings-and-how-do-i-use-them> |
| Factors | "Objective, data-driven evaluations of stocks based on over 100 metrics ... Assigns grades from A+ to F for each factor" | <https://help.seekingalpha.com/what-exclusive-stock-ratings-does-seeking-alpha-offer> |
| Peer set | "Over 100 metrics for each stock are compared to the same metrics for the other stocks in its sector, and overall." What "and overall" means is not explained. | <https://help.seekingalpha.com/premium/how-to-assess-any-stock-using-premium-features-on-symbol-summary-pages> |
| Weights | "The overall Quant Rating is not a simple average of the Factor Grades." "weighted to maximize the predictive value ... Factors with the greatest predictability carry higher weights." No numbers are published. | FAQ; <https://about.seekingalpha.com/quant-sell-ratings> |
| Cap rule | A stock that scores very badly on one factor "is disqualified as anything higher than a Neutral". The disqualifying grades are "a D+ or worse for Growth, Momentum and EPS Revisions, and a D- or worse for Value and Profitability". "Neutral" is not defined. | FAQ |
| Size and risk | The overall rating "takes account of a stock's size and risk". The factor grades do not include them, and the method is not given. | FAQ |
| Roles | "The Value, Growth and Profitability factors are used to identify mis-priced securities ... while the Momentum and EPS Revisions factors identify timeliness." | quant-sell-ratings |
| Cadence | "The Quant Ratings are updated once a day, before the market opens. ... A computer runs this model daily without human intervention." | quant-sell-ratings |
| Universe | "about 5,600 stocks". It does "not cover stocks that have no sell-side analyst coverage", because estimates and revisions are key inputs. It covers ADRs but not foreign-exchange listings. | FAQ |
| Designer | "designed and managed by Steven Cress", Head of Quant Strategy | FAQ |

### Metrics per factor

SA never publishes the full list. Here is what it names, followed by the 59 inputs an
academic replica used, which carry SA's own metric labels (Internet Appendix Table IA.2 of
<https://www.russelljame.com/quant_june26.pdf>).

| Factor | SA's own wording | Replica inputs (IA.2) |
|---|---|---|
| Value (19 inputs) | "such as P/E ratio, Price/Book, Price/Sales and Enterprise value to EBITDA ... and forward metrics based on analysts' estimates". The grade is "derived from comparing the aggregate of all the underlying metrics, and is therefore not an average of the grades for each underlying metric" ([valuation tab](https://help.seekingalpha.com/premium/what-is-the-valuation-tab-and-how-do-i-use-it)). No DCF: DCF models "are highly sensitive to the company's assumed long-term growth rate" (FAQ). | P/E GAAP and non-GAAP (TTM, FWD), PEG, EV/Sales, EV/EBITDA, EV/EBIT, P/S, P/B, P/CF, dividend yield |
| Growth (21) | Growth tab tracks Revenue, EBITDA, EBIT, Net Income, EPS (Diluted), Book Value/Share, FCF, Fully Diluted Shares. "Fiscal year values are used to compare year-to-year data", using CAGR ([growth tab](https://help.seekingalpha.com/basic/about-the-growth-tab)). The page does not say which of these feed the grade. SA's "Growth" means growth in profitability, not the academic high-market-to-book ([2023 paper](https://www.russelljame.com/quant_Ratings_9_15_23.pdf)). | YoY and FWD growth in revenue, EBITDA, EBIT, EPS, FCF, operating cash flow, ROE, dividends; 3–5Y EPS CAGR; working-capital growth; capex growth |
| Profitability (13) | not listed | gross, EBIT, EBITDA, net and levered-FCF margins; ROE; return on total capital; ROA; asset turnover; cash from operations; cash per share; capex/sales; net income per employee |
| Momentum (4) | price change "over a period of time ... such as the last 12 months or 3 months", vs the sector or the stock's own history ([definitions](https://help.seekingalpha.com/premium/what-do-value-growth-profitability-momentum-and-eps-revisions-mean-and-why-are-they-important-to-investors)) | 3M, 6M, 9M, 1Y price performance. The labels suggest no skip-month, which is an inference. |
| EPS Revisions (2) | "more frequent upward revisions than the sector average or that of historical levels" (definitions) | FY1 up revisions and FY1 down revisions, last 90 days |

The definitions page compares against "the sector average or that of historical levels",
but the FAQ rejects own-history multiples for Value. The two pages are in tension.

### Score cutoffs and distribution

No SA page gives numeric bands, and none says whether grades are percentile- or
z-score-based. The paper states them: "Strong Sell (Quant Rating < 1.5), Sell (1.5<=Quant
Rating<2.5), Hold (2.5 <=Quant Rating <3.5), Buy (3.5<=Quant Rating <4.5), and Strong Buy
(Quant Rating >=4.5)". The mean is 2.95 (s.d. 0.89), "all ratings are relative to the
current sector", and the sectors are the 11 GICS sectors (2023 and 2026 versions). The
average distribution is Strong Sell 8%, Sell 8%, Hold 64%, Buy 10.44%, Strong Buy 9.49%,
stable from year to year (Table 1, June 2026). A secondary review agrees on "4.5 or higher
a \"STRONG BUY\"" and "Consider selling anything rated 1.5 or lower"
(<https://www.wallstreetsurvivor.com/seeking-alpha-review/>).

### SA's own backtests

- **Sell side** (<https://about.seekingalpha.com/quant-sell-ratings>):
  - Method: "all the daily 'Strong Sell and Sell' ratings for 14 years from Jan 2010 to
    Aug 2024", "equal weighting, daily rebalancing, and no transaction costs".
  - Result: 41.98% cumulative (2.43% a year) against 521.88% (13.33%) for the S&P 500 TR.
    Maximum drawdown was 59.11% against 33.79%. The portfolio held "almost 1000" names and
    made "roughly 237,000 trades".
  - Survivorship is handled "to the best of our ability" by adding delisted and acquired
    names.
  - The page also says simulated trades run "from Jan 2024 to present", which contradicts
    its own window.
- **Strong Buy.** The /performance/quant page returned 403. The Alpha Picks landing page
  says "Over the last 12 years, the backtested strategy has delivered impressive returns,
  beating the S&P 500 yearly", from "December 2009 onwards", and prints no figures.
  Secondary sources give "about 25% in annualized returns since 2010" against "roughly 10%
  for the S&P 500" (<https://www.thestockdork.com/seeking-alpha-track-record/>) and 1,754%
  against 385% (wallstreetsurvivor). SA's own S&P 500 TR figure over 2010–2024 is 13.33% a
  year, not 10%.
- **Terms §22.** The original Very Bullish backtest ran 12/31/2009 to 03/02/2021, equal
  weight, daily rebalance, zero costs. Only 07/18/2020 onward was simulated trading.

### Sibling systems (not the stock rating)

- REIT ratings add "FFO, AFFO, FAD, Gross Properties" and benchmark to XLRE. The page gives
  three inconsistent backtest periods (<https://about.seekingalpha.com/quant-reit-ratings>).
- Dividend Grades are Safety, Growth, Yield and Consistency. Safety uses "payout ratios,
  dividend coverage ratios, interest coverage ratios, debt ratios, profitability metrics".
  The page claims "91.3% of all stocks that CUT their Dividend had a dividend safety grades
  'C+' or Lower" over "2010-2026", without saying how that was computed
  (<https://about.seekingalpha.com/quant-dividend-grades>).
- ETF ratings "rely on an entirely different formula" (2023 paper).

## 5. What outside research shows

### Guo, Jame (and Markov): the only academic test

- **Versions.** "Quantitative Analysis and the Informativeness of Social Media Research",
  Sept 2023, SSRN 4540580 (<https://www.russelljame.com/quant_Ratings_9_15_23.pdf>). This
  is the one SA's academic-research page cites, saying the ratings "strongly predict"
  returns "based on multiple years of data" (<https://about.seekingalpha.com/academic-research>).
  The newer version is "Quantitative Research on Main Street: Evidence from Seeking Alpha"
  (with Stanimir Markov, June 2026), "R&R: Journal of Accounting Research" and not yet
  published (<https://www.russelljame.com/research.html>).
- **Topic.** The paper is mainly about SA contributors. Validating the ratings is its first
  step.
- **Design.** CRSP share codes 10/11 with an SA rating, about 2,750 stocks a year (2,099 in
  2016, 3,543 in 2022). Quintiles are sorted by Quant Recommendation at each month-end from
  Dec 2015 to Nov 2022 and held one month. Results are equal- and value-weighted, with
  CAPM, FF3, Carhart, FF5 and 6-factor alphas.

Monthly alphas, June 2026 version, Table 3:

| | Strong Buy | Buy | Hold | Sell | Strong Sell | Long-short |
|---|---|---|---|---|---|---|
| EW CAPM | 0.84% (t 2.51) | −0.07% | −0.20% | −0.54% | −1.30% (−1.95) | 2.15% (3.12) |
| EW 6-factor | 0.90% (4.50) | | | | −0.62% (−1.65) | 1.52% (3.50) |
| VW CAPM | 0.55% (2.55) | 0.02% (0.09) | −0.02% (−0.55) | −0.71% (−2.39) | −1.40% (−2.79) | 1.95% (3.25) |
| VW 6-factor | 0.40% | −0.02% | −0.01% | −0.39% (−1.93) | −0.79% | 1.20% (2.94) |

The VW long-short alpha is 1.68% under FF3 and 1.39% under Carhart. Only Buy and Hold are
flat. The short side (Sell plus Strong Sell) carries more of the spread than the long leg.
The Sept 2023 version had EW CAPM from −1.17% to 0.81% (long-short 1.99%, 6-factor 1.38%)
and VW long-short 1.98% CAPM and 1.21% 6-factor, and said "passive factor loadings
contributed roughly 0.75% to monthly returns".

What the paper found:

- **Factor loadings.** "The decline is primarily due to the long-short portfolio's large
  loadings on value, momentum, and profitability factors." The authors leave open whether
  that is risk or mispricing. Figure IA.1, read from the chart: the VW long-short SMB
  loading is about −0.78 (a large-cap tilt) and the EW CMA loading is about −0.78.
- **What the rating is made of.** They regressed the rating on 13 Jensen-Kelly-Pedersen
  (JKP) cluster scores, with sector × month fixed effects. Standardized coefficients:
  Momentum 0.50 (t 75.69), Value 0.14, Profit Growth 0.06, Low Risk 0.05, Quality 0.05,
  Debt Issuance 0.03, Profitability 0.01 (t 0.86), Size −0.08 and Reversal −0.20
  (t −37.14). Within R² is 37.66%, against 9.12% for the single aggregate score.
  Novy-Marx's gross profits-to-assets (`gp_at`) sits in JKP's Quality cluster, not
  Profitability, which helps explain the loading pattern.
- **No skip-month.** "The negative loading on Reversals ... likely reflects that the
  momentum strategies considered by SA do not follow the common academic convention of
  skipping the most recent one-month return."
- **Replica.** A random forest with "59 predictor variables spanning valuation, growth,
  profitability, price momentum, and analyst forecast revisions" was refit on an expanding
  window, with missing values filled by industry medians. "The correlation between
  Estimated Quant Ratings and actual Quant Ratings is 0.70." No feature importances are
  reported. VW long-short CAPM alphas, from Figure IA.4 labels: actual 1.95%, estimated
  1.82% (all stocks), 1.70% (covered), 2.51% (not covered). The paper shows that SA-style
  fundamental and estimate data can approximate the rating. It does **not** show that free
  data is enough: the revisions inputs need estimate history, and the model was trained on
  SA's ratings.
- **No better than a generic composite.** The alphas "are comparable in magnitude to those
  earned by the Net Anomaly strategy of Jensen, Kelly, and Pedersen (2023)", which
  aggregates 118 anomalies with matched bucket sizes. The confidence intervals overlap.
- **Backfill.** "The ratings are backfilled in the sense that they were not provided to SA
  users in real-time. However, all the estimates are out-of-sample." VW CAPM alpha was
  positive in six of seven years. "Seeking Alpha currently provides historical ratings
  through August of 2019. However, when we began collecting the data, we were able to
  collect \"back-filled\" quantitative ratings starting from January 2015."
- **Churn.** "95% of firms with a strong buy retain the strong buy rating in the
  subsequent day, 64% ... in the subsequent month, and 18% over the subsequent year". After
  a year, 57.61% of Strong Buys are Hold, 8.02% Sell and 4.41% Strong Sell.
- **Use.** The ratings "are designed to identify better performing stocks within a sector
  but should not be used to pick better performing sectors or for market timing" (2023).
- **Reach.** The 2023 version cites about 270,000 premium and pro subscribers out of 10
  million members. The 2026 version explains why alpha persisted after launch by
  distribution "limited to roughly 70,000 premium subscribers".
- **Contributors** (the paper's main topic). After launch, one more rating point raised a
  report's recommendation by 5.5 pp, and by 17.5 pp for reports that cite quant terms.
  Quant-citing reports earned 2.97% over three months per recommendation step, "roughly
  60% (1.72% out of 2.97%)" of it from quant-style returns. The 2026 abstract adds
  "without reducing firm-specific fundamental analysis".

### Other replication attempts

`polo2444172276/SeekingAlphaQuant` ("Seeking Alpha's Quant Model Replication", created
2026-09-07, 0 stars) rebuilds sector-relative factor grades on S&P 500 data from Financial
Modeling Prep. Its config says "Exact Seeking Alpha weights and percentile cutoffs are not
publicly disclosed". It uses equal factor weights, cutoffs at the 80th, 60th and 40th
percentiles, and an upgrades-minus-downgrades proxy for revisions
(<https://github.com/polo2444172276/SeekingAlphaQuant>). No public project publishes
weights fitted to actual SA ratings.

### Analogues

| System | Construction | Independent evidence |
|---|---|---|
| Zacks Rank | Estimate revisions only: Agreement, Magnitude, Upside, Surprise. About 4,400 stocks. "only the top 5% of stocks receive a #1 Zacks Rank". "The optimal time horizons ... are 1-6 months" ([guide](https://advisortools.zacks.com/Content/ZAT_ZacksRankGuide.pdf)). | CXO (secondary): the real Zacks Rank Strategy account earned 6.5% against 6.5% for SPY, Feb 1995 to Jun 2009, despite backtested gross alpha. Frictions "may offset gross returns" ([CXO](https://www.cxoadvisory.com/fundamental-valuation/are-zacks-rankings-exploitable/)). |
| IBD Composite | EPS Rank, RS, Group Rank, SMR, Acc/Dis, % off the 52-week high, rated 1–99. "More weight is placed on the EPS Rank and Relative Strength Rating". RS weights the latest quarter 40% and each earlier quarter 20%. Ranked against "all other stocks in the trading country", not by sector ([O'Neil](https://www.williamoneil.com/about-us/legal/oneil-proprietary-rating-and-rankings)). | none found |
| Validea | 22 guru strategies, run "After each trading day" on "3000+ stocks", scored 1–100 with weights, where "90 or above" passes ([guide](https://zeusnew.validea.com/aboutus/guruanalysisuserguide.pdf)). These are absolute checklists, like this repo's Lynch and Graham. | none found |
| Value Line Timeliness | rank-based | Choi (2000, JFQA 35(3):485–498) removed recent earnings surprises to strip out PEAD and still found "performance beyond what is predicted by existing models". But "once transactions costs have been accounted for, it is doubtful profitable abnormal returns could have been realized" ([Cambridge](https://www.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/value-line-enigma-the-sum-of-known-parts/D50D5C94D2D496F85D6F7CE0ACEB7309)). |

### Factor literature each grade maps to

- **Value.** The paper says SA "incorporate[s] ... valuation ratios (Fama and French,
  1992), past returns (Jegadeesh and Titman, 1993), and profitability (Novy-Marx, 2013)".
- **Momentum.** Jegadeesh & Titman (1993, JF 48(1):65–91): winner-minus-loser strategies
  "generate significant positive returns over three- to twelve-month holding periods"
  ([EconPapers](https://econpapers.repec.org/RePEc:bla:jfinan:v:48:y:1993:i:1:p:65-91)).
- **Revisions.** Chan, Jegadeesh & Lakonishok (1996, JF 51(5):1681–1713): "Past return and
  past earnings surprise each predict large drifts in future returns after controlling for
  the other". Analysts "respond sluggishly to past news"
  ([EconPapers](https://econpapers.repec.org/RePEc:bla:jfinan:v:51:y:1996:i:5:p:1681-1713)).
  Revisions and price momentum are separate, additive signals. Post-earnings drift: Bernard
  & Thomas (1989, JAR 27:1–36), bibliographic record only.
- **Profitability.** Novy-Marx (2013, JFE 108(1):1–28): "gross profits-to-assets, has
  roughly the same power as book-to-market", and "Controlling for profitability also
  dramatically increases the performance of value strategies"
  ([EconPapers](https://econpapers.repec.org/RePEc:eee:jfinec:v:108:y:2013:i:1:p:1-28)).
  SA's grade uses margins and returns, not GP/A.
- **Decay.** McLean & Pontiff's 2013 working paper finds "average out-of-sample decay ...
  about 10%" and post-publication decay "about 35%" (<https://ivey.uwo.ca/media/3775549/pontiff.pdf>).
  The published 2016 figures (26% out of sample and 58% after publication, 97 predictors)
  are cited in `docs/research/laureate-screens.md`; they could not be re-fetched in this
  pass.
- **Cress's view** (secondary podcast description, 2026-07-24): "momentum remains the single
  strongest historical predictive factor", and "The danger of dynamic factor weighting"
  ([episode](https://marketmisbehavior.buzzsprout.com/2420291/episodes/19542423-the-quantitative-richter-scale-2026-multi-factor-modeling-with-steve-cress)).

## 6. Performance and concentration

### Three numbers that are often conflated

1. SA's notional **time-weighted portfolio Total Return**, in which winners compound into
   large weights. This is the only official figure.
2. The **simple average return per pick** against SPY bought on the same dates. Wall
   Street Survivor: "The average return of all of their picks since launch in July 2022 is
   now 94% compared to 28% for the SPY" (updated 2026-11-02). It notes this is not directly
   comparable to SA's figure (<https://www.wallstreetsurvivor.com/alpha-picks-review/>).
   HTMW: 101% against 25% (2026-09-27). moneysmylife: 69.35% against 21.99% (2026-02-17).
3. **Third-party compounded simulations.** TraderHQ: 347.9%, a 43.3% CAGR, against 103.8%
   for its own S&P series (2026-09-01). TraderHQ's S&P series runs above SA's benchmark, so
   its numbers do not belong in the SA series.

### SA since-inception Total Return, by snapshot

| As of | Alpha Picks | S&P benchmark | Source |
|---|---|---|---|
| 2024-04-17 | +125.28% | +38.69% | SA landing page (primary) |
| 2024-10-06 | +145.31% | +51.82% | SA landing page (primary) |
| 2025-03 | +136.29% | +49.41% | SA help center (primary) |
| 2025-12 | +274.79% | +81.05% | StockAnalysis, snippet only; page now 404 (secondary) |
| 2026-04-10 | +316.61% | +79.99% | [EarnForex](https://www.earnforex.com/forum/threads/alpha-picks-review.54262/latest) (secondary) |
| 2026-05-26 | 368% | ~96% | SA video "Navigating Uncertainty With Alpha Picks", snippet |
| 2026-06-09 | +421.61% | +96.50% | [WallStreetZen](https://www.wallstreetzen.com/blog/alpha-picks-review/) (secondary) |
| 2026-07-01 | "up about 415%" | 93% | Cress, 4-year anniversary video (article 4919194), snippet. Same video: YTD "up 40% versus the S&P up 6.89%" |
| 2026-07-17 | +371.06% | +99.68% | MatchMyBroker, per search index (secondary) |
| 2026-09-02 | 393% | 95% | SA figure reported by Wall Street Survivor (secondary) |
| ~2026-10-01 | +352.65% | +102.43% | [Smart Money with Kai](https://smartmoneywithkai.com/blog/seeking-alpha-picks-review), "native Since Inception view" (secondary) |
| 2026-10-30 | +294.81% | +100.19% | MatchMyBroker, updated 2026-11-03 (secondary) |

The 2026 figures disagree because they are snapshots of one volatile series taken on
different dates, not different calculations. The derived changes below are this document's
arithmetic, not published numbers:

- **Peak to 30 Oct:** from about +421.6% on Jun 9 to +294.8% on Oct 30, the portfolio fell
  24.3% (521.61 to 394.81) while the benchmark rose 1.9%. That Jun 9 was the true peak is
  an assumption, since there is no daily series.
- **October:** the portfolio fell about 12.8% and the benchmark about 1.1%, measured from
  the ~Oct 1 snapshot.
- **2026 year to date at Oct 30:** roughly +5% to +7%, depending on which end-2025 base is
  used. Most of the +40–46% mid-year gain Cress cited was given back.
- **Apr 2024 to Mar 2025:** the portfolio rose about 4.9% and the benchmark about 7.7%, so
  the portfolio lagged. An SA transcript snippet from 2025-04-30 has YTD "down 9.3% versus
  the S&P, which is down 6%".

### Concentration and hit rate (TraderHQ, 2026-09-01, secondary)

- 104 positions, 66% win rate (69 winners, 35 losers). The average winner is +121.8% and
  the average loser −21.6%. The median pick is +20.8%, and the average excluding the top
  5% is +41.1%. The average hold is 494 days.
- "Capping every position at +100% would have turned 7,646% of total gains into 2,946% — a
  61.5% haircut".
- Top five: APP, CLS, SMCI, POWL, MU (§3).
- By pick year (average / win rate / count): 2022 +65% / 75% / 16; 2023 +155% / 71% / 24;
  2024 +65% / 67% / 24; 2025 +59% / 75% / 24; 2026 −6% / 38% / 16.
- Other trackers' win rates run 66–77% depending on date and population. Wall Street
  Survivor's page alone gives 73%, 74%, 75% and 77%. moneysmylife: "Only 73% of Alpha
  Picks' recommendations are profitable (compared to 99% for the S&P 500)".

### Tilts

- **Sector.** The help center says picks "are not selected from any particular sectors"
  (<https://help.seekingalpha.com/what-sectors-does-alpha-picks-focus-on-the-most>). Real
  World Investor (June 2026) lists Industrials ~24%, Energy ~19%, IT ~17%, Consumer
  Discretionary ~16% and a "weighted average portfolio beta is 1.06". It also lists SMCI at
  "nearly 9% of holdings", which suggests the data is from 2024.
- **Factors.** No factor regression of Alpha Picks returns was found anywhere. The entry
  rule needs a 75-day Strong Buy streak, and the rating loads 0.50 on momentum (§5), so a
  momentum tilt is structural. That is an inference.
- **October 2026.** The October drop coincided with reported weakness in AI hardware: "AI-linked
  stocks ... struggled in recent days, with sharp declines in shares of semiconductor
  companies and tech hardware firms" (Reuters via [The Star](https://www.thestar.com.my/tech/tech-news/2026/10/17/as-ai-rally-wobbles-stock-market039s-spotlight-turns-to-earnings),
  2026-10-17). The timing is circumstantial, not an attribution.

## 7. Reconstruction spec

The aim is a buildable approximation of SA's five factor grades and composite from free
data, scored the same way this repo scores everything else: `None` for a missing input,
never 0, and skipped rather than zero-filled. The paper's replica filled gaps with industry
medians. This repo's financial-integrity rules forbid that, so a name missing a whole
factor gets no grade for that factor. Every threshold and weight below is `[ASSUMED]`.

### What the pipeline already fetches (read from `stock_screener.py`, `azqato.py`)

`get_yf_price_and_history` fetches:
- `fast_info.last_price`;
- `.info`, of which it reads `sector`, `beta`, `currency`, `revenueGrowth`,
  `earningsGrowth`, `totalCash`, `totalDebt`, `marketCap`, `priceEpsCurrentYear`,
  `forwardPE`, `pegRatio` and `trailingPegRatio`;
- the annual `income_stmt`, `balance_sheet` and `cashflow` frames, kept whole as
  `income_stmt_df` / `balance_sheet_df` / `cashflow_df`;
- `dividends`;
- 5-year weekly and 1-year daily (`auto_adjust=False`) price history;
- `earnings_estimate` and `revenue_estimate`, of which only the "0y" `growth` and `avg`
  are read.

`get_finnhub_metrics` fetches the whole `/stock/metric` bundle. `get_combined_data` reads
`epsAnnual`, `epsBasicExclExtraItemsAnnual`, `epsGrowth5Y`, `epsGrowth3Y`,
`dividendPerShareAnnual`, `dividendPerShareTTM`, `marketCapitalization`,
`currentRatioAnnual`/`Quarterly`, `bookValuePerShareAnnual`/`Quarterly`, `pb` and
`freeCashFlowPerShareTTM`/`Annual`. The installed yfinance (1.8.0) also exposes, unfetched
today:
- `eps_trend`: index `0q +1q 0y +1y`, columns `current 7daysAgo 30daysAgo 60daysAgo
  90daysAgo`;
- `eps_revisions`: columns `upLast7days upLast30days downLast7days downLast30days`;
- `growth_estimates`: index includes `+5y`, columns `stock industry sector index`;
- `earnings_history` and `upgrades_downgrades`.

These are from the docstrings in `yfinance/base.py`.

### Metric map

Key: **have** = a value the repo already computes. **derive** = computable from data
already fetched, with no new call. **new free** = one more free yfinance call. **gap** = no
free source.

| SA metric (IA.2 label) | Status | Where |
|---|---|---|
| P/E FWD | have | `az_pe_fwd` (current FY "0y", SA's FWD convention per `stock_screener.py`) |
| PEG | have | `az_peg_fwd` |
| P/B | have | Finnhub `pb` → `pb_ratio` |
| EV/EBIT (TTM) | have | `_compute_ev_ebit` (annual EBIT, Finnhub cap, yfinance debt and cash) |
| Dividend yield | have | `div_yield_pct` in `get_combined_data` |
| P/E GAAP TTM | derive | price / `ttm_eps`. Note that `ttm_eps` is Finnhub's *annual* EPS. |
| P/S TTM, EV/Sales TTM, P/CF TTM, EV/EBITDA TTM | derive | revenue and EBITDA rows of `income_stmt_df`, `ocf`, cap, debt, cash. Annual, not TTM. |
| P/S FWD, EV/Sales FWD | derive | `revenue_estimate.loc["0y","avg"]` is already fetched but unread |
| P/E non-GAAP TTM | new free, partial | `earnings_history` / `eps_trend(methodology="normalized")`. Yahoo's non-GAAP definition is not S&P's. |
| EV/EBITDA FWD, EV/EBIT FWD | **gap** | no free consensus EBITDA or EBIT estimate |
| Revenue growth YoY | have | `az_rev_ttm` (`info.revenueGrowth`) |
| Revenue growth FWD, EPS growth FWD | have | `az_rev_fwd`, `az_eps_fwd` |
| EPS growth YoY | have | `az_eps_ttm` (`info.earningsGrowth`) |
| EBITDA, EBIT, net income, FCF, OCF, ROE, dividend, working-capital and capex growth YoY | derive | annual statement frames. `wealthmatica.py` already derives revenue/FCF/margin trends this way. |
| 3–5Y EPS CAGR (forward) | new free | `growth_estimates.loc["+5y","stock"]`. Finnhub `epsGrowth5Y` is historical, not forward. |
| EBITDA, EBIT, OCF growth FWD | **gap** | no free consensus |
| Gross, EBIT, EBITDA, net, levered-FCF margins; CAPEX/sales | derive | statement frames |
| ROE, ROA, return on total capital, asset turnover, cash per share | derive | statement frames. `roic` is already computed. |
| Cash from operations | have | `ocf` |
| Net income per employee | new free | `info.fullTimeEmployees`, not read today |
| 3M / 6M / 9M / 1Y price performance | derive | the 1-year daily `closes` already held for RSI. Nominal, not total return. |
| FY1 up / down revisions, last 90 days | **new free, now only; gap for history** | `eps_revisions` gives counts over 7 and 30 days only. `eps_trend` gives consensus now against 90 days ago. Neither has history. |
| Size | have | `marketCapitalization` / `az_market_cap` |
| Risk | have / derive | `beta`; volatility from `closes`. SA's method is unknown. |
| Sector | have | `info.sector`. Yahoo's taxonomy ("Basic Materials", "Financial Services") is not GICS, which SA uses. |
| Analyst coverage (SA's exclusion rule) | have | a missing "0y" estimate means no coverage |

So 4 of 5 factors are fully buildable today: Value apart from the forward EBITDA and EBIT
multiples, Growth apart from the forward EBITDA, EBIT and OCF growth, Profitability, and
Momentum. EPS Revisions is buildable only from today forward, using `eps_trend`'s 90-day
consensus change as the closest free stand-in for SA's 90-day up/down counts.

### Scoring sketch

1. **Peer set.** Within each yfinance sector, rank every metric by percentile, with lower
   multiples better for Value. Exclude names with no "0y" estimate, as SA does.
2. **Factor grade.** Average the metric percentiles present within each factor. A factor
   needs at least half its metrics present, or it is `None`. SA grades "the aggregate of
   all the underlying metrics", which is not a mean of per-metric grades, so this step
   already differs from SA. Map the factor percentile to 13 letter bands, A+ … D−, F. The
   band edges are unpublished, so they are ours.
3. **Composite.** Combine the factor percentiles with weights. SA's weights are hidden. The
   outside evidence (momentum loading 0.50; Cress: momentum "the single strongest") says
   momentum should carry the most weight, but any number is ours. Add size and risk only
   once we decide how. SA gives no method.
4. **Cap rule** (SA's, stated): Growth, Momentum or Revisions ≤ D+, or Value or
   Profitability ≤ D−, caps the result at Hold.
5. **Buckets.** Either use the paper's score cutoffs (1.5 / 2.5 / 3.5 / 4.5) on a 1–5
   rescale, or cut the cross-section to the paper's observed distribution: bottom 8% Strong
   Sell, next 8% Sell, 64% Hold, ~10% Buy, top ~9.5% Strong Buy. The second is easier to
   defend, because it matches what SA actually outputs.
6. **Alpha Picks emulation** would need a stored daily rating per name to count "75
   consecutive days". This repo runs on weekdays, so the count would be in runs. It would
   also need the US-common / no-ADR / no-REIT / 3-month average cap > $500M / price > $10
   / 12-month cooldown filters and the 1st-and-15th schedule. The ledger would live on the
   `data` branch beside `picks.json`. It cannot be backfilled. SA does not say how it picks
   two names from the eligible pool, so that step would be ours.

**Differences from this repo's existing design:**
- SA is sector-relative. Azqato ranks across the whole merged market, and its tier depends
  on the peer set (CLAUDE.md, the `byIndex` note).
- This universe has about 2,000 names, with a $1B floor on Total US. SA's has about 5,600
  and includes small caps. Sector medians will differ from SA's.
- Five of Azqato's six metrics (rev TTM and FWD, EPS TTM and FWD, PEG FWD) are already
  SA-style Growth and Value inputs. An SA-style system would overlap Azqato on Growth and
  add Momentum, Profitability and Revisions.

### Gaps that cannot be closed with free data

- **Point-in-time estimate history.** Revision counts, forward multiples and forward growth
  as they stood on past dates (IBES or S&P Capital IQ). yfinance holds only "now" and four
  look-backs up to 90 days.
- **SA's hidden parameters.** Factor weights, letter-grade band edges, the size/risk
  adjustment, which of the "over 100 metrics" count, momentum window weights, and the FY1
  and FY2 mix for revisions.
- **S&P's non-GAAP EPS and its forward EBITDA, EBIT and OCF consensus.**
- **GICS sector and industry codes.** These are licensed. §19 also forbids redistributing
  SA's.
- **SA's actual ratings**, the target any calibration would need. They cannot be obtained
  compliantly (§1), and the history SA serves starts in August 2019.

### Why a backtest of the approximation would be biased

- **Look-ahead in fundamentals.** yfinance statements are the latest restated values with
  no filing dates, and `.info` fields are current snapshots. A historical run would use
  numbers nobody had at the time.
- **No estimate history.** The Revisions factor and the forward Value and Growth metrics
  would have to be dropped, which makes it a different model, or filled with today's
  values, which is look-ahead. SA's own model calls estimates key inputs.
- **Survivorship.** The universe is built from today's index constituents and VTI holdings.
  Delisted and acquired names are missing. SA's sell backtest added them back "to the best
  of our ability".
- **Short history.** yfinance returns only a few recent fiscal years of annual statements,
  so multi-year growth and trend metrics have only a handful of usable points.
- **Weight-fitting.** SA's weights are hidden. Choosing ours by backtest fits noise in the
  same sample. McLean & Pontiff measure about 35% post-publication decay even for published
  factors. SA's own 2015–2019 ratings are backfilled, so even SA's history is not live.
- **Costs and turnover.** Only 64% of Strong Buys are still Strong Buy a month later. SA's
  backtests assume daily rebalancing and zero costs. The Zacks real-money record (CXO) and
  Choi's Value Line result both show gross rating alpha disappearing after frictions.
- **Peer-set mismatch.** Sector percentiles over about 2,000 mostly large names are not
  SA's percentiles over about 5,600.

## 8. Open questions

1. Would SA license ratings or factor grades to a public, non-commercial site? Only a
   written request can answer this. The Terms say "contact Seeking Alpha". Would S&P Global
   also have to approve under §18?
2. Is the 2021-dated Terms page still the governing version?
3. Are the 75-day and 180-day clocks calendar days or trading days? Does a Hold →
   Strong Buy → Hold sequence reset the 180-day clock?
4. Is the 15%-to-10% trim official, and when did it start? Did the winner exception change
   from "sell half" to "sell the cost basis", or is it one rule worded loosely?
5. How does SA choose two picks from a pool of hundreds of eligible Strong Buys?
6. What time of day is a pick published? Performance is measured from the pick-date open.
   If picks post during the session, the reported return includes a move subscribers could
   not capture.
7. How do the grade band edges, the factor weights and the size/risk term work? Does "and
   overall" mean a second, whole-universe comparison?
8. Momentum windows: are they weighted, and is there no skip-month (the paper's reading)?
   Revisions: is the window 90 days, which fiscal years count, and are revenue revisions
   included?
9. How would the paper's results change net of costs and after 2022? The academic sample
   ends in Dec 2022, and no independent post-2022 test exists.
10. What do the Strong Buy backtest table (/performance/quant) and SSRN 4540580's abstract
    page say? Both returned 403.
11. What do a logged-out user and a Premium-only user actually see on the Alpha Picks
    portfolio and Closed tabs?
12. Product decision, not research: should an SA-style approximation become a fifth
    system, a non-gating panel like Overall, or a replacement for Azqato's growth and value
    legs? That is the owner's call.

## UNVERIFIED

These matter but could not be confirmed. Most come from seekingalpha.com pages that
returned 403.

- **SMCI discretionary exit.** SMCI was half-closed in March 2024 and the remainder removed
  before Nov 2024 "not due to specific rules of the model, but rather red flags not captured
  by Quant data" (snippet of article 4738486). If true, exits are not purely mechanical.
- **Announcement time.** Picks are said to be announced "at noon (EST)", with email about
  10 minutes later, and to have once been announced after the close (user comments).
- **Pool size.** "On any given day, we have anywhere from 380 to 400 Strong Buys" (Cress,
  article 4919194).
- **Winner rule wording.** Transcript wording for winners: "maintain half the position and
  only liquidate half" (July 2024, 4703541) against "we only sell the initial position, and
  we let the rest ride" (Nov 2024, 4737131).
- **SMCI's numbers.** The +968% return and the "~20% of the portfolio" statement. A second
  check could not reproduce either one.
- **Removal headlines.** "GigaCloud Technology And Alpha Metallurgical Resources Downgraded
  To Sell: Removed From AP Portfolio!" and "CMCSA Removed From AP Portfolio Due To Hold
  Rating".
- **Other named holdings.** EAT "since April, the stock is up 131%"; KGC, COMM and SSRM
  named in "3 Stocks To Buy From Alpha Picks/Pro Quant Portfolio"; the other nine names in
  Cress' Top 10 for 2026 (the article ID is also uncertain: 4860173 or 4856608).
- **Symbol-page rows.** The per-row grades on symbol Valuation, Growth, Profitability and
  Momentum pages (AMD, GOOGL, FI, BMO), and whether a page displaying a metric means it is
  weighted.
- **SA's write-up of the paper** (4683185) reportedly concedes "the JKP characteristics did
  not include EPS revisions" and cites "twelve out of the last 13 years".
- **Steven Cress as founder of Cress Capital Management.**
- **April 2025 cause.** That the April 2025 drawdown was caused by a rotation out of
  momentum. Also the MSCI late-July 2026 and Advisor Perspectives 2026-09-08
  momentum-unwind reports.
- **TradersUnion.** Its George Noble piece: 393% against 95%, "independently calculated by
  S&P Global".
- **Position counts.** StockAnalysis' "46 closed, 27 profitable" (snippet only; the page now
  404s) and MoneysMyLife's "37 of 56".
- **PQP fills and returns.** Whether PQP fills at VWAP, and whether S&P Global calculates
  PQP and QG&I returns.
- **Finnhub field names.** Any `/stock/metric` field the repo does not already read (for
  example margins or price returns). Their names and units were not checked against the
  live API.

## Circulating claims that are wrong

- *"Alpha Picks returns are GIPS-verified / GIPS-compliant"* (WallStreetZen,
  MatchMyBroker). SA's own words: "not ... an audited GIPS compliant investment product",
  with returns "consistent with" GIPS.
- *"The 75-day Strong Buy rule is only in third-party reviews"* (TickerNerd framing). It is
  on SA's help center.
- *"Alpha Picks are equal-weighted at entry."* No SA page says so. One review says
  positions are 2–4% of holdings.
- *"SA publishes cutoffs of 3.5 for Buy and 2.5 for Hold."* The full 1.5 / 2.5 / 3.5 / 4.5
  cutoffs come from the Guo-Jame paper. SA's pages give none.
- *"Quant Ratings cover about 6,000 stocks."* SA says "about 5,600". No source for 6,000
  was found.
- *"Cress said 378% vs 97% at mid-year."* No SA source was found. The closest match is
  TraderHQ's own simulation, +378.5% against +105.6%.
- *"The backtested Strong Buy beat a ~10% S&P."* SA's own S&P 500 TR figure for 2010–2024
  is 13.33% a year.
- *"Only Strong Buy and Strong Sell matter; Sell is flat."* In the VW panel Sell is
  significant through four factors (CAPM t −2.39).
- *"The paper shows free public data can replicate the rating."* It used SA-labelled
  inputs, including estimate revisions, and trained on SA's ratings.
- *"No public replication exists on GitHub."* One does (`polo2444172276/SeekingAlphaQuant`),
  but it is unfitted.
- *"The Value Line enigma is just PEAD."* Choi (2000) removed PEAD and still found alpha,
  but not after costs.
- *"Earnings momentum explains price momentum."* Chan-Jegadeesh-Lakonishok find each
  predicts returns after controlling for the other.
- InvestorPlace's "Alpha Picks: 3 Solid Stocks With 10X Potential" is not about SA's
  service.
