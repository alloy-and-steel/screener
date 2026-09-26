import { memo } from 'react'
import type { Row } from './types'
import { DASH, TONE, capB, num, pct, usd, type Tone } from './format'
import { azPegDisplay, combinedVerdict, verdicts } from './score'

function signedPct(v: number | null | undefined): string {
  if (typeof v !== 'number' || !Number.isFinite(v)) return DASH
  return `${v > 0 ? '+' : ''}${v.toFixed(0)}%`
}

function signTone(v: number | null | undefined): string {
  if (typeof v !== 'number' || !Number.isFinite(v) || v === 0) return 'text-slate-100'
  return v > 0 ? 'text-emerald-300' : 'text-rose-300'
}

function Stat({ label, value, className = 'text-slate-100' }: { label: string; value: string; className?: string }) {
  return (
    <div className="min-w-0">
      <div className="truncate text-[11px] text-slate-500">{label}</div>
      <div className={`tnum mt-0.5 truncate text-[15px] font-semibold ${className}`}>{value}</div>
    </div>
  )
}

// Where today's price sits in the 52-week range; the lower quarter is azqato's
// favourable-entry band (timing context, not scored).
function RangeStrip({ p }: { p: number | null | undefined }) {
  if (typeof p !== 'number' || !Number.isFinite(p)) return <div className="text-[11px] text-slate-500">52-wk {DASH}</div>
  const tone: Tone = p <= 25 ? 'green' : p >= 75 ? 'red' : 'slate'
  const x = Math.max(0, Math.min(100, p))
  return (
    <div className="flex items-center gap-2.5 text-[11px] text-slate-500" title="Position in the 52-week range">
      <span className="shrink-0">52-wk</span>
      <span className="relative h-1 flex-1 rounded-full bg-white/[0.07]">
        <span className="absolute inset-y-0 left-0 rounded-full bg-white/[0.12]" style={{ width: `${x}%` }} />
        <span
          className={`absolute top-1/2 size-2.5 -translate-y-1/2 rounded-full ring-2 ring-surface-1 ${TONE[tone].fill}`}
          style={{ left: `calc(${x}% - 5px)` }}
        />
      </span>
      <span className="tnum w-8 shrink-0 text-right text-slate-400">{x.toFixed(0)}%</span>
    </div>
  )
}

// Overall is informational (not part of the pass gate), so it is drawn as a
// quiet ring rather than a verdict chip.
function OverallRing({ score }: { score: number | null | undefined }) {
  const has = typeof score === 'number' && Number.isFinite(score)
  const r = 15
  const c = 2 * Math.PI * r
  const frac = has ? Math.max(0, Math.min(100, score)) / 100 : 0
  return (
    <div className="relative grid size-11 shrink-0 place-items-center" title="Overall score (informational, not part of the pass gate)">
      <svg viewBox="0 0 36 36" className="absolute inset-0 -rotate-90">
        <circle cx="18" cy="18" r={r} fill="none" strokeWidth="3" className="stroke-white/[0.07]" />
        {has ? (
          <circle
            cx="18"
            cy="18"
            r={r}
            fill="none"
            strokeWidth="3"
            strokeLinecap="round"
            strokeDasharray={`${frac * c} ${c}`}
            className="stroke-sky-400"
          />
        ) : null}
      </svg>
      <span className="tnum text-[12px] font-semibold text-slate-100">{has ? score.toFixed(0) : DASH}</span>
    </div>
  )
}

function StockCard({ row, onOpen }: { row: Row; onOpen: (ticker: string) => void }) {
  const vs = verdicts(row)
  const c = combinedVerdict(row)
  const az = row.azqato
  const aligned = c.passCount === 3

  return (
    <button
      type="button"
      onClick={() => onOpen(row.Ticker)}
      className={`card relative flex w-full flex-col gap-4 overflow-hidden rounded-2xl bg-surface-1 p-4 text-left ring-1 ring-inset transition duration-200 hover:bg-surface-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-400 ${
        aligned ? 'ring-emerald-400/25 hover:ring-emerald-400/45' : 'ring-white/[0.07] hover:ring-white/15'
      }`}
    >
      {/* Identity + price */}
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline gap-2">
            <span className="font-mono text-lg font-bold tracking-tight text-slate-50">{row.Ticker}</span>
            <span className="truncate text-xs text-slate-500">{row.Sector ?? ''}</span>
          </div>
          <div className="tnum mt-0.5 text-[13px] text-slate-400">
            <span className="text-slate-200">{usd(row.Price)}</span>
            <span className="mx-1.5 text-slate-600">·</span>
            {capB(row.MarketCap_B)}
          </div>
        </div>
        <OverallRing score={row.OverallScore} />
      </div>

      {/* The three independent verdicts */}
      <div className="grid grid-cols-3 gap-1.5">
        {vs.map((v) => {
          const chip = v.pillColors ?? TONE[v.tone]
          return (
            <div
              key={v.system}
              aria-label={`${v.system}: ${v.label}${v.pass ? ', passes' : ''}`}
              className={`flex flex-col items-start gap-1 rounded-xl px-2.5 py-2 ring-1 ring-inset ${
                v.pass ? 'bg-emerald-400/[0.06] ring-emerald-400/20' : 'bg-white/[0.025] ring-white/[0.05]'
              }`}
            >
              <span className="text-[11px] text-slate-500">{v.system}</span>
              <span
                className={`inline-flex h-6 items-center whitespace-nowrap rounded-md px-2 text-[12px] font-semibold ring-1 ring-inset ${chip.bg} ${chip.text} ${chip.ring}`}
              >
                {v.label}
              </span>
            </div>
          )
        })}
      </div>

      {/* Headline statistics */}
      <div className="grid grid-cols-3 gap-x-3 gap-y-2.5">
        <Stat label="PEG" value={num(row.Lynch_PEG)} />
        <Stat label="Fwd PEG" value={az ? num(azPegDisplay(az)) : DASH} />
        <Stat label="Fwd EPS" value={signedPct(az?.epsFwd)} className={signTone(az?.epsFwd)} />
        <Stat label="Graham disc" value={signedPct(row.Graham_Graham_Discount_Pct)} className={signTone(row.Graham_Graham_Discount_Pct)} />
        <Stat label="Lynch disc" value={signedPct(row.Lynch_Lynch_Discount_Pct)} className={signTone(row.Lynch_Lynch_Discount_Pct)} />
        <Stat label="Div yield" value={pct(row.DivYield_Pct)} />
      </div>

      <div className="mt-auto flex items-center gap-4 border-t border-white/[0.05] pt-3">
        <div className="min-w-0 flex-1">
          <RangeStrip p={az?.pos_52w_pct} />
        </div>
        <span className={`tnum shrink-0 text-[11px] font-semibold ${TONE[c.tone].text}`}>{c.passCount}/3 screens</span>
      </div>
    </button>
  )
}

export default memo(StockCard)
