// Shapes the SA-style quant block (saquant.py) and the Alpha Picks emulator
// (alphapicks.py) for the Scorecard. Both are informational: score.ts's pass
// gate never reads them.

import type { Tone } from './format'
import { changeSince } from './selection'
import type { AlphaPicksSummary, Row, SaFactor } from './types'
import { SA_FACTORS } from './types'

// A+ .. B- green, C+ .. C- yellow, D+ and below red.
export function gradeTone(grade: string | null | undefined): Tone {
  if (!grade) return 'slate'
  if (grade.startsWith('A') || grade.startsWith('B')) return 'green'
  if (grade.startsWith('C')) return 'yellow'
  return 'red'
}

export function ratingTone(rating: string | null | undefined): Tone {
  if (rating === 'Strong Buy' || rating === 'Buy') return 'green'
  if (rating === 'Hold') return 'yellow'
  if (rating === 'Sell' || rating === 'Strong Sell') return 'red'
  return 'slate'
}

export function factorGrades(row: Row): { factor: SaFactor; grade: string | null }[] {
  const g = row.saQuant?.grades
  return SA_FACTORS.map((factor) => ({ factor, grade: g?.[factor] ?? null }))
}

// This stock in the emulator: held (with its move since entry), or not.
export function heldView(row: Row): { at: string; price: number; change: number | null } | null {
  const p = row.alphaPicks?.position
  return p ? { at: p.at, price: p.price, change: changeSince(p.price, row.Price) } : null
}

export type EmulatorStatus =
  | { kind: 'absent' }
  | { kind: 'waiting'; firstEligibleOn: string | null; streaks: number; startedAt: string | null }
  | { kind: 'running'; picks: number; open: number; returnPct: number | null; spyReturnPct: number | null; startedAt: string | null }

export function emulatorStatus(s: AlphaPicksSummary | undefined): EmulatorStatus {
  if (!s) return { kind: 'absent' }
  if (s.picks === 0) return { kind: 'waiting', firstEligibleOn: s.firstEligibleOn, streaks: s.strongBuyStreaks, startedAt: s.startedAt }
  return { kind: 'running', picks: s.picks, open: s.open, returnPct: s.returnPct, spyReturnPct: s.spyReturnPct, startedAt: s.startedAt }
}
