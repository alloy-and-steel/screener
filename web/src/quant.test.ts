import { describe, expect, it } from 'vitest'
import { emulatorStatus, factorGrades, gradeTone, heldView, ratingTone } from './quant'
import type { AlphaPicksSummary, Row } from './types'

const summary = (over: Partial<AlphaPicksSummary> = {}): AlphaPicksSummary => ({
  startedAt: '2026-11-09T11:30:00Z',
  picks: 0,
  open: 0,
  closed: 0,
  invested: 0,
  value: null,
  returnPct: null,
  spyReturnPct: null,
  strongBuyStreaks: 0,
  firstEligibleOn: null,
  holdings: [],
  ...over,
})

describe('gradeTone / ratingTone', () => {
  it('reads A and B as green, C as yellow, D and F as red, missing as slate', () => {
    expect(['A+', 'B-', 'C+', 'C-', 'D+', 'F', null].map(gradeTone)).toEqual(['green', 'green', 'yellow', 'yellow', 'red', 'red', 'slate'])
  })
  it('reads buys green, Hold yellow, sells red, unrated slate', () => {
    expect(['Strong Buy', 'Buy', 'Hold', 'Sell', 'Strong Sell', null].map(ratingTone)).toEqual(['green', 'green', 'yellow', 'red', 'red', 'slate'])
  })
})

describe('factorGrades', () => {
  it('lists all five factors in order, null where a grade is missing or the block is absent', () => {
    const row: Row = { Ticker: 'X', saQuant: { rating: 'Hold', score: 50, capped: false, grades: { value: 'A', growth: null, profitability: 'C', momentum: 'B+', revisions: 'F' }, pctiles: {} } }
    expect(factorGrades(row)).toEqual([
      { factor: 'value', grade: 'A' },
      { factor: 'growth', grade: null },
      { factor: 'profitability', grade: 'C' },
      { factor: 'momentum', grade: 'B+' },
      { factor: 'revisions', grade: 'F' },
    ])
    expect(factorGrades({ Ticker: 'Y' }).every((g) => g.grade === null)).toBe(true)
  })
})

describe('heldView', () => {
  it('is the entry and the move since, or null when the emulator does not hold the stock', () => {
    expect(heldView({ Ticker: 'X', Price: 60, alphaPicks: { streak: null, position: { at: '2027-03-01', price: 40, slot: '2027-03-a' } } })).toEqual({ at: '2027-03-01', price: 40, change: 50 })
    expect(heldView({ Ticker: 'X', Price: 60, alphaPicks: { streak: null, position: null } })).toBeNull()
    expect(heldView({ Ticker: 'X', Price: 60 })).toBeNull()
  })
})

describe('emulatorStatus', () => {
  it('is absent on datasets published before the emulator', () => {
    expect(emulatorStatus(undefined)).toEqual({ kind: 'absent' })
  })
  it('waits, with the first possible pick date, until the first pick', () => {
    expect(emulatorStatus(summary({ strongBuyStreaks: 180, firstEligibleOn: '2027-02-22' }))).toEqual({ kind: 'waiting', firstEligibleOn: '2027-02-22', streaks: 180, startedAt: '2026-11-09T11:30:00Z' })
  })
  it('reports returns against SPY once it has picks', () => {
    expect(emulatorStatus(summary({ picks: 3, open: 2, returnPct: 12.5, spyReturnPct: 4 }))).toEqual({ kind: 'running', picks: 3, open: 2, returnPct: 12.5, spyReturnPct: 4, startedAt: '2026-11-09T11:30:00Z' })
  })
})
