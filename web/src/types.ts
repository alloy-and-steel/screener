// Shapes mirror stock_screener.py's output row. Lynch/Graham metric keys are
// DOUBLE-prefixed (e.g. Lynch_Lynch_Status, Graham_Graham_Discount_Pct) because
// process_ticker re-prefixes dicts whose keys already carry the prefix. The
// `azqato` block is the nested no-AI profile (azqato.py / azqato_profile).

export interface AzqatoBands {
  peg_lt_1: boolean | null
  revenue_growth_gt_15: boolean | null
  eps_growth_gt_15: boolean | null
  pe_lt_growth: boolean | null
  cash_gt_debt: boolean | null
  gross_gt_50: boolean | null
  net_gt_25: boolean | null
  rsi_30_45: boolean | null
  pos_52w_lower_25: boolean | null
}

export interface Azqato {
  pass: boolean
  score: number
  coverage: number
  basis: string
  bands: AzqatoBands
  peg: number | null
  revenue_growth_pct: number | null
  eps_growth_pct: number | null
  pe: number | null
  gross_margin_pct: number | null
  net_margin_pct: number | null
  rsi: number | null
  pos_52w_pct: number | null
  total_cash: number | null
  total_debt: number | null
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
