import { useEffect } from 'react'
import type { Row, Azqato } from './types'
import { INDEX_LABEL, INDEX_NAMES } from './types'
import { DASH, Dot, RangeBar, RsiGauge, TONE, capB, compactUsd, num, pct, usd } from './format'
import { inPool } from './filters'
import { selectionView, type EntryView } from './selection'
import { TIER_LABEL, TIER_TONE, azNetCashMc, combinedVerdict, verdictLines, verdicts, type Driver, type Verdict } from './score'

function DriverRow({ d }: { d: Driver }) {
  return (
    <div className="flex items-baseline justify-between gap-3 text-sm">
      <span className="flex items-center gap-2 text-slate-400">
        {d.tone ? <Dot tone={d.tone} /> : <span className="size-2" />}
        {d.label}
      </span>
      <span className="tnum font-medium text-slate-100">{d.value}</span>
    </div>
  )
}

// The Azqato model is RELATIVE, so a stock's score depends on who it is ranked
// against. This fork screens one merged universe; azqato's own screener loads
// one pool at a time, which is why the same name can sit two tiers apart on his
// site. These are the per-pool re-scores, for reconciliation only — the tier
// driving the pass gate is the pooled one shown above.
function AzqatoByIndex({ az }: { az: Azqato }) {
  const pools = INDEX_NAMES.filter((name) => az.byIndex?.[name]?.score != null)
  if (!pools.length) return null
  return (
    <div>
      <div className="mb-1 text-[11px] text-slate-500">Rank inside each pool it belongs to</div>
      <div className="space-y-1">
        {pools.map((name) => {
          const p = az.byIndex![name]!
          return (
            <div key={name} className="flex items-baseline justify-between gap-3 text-xs">
              <span className="text-slate-400">{INDEX_LABEL[name]}</span>
              <span className="tnum text-slate-200">
                {p.score}/100
                <span className={`ml-2 ${p.tier ? TONE[TIER_TONE[p.tier]].text : 'text-slate-500'}`}>
                  {p.tier ? TIER_LABEL[p.tier] : DASH}
                </span>
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function AzqatoViz({ az }: { az: Azqato }) {
  return (
    <div className="space-y-2.5">
      <AzqatoByIndex az={az} />
      <div>
        <div className="mb-1 text-[11px] text-slate-500">RSI(14) — entry timing</div>
        <RsiGauge rsi={az.rsi} />
      </div>
      <div>
        <div className="mb-1 text-[11px] text-slate-500">52-week position</div>
        <RangeBar pct={az.pos_52w_pct} />
      </div>
    </div>
  )
}

function Card({ v, row }: { v: Verdict; row: Row }) {
  const lines = verdictLines(v.system, row)
  return (
    <div className="flex flex-col gap-3 rounded-2xl bg-surface-1 p-4 ring-1 ring-inset ring-white/[0.07]">
      <div>
        <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-500">{v.system}</div>
        <div className="text-xs text-slate-500">{v.question}</div>
      </div>

      {/* Verdict(s) — Azqato is a single rank tier; Lynch & Graham each have two */}
      <div className="space-y-2 lg:min-h-[52px]">
        {lines.map((line) => (
          <div key={line.name} className="flex items-baseline justify-between gap-3">
            <span className="text-[13px] text-slate-400">{line.name}</span>
            <span className={`text-[15px] font-semibold ${line.colors?.text ?? TONE[line.tone].text}`}>{line.label}</span>
          </div>
        ))}
      </div>

      <div className="text-sm text-slate-300">{v.tagline}</div>

      {v.system === 'Azqato' && row.azqato ? <AzqatoViz az={row.azqato} /> : null}

      <dl className="mt-auto space-y-1.5 border-t border-white/[0.06] pt-3">
        {v.drivers.map((d) => (
          <DriverRow key={d.label} d={d} />
        ))}
      </dl>
    </div>
  )
}

// Informational 4-pillar composite (ported v2.0 methodology) — NOT part of the
// Azqato/Lynch/Graham pass gate above. Shown as separate context, not a 4th verdict.
function OverallPanel({ row }: { row: Row }) {
  const scores = row.scores
  if (row.OverallScore == null && !scores) return null
  const pillars: { label: string; value: number | null | undefined }[] = [
    { label: 'Value', value: scores?.value },
    { label: 'Quality', value: scores?.quality },
    { label: 'Growth', value: scores?.growth },
    { label: 'Safety', value: scores?.safety },
  ]
  return (
    <div className="mt-3 rounded-2xl bg-surface-1 p-4 ring-1 ring-inset ring-white/[0.07]">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-500">Overall</div>
          <div className="text-xs text-slate-500">Informational 4-pillar composite — not part of the pass gate above</div>
        </div>
        <span className="tnum text-lg font-bold text-slate-100">{num(row.OverallScore, 0)}/100</span>
      </div>
      <div className="grid grid-cols-2 gap-x-6 gap-y-2 sm:grid-cols-4">
        {pillars.map((p) => (
          <div key={p.label} className="flex items-center justify-between gap-2">
            <span className="text-[11px] uppercase tracking-[0.06em] text-slate-500">{p.label}</span>
            <span className="tnum text-sm font-medium text-slate-200">{num(p.value, 0)}</span>
          </div>
        ))}
      </div>
      <dl className="mt-3 grid grid-cols-1 gap-x-6 gap-y-1.5 border-t border-white/[0.06] pt-3 text-sm sm:grid-cols-2 lg:grid-cols-3">
        <DriverRow d={{ label: 'Piotroski F', value: typeof row.Piotroski_F === 'number' ? `${row.Piotroski_F}/9` : DASH }} />
        <DriverRow d={{ label: 'Altman Z', value: num(row.Altman_Z) }} />
        <DriverRow d={{ label: 'DCF discount', value: pct(row.DCF_Discount_Pct) }} />
        <DriverRow d={{ label: 'DCF implied growth', value: pct(row.DCF_Implied_Growth) }} />
        <DriverRow d={{ label: 'DCF method', value: row.DCF_Method ?? DASH }} />
      </dl>
      {row.Trap_Reasons ? <p className="mt-2 text-xs text-amber-300/80">Research flags: {row.Trap_Reasons}</p> : null}
      {row.DCF_Data_Warning ? <p className="mt-1 text-xs text-slate-500">DCF note: {row.DCF_Data_Warning}</p> : null}
    </div>
  )
}

// Full detail for one name, shown in a sheet over the card grid: bottom sheet
// on phones, right-hand panel on wide screens. Escape / backdrop / ✕ close it.
function signed(v: number | null): string {
  return v === null ? DASH : `${v > 0 ? '+' : ''}${v.toFixed(1)}%`
}

// When the screen picked this stock (2+ screens) and what it has done since.
// "Latest entry" appears only after a drop-out and return; the first entry is
// never overwritten.
function SelectionPanel({ row }: { row: Row }) {
  const v = selectionView(row, new Date())
  if (!v) return null
  const entries: [string, EntryView][] = [
    ['First picked', v.first],
    ...(v.reentry ? [['Back on the list', v.reentry] as [string, EntryView]] : []),
  ]
  return (
    <div className="mt-3 rounded-2xl bg-surface-1 p-4 ring-1 ring-inset ring-white/[0.07]">
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-500">Since selected</div>
        <div className={`text-xs ${v.selected ? 'text-emerald-300' : 'text-slate-500'}`}>
          {v.selected ? 'On the 2+ list now' : 'Not on the 2+ list now'}
        </div>
      </div>
      <dl className="space-y-1.5">
        {entries.map(([label, e]) => (
          <div key={label} className="flex items-baseline justify-between gap-3 text-sm">
            <dt className="text-slate-400">
              {label} <span className="text-slate-500">{e.date}</span>
            </dt>
            <dd className="tnum text-right text-slate-100">
              {usd(e.price)}
              <span
                className={`ml-2 font-medium ${e.change === null ? 'text-slate-500' : e.change >= 0 ? 'text-emerald-300' : 'text-rose-300'}`}
              >
                {signed(e.change)}
              </span>
            </dd>
          </div>
        ))}
      </dl>
    </div>
  )
}

// The raw inputs behind the verdicts — what the old full-width grid showed —
// so a fair value can be traced back to the growth and earnings it came from.
function FundamentalsPanel({ row }: { row: Row }) {
  const az = row.azqato
  const cells: Driver[] = [
    { label: 'Growth (g) used', value: pct(row.Growth_g_Pct) },
    { label: 'EPS TTM', value: num(row.EPS_TTM) },
    { label: 'P/B', value: num(row.PB_Ratio) },
    { label: 'Dividend yield', value: pct(row.DivYield_Pct) },
    { label: 'Lynch score', value: num(row.Lynch_Lynch_Score) },
    { label: 'P/E FWD', value: az ? num(az.peFwd) : DASH },
    { label: 'Cash', value: az ? compactUsd(az.cash) : DASH },
    { label: 'Debt', value: az ? compactUsd(az.debt) : DASH },
    { label: 'Net cash / cap', value: az ? pct(azNetCashMc(az)) : DASH },
  ]
  return (
    <div className="mt-3 rounded-2xl bg-surface-1 p-4 ring-1 ring-inset ring-white/[0.07]">
      <div className="mb-3 text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-500">Fundamentals</div>
      <dl className="grid grid-cols-1 gap-x-6 gap-y-1.5 sm:grid-cols-2 lg:grid-cols-3">
        {cells.map((d) => (
          <DriverRow key={d.label} d={d} />
        ))}
      </dl>
    </div>
  )
}

export default function Scorecard({ row, onClose }: { row: Row; onClose: () => void }) {
  const c = combinedVerdict(row)
  const ct = TONE[c.tone]

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = prev
    }
  }, [onClose])

  return (
    <div
      className="fixed inset-0 z-40 flex items-end justify-center sm:items-stretch sm:justify-end"
      role="dialog"
      aria-modal="true"
      aria-label={`${row.Ticker} scorecard`}
    >
      <div className="fade-in absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} aria-hidden />
      <div className="sheet-in relative flex max-h-[92dvh] w-full flex-col overflow-hidden rounded-t-3xl border border-white/10 bg-canvas shadow-2xl sm:max-h-none sm:max-w-5xl sm:rounded-none sm:rounded-l-3xl">
        <header className="shrink-0 border-b border-white/[0.06] px-5 pb-4 pt-3 sm:px-6 sm:pt-5">
          <div className="flex items-center gap-3">
            <a
              href={`https://finviz.com/quote.ashx?t=${row.Ticker}`}
              target="_blank"
              rel="noopener noreferrer"
              title="Open on Finviz"
              className="py-1.5 font-mono text-2xl font-bold tracking-tight text-slate-50 hover:text-sky-300"
            >
              {row.Ticker} <span className="text-base text-slate-500">↗</span>
            </a>
            {!row.Error && (
              <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 ring-1 ring-inset ${ct.bg} ${ct.ring}`}>
                <span className={`tnum text-xs font-semibold ${ct.text}`}>{c.passCount}/3 screens</span>
              </span>
            )}
            <button
              type="button"
              onClick={onClose}
              aria-label="Close"
              className="ml-auto grid size-11 shrink-0 place-items-center rounded-full bg-white/[0.05] text-slate-300 ring-1 ring-inset ring-white/10 hover:bg-white/10 hover:text-slate-50"
            >
              ✕
            </button>
          </div>
          <div className="mt-1 flex flex-wrap items-baseline gap-x-2 text-sm text-slate-400">
            {!row.Error && (
              <span className="tnum">
                <span className="text-slate-200">{usd(row.Price)}</span>
                <span className="mx-2 text-slate-600">·</span>
                <span className="text-slate-200">{capB(row.MarketCap_B)}</span> mkt cap
              </span>
            )}
            <span className="text-xs text-slate-500">
              {[row.Sector, ...INDEX_NAMES.filter((n) => inPool(row, n)).map((n) => INDEX_LABEL[n])].filter(Boolean).join(' · ')}
            </span>
          </div>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-5 pb-[calc(1.5rem+env(safe-area-inset-bottom))] pt-4 sm:px-6">
          {row.Error ? (
            <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-300">
              No scores for {row.Ticker}: {String(row.Error)}.
            </div>
          ) : (
            <>
              {row.Valuation_Input_Warning ? (
                <p className="mb-3 rounded-2xl border border-amber-400/20 bg-amber-400/[0.06] px-4 py-2.5 text-xs text-amber-200/90">
                  Lynch and Graham are N/A here: {row.Valuation_Input_Warning}. The name stays visible — Azqato ranks it relative to the
                  universe, and the Graham defensive checks still run.
                </p>
              ) : null}
              <div className="grid gap-3 lg:grid-cols-3">
                {verdicts(row).map((v) => (
                  <Card key={v.system} v={v} row={row} />
                ))}
              </div>
              <SelectionPanel row={row} />
              <OverallPanel row={row} />
              <FundamentalsPanel row={row} />
            </>
          )}
        </div>
      </div>
    </div>
  )
}
