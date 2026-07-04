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

  // Tolerate the full set of emitted columns without enumerating every one.
  [key: string]: unknown
}

export interface Dataset {
  generated_at: string
  rows: Row[]
}
