import { describe, expect, it } from 'vitest'
import { filterRows, sortRows } from './filters'
import type { Row } from './types'

// Minimal rows: only the fields the filters/sorts read.
function row(t: string, extra: Partial<Row> = {}): Row {
  return { Ticker: t, ...extra } as Row
}

const az = (score: number | null, tier: 'sp' | 's' | 'a' | 'b' | 'c' | 'f' | null) =>
  ({ score, tier, passes: 0, total: 6, parts: {}, pctiles: {} }) as unknown as Row['azqato']

// Passes all three: tier A + Lynch Buy + Graham Buy.
const ALL3 = { azqato: az(80, 'a'), Lynch_Lynch_Status: 'Buy', Graham_Graham_Status: 'Buy' }

describe('sortRows', () => {
  it('puts missing values last in BOTH directions — a dash is never ranked as zero', () => {
    const rows = [row('A', { OverallScore: 10 }), row('B', { OverallScore: null }), row('C', { OverallScore: 90 })]
    expect(sortRows(rows, 'overall').map((r) => r.Ticker)).toEqual(['C', 'A', 'B'])
    expect(sortRows(rows, 'peg').map((r) => r.Ticker)).toEqual(['A', 'B', 'C']) // no PEG anywhere: stable
  })

  it('ranks a non-positive PEG (shrinking earnings) after every positive one, ahead of missing', () => {
    const rows = [row('NEG', { Lynch_PEG: -0.5 }), row('NONE'), row('HI', { Lynch_PEG: 2.1 }), row('LO', { Lynch_PEG: 0.4 })]
    expect(sortRows(rows, 'peg').map((r) => r.Ticker)).toEqual(['LO', 'HI', 'NEG', 'NONE'])
  })

  it('defaults to screens passed, then Azqato score', () => {
    const rows = [
      row('ONE', { azqato: az(95, 's') }),
      row('ALL_LO', { ...ALL3, azqato: az(81, 'a') }),
      row('ALL_HI', { ...ALL3, azqato: az(99, 's') }),
    ]
    expect(sortRows(rows, 'best').map((r) => r.Ticker)).toEqual(['ALL_HI', 'ALL_LO', 'ONE'])
  })

  it('does not mutate its input', () => {
    const rows = [row('B'), row('A')]
    sortRows(rows, 'ticker')
    expect(rows.map((r) => r.Ticker)).toEqual(['B', 'A'])
  })
})

describe('filterRows', () => {
  const rows = [
    row('AAPL', { ...ALL3, Indexes: 'S&P500, Dow30, Nasdaq100', Sector: 'Technology' }),
    row('KO', { Indexes: 'S&P500, Dow30, Dividend100', Sector: 'Consumer Defensive' }),
    row('BAD', { Error: 'No price' }),
  ]

  it('drops error rows and applies the pass floor', () => {
    expect(filterRows(rows, { minPass: 0, pool: null, query: '' }).map((r) => r.Ticker)).toEqual(['AAPL', 'KO'])
    expect(filterRows(rows, { minPass: 3, pool: null, query: '' }).map((r) => r.Ticker)).toEqual(['AAPL'])
  })

  it('matches pools by exact membership token, not substring', () => {
    expect(filterRows(rows, { minPass: 0, pool: 'Dividend100', query: '' }).map((r) => r.Ticker)).toEqual(['KO'])
    expect(filterRows(rows, { minPass: 0, pool: 'Dow30', query: '' }).map((r) => r.Ticker)).toEqual(['AAPL', 'KO'])
  })

  it('searches ticker and sector, case-insensitively', () => {
    expect(filterRows(rows, { minPass: 0, pool: null, query: 'aap' }).map((r) => r.Ticker)).toEqual(['AAPL'])
    expect(filterRows(rows, { minPass: 0, pool: null, query: 'defens' }).map((r) => r.Ticker)).toEqual(['KO'])
  })
})
