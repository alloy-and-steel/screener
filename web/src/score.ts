// Four INDEPENDENT scoring systems — Azqato, Lynch, Graham, Wealthmatica — each
// with its own suggestion + drivers. No blended/combined number (decoupled on
// purpose). `combinedVerdict` only counts how many of the four a name clears.

import type { Azqato, AzqatoTier, Row, WealthmaticaCheckKey } from './types'
import { WEALTHMATICA_CHECKS } from './types'
import { DASH, boolTone, num, pct, ptsTone, ratio, signalTone, signedPct, type Tone } from './format'
import { statusLabel, type Messages } from './messages'

const LYNCH_BUY = new Set(['Strong Buy', 'Buy'])
const GRAHAM_BUY = new Set(['Deep Buy', 'Buy'])

// Azqato tiers are ranks (see types.ts). "Pass" for the four-system gate =
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

// Net cash (cash minus debt) as a percent of market cap. Positive = net cash,
// negative = net debt. Context only — ranked for cell color, never scored.
export function azNetCashMc(az: Azqato): number | null {
  if (az.cash === null || az.debt === null || az.marketCap === null || az.marketCap <= 0) return null
  return ((az.cash - az.debt) / az.marketCap) * 100
}

// Canonical "not valued / no data" marker. A not-valued name (declining or
// growth-unknown) is shown with this slate label — a distinct signal from a
// numeric dash, never a real grade. Matches the 'N/A' sentinel the backend
// writes into Lynch_Lynch_Status / Graham_Graham_Status.
export const NA_LABEL = 'N/A'

export interface Driver {
  label: string
  value: string
  tone?: Tone // optional pass/fail dot
}

export type SystemName = 'Azqato' | 'Lynch' | 'Graham' | 'Wealthmatica'

export interface Verdict {
  system: SystemName
  question: string // what this system answers, plain language
  label: string // the suggestion, e.g. "Buy" / "S+" / "Avoid"
  tagline: string // one-line plain-english read
  tone: Tone
  pillColors?: TierColors // azqato tier palette; Lynch/Graham use the tone
  pass: boolean // counts toward "passes all 4"
  drivers: Driver[]
}

// The four pass gates, apart from the labels: counting passes for ~2,000
// rows needs no language.
function azqatoPass(row: Row): boolean {
  const tier = row.azqato?.score != null ? row.azqato.tier : null
  return tier != null && AZQATO_PASS_TIERS.has(tier)
}
function lynchPass(row: Row): boolean {
  return LYNCH_BUY.has(row.Lynch_Lynch_Status as string)
}
function grahamPass(row: Row): boolean {
  return GRAHAM_BUY.has(row.Graham_Graham_Status as string)
}
function wealthmaticaPass(row: Row): boolean {
  const wm = row.wealthmatica
  return !!wm && wm.pass === true
}
const PASSES = [azqatoPass, lynchPass, grahamPass, wealthmaticaPass]

export function azqatoVerdict(row: Row, m: Messages): Verdict {
  const az = row.azqato
  const base = { system: 'Azqato', question: m.question.Azqato } as const
  // `== null` also catches a stale published dataset (pre-tier shape, no
  // score/tier keys) — it renders N/A until the next Screen run, never crashes.
  if (!az || az.score == null || az.tier == null) {
    return { ...base, label: statusLabel(m, NA_LABEL), tagline: m.noData, tone: 'slate', pass: false, drivers: [] }
  }
  return {
    ...base,
    label: TIER_LABEL[az.tier],
    tagline: m.tierTagline[az.tier],
    tone: TIER_TONE[az.tier],
    pillColors: TIER_STYLE[az.tier],
    pass: azqatoPass(row),
    drivers: [
      { label: m.az.score, value: `${az.score}/100` },
      { label: m.az.strong, value: `${az.passes}/${az.total}` },
      { label: m.az.revTTM, value: pct(az.revTTM), tone: ptsTone(az.parts.revTTM) },
      { label: m.az.revFwd, value: pct(az.revFwd), tone: ptsTone(az.parts.revFwd) },
      { label: m.az.epsTTM, value: pct(az.epsTTM), tone: ptsTone(az.parts.epsTTM) },
      { label: m.az.epsFwd, value: pct(az.epsFwd), tone: ptsTone(az.parts.epsFwd) },
      { label: m.az.pegFwd, value: num(azPegDisplay(az)), tone: ptsTone(az.parts.pegFwd) },
      { label: m.az.cashDebt, value: ratio(azCashDebt(az)), tone: ptsTone(az.parts.cashDebt) },
    ],
  }
}

export function lynchVerdict(row: Row, m: Messages): Verdict {
  const status = (row.Lynch_Lynch_Status as string | null | undefined) ?? null
  const tone = status ? signalTone('Lynch_Lynch_Status', status) : 'slate'
  return {
    system: 'Lynch',
    question: m.question.Lynch,
    label: statusLabel(m, status ?? NA_LABEL),
    tagline: tone === 'slate' ? m.notValued : m.lynchTagline[tone],
    tone,
    pass: lynchPass(row),
    drivers: [
      { label: m.lynch.pe, value: num(row.Lynch_PE) },
      { label: m.lynch.peg, value: num(row.Lynch_PEG), tone: pegTone(row.Lynch_PEG) },
      { label: m.lynch.buyPrice, value: num(row.Lynch_Lynch_BuyPrice) },
      { label: m.lynch.discount, value: pct(row.Lynch_Lynch_Discount_Pct) },
    ],
  }
}

export function grahamVerdict(row: Row, m: Messages): Verdict {
  const status = (row.Graham_Graham_Status as string | null | undefined) ?? null
  const tone = status ? signalTone('Graham_Graham_Status', status) : 'slate'
  return {
    system: 'Graham',
    question: m.question.Graham,
    label: statusLabel(m, status ?? NA_LABEL),
    tagline: tone === 'slate' ? m.notValued : m.grahamTagline[tone],
    tone,
    pass: grahamPass(row),
    drivers: [
      { label: m.graham.fairValue, value: num(row.Graham_Graham_FV) },
      { label: m.graham.discount, value: pct(row.Graham_Graham_Discount_Pct) },
    ],
  }
}

function wealthmaticaFormat(k: WealthmaticaCheckKey, v: number | null, m: Messages): string {
  if (v === null) return DASH
  switch (k) {
    case 'revGrowth':
      return signedPct(v, 1)
    case 'revAccel':
    case 'grossMargin':
    case 'opMargin':
      return m.pts(`${v > 0 ? '+' : ''}${v.toFixed(1)}`)
    case 'fcf':
    case 'fcfSbc':
      return pct(v)
    case 'eps':
      return num(v)
  }
}

// Wealthmatica's checklist: the pass/fail (and its thresholds) is computed in
// wealthmatica.py; this only presents it. An N/A check (inputs absent) shows a
// dash and no tone — it is not a fail.
export function wealthmaticaVerdict(row: Row, m: Messages): Verdict {
  const wm = row.wealthmatica
  const base = { system: 'Wealthmatica', question: m.question.Wealthmatica } as const
  if (!wm || wm.pass === null || wm.pass === undefined) {
    return { ...base, label: statusLabel(m, NA_LABEL), tagline: m.wmTooFew, tone: 'slate', pass: false, drivers: [] }
  }
  const pass = wealthmaticaPass(row)
  return {
    ...base,
    label: statusLabel(m, pass ? 'Pass' : 'Fail'),
    tagline: pass ? m.wmPass : m.wmFail,
    tone: pass ? 'green' : 'red',
    pass,
    // The passed/applicable count rides on the verdict line (verdictLines).
    drivers: WEALTHMATICA_CHECKS.map((k) => {
      const c = wm.checks[k]
      return { label: m.wm[k], value: wealthmaticaFormat(k, c?.value ?? null, m), tone: boolTone(c?.pass) }
    }),
  }
}

function pegTone(v: unknown): Tone {
  if (typeof v !== 'number') return 'slate'
  return v < 1 ? 'green' : v <= 2 ? 'yellow' : 'red'
}

export interface VerdictLine {
  name: string
  label: string
  tone: Tone
  colors?: TierColors // azqato tier palette; graded lines use the tone
}

function gradeLine(name: string, field: string, status: string | null | undefined, m: Messages): VerdictLine {
  return {
    name,
    label: statusLabel(m, status ?? NA_LABEL),
    tone: status ? signalTone(field, status) : 'slate',
  }
}

// The verdict(s) a system produces. Azqato is a single rank tier; Lynch and
// Graham each have TWO facets (Lynch: two valuation methods; Graham: valuation
// + defensive safety).
export function verdictLines(system: SystemName, row: Row, m: Messages): VerdictLine[] {
  if (system === 'Wealthmatica') {
    const v = wealthmaticaVerdict(row, m)
    const wm = row.wealthmatica
    const count = wm && wm.pass != null ? ` · ${wm.passed}/${wm.applicable}` : ''
    return [{ name: m.line.checklist, label: `${v.label}${count}`, tone: v.tone }]
  }
  if (system === 'Azqato') {
    const az = row.azqato
    const scored = az != null && az.score != null && az.tier != null
    return [
      {
        name: m.line.tier,
        label: scored ? TIER_LABEL[az.tier!] : statusLabel(m, NA_LABEL),
        tone: scored ? TIER_TONE[az.tier!] : 'slate',
        colors: scored ? TIER_STYLE[az.tier!] : undefined,
      },
    ]
  }
  if (system === 'Lynch') {
    return [
      gradeLine(m.line.lynchValue, 'Lynch_Lynch_Status', row.Lynch_Lynch_Status as string | null | undefined, m),
      gradeLine(m.line.pegBand, 'Lynch_Lynch_PEG_Band', row.Lynch_Lynch_PEG_Band as string | null | undefined, m),
    ]
  }
  const def = row.DefensiveScore
  return [
    gradeLine(m.line.valuation, 'Graham_Graham_Status', row.Graham_Graham_Status as string | null | undefined, m),
    {
      name: m.line.defensive,
      // The meter that used to carry the 0-8 score is gone; the count rides on the label.
      label: row.DefensiveLabel ? `${statusLabel(m, row.DefensiveLabel as string)}${typeof def === 'number' ? ` · ${def}/8` : ''}` : statusLabel(m, NA_LABEL),
      tone: row.DefensiveLabel ? signalTone('DefensiveLabel', row.DefensiveLabel as string) : 'slate',
    },
  ]
}

export function verdicts(row: Row, m: Messages): Verdict[] {
  return [azqatoVerdict(row, m), lynchVerdict(row, m), grahamVerdict(row, m), wealthmaticaVerdict(row, m)]
}


export interface Combined {
  passCount: number
  tone: Tone
}

// How many of the four independent systems a name clears.
export function combinedVerdict(row: Row): Combined {
  const passCount = PASSES.filter((p) => p(row)).length
  const tone: Tone = passCount === PASSES.length ? 'green' : passCount >= 1 ? 'yellow' : 'red'
  return { passCount, tone }
}

// "Passes all": a name clears ALL FOUR independent systems.
export function passesAll(row: Row): boolean {
  if (row.Error) return false
  return PASSES.every((p) => p(row))
}
