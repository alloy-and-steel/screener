import { useCallback, useEffect, useRef, useState } from 'react'
import { isNewerDataset } from './freshness'
import type { Dataset } from './types'

const DATA_URL = `${import.meta.env.BASE_URL}data/results.json`
// The screen publishes at most once a weekday; a half-hourly look (plus one
// whenever the tab comes back into view) finds it without hammering Pages.
const POLL_MS = 30 * 60_000

export type LoadState = { status: 'loading' } | { status: 'error'; message: string } | { status: 'ready'; data: Dataset }

// `no-cache` revalidates against Pages' ETag every time (a 304 when nothing
// changed) — and, unlike a `?v=` cache-buster, keeps one stable URL so the
// service worker's offline copy is found again.
async function fetchDataset(): Promise<Dataset> {
  const r = await fetch(DATA_URL, { cache: 'no-cache' })
  if (!r.ok) throw new Error(`HTTP ${r.status} fetching results.json`)
  return (await r.json()) as Dataset
}

export function useDataset() {
  const [load, setLoad] = useState<LoadState>({ status: 'loading' })
  // A newer dataset found in the background. Held, not swapped in, so the
  // grid never reshuffles under someone mid-read — they tap to load it.
  const [pending, setPending] = useState<Dataset | null>(null)
  const [checking, setChecking] = useState(false)
  const [lastChecked, setLastChecked] = useState<Date | null>(null)
  const [checkFailed, setCheckFailed] = useState(false)
  const current = useRef<string | undefined>(undefined)
  // A dataset the user waved away isn't re-offered by the background poll;
  // an explicit "Check for new data" still shows it.
  const dismissed = useRef<string | undefined>(undefined)

  const reload = useCallback(() => {
    setLoad({ status: 'loading' })
    fetchDataset()
      .then((data) => {
        current.current = data.generated_at
        setPending(null)
        setLastChecked(new Date())
        setLoad({ status: 'ready', data })
      })
      .catch((e: unknown) => setLoad({ status: 'error', message: e instanceof Error ? e.message : String(e) }))
  }, [])

  const check = useCallback(async (manual = false) => {
    if (current.current === undefined) return
    setChecking(true)
    try {
      const next = await fetchDataset()
      setLastChecked(new Date())
      setCheckFailed(false)
      if (isNewerDataset(current.current, next.generated_at) && (manual || next.generated_at !== dismissed.current)) setPending(next)
    } catch (e) {
      // The loaded data stays (its real age is still on the chip); the
      // popover says the last check failed.
      console.warn('Background data check failed:', e)
      setCheckFailed(true)
    } finally {
      setChecking(false)
    }
  }, [])

  const applyPending = useCallback(() => {
    if (!pending) return
    current.current = pending.generated_at
    setLoad({ status: 'ready', data: pending })
    setPending(null)
  }, [pending])

  const dismissPending = useCallback(() => {
    dismissed.current = pending?.generated_at
    setPending(null)
  }, [pending])

  useEffect(reload, [reload])

  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState === 'visible') void check()
    }
    const id = window.setInterval(onVisible, POLL_MS)
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      window.clearInterval(id)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [check])

  return { load, reload, pending, applyPending, dismissPending, check, checking, lastChecked, checkFailed }
}

// Re-renders the caller every `ms` so relative times ("3 hr ago") stay true.
export function useNow(ms = 60_000): Date {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), ms)
    return () => window.clearInterval(id)
  }, [ms])
  return now
}

export function useOnline(): boolean {
  const [online, setOnline] = useState(() => navigator.onLine)
  useEffect(() => {
    const up = () => setOnline(true)
    const down = () => setOnline(false)
    window.addEventListener('online', up)
    window.addEventListener('offline', down)
    return () => {
      window.removeEventListener('online', up)
      window.removeEventListener('offline', down)
    }
  }, [])
  return online
}
