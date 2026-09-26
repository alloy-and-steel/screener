// Which cards are shown, and in what order. Pure; the card grid only renders.

import type { IndexName, Row } from './types'
import { azPegDisplay, combinedVerdict } from './score'

export interface Filter {
  minPass: number // 3 = all three screens, 0 = everything
  pool: IndexName | null // null = the whole merged universe
  query: string // ticker or sector substring
}

export function inPool(row: Row, pool: IndexName): boolean {
  return typeof row.Indexes === 'string' && row.Indexes.split(',').some((s) => s.trim() === pool)
}

export function filterRows(rows: Row[], f: Filter): Row[] {
  const q = f.query.trim().toUpperCase()
  return rows.filter((r) => {
    if (r.Error) return false
    if (f.pool && !inPool(r, f.pool)) return false
    if (q && !r.Ticker.toUpperCase().includes(q) && !(r.Sector ?? '').toUpperCase().includes(q)) return false
    return combinedVerdict(r).passCount >= f.minPass
  })
}

type Key = number | string | null

interface SortDef {
  label: string
  // Higher-is-better keys sort descending; missing (null) always sorts last.
  dir: 'asc' | 'desc'
  keys: (r: Row) => Key[]
}

const n = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null)

// A non-positive PEG means shrinking or negative earnings — worse than any
// positive PEG, but still a real value, so it ranks ahead of a missing one.
function pegKey(v: number | null): Key {
  return v === null ? null : v > 0 ? v : Number.MAX_VALUE
}

export const SORTS = {
  best: { label: 'Screens passed', dir: 'desc', keys: (r) => [combinedVerdict(r).passCount, n(r.azqato?.score)] },
  azqato: { label: 'Azqato score', dir: 'desc', keys: (r) => [n(r.azqato?.score)] },
  overall: { label: 'Overall score', dir: 'desc', keys: (r) => [n(r.OverallScore)] },
  graham: { label: 'Graham discount', dir: 'desc', keys: (r) => [n(r.Graham_Graham_Discount_Pct)] },
  lynch: { label: 'Lynch discount', dir: 'desc', keys: (r) => [n(r.Lynch_Lynch_Discount_Pct)] },
  peg: { label: 'Lowest PEG', dir: 'asc', keys: (r) => [pegKey(n(r.Lynch_PEG))] },
  pegFwd: { label: 'Lowest forward PEG', dir: 'asc', keys: (r) => [pegKey(r.azqato ? n(azPegDisplay(r.azqato)) : null)] },
  epsFwd: { label: 'Forward EPS growth', dir: 'desc', keys: (r) => [n(r.azqato?.epsFwd)] },
  yield: { label: 'Dividend yield', dir: 'desc', keys: (r) => [n(r.DivYield_Pct)] },
  cap: { label: 'Market cap', dir: 'desc', keys: (r) => [n(r.MarketCap_B)] },
  ticker: { label: 'Ticker A–Z', dir: 'asc', keys: (r) => [r.Ticker] },
} satisfies Record<string, SortDef>

export type SortKey = keyof typeof SORTS

function cmp(a: Key, b: Key, dir: 'asc' | 'desc'): number {
  if (a === b) return 0
  if (a === null) return 1
  if (b === null) return -1
  const c = a < b ? -1 : 1
  return dir === 'asc' ? c : -c
}

export function sortRows(rows: Row[], key: SortKey): Row[] {
  const def: SortDef = SORTS[key]
  const keyed = rows.map((r) => ({ r, k: def.keys(r) }))
  keyed.sort((x, y) => {
    for (let i = 0; i < x.k.length; i++) {
      const c = cmp(x.k[i], y.k[i], def.dir)
      if (c) return c
    }
    return 0
  })
  return keyed.map((x) => x.r)
}
