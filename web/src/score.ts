// Three INDEPENDENT scoring systems — Azqato, Lynch, Graham — each with its own
// suggestion + drivers. No blended/combined number (decoupled on purpose).
// `combinedVerdict` only counts how many of the three a name clears.

import type { Row } from './types'
import { num, pct, signalTone, type Tone } from './format'

// azqato is a binary screen — azqato.pass is decided in azqato.py (score >= 6).
const LYNCH_BUY = new Set(['Strong Buy', 'Buy'])
const GRAHAM_BUY = new Set(['Deep Buy', 'Buy'])

// Canonical "not valued / no data" marker. A not-valued name (declining or
// growth-unknown) is shown with this slate label — a distinct signal from a
// numeric dash, never a real grade. Matches the 'N/A' sentinel the backend
// writes into Lynch_Lynch_Status / Graham_Graham_Status.
export const NA_LABEL = 'N/A'

// Graded verdict -> 0..1 meter fill.
const GRADE_LEVEL: Record<string, number> = {
  'Strong Buy': 1,
  'Deep Buy': 1,
  Buy: 0.8,
  Hold: 0.5,
  Watch: 0.5,
  Avoid: 0.2,
}

export interface Driver {
  label: string
  value: string
  tone?: Tone // optional pass/fail dot
}

export interface Verdict {
  system: 'Azqato' | 'Lynch' | 'Graham'
  question: string // what this system answers, plain language
  label: string // the suggestion, e.g. "Buy" / "Pass" / "Avoid"
  tagline: string // one-line plain-english read
  tone: Tone
  kind: 'binary' | 'graded' // Azqato is a gate; Lynch/Graham live on a scale
  level: number // 0..1 fill for graded meter
  pass: boolean // counts toward "passes all 3"
  drivers: Driver[]
}

export function azqatoVerdict(row: Row): Verdict {
  const az = row.azqato
  if (!az) {
    return {
      system: 'Azqato',
      question: 'Growth + technical entry',
      label: NA_LABEL,
      tagline: 'No data',
      tone: 'slate',
      kind: 'binary',
      level: 0,
      pass: false,
      drivers: [],
    }
  }
  return {
    system: 'Azqato',
    question: 'Growth + technical entry',
    label: az.pass ? 'Pass' : 'Fail',
    tagline: az.pass ? 'Clears the growth + entry screen' : 'Does not clear the screen',
    tone: az.pass ? 'green' : 'red',
    kind: 'binary',
    level: az.pass ? 1 : 0,
    pass: az.pass,
    drivers: [
      { label: 'Bands met', value: `${az.score}/${az.coverage}` },
      { label: 'PEG (trailing)', value: num(az.peg), tone: bandTone(az.bands.peg_lt_1) },
      { label: 'EPS growth', value: pct(az.eps_growth_pct), tone: bandTone(az.bands.eps_growth_gt_15) },
      { label: 'Gross margin', value: pct(az.gross_margin_pct), tone: bandTone(az.bands.gross_gt_50) },
      { label: 'Net margin', value: pct(az.net_margin_pct), tone: bandTone(az.bands.net_gt_25) },
    ],
  }
}

function bandTone(b: boolean | null | undefined): Tone {
  if (b === null || b === undefined) return 'slate'
  return b ? 'green' : 'red'
}

export function lynchVerdict(row: Row): Verdict {
  const status = (row.Lynch_Lynch_Status as string | null | undefined) ?? null
  const tone = status ? signalTone('Lynch_Lynch_Status', status) : 'slate'
  return {
    system: 'Lynch',
    question: 'Growth at a reasonable price',
    label: status ?? NA_LABEL,
    tagline: lynchTagline(tone),
    tone,
    kind: 'graded',
    level: status ? (GRADE_LEVEL[status] ?? 0) : 0,
    pass: status ? LYNCH_BUY.has(status) : false,
    drivers: [
      { label: 'P/E', value: num(row.Lynch_PE) },
      { label: 'PEG', value: num(row.Lynch_PEG), tone: pegTone(row.Lynch_PEG) },
      { label: 'Buy price', value: num(row.Lynch_Lynch_BuyPrice) },
      { label: 'Discount', value: pct(row.Lynch_Lynch_Discount_Pct) },
    ],
  }
}

export function grahamVerdict(row: Row): Verdict {
  const status = (row.Graham_Graham_Status as string | null | undefined) ?? null
  const tone = status ? signalTone('Graham_Graham_Status', status) : 'slate'
  return {
    system: 'Graham',
    question: 'Intrinsic value + balance-sheet safety',
    label: status ?? NA_LABEL,
    tagline: grahamTagline(tone),
    tone,
    kind: 'graded',
    level: status ? (GRADE_LEVEL[status] ?? 0) : 0,
    pass: status ? GRAHAM_BUY.has(status) : false,
    drivers: [
      { label: 'Fair value', value: num(row.Graham_Graham_FV) },
      { label: 'Discount', value: pct(row.Graham_Graham_Discount_Pct) },
    ],
  }
}

function pegTone(v: unknown): Tone {
  if (typeof v !== 'number') return 'slate'
  return v < 1 ? 'green' : v <= 2 ? 'yellow' : 'red'
}

function lynchTagline(t: Tone): string {
  if (t === 'slate') return 'Not valued — needs positive growth'
  return t === 'green' ? 'Reasonably priced for its growth' : t === 'yellow' ? 'Fairly priced' : 'Expensive for its growth'
}

function grahamTagline(t: Tone): string {
  if (t === 'slate') return 'Not valued — needs positive growth'
  return t === 'green' ? 'Below intrinsic value, defensive' : t === 'yellow' ? 'Near fair value' : 'Above intrinsic value'
}

export interface VerdictLine {
  name: string
  label: string
  tone: Tone
  kind: 'binary' | 'graded'
  level: number
}

function gradeLine(name: string, field: string, status: string | null | undefined): VerdictLine {
  return {
    name,
    label: status ?? NA_LABEL,
    tone: status ? signalTone(field, status) : 'slate',
    kind: 'graded',
    level: status ? (GRADE_LEVEL[status] ?? 0) : 0,
  }
}

// The verdict(s) a system produces. Azqato is a single binary gate; Lynch and
// Graham each have TWO facets (Lynch: two valuation methods; Graham: valuation
// + defensive safety).
export function verdictLines(system: 'Azqato' | 'Lynch' | 'Graham', row: Row): VerdictLine[] {
  if (system === 'Azqato') {
    const az = row.azqato
    return [
      {
        name: 'Screen',
        label: !az ? NA_LABEL : az.pass ? 'Pass' : 'Fail',
        tone: !az ? 'slate' : az.pass ? 'green' : 'red',
        kind: 'binary',
        level: !az ? 0 : az.pass ? 1 : 0,
      },
    ]
  }
  if (system === 'Lynch') {
    return [
      gradeLine('Value (G+D)', 'Lynch_Lynch_Status', row.Lynch_Lynch_Status as string | null | undefined),
      gradeLine('PEG price band', 'Lynch_Lynch_PEG_Band', row.Lynch_Lynch_PEG_Band as string | null | undefined),
    ]
  }
  const def = row.DefensiveScore
  return [
    gradeLine('Valuation', 'Graham_Graham_Status', row.Graham_Graham_Status as string | null | undefined),
    {
      name: 'Defensive',
      label: (row.DefensiveLabel as string) ?? NA_LABEL,
      tone: row.DefensiveLabel ? signalTone('DefensiveLabel', row.DefensiveLabel as string) : 'slate',
      kind: 'graded',
      level: typeof def === 'number' ? def / 8 : 0,
    },
  ]
}

export function verdicts(row: Row): Verdict[] {
  return [azqatoVerdict(row), lynchVerdict(row), grahamVerdict(row)]
}

export interface Combined {
  passCount: number
  tone: Tone
  label: string
}

// How many of the three independent systems a name clears.
export function combinedVerdict(row: Row): Combined {
  const vs = verdicts(row)
  const passCount = vs.filter((v) => v.pass).length
  const tone: Tone = passCount === 3 ? 'green' : passCount >= 1 ? 'yellow' : 'red'
  const label = passCount === 3 ? 'Aligned' : passCount === 0 ? 'None' : 'Split'
  return { passCount, tone, label }
}

// Default screener list: a name must clear ALL THREE independent systems.
export function passesAll(row: Row): boolean {
  if (row.Error) return false
  return azqatoVerdict(row).pass && lynchVerdict(row).pass && grahamVerdict(row).pass
}
