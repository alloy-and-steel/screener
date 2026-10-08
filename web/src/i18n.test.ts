import { describe, expect, it } from 'vitest'
import { detectLang } from './i18n'

describe('detectLang', () => {
  it('keeps a choice the visitor made on this device', () => {
    expect(detectLang('en', ['zh-TW'])).toBe('en')
    expect(detectLang('zh-TW', ['en-US'])).toBe('zh-TW')
  })

  it('otherwise follows the first English or Chinese language the browser prefers', () => {
    expect(detectLang(null, ['zh-TW', 'en'])).toBe('zh-TW')
    expect(detectLang(null, ['zh-Hant-HK'])).toBe('zh-TW')
    expect(detectLang(null, ['ja-JP', 'zh-TW', 'en'])).toBe('zh-TW')
    expect(detectLang(null, ['en-GB', 'zh-TW'])).toBe('en')
    // Simplified-Chinese readers get Traditional too: closer to them than English.
    expect(detectLang(null, ['zh-CN'])).toBe('zh-TW')
  })

  it('falls back to English for anything else, including a stale saved value', () => {
    expect(detectLang(null, ['fr-FR', 'de'])).toBe('en')
    expect(detectLang(null, [])).toBe('en')
    expect(detectLang('klingon', ['fr'])).toBe('en')
  })
})
