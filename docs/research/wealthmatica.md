# Can Wealthmatica become a screen?

Question (2026-10-04): can the method behind <https://wealthmatica.substack.com> be
systematized into a screen alongside Azqato / Lynch / Graham?

Sources: all 14 posts, read in full through the Substack archive API
(`/api/v1/archive`, `/api/v1/posts/<slug>`). One is paywalled and was not readable
(`zeta-global-2030-financial-model`). Posts are cited by slug; the URL is
`https://wealthmatica.substack.com/p/<slug>`.

## What the blog is

Single-stock thesis essays by one retail investor, not a published rule set. Of 14
posts, 9 are about Zeta Global (ZETA). The others: UiPath (PATH), AppLovin (APP), Voyager
Technologies (VOYG), Keel Infrastructure (KEEL, ex-Bitfarms), and one sector essay.
No post states entry criteria, thresholds, or a universe he screens. Picks come from a
macro narrative ("agentic AI", first-party data, scarce power, space infrastructure),
not from a filter (`the-rise-of-zeta-global`, `how-to-navigate-the-agentic-the-data`).

So he has no screen to port. The closest thing to a method is the financial checklist
that repeats in each full report. Below is what it contains and how much of it can be
computed.

## The repeated checklist

The "Financial Data Overview" section uses the same headings in
`zeta-global-stock-report-and-analysis` (2025-11), `uipath-inc-stock-report-and-analysis`
(2025-12), `zeta-global-the-master-thesis` (2026-09) and
`applovin-the-ad-tech-channel-cmos` (2026-09). He judges each line by its **trend**, not
against a fixed level:

| Heading | What he rewards (quote/paraphrase, source) | Computable from yfinance? |
|---|---|---|
| Revenue (TTM) | 1y and 2y/5y growth; re-acceleration ("+6% → +14% → +16% YoY", PATH; "fifth consecutive quarter of acceleration", `zeta-global-q2-2026-projections`) | yes |
| Free Cash Flow (TTM) | FCF growth ("1-year FCF growth exceeding 100%", ZETA 2.0); FCF margin rising (`zeta-global-the-master-thesis`) | yes |
| FCF v. SBC | SBC falling, FCF − SBC compounding; "SBC as a percentage of FCF ... 6.23%" (APP) | yes |
| Earnings per Share | profitability inflection: "losses decreasing by over 72%" (ZETA 2.0); "first ever GAAP [profitable] third quarter" (PATH) | yes |
| Debt v. Cash | cash above debt (ZETA, PATH "has no debt") | yes |
| Expenses (TTM) | expense growth moderating (ZETA 2.0, PATH) | yes, as operating margin trend |
| Outstanding Shares | flat or falling count, buybacks (PATH, APP "38.9 million shares (~10.6%)" over 3y) | yes |
| Gross Margin | stable/expanding ("held around the 80% range for 5 years", PATH) | yes |
| Operating Margin | direction over level: "Companies that consistently improve operation margin are attractive" (PATH) | yes |
| Analyst EPS / revenue projections | consensus forward growth (APP, ZETA master) | partly (yfinance `earnings_estimate`) |
| Client KPIs: NRR, $1M+ customers, ARPU, RPO, ARR | ZETA, PATH | **no** — company-reported KPIs, no free feed |
| Beat-and-raise streak | "16 consecutive quarters" (ZETA 2.0) | partly (EPS surprise history; guidance raises not in any feed) |
| Insider buying | ZETA 2.0, KEEL | partly (`insider_purchases`) |
| MOAT rating /10, TAM, management, partnerships | every report | **no** — judgement |

His picks are growth names that are not yet profitable or have only just turned
profitable. Most of them have no usable EPS, so Lynch and Graham return N/A for them by
design (CLAUDE.md, financial-integrity rules). The checklist judges them on a different
axis. That makes it a genuinely different fourth voice, consistent with "disagreement is
the signal".

## Valuation: three methods, none stable across posts

- **FCF-per-share exit-yield model** (Qualtrim's DCF tool, ZETA 2.0): project FCF/share
  at a growth rate g for 5 years, divide by an exit FCF yield, then discount at the
  desired return. He picks g from management targets and recent CAGR (bear 22%, base 40%,
  bull 45%). The exit yield comes from the stock's own pre-short-report average (2.7%).
  He never states his desired return. This method can be mechanized; g, the exit yield
  and r would be our assumptions, not his.
- **Price/sales or price/ARR re-rating vs peers** (PATH: P/ARR 4.84x vs an 8–10x peer
  band; VOYG: exit at 7–9.5x forward sales on management's revenue path). This needs
  forward revenue paths and a peer set chosen by hand.
- **Market cap per pipeline MW** (KEEL). Specific to one industry.

Every model is anchored on **management guidance** ("sandbagging", "2–5% buffer"),
which no free feed carries.

## Live-data test (2026-10-04, yfinance 1.7.0)

The computable rows were turned into nine pass/fail checks. Every threshold is ours
`[ASSUMED]`; he publishes none:

- C1: revenue growth ≥ 15%.
- C2: revenue re-accelerating, or growth ≥ 25%.
- C3: FCF > 0 and growing.
- C4: FCF − SBC > 0.
- C5: share count ≤ +2% YoY.
- C6: gross margin down no more than 1 pt.
- C7: operating margin up YoY.
- C8: EPS positive and rising, or the loss narrowing.
- C9: cash ≥ debt.

Growth compares TTM to the prior TTM where Yahoo has both points, and the fiscal year to
the prior year otherwise. We ran it on his 5 picks, on 8 mature controls, and on the
whole Nasdaq-100.

| | his picks | controls (KO PFE VZ INTC NKE T MMM CVS) | Nasdaq-100 |
|---|---|---|---|
| score ≥ 7 of 9 | 3 of 5 (PATH 8, ZETA 7, APP 7; KEEL 4, VOYG 3) | 1 of 8 (KO 7) | 47 of 101 |
| C1 required **and** ≥ 7 of 9 | 2 of 5 (ZETA, APP) | 0 of 8 | 31 of 101 |

Read-outs:

- **The checklist alone does not discriminate.** Seven of the nine checks pass for
  67–81% of the Nasdaq-100, because a mature company also has stable margins, positive
  FCF and a flat share count. Only revenue growth (47 of 101) and net cash (35 of 101)
  filter anything. KO scores the same as ZETA.
- **Two of his five picks fail it outright.** VOYG and KEEL burn cash, have negative
  operating margins, and KEEL's share count is +10.6%. He bought them on catalysts:
  Starlab and Golden Dome for VOYG, a first data-center lease for KEEL
  (`voyager-technologies-building-americas`, `keel-infrastructure-a-capacity-solution`).
  The checklist describes his software picks; it is not how he picks.
- **Requiring growth turns it into a generic quality-growth screen.** That version passes
  31 names, including AVGO, PLTR, CRWD, DDOG, NVDA and MSFT, and no controls. It is
  defensible, but at that point the thresholds are ours, not his. PATH drops out at 13%
  fiscal-year growth, even though he bought it at 16% quarterly YoY.
- **The FCF/share exit-yield model** (g = min(2-year FCF/share CAGR, 40%), exit yield 4%,
  r = 15%) put ZETA at 0.60× fair, PATH 0.82× and APP 0.30×. It breaks on cyclicals and
  one-off years: KO 9.5×, MMM 38×, and no value at all for MU, SNDK or WDC. Of 114 rows,
  25 got no value.

Data limits found, each of which a real implementation must handle:

- **Quarters:** Yahoo returns at most 5 quarters (yfinance source: "maximum 4 years or 5
  quarters"). Quarter-over-quarter re-acceleration, his favorite signal, can only be
  approximated as latest-quarter YoY minus last fiscal-year growth.
- **Prior TTM:** this point comes only from Yahoo's private timeseries endpoint. It is
  missing for 29 of 101 Nasdaq-100 names, clustered on non-December fiscal years.
- **Divestitures:** APP's prior TTM still includes the divested apps business, so TTM
  growth reads 19% against 70% fiscal-year growth and 53% for the latest quarter.
- **SBC:** the row is missing entirely for 12 names (VZ, T, WMT, MELI, the utilities).
- **No-debt companies:** debt-free names (ISRG, MNST, ALAB) have no Total Debt row.
  Under "None, never 0" they read as missing, not as zero debt.
- **EPS:** Yahoo's trailing EPS sometimes disagrees with the sum of its own quarters
  (VOYG −1.28 vs −2.34).

What it would add that the screener lacks: SBC-adjusted FCF, share-count trend, and
margin and profitability **trajectory**. The other rows overlap existing systems:
revenue growth and cash vs debt are Azqato pillars; FCF yield and a DCF are in Overall.
Statements the pipeline already fetches (annual `income_stmt`, `cashflow`,
`balance_sheet` in `get_yf_price_and_history`) cover every check on an annual basis, so an
annual-basis version needs no new API calls.

## Verdict

- **His method cannot be ported as a screen.** It is narrative stock-picking plus custom
  valuation models anchored on management guidance, and 2 of his 5 picks fail his own
  checklist.
- **The checklist can be systematized,** but only by inventing thresholds. Ungated, it
  does not separate his picks from Coca-Cola.
- **Gating cost:** as a fourth gating system it would change "passes all 3" in
  `web/src/score.ts` and the selection ledger's levels 1–3. That means a `LEDGER_VERSION`
  bump and a backfill replay (CLAUDE.md gotcha).
- **Informational cost:** as an informational scorecard panel, like Overall, it is cheap
  and adds the trajectory signals above.

## Outcome

Built 2026-10-05 as a 4th **gating** system (user's call over the panel): 7 of 9 on annual
statements, no growth gate, N/A checks skipped. Plan: `docs/plans/wealthmatica-fourth-system.md`.
On the annual basis the picks split the same way as above: ZETA, PATH and APP pass; VOYG, KEEL
and KO fail. Of the 20 stocks passing all three systems on 2026-10-02, 7 also pass the 4th.
