import { SORTS, type SortKey } from './filters'
import { INDEX_LABEL, INDEX_NAMES, type IndexName } from './types'

export type PassCounts = Record<0 | 1 | 2 | 3, number>

const LEVELS: { level: 0 | 1 | 2 | 3; label: string; spoken: string }[] = [
  { level: 3, label: 'All 3', spoken: 'Passes all 3 screens' },
  { level: 2, label: '2+', spoken: 'Passes 2 or more' },
  { level: 1, label: '1+', spoken: 'Passes 1 or more' },
  { level: 0, label: 'Any', spoken: 'Any' },
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

const CHEVRON = 'M5.5 7.5 10 12l4.5-4.5 1 1L10 14 4.5 8.5l1-1Z'

// A native select, so the phone's own picker does the listing. The visible
// face is the current choice as plain text with the transparent select laid
// over it, so the choice always shows and truncates cleanly.
function Picker<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string
  value: T
  options: { value: T; label: string }[]
  onChange: (v: T) => void
}) {
  const current = options.find((o) => o.value === value)?.label ?? ''
  return (
    <label className="relative flex h-11 min-w-0 items-center gap-1.5 rounded-xl bg-white/[0.04] pl-3.5 pr-9 text-[14px] ring-1 ring-inset ring-white/10 focus-within:ring-emerald-400/50">
      <span className="truncate font-medium text-slate-100">{current}</span>
      <svg
        viewBox="0 0 20 20"
        className="pointer-events-none absolute right-3 top-1/2 size-4 -translate-y-1/2 text-slate-500"
        fill="currentColor"
        aria-hidden
      >
        <path d={CHEVRON} />
      </svg>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value as T)}
        aria-label={label}
        className="absolute inset-0 cursor-pointer appearance-none opacity-0"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  )
}

const ALL_POOLS = 'all'
const POOL_OPTIONS = [{ value: ALL_POOLS, label: 'All pools' }, ...INDEX_NAMES.map((n) => ({ value: n as string, label: INDEX_LABEL[n] }))]
const SORT_OPTIONS = (Object.keys(SORTS) as SortKey[]).map((k) => ({ value: k, label: SORTS[k].label }))

// Scrolls with the page on phones (a sticky bar ate a quarter of the screen);
// sticks under the header from tablet width up, where there is room.
export default function FilterBar(p: FilterBarProps) {
  return (
    <div className="-mx-4 flex flex-col gap-2 border-b border-white/[0.06] bg-canvas/85 px-4 py-3 backdrop-blur-xl sm:sticky sm:top-14 sm:z-20 sm:-mx-6 sm:px-6 lg:flex-row lg:items-center">
      <label className="relative min-w-0 lg:flex-1">
        <svg
          viewBox="0 0 20 20"
          className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-slate-500"
          fill="currentColor"
          aria-hidden
        >
          <path d="M8.5 3a5.5 5.5 0 0 1 4.38 8.83l3.65 3.64-1.06 1.06-3.64-3.65A5.5 5.5 0 1 1 8.5 3Zm0 1.5a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z" />
        </svg>
        <input
          type="search"
          enterKeyHint="search"
          value={p.query}
          onChange={(e) => p.onQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') p.onSubmit()
          }}
          placeholder="Ticker or sector"
          aria-label="Search by ticker or sector"
          autoComplete="off"
          autoCapitalize="characters"
          spellCheck={false}
          className="h-11 w-full rounded-xl bg-white/[0.04] pl-10 pr-3 text-[16px] text-slate-100 ring-1 ring-inset ring-white/10 placeholder:text-slate-500 focus:bg-white/[0.06] focus:outline-none focus:ring-emerald-400/50"
        />
      </label>

      <div
        role="group"
        aria-label="Screens passed"
        className="grid h-12 grid-cols-4 gap-0.5 rounded-xl bg-white/[0.04] p-0.5 ring-1 ring-inset ring-white/10 lg:w-80"
      >
        {LEVELS.map((l) => {
          const on = p.minPass === l.level
          return (
            <button
              key={l.level}
              type="button"
              aria-pressed={on}
              aria-label={`${l.spoken}: ${p.counts[l.level]} stocks`}
              onClick={() => p.onMinPass(l.level)}
              className={`flex items-center justify-center gap-1 rounded-lg text-[14px] font-medium transition-colors ${
                on ? 'bg-slate-50 text-slate-950' : 'text-slate-300'
              }`}
            >
              {l.label}
              <span className="tnum text-[12px] text-slate-500">{p.counts[l.level]}</span>
            </button>
          )
        })}
      </div>

      <div className="grid grid-cols-2 gap-2 lg:w-[26rem]">
        <Picker
          label="Pool"
          value={p.pool ?? ALL_POOLS}
          options={POOL_OPTIONS}
          onChange={(v) => p.onPool(v === ALL_POOLS ? null : (v as IndexName))}
        />
        <Picker label="Sort" value={p.sort} options={SORT_OPTIONS} onChange={p.onSort} />
      </div>
    </div>
  )
}
