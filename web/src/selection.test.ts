import { describe, expect, it } from 'vitest'
import { changeSince, entryDate, selectionView } from './selection'
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
    expect(entryDate('2026-08-20T23:59:00Z', now)).toBe('Aug 20')
    expect(entryDate('2025-12-31T11:00:00Z', now)).toBe('Dec 31, 2025')
  })
})

describe('selectionView', () => {
  const now = new Date('2026-09-26T12:00:00Z')
  it('is null for a stock never selected', () => {
    expect(selectionView({ Ticker: 'X', Price: 5, selection: null } as Row, now)).toBeNull()
    expect(selectionView({ Ticker: 'X', Price: 5 } as Row, now)).toBeNull()
  })
  it('shows only the first entry while it has never dropped out', () => {
    const v = selectionView(
      {
        Ticker: 'X',
        Price: 126,
        selection: { first: mark('2026-08-20T11:00:00Z', 100), latest: mark('2026-08-20T11:00:00Z', 100), selected: true },
      } as Row,
      now,
    )!
    expect(v.first).toEqual({ date: 'Aug 20', price: 100, change: expect.closeTo(26) })
    expect(v.reentry).toBeNull()
    expect(v.selected).toBe(true)
  })
  it('adds the re-entry when the latest entry differs from the first', () => {
    const v = selectionView(
      {
        Ticker: 'X',
        Price: 90,
        selection: { first: mark('2026-09-02T15:00:00Z', 120), latest: mark('2026-09-09T15:00:00Z', 100), selected: false },
      } as Row,
      now,
    )!
    expect(v.reentry).toEqual({ date: 'Sep 9', price: 100, change: expect.closeTo(-10) })
    expect(v.selected).toBe(false)
  })
})
