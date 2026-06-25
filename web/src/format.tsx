import type { ReactNode } from 'react'

export const DASH = '—' // em dash for missing/null values

function isMissing(v: unknown): boolean {
  return v === null || v === undefined || (typeof v === 'number' && Number.isNaN(v))
}

export function num(v: unknown, decimals = 2): string {
  if (isMissing(v)) return DASH
  return typeof v === 'number' ? v.toFixed(decimals) : String(v)
}

export function pct(v: unknown, decimals = 1): string {
  if (isMissing(v)) return DASH
  return typeof v === 'number' ? `${v.toFixed(decimals)}%` : String(v)
}

// Compact magnitude (TradingView K/M/B convention) — input is a raw dollar value.
export function compactUsd(v: unknown): string {
  if (isMissing(v) || typeof v !== 'number') return DASH
  const abs = Math.abs(v)
  if (abs >= 1e12) return `${(v / 1e12).toFixed(2)}T`
  if (abs >= 1e9) return `${(v / 1e9).toFixed(2)}B`
  if (abs >= 1e6) return `${(v / 1e6).toFixed(1)}M`
  if (abs >= 1e3) return `${(v / 1e3).toFixed(1)}K`
  return v.toFixed(0)
}

export type Tone = 'green' | 'yellow' | 'red' | 'slate'

// One shared semantic ramp — a color means the same thing in the grid and the
// scorecard. Low-saturation tinted fill + ring reads as a status chip on the
// near-black canvas (solid green/red glares).
export const TONE: Record<
  Tone,
  { text: string; bg: string; ring: string; dot: string; fill: string; border: string }
> = {
  green: {
    text: 'text-emerald-300',
    bg: 'bg-emerald-500/15',
    ring: 'ring-emerald-500/30',
    dot: 'bg-emerald-400',
    fill: 'bg-emerald-400',
    border: 'border-emerald-500/70',
  },
  yellow: {
    text: 'text-amber-300',
    bg: 'bg-amber-500/15',
    ring: 'ring-amber-500/30',
    dot: 'bg-amber-400',
    fill: 'bg-amber-400',
    border: 'border-amber-500/70',
  },
  red: {
    text: 'text-rose-300',
    bg: 'bg-rose-500/15',
    ring: 'ring-rose-500/30',
    dot: 'bg-rose-400',
    fill: 'bg-rose-400',
    border: 'border-rose-500/70',
  },
  slate: {
    text: 'text-slate-400',
    bg: 'bg-slate-500/15',
    ring: 'ring-slate-500/25',
    dot: 'bg-slate-500',
    fill: 'bg-slate-600',
    border: 'border-slate-600/70',
  },
}

// Colorblind-safe redundancy: every tone also carries a glyph.
export const GLYPH: Record<Tone, string> = { green: '✓', yellow: '–', red: '✕', slate: '–' }

export function Badge({ tone, children }: { tone: Tone; children: ReactNode }) {
  const t = TONE[tone]
  return (
    <span
      className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-semibold ring-1 ring-inset ${t.bg} ${t.text} ${t.ring}`}
    >
      {children}
    </span>
  )
}

// The canonical verdict chip — glyph + label, used in the grid and scorecard.
export function VerdictPill({
  tone,
  glyph = true,
  children,
}: {
  tone: Tone
  glyph?: boolean
  children: ReactNode
}) {
  const t = TONE[tone]
  return (
    <span
      className={`inline-flex h-5 items-center gap-1 rounded-md px-2 text-[11px] font-semibold uppercase tracking-wide ring-1 ring-inset ${t.bg} ${t.text} ${t.ring}`}
    >
      {glyph && (
        <span aria-hidden className="text-[10px] leading-none">
          {GLYPH[tone]}
        </span>
      )}
      {children}
    </span>
  )
}

export function Dot({ tone }: { tone: Tone }) {
  return <span className={`inline-block size-2 shrink-0 rounded-full ${TONE[tone].dot}`} aria-hidden />
}

// 5-segment graded meter (Lynch/Graham). `level` is 0..1.
export function Meter({ level, tone, segments = 5 }: { level: number; tone: Tone; segments?: number }) {
  const filled = Math.max(0, Math.min(segments, Math.round(level * segments)))
  return (
    <span className="inline-flex gap-[3px]" aria-hidden>
      {Array.from({ length: segments }, (_, i) => (
        <span
          key={i}
          className={`h-2.5 w-3 rounded-[2px] ${i < filled ? TONE[tone].fill : 'bg-slate-700/50'}`}
        />
      ))}
    </span>
  )
}

// 52-week range bar: track + thumb positioned by `pct` (0 = at low, 100 = at
// high). For a value/entry screen, near-low is the opportunity (emerald).
export function RangeBar({ pct: p }: { pct: number | null | undefined }) {
  if (isMissing(p) || typeof p !== 'number') return <span className="text-slate-500">{DASH}</span>
  const tone: Tone = p <= 33 ? 'green' : p >= 75 ? 'red' : 'slate'
  return (
    <span className="inline-flex w-full items-center gap-2">
      <span className="relative h-1.5 flex-1 rounded-full bg-surface-3">
        <span
          className={`absolute top-1/2 size-2.5 -translate-y-1/2 rounded-full ring-2 ring-surface-2 ${TONE[tone].fill}`}
          style={{ left: `calc(${Math.max(0, Math.min(100, p))}% - 5px)` }}
        />
      </span>
      <span className="tnum w-10 text-right text-[11px] text-slate-400">{p.toFixed(0)}%</span>
    </span>
  )
}

// RSI(14) gauge 0..100 with oversold/overbought marker.
export function RsiGauge({ rsi }: { rsi: number | null | undefined }) {
  if (isMissing(rsi) || typeof rsi !== 'number') return <span className="text-slate-500">{DASH}</span>
  const tone: Tone = rsi < 30 ? 'green' : rsi > 70 ? 'red' : 'slate'
  return (
    <span className="inline-flex w-full items-center gap-2">
      <span className="relative h-1.5 flex-1 rounded-full bg-gradient-to-r from-emerald-500/30 via-slate-600/40 to-rose-500/30">
        <span
          className={`absolute top-1/2 h-3 w-0.5 -translate-y-1/2 ${TONE[tone].fill}`}
          style={{ left: `calc(${Math.max(0, Math.min(100, rsi))}% - 1px)` }}
        />
      </span>
      <span className="tnum w-10 text-right text-[11px] text-slate-400">{rsi.toFixed(0)}</span>
    </span>
  )
}

// Signal value -> tone, keyed by the ACTUAL (double-prefixed) row field name.
const SIGNAL_TONE: Record<string, Record<string, Tone>> = {
  Lynch_Lynch_Status: { 'Strong Buy': 'green', Buy: 'green', Hold: 'yellow', Avoid: 'red' },
  Lynch_Lynch_PEG_Band: { 'Strong Buy': 'green', Buy: 'green', Hold: 'yellow', Avoid: 'red' },
  Graham_Graham_Status: { 'Deep Buy': 'green', Buy: 'green', Watch: 'yellow', Avoid: 'red' },
  DefensiveLabel: { Pass: 'green', Borderline: 'yellow', Fail: 'red' },
  Lynch_PEG_Status: { Cheap: 'green', Reasonable: 'yellow', Rich: 'red' },
  Lynch_PEGY_Status: { Cheap: 'green', Reasonable: 'yellow', Rich: 'red' },
}

export function signalTone(field: string, value: string): Tone {
  return SIGNAL_TONE[field]?.[value] ?? 'slate'
}

export function boolTone(v: boolean | null | undefined): Tone {
  if (v === null || v === undefined) return 'slate'
  return v ? 'green' : 'red'
}

export function boolLabel(v: boolean | null | undefined): string {
  if (v === null || v === undefined) return 'n/a'
  return v ? 'yes' : 'no'
}
