import { describe, expect, it } from 'vitest'
import { dataNote, sectorLabel } from './dataText'
import screenerPy from '../../stock_screener.py?raw'

describe('dataNote', () => {
  it('passes English through untouched', () => {
    expect(dataNote('Non-positive EPS; Growth unavailable', 'en')).toBe('Non-positive EPS; Growth unavailable')
  })

  it('translates each "; "-joined phrase, numbers included', () => {
    expect(dataNote('Non-positive EPS; Non-positive growth (-3.4%)', 'zh-TW')).toBe('EPS 非正值；成長率非正值（-3.4%）')
    expect(dataNote('WACC guardrail applied (5.10% to 7.25%)', 'zh-TW')).toBe('WACC 已套用下限（5.10% 調至 7.25%）')
    expect(dataNote('Missing total debt, base FCFF', 'zh-TW')).toBe('缺少總負債、基期 FCFF')
  })

  it('leaves a phrase it does not know in English rather than dropping it', () => {
    expect(dataNote('Negative FCF; Some brand-new warning', 'zh-TW')).toBe('自由現金流為負；Some brand-new warning')
  })
})

describe('sectorLabel', () => {
  it('names every sector the data carries in Chinese, and keeps an unknown one as is', () => {
    expect(sectorLabel('Technology', 'zh-TW')).toBe('科技')
    expect(sectorLabel('Financial Services', 'zh-TW')).toBe('金融服務')
    expect(sectorLabel('Technology', 'en')).toBe('Technology')
    expect(sectorLabel('Space Mining', 'zh-TW')).toBe('Space Mining')
  })
})

// The screener writes these phrases into results.json. A phrase added there
// without a translation here fails this test instead of quietly showing up in
// English on the Chinese site.
describe('every phrase stock_screener.py can emit has a translation', () => {
  const src = screenerPy
  const literals = (s: string) => [...s.matchAll(/f?"((?:[^"\\]|\\.)*)"/g)].map((m) => m[1].replace(/\{[^}]*\}/g, '1.0'))

  const phrases = new Set<string>()
  for (const line of src.split('\n')) {
    if (/\b(?:valuation_warnings|dcf_assumption_warnings|reasons)\.append\(/.test(line)) literals(line).forEach((p) => phrases.add(p))
    // Missing inputs are emitted as one "Missing a, b" phrase.
    if (/\bdcf_missing_inputs\.append\(/.test(line)) literals(line).forEach((p) => phrases.add(`Missing ${p}`))
    if (/row\["(?:Error|DCF_Method)"\] =|"Error": f?"/.test(line)) literals(line.replace(/^.*?(?:\] =|"Error":)/, '')).forEach((p) => phrases.add(p))
  }
  const wacc = src.match(/wacc_inputs = \{([^}]*)\}/)
  expect(wacc).not.toBeNull()
  for (const m of wacc![1].matchAll(/"([^"]+)":/g)) phrases.add(`Missing ${m[1]}`)

  it('finds the phrases (a guard on this test, not the app)', () => {
    expect(phrases.size).toBeGreaterThanOrEqual(25)
  })

  it.each([...phrases])('%s', (phrase) => {
    for (const piece of phrase.split('; ')) expect(dataNote(piece, 'zh-TW')).not.toBe(piece)
  })
})
