// Shapes mirror stock_screener.py's output row. Lynch/Graham metric keys are
// DOUBLE-prefixed (e.g. Lynch_Lynch_Status, Graham_Graham_Discount_Pct) because
// process_ticker re-prefixes dicts whose keys already carry the prefix. The
// `azqato` block is the nested no-AI relative score (azqato.py / azqato_score_all).

// Rank tiers of the azqato relative percentile model: S = top 10% of scored
// names, A = next 10%, B = 20-50%, C = 50-75%, F = bottom 25%; 'sp' (S+) = a
// perfect 100. Ranks, not buy/sell ratings.
export type AzqatoTier = 'sp' | 's' | 'a' | 'b' | 'c' | 'f'

// The seven ranked metrics; peVsG (forward P/E vs growth) is a weight-0
// context ratio — ranked for cell coloring only, never scored.
export type AzqatoMetricKey = 'revTTM' | 'revFwd' | 'epsTTM' | 'epsFwd' | 'peVsG' | 'pegFwd' | 'cashDebt'

export interface Azqato {
  score: number | null // 0-100; null when no metric was evaluable
  tier: AzqatoTier | null
  passes: number // metrics in the upper part of the pack (points >= 15)
  total: number // fixed 6 — a missing metric is a miss, not a pass
  parts: Partial<Record<AzqatoMetricKey, number>> // points 0-20; missing key = hard zero
  pctiles: Partial<Record<AzqatoMetricKey, number>> // raw percentile 0..1
  revTTM: number | null
  revFwd: number | null
  epsTTM: number | null
  epsFwd: number | null
  peFwd: number | null
  pegFwd: number | null
  cash: number | null
  debt: number | null
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

  DefensiveScore?: number | null
  DefensiveLabel?: string | null
  CombinedScore?: number | null

  Show?: boolean
  Error?: string | null
  Indexes_?: never
  azqato?: Azqato

  // ── OverallScore (ported v2.0 methodology) — informational 4-pillar
  // composite. Does NOT participate in the Azqato/Lynch/Graham pass gate
  // (score.ts's verdicts()/combinedVerdict()/passesAll() are unchanged).
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

  // Tolerate the full set of emitted columns without enumerating every one.
  [key: string]: unknown
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
