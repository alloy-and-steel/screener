// Which language the app speaks, and the catalog for it. English is the
// source catalog; Traditional Chinese (Taiwan) mirrors it key for key, and the
// type system refuses a catalog with a key missing.

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { MESSAGES, type Messages } from './messages'

export const LANGS = ['en', 'zh-TW'] as const
export type Lang = (typeof LANGS)[number]

// Kept apart from the view prefs: bumping their version must not forget this.
export const LANG_KEY = 'screener:lang'

// A choice made on this device wins; otherwise the first English or Chinese
// language the browser lists. Any Chinese gets Traditional — closer to a
// Simplified reader than English is.
export function detectLang(saved: string | null, languages: readonly string[]): Lang {
  if (LANGS.includes(saved as Lang)) return saved as Lang
  for (const l of languages) {
    const base = l.toLowerCase().split('-')[0]
    if (base === 'zh') return 'zh-TW'
    if (base === 'en') return 'en'
  }
  return 'en'
}

function loadLang(): Lang {
  let saved: string | null = null
  try {
    saved = localStorage.getItem(LANG_KEY)
  } catch {
    // storage blocked (private mode): follow the browser
  }
  return detectLang(saved, navigator.languages ?? [navigator.language])
}

interface I18n {
  lang: Lang
  m: Messages
  setLang: (l: Lang) => void
}

const I18nContext = createContext<I18n | null>(null)

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, set] = useState<Lang>(loadLang)
  const setLang = useCallback((l: Lang) => {
    set(l)
    try {
      localStorage.setItem(LANG_KEY, l)
    } catch {
      // Storage full or blocked: the switch still applies, it just won't be remembered.
    }
  }, [])
  useEffect(() => {
    document.documentElement.lang = lang
  }, [lang])
  const value = useMemo(() => ({ lang, m: MESSAGES[lang], setLang }), [lang, setLang])
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n(): I18n {
  const v = useContext(I18nContext)
  if (!v) throw new Error('useI18n outside <I18nProvider>')
  return v
}
