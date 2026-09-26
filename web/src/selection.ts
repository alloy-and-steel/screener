// When the screener picked a stock (passed 2+ screens) and what it cost then.
// The history itself is kept by selections.py on the data branch and arrives
// on each row as `selection`; this only shapes it for display.

import type { Row } from './types'

export interface EntryView {
  date: string
  price: number | null
  change: number | null // percent move from `price` to today's price
}

export interface SelectionView {
  first: EntryView
  reentry: EntryView | null // the latest entry, when it came after a drop-out
  selected: boolean // selected on the latest run
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

export function selectionView(row: Row, now: Date): SelectionView | null {
  const s = row.selection
  if (!s) return null
  const view = (m: { at: string; price: number | null }): EntryView => ({
    date: entryDate(m.at, now),
    price: m.price,
    change: changeSince(m.price, row.Price),
  })
  return { first: view(s.first), reentry: s.latest.at !== s.first.at ? view(s.latest) : null, selected: s.selected }
}
