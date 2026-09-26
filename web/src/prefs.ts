// The view a visitor last chose (pass floor, pool, sort), remembered on this
// device. The search box is deliberately not saved: a stale query hiding most
// cards on the next visit reads as missing data.

import { SORTS, type SortKey } from './filters'
import { INDEX_NAMES, type IndexName } from './types'

export const PREFS_KEY = 'screener:view:v1'

export interface Prefs {
  minPass: number
  pool: IndexName | null
  sort: SortKey
}

export const DEFAULT_PREFS: Prefs = { minPass: 3, pool: null, sort: 'best' }

// Anything unrecognised (an old key, a hand-edited value, a pool or sort that
// has since been removed) falls back to the default for that field alone.
export function parsePrefs(raw: string | null): Prefs {
  let v: unknown
  try {
    v = raw ? JSON.parse(raw) : null
  } catch {
    return DEFAULT_PREFS
  }
  if (!v || typeof v !== 'object' || Array.isArray(v)) return DEFAULT_PREFS
  const o = v as Record<string, unknown>
  return {
    minPass: [0, 1, 2, 3].includes(o.minPass as number) ? (o.minPass as number) : DEFAULT_PREFS.minPass,
    pool: INDEX_NAMES.includes(o.pool as IndexName) ? (o.pool as IndexName) : DEFAULT_PREFS.pool,
    sort: typeof o.sort === 'string' && Object.hasOwn(SORTS, o.sort) ? (o.sort as SortKey) : DEFAULT_PREFS.sort,
  }
}

export function loadPrefs(): Prefs {
  try {
    return parsePrefs(localStorage.getItem(PREFS_KEY))
  } catch {
    return DEFAULT_PREFS // storage blocked (private mode): just use defaults
  }
}

export function savePrefs(p: Prefs): void {
  try {
    localStorage.setItem(PREFS_KEY, JSON.stringify(p))
  } catch {
    // Storage full or blocked: the view still works, it just won't be remembered.
  }
}
