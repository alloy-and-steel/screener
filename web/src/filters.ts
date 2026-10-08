// Which cards are shown, and in what order. Pure; the card grid only renders.

import { INDEX_NAMES, type IndexName, type Row } from './types'
import { azPegDisplay, combinedVerdict } from './score'
import { sectorMatches } from './dataText'

export interface Filter {
  minPass: number // screens passed at least (4 = all four), 0 = everything
  pool: IndexName | null // null = the whole merged universe
  query: string // ticker or sector substring (English or Chinese sector name)
}

export function inPool(row: Row, pool: IndexName): boolean {
  return typeof row.Indexes === 'string' && row.Indexes.split(',').some((s) => s.trim() === pool)
}

// The pools a stock belongs to, for display. Nearly every name is in Total US,
// so it is named only when it is the one pool that brought the stock in.
export function poolNames(row: Row): IndexName[] {
  const pools = INDEX_NAMES.filter((n) => inPool(row, n))
  const curated = pools.filter((n) => n !== 'TotalUS')
  return curated.length ? curated : pools
}

export function filterRows(rows: Row[], f: Filter): Row[] {
  const q = f.query.trim().toUpperCase()
  return rows.filter((r) => {
    if (r.Error) return false
    if (f.pool && !inPool(r, f.pool)) return false
    if (q && !r.Ticker.toUpperCase().includes(q) && !sectorMatches(r.Sector ?? '', q)) return false
    return combinedVerdict(r).passCount >= f.minPass
  })
}

type Key = number | string | null

interface SortDef {
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
  best: { dir: 'desc', keys: (r) => [combinedVerdict(r).passCount, n(r.azqato?.score)] },
  azqato: { dir: 'desc', keys: (r) => [n(r.azqato?.score)] },
  overall: { dir: 'desc', keys: (r) => [n(r.OverallScore)] },
  graham: { dir: 'desc', keys: (r) => [n(r.Graham_Graham_Discount_Pct)] },
  lynch: { dir: 'desc', keys: (r) => [n(r.Lynch_Lynch_Discount_Pct)] },
  peg: { dir: 'asc', keys: (r) => [pegKey(n(r.Lynch_PEG))] },
  pegFwd: { dir: 'asc', keys: (r) => [pegKey(r.azqato ? n(azPegDisplay(r.azqato)) : null)] },
  epsFwd: { dir: 'desc', keys: (r) => [n(r.azqato?.epsFwd)] },
  yield: { dir: 'desc', keys: (r) => [n(r.DivYield_Pct)] },
  cap: { dir: 'desc', keys: (r) => [n(r.MarketCap_B)] },
  ticker: { dir: 'asc', keys: (r) => [r.Ticker] },
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
