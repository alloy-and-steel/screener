import { useEffect } from 'react'
import type { Row, Azqato } from './types'
import { INDEX_NAMES } from './types'
import { DASH, Dot, RangeBar, RsiGauge, TONE, capB, compactUsd, num, pct, signTone, signedPct, usd } from './format'
import { poolNames } from './filters'
import { LEVELS, pickViews } from './selection'
import { dataNote, sectorLabel } from './dataText'
import { useI18n } from './i18n'
import { fairPrices } from './fairPrice'
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
  const { m } = useI18n()
  const pools = INDEX_NAMES.filter((name) => az.byIndex?.[name]?.score != null)
  if (!pools.length) return null
  return (
    <div>
      <div className="mb-1 text-[11px] text-slate-500">{m.rankInPools}</div>
      <div className="space-y-1">
        {pools.map((name) => {
          const p = az.byIndex![name]!
          return (
            <div key={name} className="flex items-baseline justify-between gap-3 text-xs">
              <span className="text-slate-400">{m.poolLabel[name]}</span>
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
  const { m } = useI18n()
  return (
    <div className="space-y-2.5">
      <p className="text-[12px] text-slate-500">{m.dotsNote}</p>
      <AzqatoByIndex az={az} />
      <div>
        <div className="mb-1 text-[11px] text-slate-500">{m.rsiTiming}</div>
        <RsiGauge rsi={az.rsi} />
      </div>
      <div>
        <div className="mb-1 text-[11px] text-slate-500">{m.pos52w}</div>
        <RangeBar pct={az.pos_52w_pct} />
      </div>
    </div>
  )
}

function Card({ v, row }: { v: Verdict; row: Row }) {
  const { m } = useI18n()
  const lines = verdictLines(v.system, row, m)
  return (
    <div className="flex flex-col gap-3 rounded-2xl bg-surface-1 p-4 ring-1 ring-inset ring-white/[0.07]">
      <div>
        <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-500">{v.system}</div>
        <div className="text-xs text-slate-500">{v.question}</div>
      </div>

      {/* Verdict(s) — Azqato and Wealthmatica have one line; Lynch & Graham each have two */}
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
// four-system pass gate above. Shown as separate context, not a verdict.
function OverallPanel({ row }: { row: Row }) {
  const { m, lang } = useI18n()
  const scores = row.scores
  if (row.OverallScore == null && !scores) return null
  const pillars: { label: string; value: number | null | undefined }[] = [
    { label: m.pillars.value, value: scores?.value },
    { label: m.pillars.quality, value: scores?.quality },
    { label: m.pillars.growth, value: scores?.growth },
    { label: m.pillars.safety, value: scores?.safety },
  ]
  return (
    <div className="mt-3 rounded-2xl bg-surface-1 p-4 ring-1 ring-inset ring-white/[0.07]">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-500">{m.overall}</div>
          <div className="text-xs text-slate-500">{m.overallSub}</div>
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
        <DriverRow d={{ label: m.dcfDiscount, value: pct(row.DCF_Discount_Pct) }} />
        <DriverRow d={{ label: m.dcfImpliedGrowth, value: pct(row.DCF_Implied_Growth) }} />
        <DriverRow d={{ label: m.dcfMethod, value: row.DCF_Method ? dataNote(row.DCF_Method, lang) : DASH }} />
      </dl>
      {row.Trap_Reasons ? (
        <p className="mt-2 text-xs text-amber-300/80">
          {m.researchFlags}
          {dataNote(row.Trap_Reasons, lang)}
        </p>
      ) : null}
      {row.DCF_Data_Warning ? (
        <p className="mt-1 text-xs text-slate-500">
          {m.dcfNote}
          {dataNote(row.DCF_Data_Warning, lang)}
        </p>
      ) : null}
    </div>
  )
}

// What each method says the stock is worth next to today's price. Kept as three
// numbers on purpose (see fairPrice.ts): the spread between them is the signal.
function FairPricePanel({ row }: { row: Row }) {
  const { m } = useI18n()
  return (
    <div className="mt-3 rounded-2xl bg-surface-1 p-4 ring-1 ring-inset ring-white/[0.07]">
      <div className="mb-3">
        <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-500">{m.fairPrice}</div>
        <div className="text-xs text-slate-500">{m.fairPriceSub}</div>
      </div>
      <dl className="space-y-1.5">
        <div className="flex items-baseline justify-between gap-3 text-sm">
          <dt className="text-slate-400">{m.todayPrice}</dt>
          <dd className="tnum text-slate-100">{usd(row.Price)}</dd>
        </div>
        {fairPrices(row).map((f) => (
          <div key={f.method} className="flex items-baseline justify-between gap-3 text-sm">
            <dt className="text-slate-400">
              {f.method} <span className="text-xs text-slate-500">{m.fairHint[f.method]}</span>
            </dt>
            <dd className="tnum text-right text-slate-100">
              {usd(f.value)}
              {f.vsPrice !== null ? <span className={`ml-2 font-medium ${signTone(f.vsPrice)}`}>{signedPct(f.vsPrice, 0)}</span> : null}
              {f.range ? <div className="text-xs text-slate-500">{m.dcfRange(usd(f.range.low), usd(f.range.high))}</div> : null}
            </dd>
          </div>
        ))}
      </dl>
      <p className="mt-2 text-xs text-slate-500">{m.fairVsToday}</p>
    </div>
  )
}

// When the screen first picked this stock at each pass level (exactly 1, 2, 3
// or 4 screens) and what it has done since. Every level is listed, so one it has
// never reached reads as such; the first pick is never overwritten.
function PicksPanel({ row }: { row: Row }) {
  const { m, lang } = useI18n()
  const picks = pickViews(row, 0, new Date(), lang)
  if (!picks.length) return null
  const now = combinedVerdict(row).passCount
  return (
    <div className="mt-3 rounded-2xl bg-surface-1 p-4 ring-1 ring-inset ring-white/[0.07]">
      <div className="mb-3 text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-500">{m.firstPicked}</div>
      <dl className="space-y-1.5">
        {LEVELS.map((level) => {
          const e = picks.find((p) => p.level === level)
          return (
            <div key={level} className="flex items-baseline justify-between gap-3 text-sm">
              <dt className="text-slate-400">
                {m.levelLabel(level)} {e ? <span className="text-slate-500">{e.date}</span> : null}
                {level === now ? <span className="ml-2 text-xs text-emerald-300">{m.now}</span> : null}
              </dt>
              <dd className="tnum text-right text-slate-100">
                {e ? (
                  <>
                    {usd(e.price)}
                    <span className={`ml-2 font-medium ${signTone(e.change)}`}>{signedPct(e.change, 1)}</span>
                  </>
                ) : (
                  <span className="text-slate-500">{m.never}</span>
                )}
              </dd>
            </div>
          )
        })}
      </dl>
    </div>
  )
}

// The raw inputs behind the verdicts — what the old full-width grid showed —
// so a fair value can be traced back to the growth and earnings it came from.
function FundamentalsPanel({ row }: { row: Row }) {
  const { m, lang } = useI18n()
  const az = row.azqato
  const cells: Driver[] = [
    { label: m.fund.growthUsed, value: pct(row.Growth_g_Pct) },
    { label: m.fund.epsTtm, value: num(row.EPS_TTM) },
    { label: m.fund.pb, value: num(row.PB_Ratio) },
    { label: m.fund.divYield, value: pct(row.DivYield_Pct) },
    { label: m.fund.lynchScore, value: num(row.Lynch_Lynch_Score) },
    { label: m.fund.peFwd, value: az ? num(az.peFwd) : DASH },
    { label: m.fund.cash, value: az ? compactUsd(az.cash, lang) : DASH },
    { label: m.fund.debt, value: az ? compactUsd(az.debt, lang) : DASH },
    { label: m.fund.netCashCap, value: az ? pct(azNetCashMc(az)) : DASH },
  ]
  return (
    <div className="mt-3 rounded-2xl bg-surface-1 p-4 ring-1 ring-inset ring-white/[0.07]">
      <div className="mb-3 text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-500">{m.fundamentals}</div>
      <dl className="grid grid-cols-1 gap-x-6 gap-y-1.5 sm:grid-cols-2 lg:grid-cols-3">
        {cells.map((d) => (
          <DriverRow key={d.label} d={d} />
        ))}
      </dl>
    </div>
  )
}

// Full detail for one name, shown in a sheet over the card grid: bottom sheet
// on phones, right-hand panel on wide screens. Escape / backdrop / ✕ close it.
export default function Scorecard({ row, onClose }: { row: Row; onClose: () => void }) {
  const { m, lang } = useI18n()
  const vs = verdicts(row, m)
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
      aria-label={m.scorecardAria(row.Ticker)}
    >
      <div className="fade-in absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} aria-hidden />
      <div className="sheet-in relative flex max-h-[92dvh] w-full flex-col overflow-hidden rounded-t-3xl border border-white/10 bg-canvas shadow-2xl sm:max-h-none sm:max-w-5xl sm:rounded-none sm:rounded-l-3xl">
        <header className="shrink-0 border-b border-white/[0.06] px-5 pb-4 pt-3 sm:px-6 sm:pt-5">
          <div className="flex items-center gap-3">
            <a
              href={`https://finviz.com/quote.ashx?t=${row.Ticker}`}
              target="_blank"
              rel="noopener noreferrer"
              title={m.openFinviz}
              className="py-1.5 font-mono text-2xl font-bold tracking-tight text-slate-50 hover:text-sky-300"
            >
              {row.Ticker} <span className="text-base text-slate-500">↗</span>
            </a>
            {!row.Error && (
              <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 ring-1 ring-inset ${ct.bg} ${ct.ring}`}>
                <span className={`tnum text-xs font-semibold ${ct.text}`}>{m.screensCount(c.passCount, vs.length)}</span>
              </span>
            )}
            <button
              type="button"
              onClick={onClose}
              aria-label={m.close}
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
                {m.capLine(<span className="text-slate-200">{capB(row.MarketCap_B, lang)}</span>)}
              </span>
            )}
            <span className="w-full truncate text-xs text-slate-500">
              {[row.Sector ? sectorLabel(row.Sector, lang) : null, ...poolNames(row).map((n) => m.poolLabel[n])].filter(Boolean).join(' · ')}
            </span>
          </div>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-5 pb-[calc(1.5rem+env(safe-area-inset-bottom))] pt-4 sm:px-6">
          {row.Error ? (
            <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-300">
              {m.noScores(row.Ticker, dataNote(String(row.Error), lang))}
            </div>
          ) : (
            <>
              {row.Valuation_Input_Warning ? (
                <p className="mb-3 rounded-2xl border border-amber-400/20 bg-amber-400/[0.06] px-4 py-2.5 text-xs text-amber-200/90">
                  {m.valuationNA(dataNote(row.Valuation_Input_Warning, lang))}
                </p>
              ) : null}
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                {vs.map((v) => (
                  <Card key={v.system} v={v} row={row} />
                ))}
              </div>
              <FairPricePanel row={row} />
              <PicksPanel row={row} />
              <OverallPanel row={row} />
              <FundamentalsPanel row={row} />
            </>
          )}
        </div>
      </div>
    </div>
  )
}
