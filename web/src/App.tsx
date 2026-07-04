import { useCallback, useEffect, useMemo, useState } from 'react'
import type { SortingState, VisibilityState } from '@tanstack/react-table'
import Toolbar, { type PassCounts } from './Toolbar'
import DataTable from './DataTable'
import Scorecard from './Scorecard'
import { columns, presetVisibility } from './columns'
import { combinedVerdict } from './score'
import type { Dataset } from './types'

const DATA_URL = `${import.meta.env.BASE_URL}data/results.json`

type LoadState = { status: 'loading' } | { status: 'error'; message: string } | { status: 'ready'; data: Dataset }

export default function App() {
  const [load, setLoad] = useState<LoadState>({ status: 'loading' })
  const [minPass, setMinPass] = useState(3) // default: pass all three
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>(() => presetVisibility('summary'))
  const [query, setQuery] = useState('')
  const [sorting, setSorting] = useState<SortingState>([{ id: 'combined', desc: true }])

  const fetchData = useCallback(() => {
    setLoad({ status: 'loading' })
    fetch(`${DATA_URL}?v=${Date.now()}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status} fetching results.json`)
        return r.json() as Promise<Dataset>
      })
      .then((data) => setLoad({ status: 'ready', data }))
      .catch((e: unknown) => setLoad({ status: 'error', message: e instanceof Error ? e.message : String(e) }))
  }, [])

  useEffect(fetchData, [fetchData])

  const rows = load.status === 'ready' ? load.data.rows : []
  const q = query.trim().toUpperCase()

  const counts = useMemo<PassCounts>(() => {
    const nonErr = rows.filter((r) => !r.Error)
    const pc = nonErr.map((r) => combinedVerdict(r).passCount)
    return {
      3: pc.filter((n) => n >= 3).length,
      2: pc.filter((n) => n >= 2).length,
      1: pc.filter((n) => n >= 1).length,
      0: nonErr.length,
    }
  }, [rows])

  const exactMatch = useMemo(() => (q ? rows.find((r) => r.Ticker?.toUpperCase() === q) : undefined), [rows, q])

  const filtered = useMemo(() => {
    return rows.filter((r) => {
      if (r.Error) return false
      if (combinedVerdict(r).passCount < minPass) return false
      if (q && !r.Ticker.toUpperCase().includes(q)) return false
      return true
    })
  }, [rows, minPass, q])

  if (load.status === 'error') {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4 bg-canvas text-slate-200">
        <p className="text-rose-300">Failed to load data: {load.message}</p>
        <button
          type="button"
          onClick={fetchData}
          className="rounded-md bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-500"
        >
          Retry
        </button>
      </div>
    )
  }

  const looser = [2, 1, 0].find((l) => l < minPass && counts[l as keyof PassCounts] > 0)

  return (
    <div className="flex h-full flex-col bg-canvas text-slate-100">
      <Toolbar
        minPass={minPass}
        onMinPass={setMinPass}
        counts={counts}
        visibility={columnVisibility}
        onVisibility={setColumnVisibility}
        query={query}
        onQuery={setQuery}
        shown={filtered.length}
        total={rows.length}
        generatedAt={load.status === 'ready' ? load.data.generated_at : undefined}
      />

      <main className="min-h-0 flex-1">
        {load.status === 'loading' ? (
          <div className="space-y-1 p-5">
            {Array.from({ length: 10 }).map((_, i) => (
              <div key={i} className="skeleton h-8 rounded bg-surface-2" />
            ))}
          </div>
        ) : exactMatch ? (
          <Scorecard row={exactMatch} onBack={() => setQuery('')} />
        ) : filtered.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
            <p className="text-slate-300">No names match this filter.</p>
            {looser !== undefined ? (
              <button
                type="button"
                onClick={() => setMinPass(looser)}
                className="rounded-md bg-surface-3 px-4 py-2 text-sm text-slate-100 ring-1 ring-inset ring-edge hover:bg-surface-2"
              >
                Relax to {looser === 0 ? 'show all' : `${looser}+ screens`} ({counts[looser as keyof PassCounts]})
              </button>
            ) : null}
          </div>
        ) : (
          <div className="h-full p-4">
            <div className="h-full overflow-hidden rounded-xl border border-hairline">
              <DataTable
                data={filtered}
                columns={columns}
                sorting={sorting}
                onSortingChange={setSorting}
                columnVisibility={columnVisibility}
                onRowClick={(row) => setQuery(row.Ticker)}
              />
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
