// How old the published dataset is, and when the next one is due. Pure — `now`
// is always passed in so the rules are testable and the UI can re-render on a
// clock tick.

const MINUTE = 60_000
const HOUR = 60 * MINUTE
const DAY = 24 * HOUR

// A week, not 3 days (azqato upstream learned the same lesson at v3.37.2).
// The screen runs on a WEEKDAY cron, so Friday's data is legitimately ~3 days
// old by Monday morning. Only a genuinely stuck pipeline (5 consecutive missed
// runs) is worth flagging; the exact date is always shown alongside either way.
export const STALE_AFTER_MS = 7 * DAY

// Mirrors screen.yml's `cron: "0 11 * * 1-5"` (UTC). Change both together.
const SCREEN_HOUR_UTC = 11
const SCREEN_DAYS_UTC = new Set([1, 2, 3, 4, 5])

export interface Freshness {
  generatedAt: Date
  ageMs: number
  relative: string
  stale: boolean
}

export function relativeAge(ms: number): string {
  if (ms < MINUTE) return 'just now'
  if (ms < HOUR) return `${Math.floor(ms / MINUTE)} min ago`
  if (ms < DAY) return `${Math.floor(ms / HOUR)} hr ago`
  const d = Math.floor(ms / DAY)
  return `${d} day${d === 1 ? '' : 's'} ago`
}

function parse(iso: string | undefined): Date | null {
  if (!iso) return null
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? null : d
}

export function freshness(generatedAt: string | undefined, now: Date): Freshness | null {
  const dt = parse(generatedAt)
  if (!dt) return null
  const ageMs = now.getTime() - dt.getTime()
  return { generatedAt: dt, ageMs, relative: relativeAge(ageMs), stale: ageMs > STALE_AFTER_MS }
}

// When the cron next STARTS a screen. Fresh data lands once that run and the
// deploy it triggers finish, so this is "no earlier than", not an ETA.
export function nextScreenRun(now: Date): Date {
  const t = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate(), SCREEN_HOUR_UTC))
  while (t.getTime() <= now.getTime() || !SCREEN_DAYS_UTC.has(t.getUTCDay())) t.setUTCDate(t.getUTCDate() + 1)
  return t
}

// True when `candidate` is a real timestamp strictly after `current` — the
// only condition under which a background re-fetch is offered to the user.
export function isNewerDataset(current: string | undefined, candidate: string | undefined): boolean {
  const next = parse(candidate)
  if (!next) return false
  const cur = parse(current)
  return !cur || next.getTime() > cur.getTime()
}
