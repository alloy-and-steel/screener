import { useEffect } from 'react'
import type { ReactNode } from 'react'
import { Dot } from './format'
import { Logo } from './Logo'

function Block({ title, dot, children }: { title: string; dot?: boolean; children: ReactNode }) {
  return (
    <section className="mb-4">
      <h3 className="mb-1 flex items-center gap-2 text-sm font-semibold text-slate-100">
        {dot ? <Dot tone="green" /> : null}
        {title}
      </h3>
      <div className="text-[13px] leading-relaxed text-slate-300">{children}</div>
    </section>
  )
}

export default function MethodologyDialog({ onClose }: { onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" role="dialog" aria-modal="true">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} aria-hidden />
      <div className="relative z-10 max-h-[85vh] w-full max-w-2xl overflow-auto rounded-2xl border border-edge bg-surface-2 shadow-2xl">
        <header className="sticky top-0 flex items-center justify-between border-b border-hairline bg-surface-2 px-6 py-4">
          <div className="flex items-center gap-2">
            <Logo className="h-5 w-5 text-emerald-400" />
            <h2 className="text-lg font-bold tracking-tight text-slate-100">How Screener3000 works</h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="rounded-md px-2 py-1 text-slate-400 hover:bg-surface-3 hover:text-slate-100"
          >
            ✕
          </button>
        </header>

        <div className="px-6 py-5">
          <p className="mb-5 text-[13px] leading-relaxed text-slate-300">
            Screener3000 runs <strong className="text-slate-100">three independent value/growth screens</strong> on every
            S&amp;P 500, Dow 30, and Nasdaq-100 stock, then shows where they agree and where they don&rsquo;t. The default
            list shows only names that clear <strong className="text-slate-100">all three</strong>. Each system answers a
            different question, and they often disagree &mdash; that disagreement is the signal.
          </p>

          <Block title="Azqato — growth + technical entry" dot>
            A binary pass/fail screen of eight growth bands: PEG &lt; 1.0, EPS growth &gt; 15%, P/E below the growth rate,
            net cash (cash &gt; debt), gross margin &gt; 50%, net margin &gt; 25%, RSI(14) in 30&ndash;45, and price in the
            lower 25% of its 52-week range. A stock <strong className="text-slate-100">passes</strong> when it clears at
            least 6 of the 8. Forward estimates are premium data, so growth / PEG / P-E use trailing figures as a proxy.
          </Block>

          <Block title="Lynch — growth at a reasonable price" dot>
            Peter Lynch&rsquo;s PEG-centric method. Fair value is estimated two ways, giving two verdicts: a{' '}
            <strong className="text-slate-100">Value</strong> band (price vs. the earnings &times; (growth + dividend yield)
            fair value) and a <strong className="text-slate-100">PEG price band</strong> (price vs. the PEG fair value).
            Each is graded Strong Buy / Buy / Hold / Avoid &mdash; cheap relative to its growth reads as Buy.
          </Block>

          <Block title="Graham — intrinsic value + balance-sheet safety" dot>
            Benjamin Graham&rsquo;s two orthogonal checks. <strong className="text-slate-100">Valuation</strong>: a
            rate-adjusted intrinsic value (Graham&rsquo;s formula, discounted by the current AAA corporate-bond yield),
            graded Deep Buy / Buy / Watch / Avoid by margin of safety. <strong className="text-slate-100">Defensive</strong>:
            eight balance-sheet criteria (size, current ratio &ge; 2, low debt/equity, 8-of-10 years of positive EPS,
            dividend record, 10-year EPS growth, P/E &le; 15, P/B &le; 1.5) &mdash; Pass / Borderline / Fail.
          </Block>

          <Block title="Reading the screen">
            Each row&rsquo;s left rail and the <strong className="text-slate-100">N/3</strong> chip show how many systems a
            stock clears. Click any row (or search a ticker) for the full scorecard &mdash; every verdict, its drivers, an
            RSI gauge, and a 52-week-range bar. Relax the <em>Pass</em> filter to see names that clear 2, 1, or any; use{' '}
            <em>Columns</em> to choose what the grid shows.
          </Block>

          <p className="mt-5 border-t border-hairline pt-4 text-[12px] leading-relaxed text-slate-500">
            Fundamentals from Yahoo Finance and Finnhub; AAA yield from FRED. Missing values render as &ldquo;&mdash;&rdquo;,
            never zero. <strong className="text-slate-400">Educational use only &mdash; not financial advice.</strong> Verify
            every name yourself before acting.
          </p>
        </div>
      </div>
    </div>
  )
}
