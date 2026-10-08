import { describe, expect, it } from 'vitest'
import { changeSince, entryDate, pickViews } from './selection'
import type { Row } from './types'

const mark = (at: string, price: number | null) => ({ at, price })

describe('changeSince', () => {
  it('is the percent move from the entry price to today', () => {
    expect(changeSince(100, 126)).toBeCloseTo(26)
    expect(changeSince(200, 150)).toBeCloseTo(-25)
  })
  it('is null — never 0 — when either price is missing or the entry is not positive', () => {
    expect(changeSince(null, 10)).toBeNull()
    expect(changeSince(10, null)).toBeNull()
    expect(changeSince(0, 10)).toBeNull()
  })
})

describe('entryDate', () => {
  it('uses the UTC calendar day of the run, adding the year only when it differs', () => {
    const now = new Date('2026-09-26T12:00:00Z')
    expect(entryDate('2026-08-20T23:59:00Z', now, 'en')).toBe('Aug 20')
    expect(entryDate('2025-12-31T11:00:00Z', now, 'en')).toBe('Dec 31, 2025')
  })
  it('writes the date the Chinese way in Chinese', () => {
    const now = new Date('2026-09-26T12:00:00Z')
    expect(entryDate('2026-08-20T23:59:00Z', now, 'zh-TW')).toBe('8月20日')
    expect(entryDate('2025-12-31T11:00:00Z', now, 'zh-TW')).toBe('2025年12月31日')
  })
})

describe('pickViews', () => {
  const now = new Date('2026-09-26T12:00:00Z')
  const row = { Ticker: 'X', Price: 90, picks4: { '1': mark('2026-08-20T11:00:00Z', 100), '4': mark('2026-09-02T15:00:00Z', 120) } } as Row

  it('is empty for a stock never picked', () => {
    expect(pickViews({ Ticker: 'X', Price: 5, picks4: null } as Row, 0, now, 'en')).toEqual([])
    expect(pickViews({ Ticker: 'X', Price: 5 } as Row, 0, now, 'en')).toEqual([])
    // The three-screen ledger's field is not read: its levels mean something else.
    expect(pickViews({ Ticker: 'X', Price: 5, picks: { '3': mark('2026-09-02T15:00:00Z', 1) } } as Row, 0, now, 'en')).toEqual([])
  })
  it('lists every level reached, highest first, when the floor is "any"', () => {
    expect(pickViews(row, 0, now, 'en')).toEqual([
      { level: 4, date: 'Sep 2', price: 120, change: expect.closeTo(-25) },
      { level: 1, date: 'Aug 20', price: 100, change: expect.closeTo(-10) },
    ])
  })
  it('drops the levels below the pass floor the visitor filtered on', () => {
    expect(pickViews(row, 2, now, 'en').map((p) => p.level)).toEqual([4])
    expect(pickViews(row, 1, now, 'en').map((p) => p.level)).toEqual([4, 1])
    expect(pickViews({ ...row, picks4: { '1': mark('2026-08-20T11:00:00Z', 100) } } as Row, 2, now, 'en')).toEqual([])
  })
})
