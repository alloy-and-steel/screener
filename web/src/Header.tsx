import { useEffect, useRef, useState } from 'react'
import { freshness, nextScreenRun, relativeAge } from './freshness'
import { useNow, useOnline } from './useDataset'
import { Logo } from './Logo'

const DATE_TIME: Intl.DateTimeFormatOptions = { weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }

interface HeaderProps {
  generatedAt?: string
  checking: boolean
  lastChecked: Date | null
  checkFailed: boolean
  onCheck: () => void
  onMethodology: () => void
}

// Always-visible answer to "how old is this?": a live relative age, amber once
// the pipeline has missed a week of runs, grey with an offline note when the
// numbers came from the service worker's cached copy.
function FreshnessChip({ generatedAt, checking, lastChecked, checkFailed, onCheck }: Omit<HeaderProps, 'onMethodology'>) {
  const now = useNow()
  const online = useOnline()
  const [open, setOpen] = useState(false)
  const box = useRef<HTMLDivElement>(null)
  // Outside-tap / Escape close. Not a fixed backdrop: the header's
  // backdrop-filter makes it the containing block for `fixed` children, so a
  // full-screen overlay inside it would only cover the header.
  useEffect(() => {
    if (!open) return
    const onDown = (e: PointerEvent) => {
      if (!box.current?.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('pointerdown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('pointerdown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])
  const f = freshness(generatedAt, now)
  const tone = !f ? 'bg-slate-500' : f.stale ? 'bg-amber-400' : 'bg-emerald-400'
  const text = !f ? 'text-slate-400' : f.stale ? 'text-amber-200' : 'text-slate-200'

  return (
    <div className="relative" ref={box}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className={`flex h-11 items-center gap-2 rounded-full bg-white/[0.04] pl-3.5 pr-4 text-[14px] ring-1 ring-inset ring-white/10 transition hover:bg-white/[0.08] ${text}`}
      >
        <span className={`size-2 shrink-0 rounded-full ${online ? tone : 'bg-slate-500'}`} aria-hidden />
        {!online ? 'Offline · ' : ''}
        {f ? `Updated ${f.relative}` : 'Data date unknown'}
        {f?.stale ? <span className="font-semibold">· stale</span> : null}
      </button>

      {open ? (
        <div className="absolute right-0 z-50 mt-2 w-72 rounded-2xl border border-white/10 bg-surface-2/95 p-4 text-sm shadow-2xl shadow-black/50 backdrop-blur-xl">
          <dl className="space-y-2">
            <div className="flex justify-between gap-3">
              <dt className="text-slate-400">Screened</dt>
              <dd className="tnum text-right text-slate-100">{f ? f.generatedAt.toLocaleString(undefined, DATE_TIME) : '—'}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-slate-400">Next screen</dt>
              <dd className="tnum text-right text-slate-100">{nextScreenRun(now).toLocaleString(undefined, DATE_TIME)}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-slate-400">Last checked</dt>
              <dd className={`tnum text-right ${checkFailed ? 'text-amber-300' : 'text-slate-100'}`}>
                {checkFailed ? 'failed · ' : ''}
                {lastChecked ? relativeAge(now.getTime() - lastChecked.getTime()) : '—'}
              </dd>
            </div>
          </dl>
          <p className="mt-3 text-xs leading-relaxed text-slate-500">
            {f?.stale
              ? 'Over a week old — the daily screen has not published since. Treat prices and verdicts with care.'
              : 'Screens run every weekday morning (US); new data appears here once the run finishes.'}
            {!online ? ' You are offline, so this is the last copy saved on this device.' : ''}
          </p>
          <button
            type="button"
            onClick={onCheck}
            disabled={checking || !online}
            className="mt-3 h-11 w-full rounded-xl bg-white/[0.06] text-[14px] font-medium text-slate-100 ring-1 ring-inset ring-white/10 transition hover:bg-white/10 disabled:opacity-50"
          >
            {checking ? 'Checking…' : 'Check for new data'}
          </button>
        </div>
      ) : null}
    </div>
  )
}

export default function Header(props: HeaderProps) {
  return (
    <header className="sticky top-0 z-30 border-b border-white/[0.06] bg-canvas/75 pt-[env(safe-area-inset-top)] backdrop-blur-xl">
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-3 px-4 sm:px-6">
        <div className="flex items-center gap-2.5">
          <Logo className="size-5 text-emerald-400" />
          <span className="hidden text-[15px] font-semibold tracking-tight text-slate-50 min-[400px]:inline">Screener3000</span>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <FreshnessChip
            generatedAt={props.generatedAt}
            checking={props.checking}
            lastChecked={props.lastChecked}
            checkFailed={props.checkFailed}
            onCheck={props.onCheck}
          />
          <button
            type="button"
            onClick={props.onMethodology}
            aria-label="How the screens work"
            title="How the screens work"
            className="grid size-11 shrink-0 place-items-center rounded-full bg-white/[0.04] text-slate-300 ring-1 ring-inset ring-white/10 transition hover:bg-white/[0.08] hover:text-slate-50"
          >
            <svg viewBox="0 0 20 20" className="size-4" fill="currentColor" aria-hidden>
              <path d="M10 2a8 8 0 1 0 0 16 8 8 0 0 0 0-16Zm0 3.5a1.1 1.1 0 1 1 0 2.2 1.1 1.1 0 0 1 0-2.2ZM11.2 14.5H8.8v-1.2h.6V10h-.6V8.8h1.8v4.5h.6v1.2Z" />
            </svg>
          </button>
        </div>
      </div>
    </header>
  )
}
