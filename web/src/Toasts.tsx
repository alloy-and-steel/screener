import { useEffect } from 'react'
import { useRegisterSW } from 'virtual:pwa-register/react'

// Look for a new deploy hourly and whenever the app is brought back to the
// front — an installed PWA can stay open for days without a navigation.
const SW_CHECK_MS = 60 * 60_000

function Toast({ children, onDismiss }: { children: React.ReactNode; onDismiss?: () => void }) {
  return (
    <div
      role="status"
      className="toast-in pointer-events-auto flex w-full max-w-md items-center gap-3 rounded-2xl border border-white/10 bg-surface-3/90 py-2.5 pl-4 pr-2.5 text-sm text-slate-100 shadow-2xl shadow-black/60 backdrop-blur-xl"
    >
      <div className="min-w-0 flex-1">{children}</div>
      {onDismiss ? (
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Dismiss"
          className="grid size-8 place-items-center rounded-full text-slate-400 hover:bg-white/10 hover:text-slate-100"
        >
          ✕
        </button>
      ) : null}
    </div>
  )
}

function Action({ onClick, children }: { onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="h-8 shrink-0 rounded-full bg-emerald-400 px-3.5 text-[13px] font-semibold text-emerald-950 transition hover:bg-emerald-300"
    >
      {children}
    </button>
  )
}

interface ToastsProps {
  pendingAt?: string // generated_at of newer data found in the background
  onLoadPending: () => void
  onDismissPending: () => void
}

export default function Toasts({ pendingAt, onLoadPending, onDismissPending }: ToastsProps) {
  const {
    needRefresh: [needRefresh, setNeedRefresh],
    offlineReady: [offlineReady, setOfflineReady],
    updateServiceWorker,
  } = useRegisterSW({
    onRegisteredSW(_url, reg) {
      if (!reg) return
      const check = () => {
        if (document.visibilityState === 'visible' && navigator.onLine) void reg.update()
      }
      window.setInterval(check, SW_CHECK_MS)
      document.addEventListener('visibilitychange', check)
    },
    onRegisterError(e) {
      console.error('Service worker registration failed:', e)
    },
  })

  useEffect(() => {
    if (!offlineReady) return
    const id = window.setTimeout(() => setOfflineReady(false), 4000)
    return () => window.clearTimeout(id)
  }, [offlineReady, setOfflineReady])

  const pendingLabel = pendingAt
    ? new Date(pendingAt).toLocaleString(undefined, { weekday: 'short', hour: 'numeric', minute: '2-digit' })
    : ''

  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-0 z-50 flex flex-col items-center gap-2 px-4 pb-[calc(1rem+env(safe-area-inset-bottom))]">
      {needRefresh ? (
        <Toast onDismiss={() => setNeedRefresh(false)}>
          <div className="flex items-center justify-between gap-3">
            <span>A new version of the app is ready.</span>
            <Action onClick={() => void updateServiceWorker(true)}>Update</Action>
          </div>
        </Toast>
      ) : null}
      {pendingAt ? (
        <Toast onDismiss={onDismissPending}>
          <div className="flex items-center justify-between gap-3">
            <span>
              Fresh data from <span className="font-semibold">{pendingLabel}</span>
            </span>
            <Action onClick={onLoadPending}>Load</Action>
          </div>
        </Toast>
      ) : null}
      {offlineReady ? <Toast>Saved for offline use.</Toast> : null}
    </div>
  )
}
