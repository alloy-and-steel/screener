// Three INDEPENDENT scoring systems — Azqato, Lynch, Graham — each with its own
// suggestion + drivers. No blended/combined number (decoupled on purpose).
// `combinedVerdict` only counts how many of the three a name clears.

import type { Azqato, AzqatoTier, Row } from './types'
import { num, pct, ptsTone, ratio, signalTone, type Tone } from './format'

const LYNCH_BUY = new Set(['Strong Buy', 'Buy'])
const GRAHAM_BUY = new Set(['Deep Buy', 'Buy'])

// Azqato tiers are ranks (see types.ts). "Pass" for the three-system gate =
// tier A or better — the top ~20% of the scored universe.
export const TIER_LABEL: Record<AzqatoTier, string> = { sp: 'S+', s: 'S', a: 'A', b: 'B', c: 'C', f: 'F' }
export const TIER_TONE: Record<AzqatoTier, Tone> = { sp: 'green', s: 'green', a: 'green', b: 'yellow', c: 'yellow', f: 'red' }
const AZQATO_PASS_TIERS = new Set<AzqatoTier>(['sp', 's', 'a'])

// azqato's own tier palette (style.css --color-tier-*): S dark green, A light
// green, B yellow, C light red, F dark red; S+ purple, apart from the green
// ramp. Overrides the 4-tone chip colors wherever a tier is rendered.
export interface TierColors {
  text: string
  bg: string
  ring: string
  fill: string
}
export const TIER_STYLE: Record<AzqatoTier, TierColors> = {
  sp: { text: 'text-[#bc8cff]', bg: 'bg-[#bc8cff]/15', ring: 'ring-[#bc8cff]/30', fill: 'bg-[#bc8cff]' },
  s: { text: 'text-[#2ea043]', bg: 'bg-[#2ea043]/15', ring: 'ring-[#2ea043]/30', fill: 'bg-[#2ea043]' },
  a: { text: 'text-[#7ee787]', bg: 'bg-[#7ee787]/15', ring: 'ring-[#7ee787]/30', fill: 'bg-[#7ee787]' },
  b: { text: 'text-[#e3b341]', bg: 'bg-[#e3b341]/15', ring: 'ring-[#e3b341]/30', fill: 'bg-[#e3b341]' },
  c: { text: 'text-[#ffa198]', bg: 'bg-[#ffa198]/15', ring: 'ring-[#ffa198]/30', fill: 'bg-[#ffa198]' },
  f: { text: 'text-[#f85149]', bg: 'bg-[#f85149]/15', ring: 'ring-[#f85149]/30', fill: 'bg-[#f85149]' },
}

const TIER_TAGLINE: Record<AzqatoTier, string> = {
  sp: 'Perfect score — tops every scored metric',
  s: 'Top 10% of the screened universe',
  a: 'Top 20% of the screened universe',
  b: 'Upper half of the screened universe',
  c: 'Below the median',
  f: 'Bottom quarter of the screened universe',
}

// For unprofitable companies (negative forward P/E) Yahoo's positive PEG is
// misleading, so display our own forward PEG = P/E / EPS growth (negative).
export function azPegDisplay(az: Azqato): number | null {
  if (az.peFwd !== null && az.peFwd <= 0 && az.epsFwd !== null && az.epsFwd > 0) return az.peFwd / az.epsFwd
  return az.pegFwd
}

// Cash/debt ratio; Infinity when there is no debt (rendered as "∞").
export function azCashDebt(az: Azqato): number | null {
  if (az.cash === null || az.debt === null) return null
  if (az.debt > 0) return az.cash / az.debt
  return az.cash > 0 ? Infinity : null
}

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
  label: string // the suggestion, e.g. "Buy" / "S+" / "Avoid"
  tagline: string // one-line plain-english read
  tone: Tone
  pillColors?: TierColors // azqato tier palette; Lynch/Graham use the tone
  level: number // 0..1 fill for graded meter
  pass: boolean // counts toward "passes all 3"
  drivers: Driver[]
}

export function azqatoVerdict(row: Row): Verdict {
  const az = row.azqato
  // `== null` also catches a stale published dataset (pre-tier shape, no
  // score/tier keys) — it renders N/A until the next Screen run, never crashes.
  if (!az || az.score == null || az.tier == null) {
    return {
      system: 'Azqato',
      question: 'Growth rank vs the field',
      label: NA_LABEL,
      tagline: 'No data',
      tone: 'slate',
      level: 0,
      pass: false,
      drivers: [],
    }
  }
  return {
    system: 'Azqato',
    question: 'Growth rank vs the field',
    label: TIER_LABEL[az.tier],
    tagline: TIER_TAGLINE[az.tier],
    tone: TIER_TONE[az.tier],
    pillColors: TIER_STYLE[az.tier],
    level: az.score / 100,
    pass: AZQATO_PASS_TIERS.has(az.tier),
    drivers: [
      { label: 'Score', value: `${az.score}/100` },
      { label: 'Strong metrics', value: `${az.passes}/${az.total}` },
      { label: 'Revenue growth TTM', value: pct(az.revTTM), tone: ptsTone(az.parts.revTTM) },
      { label: 'Revenue growth FWD', value: pct(az.revFwd), tone: ptsTone(az.parts.revFwd) },
      { label: 'EPS growth TTM', value: pct(az.epsTTM), tone: ptsTone(az.parts.epsTTM) },
      { label: 'EPS growth FWD', value: pct(az.epsFwd), tone: ptsTone(az.parts.epsFwd) },
      { label: 'PEG FWD', value: num(azPegDisplay(az)), tone: ptsTone(az.parts.pegFwd) },
      { label: 'Cash vs debt', value: ratio(azCashDebt(az)), tone: ptsTone(az.parts.cashDebt) },
    ],
  }
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
  colors?: TierColors // azqato tier palette; graded lines use the tone
  level: number
}

function gradeLine(name: string, field: string, status: string | null | undefined): VerdictLine {
  return {
    name,
    label: status ?? NA_LABEL,
    tone: status ? signalTone(field, status) : 'slate',
    level: status ? (GRADE_LEVEL[status] ?? 0) : 0,
  }
}

// The verdict(s) a system produces. Azqato is a single rank tier; Lynch and
// Graham each have TWO facets (Lynch: two valuation methods; Graham: valuation
// + defensive safety).
export function verdictLines(system: 'Azqato' | 'Lynch' | 'Graham', row: Row): VerdictLine[] {
  if (system === 'Azqato') {
    const az = row.azqato
    const scored = az != null && az.score != null && az.tier != null
    return [
      {
        name: 'Tier',
        label: scored ? TIER_LABEL[az.tier!] : NA_LABEL,
        tone: scored ? TIER_TONE[az.tier!] : 'slate',
        colors: scored ? TIER_STYLE[az.tier!] : undefined,
        level: scored ? az.score! / 100 : 0,
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
