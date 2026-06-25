import type { Row, Azqato } from './types'
import { Dot, Meter, RangeBar, RsiGauge, TONE, num, VerdictPill } from './format'
import { combinedVerdict, NA_LABEL, verdictLines, verdicts, type Driver, type Verdict } from './score'

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

function AzqatoViz({ az }: { az: Azqato }) {
  return (
    <div className="space-y-2.5">
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
  const single = lines.length === 1 ? lines[0] : null
  return (
    <div className="flex flex-col gap-3 rounded-xl border border-edge bg-surface-2 p-4">
      <div>
        <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-500">{v.system}</div>
        <div className="text-xs text-slate-500">{v.question}</div>
      </div>

      {/* Verdict(s) — Azqato is a single binary gate; Lynch & Graham each have two */}
      <div className="min-h-[44px]">
        {single && single.kind === 'binary' ? (
          single.label === NA_LABEL ? (
            <span className="text-slate-500">No data</span>
          ) : (
            <div
              className={`inline-flex h-11 items-center gap-2 rounded-lg px-4 ring-1 ring-inset ${TONE[single.tone].bg} ${TONE[single.tone].ring}`}
            >
              <span className={`text-xl leading-none ${TONE[single.tone].text}`} aria-hidden>
                {single.tone === 'green' ? '✓' : '✕'}
              </span>
              <span className={`text-lg font-bold uppercase ${TONE[single.tone].text}`}>{single.label}</span>
            </div>
          )
        ) : (
          <div className="space-y-2.5">
            {lines.map((line) => (
              <div key={line.name} className="flex items-center justify-between gap-3">
                <span className="text-[11px] uppercase tracking-[0.06em] text-slate-500">{line.name}</span>
                <span className="flex items-center gap-2">
                  <Meter level={line.level} tone={line.tone} />
                  <span className={`w-24 text-right text-sm font-semibold ${TONE[line.tone].text}`}>{line.label}</span>
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="text-sm text-slate-300">{v.tagline}</div>

      {v.system === 'Azqato' && row.azqato ? <AzqatoViz az={row.azqato} /> : null}

      <dl className="mt-auto space-y-1.5 border-t border-hairline pt-3">
        {v.drivers.map((d) => (
          <DriverRow key={d.label} d={d} />
        ))}
      </dl>
    </div>
  )
}

export default function Scorecard({ row, onBack }: { row: Row; onBack: () => void }) {
  const c = combinedVerdict(row)
  const ct = TONE[c.tone]

  return (
    <div className="h-full overflow-auto bg-canvas px-6 py-5">
      <div className="mx-auto max-w-5xl">
        <button
          type="button"
          onClick={onBack}
          className="mb-4 inline-flex items-center gap-1 rounded-md px-2 py-1 text-sm text-slate-400 hover:bg-surface-2 hover:text-slate-100"
        >
          ‹ Back to screener
        </button>

        {/* Combined verdict strip */}
        <div className="mb-4 flex flex-wrap items-center gap-x-4 gap-y-2 rounded-xl border border-edge bg-surface-2 px-5 py-3">
          <a
            href={`https://finviz.com/quote.ashx?t=${row.Ticker}`}
            target="_blank"
            rel="noopener noreferrer"
            className="font-mono text-2xl font-bold text-slate-100 hover:text-sky-300"
          >
            {row.Ticker}
          </a>
          <span className="text-sm text-slate-400">{(row.Indexes as string) ?? ''}</span>
          {!row.Error && (
            <span className="text-sm text-slate-400">
              <span className="tnum text-slate-200">{num(row.Price)}</span>
              <span className="mx-2 text-slate-600">·</span>
              <span className="tnum text-slate-200">{num(row.MarketCap_B, 1)}B</span> mkt cap
            </span>
          )}
          {!row.Error && (
            <span className={`ml-auto inline-flex items-center gap-2 rounded-lg px-3 py-1 ring-1 ring-inset ${ct.bg} ${ct.ring}`}>
              <span className={`text-sm font-semibold ${ct.text}`}>{c.label}</span>
              <span className={`tnum text-sm font-bold ${ct.text}`}>{c.passCount}/3</span>
            </span>
          )}
        </div>

        {row.Error ? (
          <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-300">
            No scores for {row.Ticker}: {String(row.Error)}.
          </div>
        ) : (
          <>
            <div className="grid gap-3 md:grid-cols-3">
              {verdicts(row).map((v) => (
                <Card key={v.system} v={v} row={row} />
              ))}
            </div>
            <p className="mt-4 flex items-center gap-2 text-xs text-slate-500">
              <span className="inline-flex items-center gap-1">
                <VerdictPill tone="green">Pass</VerdictPill>
              </span>
              Three independent systems. They often disagree — that disagreement is the signal. The
              screener's default list shows only names that clear all three.
            </p>
          </>
        )}
      </div>
    </div>
  )
}
