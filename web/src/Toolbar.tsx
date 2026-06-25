import { useState } from 'react'
import type { VisibilityState } from '@tanstack/react-table'
import { Dot } from './format'
import { pickerGroups, presetVisibility } from './columns'
import MethodologyDialog from './MethodologyDialog'
import { Logo } from './Logo'

export interface PassCounts {
  3: number
  2: number
  1: number
  0: number
}

interface ToolbarProps {
  minPass: number // 3 = all three (default), 2, 1, 0 = show all
  onMinPass: (n: number) => void
  counts: PassCounts
  visibility: VisibilityState
  onVisibility: (v: VisibilityState) => void
  query: string
  onQuery: (q: string) => void
  shown: number
  total: number
  generatedAt?: string
}

function Seg({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={`h-7 rounded-md px-2.5 text-xs font-medium transition-colors ${
        active ? 'bg-surface-3 text-slate-100 ring-1 ring-inset ring-edge' : 'text-slate-400 hover:text-slate-200'
      }`}
    >
      {children}
    </button>
  )
}

function ColumnsMenu({
  visibility,
  onVisibility,
}: {
  visibility: VisibilityState
  onVisibility: (v: VisibilityState) => void
}) {
  const [open, setOpen] = useState(false)
  const isVisible = (id: string) => visibility[id] !== false
  const shown = pickerGroups.reduce((n, g) => n + g.items.filter((i) => isVisible(i.id)).length, 0)
  const toggle = (id: string) => onVisibility({ ...visibility, [id]: visibility[id] === false })

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex h-8 items-center gap-1 rounded-md border border-edge bg-surface-1 px-3 text-xs font-medium text-slate-300 hover:text-slate-100"
      >
        Columns
        <span className="text-slate-500">{shown} ▾</span>
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} aria-hidden />
          <div className="absolute right-0 z-50 mt-1 w-64 rounded-lg border border-edge bg-surface-2 p-2 shadow-2xl">
            <div className="mb-2 flex gap-1 border-b border-hairline pb-2">
              <button
                type="button"
                onClick={() => onVisibility(presetVisibility('summary'))}
                className="flex-1 rounded-md bg-surface-1 px-2 py-1 text-xs text-slate-300 ring-1 ring-inset ring-hairline hover:text-slate-100"
              >
                Summary
              </button>
              <button
                type="button"
                onClick={() => onVisibility(presetVisibility('full'))}
                className="flex-1 rounded-md bg-surface-1 px-2 py-1 text-xs text-slate-300 ring-1 ring-inset ring-hairline hover:text-slate-100"
              >
                Show all
              </button>
            </div>
            <div className="max-h-[60vh] overflow-auto pr-1">
              {pickerGroups.map((g) => (
                <div key={g.group} className="mb-1">
                  <div className="px-1 pb-0.5 pt-1 text-[9px] font-semibold uppercase tracking-[0.1em] text-slate-500">
                    {g.group}
                  </div>
                  {g.items.map((it) => (
                    <label
                      key={it.id}
                      className="flex cursor-pointer items-center gap-2 rounded px-1.5 py-1 text-[13px] text-slate-300 hover:bg-surface-3"
                    >
                      <input
                        type="checkbox"
                        checked={isVisible(it.id)}
                        onChange={() => toggle(it.id)}
                        className="accent-sky-500"
                      />
                      {it.header}
                    </label>
                  ))}
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  )
}

function freshness(generatedAt?: string): { label: string; stale: boolean } {
  if (!generatedAt) return { label: 'Data date unknown', stale: false }
  const dt = new Date(generatedAt)
  if (Number.isNaN(dt.getTime())) return { label: 'Data date unknown', stale: false }
  const ageDays = (Date.now() - dt.getTime()) / 86_400_000
  const label = `as of ${dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}`
  return { label, stale: ageDays > 3 }
}

function sentence(minPass: number, shown: number): string {
  if (minPass === 3) return `${shown} names pass Azqato, Lynch, and Graham`
  if (minPass === 2) return `${shown} names pass at least 2 of the 3 screens`
  if (minPass === 1) return `${shown} names pass at least 1 screen`
  return `Showing all ${shown} names`
}

const RELAX: { level: number; label: string }[] = [
  { level: 3, label: 'All 3' },
  { level: 2, label: '2+' },
  { level: 1, label: '1+' },
  { level: 0, label: 'All' },
]

export default function Toolbar(props: ToolbarProps) {
  const { label, stale } = freshness(props.generatedAt)
  const [infoOpen, setInfoOpen] = useState(false)

  return (
    <>
    <header className="border-b border-hairline bg-surface-2">
      {/* Title row */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-5 py-2.5">
        <span className="flex items-center gap-2">
          <Logo className="h-5 w-5 text-emerald-400" />
          <span className="text-[16px] font-bold tracking-tight text-slate-100">Screener3000</span>
        </span>
        <button
          type="button"
          onClick={() => setInfoOpen(true)}
          title="How the three screens work"
          className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] text-slate-400 ring-1 ring-inset ring-hairline hover:text-slate-100"
        >
          ⓘ Methodology
        </button>
        <div className="flex items-center gap-3 text-[11px] text-slate-400">
          <span className="inline-flex items-center gap-1.5" title="Growth + technical entry screen (binary pass/fail)">
            <Dot tone="green" /> Azqato
          </span>
          <span className="inline-flex items-center gap-1.5" title="Growth at a reasonable price (Buy / Hold / Avoid)">
            <Dot tone="green" /> Lynch
          </span>
          <span className="inline-flex items-center gap-1.5" title="Intrinsic value + balance-sheet safety">
            <Dot tone="green" /> Graham
          </span>
        </div>
        <span className={`text-[11px] ${stale ? 'text-amber-300' : 'text-slate-500'}`}>
          {label}
          {stale ? ' · stale' : ''}
        </span>
        <input
          type="search"
          value={props.query}
          onChange={(e) => props.onQuery(e.target.value)}
          placeholder="Look up a symbol…"
          aria-label="Symbol lookup"
          autoComplete="off"
          spellCheck={false}
          className="ml-auto h-8 w-56 rounded-md border border-edge bg-surface-1 px-3 text-sm text-slate-100 placeholder:text-slate-500 focus:border-sky-500 focus:outline-none"
        />
      </div>

      {/* Framing row */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-hairline px-5 py-2">
        <span className="text-[13px] text-slate-300">{sentence(props.minPass, props.shown)}</span>

        <div className="ml-auto flex items-center gap-3">
          <div className="flex items-center gap-1 rounded-lg bg-surface-1 p-1 ring-1 ring-inset ring-hairline">
            <span className="px-1 text-[10px] uppercase tracking-wide text-slate-500">Pass</span>
            {RELAX.map((r) => (
              <Seg key={r.level} active={props.minPass === r.level} onClick={() => props.onMinPass(r.level)}>
                {r.label}
                <span className="ml-1 text-[10px] text-slate-500">{props.counts[r.level as keyof PassCounts]}</span>
              </Seg>
            ))}
          </div>

          <ColumnsMenu visibility={props.visibility} onVisibility={props.onVisibility} />
        </div>
      </div>
    </header>
    {infoOpen ? <MethodologyDialog onClose={() => setInfoOpen(false)} /> : null}
    </>
  )
}
