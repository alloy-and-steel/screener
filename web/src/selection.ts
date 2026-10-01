// When the screener first picked a stock at each pass level (exactly 1, 2 or
// all 3 screens) and what it cost then. The history itself is kept by
// selections.py on the data branch and arrives on each row as `picks`; this
// only shapes it for display.

import type { PickLevel, Row } from './types'

export interface PickView {
  level: PickLevel
  date: string
  price: number | null
  change: number | null // percent move from `price` to today's price
}

export function changeSince(entry: number | null | undefined, now: number | null | undefined): number | null {
  if (typeof entry !== 'number' || typeof now !== 'number' || !(entry > 0) || !Number.isFinite(now)) return null
  return ((now - entry) / entry) * 100
}

// Runs are stamped in UTC; the UTC day is the screen's own calendar.
export function entryDate(at: string, now: Date): string {
  const d = new Date(at)
  const sameYear = d.getUTCFullYear() === now.getUTCFullYear()
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', ...(sameYear ? {} : { year: 'numeric' }), timeZone: 'UTC' })
}

const LEVELS: PickLevel[] = [3, 2, 1]

// The picks at or above `minPass` (the visitor's pass floor; 0 = any), highest
// level first. Below the floor is left out: those are levels the visitor has
// filtered away.
export function pickViews(row: Row, minPass: number, now: Date): PickView[] {
  const picks = row.picks
  if (!picks) return []
  return LEVELS.filter((l) => l >= minPass).flatMap((level) => {
    const m = picks[level]
    return m ? [{ level, date: entryDate(m.at, now), price: m.price, change: changeSince(m.price, row.Price) }] : []
  })
}
