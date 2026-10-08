// Shapes mirror stock_screener.py's output row. Lynch/Graham metric keys are
// DOUBLE-prefixed (e.g. Lynch_Lynch_Status, Graham_Graham_Discount_Pct) because
// process_ticker re-prefixes dicts whose keys already carry the prefix. The
// `azqato` block is the nested no-AI relative score (azqato.py / azqato_score_all).

// Rank tiers of the azqato relative percentile model: S = top 10% of scored
// names, A = next 10%, B = 20-50%, C = 50-75%, F = bottom 25%; 'sp' (S+) = a
// perfect 100. Ranks, not buy/sell ratings.
export type AzqatoTier = 'sp' | 's' | 'a' | 'b' | 'c' | 'f'

// The eight ranked metrics; peVsG (forward P/E vs growth) and netCashMc (net
// cash as a percent of market cap) are weight-0 context ratios — ranked for
// cell coloring only, never scored.
export type AzqatoMetricKey =
  | 'revTTM'
  | 'revFwd'
  | 'epsTTM'
  | 'epsFwd'
  | 'peVsG'
  | 'pegFwd'
  | 'cashDebt'
  | 'netCashMc'

// The pools the screener covers, in the order stock_screener.INDEX_FETCHERS
// lists them — each is a universe azqato's own screener ranks separately.
// TotalUS is every US-listed VTI holding of $1B+ market cap.
export const INDEX_NAMES = ['S&P500', 'Dow30', 'Nasdaq100', 'Growth100', 'Value100', 'Dividend100', 'TotalUS'] as const
export type IndexName = (typeof INDEX_NAMES)[number]

export interface Azqato {
  score: number | null // 0-100; null when no metric was evaluable
  tier: AzqatoTier | null
  passes: number // metrics in the upper part of the pack (points >= 15)
  total: number // 6 — a missing metric is a miss, not a pass; 0 if nothing was evaluable
  parts: Partial<Record<AzqatoMetricKey, number>> // points 0-20; missing key = hard zero
  pctiles: Partial<Record<AzqatoMetricKey, number>> // raw percentile 0..1
  // The same stock re-scored inside each pool it belongs to, the way azqato's
  // own screener loads one universe at a time. Display only — the score/tier
  // above (the pooled cross-section) is what the pass gate reads.
  byIndex?: Partial<Record<IndexName, { score: number | null; tier: AzqatoTier | null }>>
  revTTM: number | null
  revFwd: number | null
  epsTTM: number | null
  epsFwd: number | null
  peFwd: number | null
  pegFwd: number | null
  cash: number | null
  debt: number | null
  marketCap: number | null // Yahoo marketCap, same snapshot as cash/debt (netCashMc)
  rsi: number | null // scorecard display only — not scored
  pos_52w_pct: number | null // scorecard display only — not scored
}

export interface Row {
  Ticker: string
  Price?: number | null
  MarketCap_B?: number | null
  EPS_TTM?: number | null
  EPS_Annual?: string | null
  DivYield_Pct?: number | null
  Growth_g_Pct?: number | null
  AAA_Yield?: number | null
  PB_Ratio?: number | null
  Indexes?: string | null

  Lynch_PE?: number | null
  Lynch_PEG?: number | null
  Lynch_PEGY?: number | null
  Lynch_Lynch_Score?: number | null
  Lynch_Lynch_Category?: string | null
  Lynch_Lynch_BuyPrice?: number | null
  Lynch_LV_Ratio?: number | null
  Lynch_Lynch_Discount_Pct?: number | null
  Lynch_Lynch_Status?: string | null
  Lynch_Lynch_PEG_Band?: string | null
  Lynch_PEG_Status?: string | null
  Lynch_PEGY_Status?: string | null

  Graham_Graham_FV?: number | null
  Graham_Graham_Discount_Pct?: number | null
  Graham_Graham_Status?: string | null

  // Why Lynch/Graham are "N/A" for this row (non-positive EPS, unknown or
  // non-positive growth). Null whenever the valuation actually ran.
  Valuation_Input_Warning?: string | null

  DefensiveScore?: number | null
  DefensiveLabel?: string | null
  CombinedScore?: number | null

  Show?: boolean
  Error?: string | null
  Indexes_?: never
  azqato?: Azqato

  // The Wealthmatica checklist (wealthmatica.py) — the 4th gating system.
  // Absent on error rows and on datasets published before it existed.
  wealthmatica?: Wealthmatica

  // ── OverallScore (ported v2.0 methodology) — informational 4-pillar
  // composite. Does NOT participate in the pass gate (score.ts's
  // verdicts()/combinedVerdict()/passesAll() never read it).
  OverallScore?: number | null
  Sector?: string | null
  Trap_Reasons?: string | null
  Piotroski_F?: number | null
  Altman_Z?: number | null
  DCF_Intrinsic_Value?: number | null
  DCF_Value_Low?: number | null
  DCF_Value_High?: number | null
  DCF_Discount_Pct?: number | null
  DCF_Implied_Growth?: number | null
  DCF_WACC_Pct?: number | null
  DCF_Method?: string | null
  DCF_Data_Warning?: string | null
  DCF_Cyclical_Flag?: boolean | null
  FCF_Yield_Pct?: number | null
  EV_EBIT?: number | null
  Earnings_Yield_Pct?: number | null
  ROIC_Pct?: number | null
  Shareholder_Yield_Pct?: number | null
  scores?: Scores

  // Selection ledger (selections.py): the run and price at which this stock
  // first passed exactly 1, 2, 3 and 4 screens, keyed by that count. A level it
  // never reached is absent; null/absent when it never passed any. (The
  // three-screen ledger's `picks` field is retired and never read.)
  picks4?: Picks | null

  // Tolerate the full set of emitted columns without enumerating every one.
  [key: string]: unknown
}

export interface EntryMark {
  at: string // generated_at of the run
  price: number | null
}

export type PickLevel = 1 | 2 | 3 | 4

// Keyed by the level as a string: that is how the JSON carries it.
export type Picks = Partial<Record<`${PickLevel}`, EntryMark>>

// The nine checks, in display order (wealthmatica.CHECKS).
export const WEALTHMATICA_CHECKS = [
  'revGrowth',
  'revAccel',
  'fcf',
  'fcfSbc',
  'shareChange',
  'grossMargin',
  'opMargin',
  'eps',
  'cashDebt',
] as const
export type WealthmaticaCheckKey = (typeof WEALTHMATICA_CHECKS)[number]

// pass null = N/A: the statements don't carry that line (a bank has no gross
// profit). N/A is neither a pass nor a fail.
export interface WealthmaticaCheck {
  value: number | null
  pass: boolean | null
}

export interface Wealthmatica {
  checks: Record<WealthmaticaCheckKey, WealthmaticaCheck>
  passed: number
  applicable: number
  pass: boolean | null // null when too few checks apply to judge
}

export interface Scores {
  overall: number | null
  value: number | null
  value_discount: number | null
  value_yield: number | null
  value_price: number | null
  value_dcf?: number | null
  quality: number | null
  growth: number | null
  safety: number | null
  coverage_pct: number
  trap: boolean
  piotroski: number | null
  altman: number | null
  dcf_discount: number | null
}

export interface Dataset {
  generated_at: string
  rows: Row[]
}
