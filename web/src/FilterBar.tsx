import { SORTS, type SortKey } from './filters'
import { INDEX_LABEL, INDEX_NAMES, type IndexName } from './types'

export type PassCounts = Record<0 | 1 | 2 | 3, number>

const LEVELS: { level: 0 | 1 | 2 | 3; label: string }[] = [
  { level: 3, label: 'All 3' },
  { level: 2, label: '2+' },
  { level: 1, label: '1+' },
  { level: 0, label: 'Any' },
]

interface FilterBarProps {
  minPass: number
  onMinPass: (n: number) => void
  counts: PassCounts
  pool: IndexName | null
  onPool: (p: IndexName | null) => void
  sort: SortKey
  onSort: (s: SortKey) => void
  query: string
  onQuery: (q: string) => void
  onSubmit: () => void
}

function Chip({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={`h-9 shrink-0 whitespace-nowrap rounded-full px-3.5 text-[13px] font-medium transition ${
        active
          ? 'bg-emerald-400/15 text-emerald-200 ring-1 ring-inset ring-emerald-400/40'
          : 'bg-white/[0.04] text-slate-300 ring-1 ring-inset ring-white/10 hover:bg-white/[0.08]'
      }`}
    >
      {children}
    </button>
  )
}

const SORT_ICON = 'M3 5h14v1.5H3V5Zm2.5 4.25h9v1.5h-9v-1.5ZM8 13.5h4V15H8v-1.5Z'

export default function FilterBar(p: FilterBarProps) {
  return (
    <div className="sticky top-[calc(3.5rem+env(safe-area-inset-top))] z-20 -mx-4 border-b border-white/[0.06] bg-canvas/80 px-4 py-3 backdrop-blur-xl sm:-mx-6 sm:px-6">
      <div className="flex items-center gap-2">
        <label className="relative min-w-0 flex-1">
          <svg
            viewBox="0 0 20 20"
            className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-500"
            fill="currentColor"
            aria-hidden
          >
            <path d="M8.5 3a5.5 5.5 0 0 1 4.38 8.83l3.65 3.64-1.06 1.06-3.64-3.65A5.5 5.5 0 1 1 8.5 3Zm0 1.5a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z" />
          </svg>
          <input
            type="search"
            value={p.query}
            onChange={(e) => p.onQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') p.onSubmit()
            }}
            placeholder="Ticker or sector"
            aria-label="Search by ticker or sector"
            autoComplete="off"
            spellCheck={false}
            className="h-10 w-full rounded-xl bg-white/[0.04] pl-9 pr-3 text-[16px] text-slate-100 ring-1 ring-inset ring-white/10 placeholder:text-slate-500 focus:bg-white/[0.06] focus:outline-none focus:ring-emerald-400/50 sm:text-[15px]"
          />
        </label>

        {/* Icon-only on phones (the native picker still lists every label). */}
        <label className="relative shrink-0" title={`Sort: ${SORTS[p.sort].label}`}>
          <span className="sr-only">Sort by</span>
          <select
            value={p.sort}
            onChange={(e) => p.onSort(e.target.value as SortKey)}
            className="h-10 w-10 appearance-none rounded-xl bg-white/[0.04] text-[13px] font-medium text-transparent ring-1 ring-inset ring-white/10 focus:outline-none focus:ring-emerald-400/50 sm:w-auto sm:pl-9 sm:pr-4 sm:text-slate-200"
          >
            {(Object.keys(SORTS) as SortKey[]).map((k) => (
              <option key={k} value={k} className="bg-surface-2 text-slate-100">
                {SORTS[k].label}
              </option>
            ))}
          </select>
          <svg
            viewBox="0 0 20 20"
            className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400"
            fill="currentColor"
            aria-hidden
          >
            <path d={SORT_ICON} />
          </svg>
        </label>
      </div>

      <div className="no-scrollbar -mx-4 mt-2.5 flex items-center gap-2 overflow-x-auto px-4 sm:mx-0 sm:px-0">
        <div
          role="group"
          aria-label="Screens passed"
          className="flex h-9 shrink-0 items-center gap-0.5 rounded-full bg-white/[0.04] p-0.5 ring-1 ring-inset ring-white/10"
        >
          {LEVELS.map((l) => (
            <button
              key={l.level}
              type="button"
              aria-pressed={p.minPass === l.level}
              onClick={() => p.onMinPass(l.level)}
              className={`h-8 whitespace-nowrap rounded-full px-3 text-[13px] font-medium transition ${
                p.minPass === l.level ? 'bg-slate-50 text-slate-950' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {l.label}
              <span className="tnum ml-1 text-[11px] text-slate-500">{p.counts[l.level]}</span>
            </button>
          ))}
        </div>
        <span className="mx-1 h-5 w-px shrink-0 bg-white/10" aria-hidden />
        <div role="group" aria-label="Index pool" className="flex gap-2">
          <Chip active={p.pool === null} onClick={() => p.onPool(null)}>
            All pools
          </Chip>
          {INDEX_NAMES.map((name) => (
            <Chip key={name} active={p.pool === name} onClick={() => p.onPool(p.pool === name ? null : name)}>
              {INDEX_LABEL[name]}
            </Chip>
          ))}
        </div>
      </div>
    </div>
  )
}
