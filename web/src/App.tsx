import { useCallback, useDeferredValue, useEffect, useMemo, useRef, useState } from 'react'
import Header from './Header'
import FilterBar, { type PassCounts } from './FilterBar'
import StockCard from './StockCard'
import Scorecard from './Scorecard'
import MethodologyDialog from './MethodologyDialog'
import Toasts from './Toasts'
import { filterRows, sortRows, type SortKey } from './filters'
import { PASS_RULE, combinedVerdict, verdicts } from './score'
import { useDataset } from './useDataset'
import { loadPrefs, savePrefs } from './prefs'
import { INDEX_LABEL, type IndexName, type Row } from './types'

// Cards render in pages as the list is scrolled — ~520 cards at once is a
// noticeable stall on a phone, and nobody reads past the first screenful.
const PAGE = 48

// The open scorecard lives in the URL hash (#AAPL), so it is linkable and the
// phone's back gesture closes it.
function useHashTicker(): [string | null, (t: string | null) => void] {
  const read = () => decodeURIComponent(window.location.hash.slice(1)).toUpperCase() || null
  const [ticker, setTicker] = useState<string | null>(read)
  const pushed = useRef(false)
  useEffect(() => {
    const onHash = () => {
      const t = read()
      // Closed by the browser's own back gesture: nothing left to pop.
      if (!t) pushed.current = false
      setTicker(t)
    }
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])
  const set = useCallback((t: string | null) => {
    if (t) {
      pushed.current = true
      window.location.hash = encodeURIComponent(t)
    } else if (pushed.current) {
      pushed.current = false
      window.history.back()
    } else {
      // Arrived on a deep link: there is no in-app entry to go back to.
      window.history.replaceState(null, '', window.location.pathname + window.location.search)
      setTicker(null)
    }
  }, [])
  return [ticker, set]
}

function Summary({ rows, pool }: { rows: Row[]; pool: IndexName | null }) {
  const stats = useMemo(() => {
    let all = 0
    const per = { Azqato: 0, Lynch: 0, Graham: 0 }
    for (const r of rows) {
      if (combinedVerdict(r).passCount === 3) all++
      for (const v of verdicts(r)) if (v.pass) per[v.system]++
    }
    return { all, per }
  }, [rows])

  const tiles = (['Azqato', 'Lynch', 'Graham'] as const).map((s) => ({ label: s, hint: PASS_RULE[s], value: stats.per[s] }))

  return (
    <section className="pb-4 pt-5 sm:pb-5 sm:pt-8">
      <h1 className="text-balance text-[22px] font-semibold leading-tight tracking-tight text-slate-50 sm:text-3xl">
        <span className="tnum bg-gradient-to-br from-emerald-300 to-sky-300 bg-clip-text text-transparent">{stats.all}</span> of{' '}
        <span className="tnum">{rows.length}</span> {pool ? `${INDEX_LABEL[pool]} stocks` : 'stocks'} pass all three screens
      </h1>
      <p className="mt-1.5 text-sm text-slate-400">
        Azqato, Lynch and Graham judge each name independently — where they agree is the short list.
      </p>
      <div className="mt-4 grid grid-cols-3 gap-2 sm:max-w-xl">
        {tiles.map((t) => (
          <div key={t.label} className="rounded-2xl bg-surface-1 px-3 py-2.5 ring-1 ring-inset ring-white/[0.07]">
            <div className="text-[11px] font-medium uppercase tracking-[0.08em] text-slate-500">{t.label}</div>
            <div className="tnum mt-0.5 text-xl font-semibold text-slate-100">{t.value}</div>
            <div className="truncate text-[11px] text-slate-500">{t.hint}</div>
          </div>
        ))}
      </div>
    </section>
  )
}

export default function App() {
  const { load, reload, pending, applyPending, dismissPending, check, checking, lastChecked, checkFailed } = useDataset()
  // First visit opens on the all-three short list; after that, the last view.
  const [initial] = useState(loadPrefs)
  const [minPass, setMinPass] = useState(initial.minPass)
  const [pool, setPool] = useState<IndexName | null>(initial.pool)
  const [sort, setSort] = useState<SortKey>(initial.sort)
  useEffect(() => savePrefs({ minPass, pool, sort }), [minPass, pool, sort])
  const [query, setQuery] = useState('')
  const [limit, setLimit] = useState(PAGE)
  const [infoOpen, setInfoOpen] = useState(false)
  const [openTicker, setOpenTicker] = useHashTicker()
  const deferredQuery = useDeferredValue(query)

  const rows = load.status === 'ready' ? load.data.rows : []

  // Everything the pass filter chooses between: pool + search applied, pass
  // floor not — so each segment's count is what tapping it would show.
  const candidates = useMemo(() => filterRows(rows, { minPass: 0, pool, query: deferredQuery }), [rows, pool, deferredQuery])
  const poolRows = useMemo(() => filterRows(rows, { minPass: 0, pool, query: '' }), [rows, pool])

  const counts = useMemo<PassCounts>(() => {
    const pc = candidates.map((r) => combinedVerdict(r).passCount)
    return { 3: pc.filter((n) => n >= 3).length, 2: pc.filter((n) => n >= 2).length, 1: pc.filter((n) => n >= 1).length, 0: pc.length }
  }, [candidates])

  const shown = useMemo(
    () => sortRows(filterRows(rows, { minPass, pool, query: deferredQuery }), sort),
    [rows, minPass, pool, deferredQuery, sort],
  )

  useEffect(() => setLimit(PAGE), [minPass, pool, sort, deferredQuery, rows])

  const sentinel = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const el = sentinel.current
    if (!el) return
    const io = new IntersectionObserver(
      (es) => {
        if (es.some((e) => e.isIntersecting)) setLimit((l) => l + PAGE)
      },
      { rootMargin: '800px' },
    )
    io.observe(el)
    return () => io.disconnect()
  }, [shown.length, limit])

  const openRow = openTicker ? rows.find((r) => r.Ticker.toUpperCase() === openTicker) : undefined

  // Enter in the search box opens an exact ticker match straight away.
  const onSubmit = () => {
    const q = query.trim().toUpperCase()
    const hit = rows.find((r) => r.Ticker.toUpperCase() === q) ?? (shown.length === 1 ? shown[0] : undefined)
    if (hit) setOpenTicker(hit.Ticker)
  }

  const looser = ([2, 1, 0] as const).find((l) => l < minPass && counts[l] > 0)

  return (
    <div className="min-h-full">
      <Header
        generatedAt={load.status === 'ready' ? load.data.generated_at : undefined}
        checking={checking}
        lastChecked={lastChecked}
        checkFailed={checkFailed}
        onCheck={() => void check(true)}
        onMethodology={() => setInfoOpen(true)}
      />

      <main className="mx-auto max-w-7xl px-4 pb-24 sm:px-6">
        {load.status === 'error' ? (
          <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 text-center">
            <p className="text-rose-300">Couldn&rsquo;t load the screen: {load.message}</p>
            <button
              type="button"
              onClick={reload}
              className="rounded-full bg-emerald-400 px-5 py-2 text-sm font-semibold text-emerald-950 hover:bg-emerald-300"
            >
              Try again
            </button>
          </div>
        ) : (
          <>
            {load.status === 'ready' ? (
              <Summary rows={poolRows} pool={pool} />
            ) : (
              <div className="skeleton mb-5 mt-8 h-24 max-w-xl rounded-2xl bg-surface-1" />
            )}

            <FilterBar
              minPass={minPass}
              onMinPass={setMinPass}
              counts={counts}
              pool={pool}
              onPool={setPool}
              sort={sort}
              onSort={setSort}
              query={query}
              onQuery={setQuery}
              onSubmit={onSubmit}
            />

            {load.status === 'loading' ? (
              <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {Array.from({ length: 8 }).map((_, i) => (
                  <div key={i} className="skeleton h-64 rounded-2xl bg-surface-1" />
                ))}
              </div>
            ) : shown.length === 0 ? (
              <div className="flex min-h-[40vh] flex-col items-center justify-center gap-3 text-center">
                <p className="text-slate-300">No stocks match.</p>
                {looser !== undefined ? (
                  <button
                    type="button"
                    onClick={() => setMinPass(looser)}
                    className="rounded-full bg-white/[0.06] px-4 py-2 text-sm text-slate-100 ring-1 ring-inset ring-white/10 hover:bg-white/10"
                  >
                    Show {looser === 0 ? 'every name' : `${looser}+ screens`} ({counts[looser]})
                  </button>
                ) : null}
              </div>
            ) : (
              <>
                <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                  {shown.slice(0, limit).map((r) => (
                    <StockCard key={r.Ticker} row={r} onOpen={setOpenTicker} />
                  ))}
                </div>
                {limit < shown.length ? <div ref={sentinel} className="h-px" aria-hidden /> : null}
                <p className="mt-8 text-center text-xs text-slate-600">
                  {shown.length} of {counts[0]} shown · Educational use only — not financial advice.
                </p>
              </>
            )}
          </>
        )}
      </main>

      {openRow ? <Scorecard row={openRow} onClose={() => setOpenTicker(null)} /> : null}
      {infoOpen ? <MethodologyDialog onClose={() => setInfoOpen(false)} /> : null}
      <Toasts pendingAt={pending?.generated_at} onLoadPending={applyPending} onDismissPending={dismissPending} />
    </div>
  )
}
