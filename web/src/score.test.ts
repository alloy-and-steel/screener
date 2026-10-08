import { describe, expect, it } from 'vitest'
import { combinedVerdict, passesAll, verdictLines, wealthmaticaVerdict } from './score'
import { MESSAGES } from './messages'
import type { Row, Wealthmatica } from './types'

const EN = MESSAGES.en
const ZH = MESSAGES['zh-TW']

const az = (tier: 'a' | 'c') => ({ score: 50, tier, passes: 0, total: 6, parts: {}, pctiles: {} }) as unknown as Row['azqato']

const check = (value: number | null, pass: boolean | null) => ({ value, pass })

// A bank-like row: three checks N/A, 5 of the 6 that apply pass (5 needed).
const WM: Wealthmatica = {
  checks: {
    revGrowth: check(18.2, true),
    revAccel: check(3.1, true),
    fcf: check(12.0, true),
    fcfSbc: check(null, null),
    shareChange: check(-1.5, true),
    grossMargin: check(null, null),
    opMargin: check(null, null),
    eps: check(4.2, true),
    cashDebt: check(-2.0e9, false),
  },
  passed: 5,
  applicable: 6,
  pass: true,
}

const ALL3 = { azqato: az('a'), Lynch_Lynch_Status: 'Buy', Graham_Graham_Status: 'Buy' }

describe('wealthmaticaVerdict', () => {
  it('passes on the backend verdict and shows the count over the checks that apply', () => {
    const v = wealthmaticaVerdict({ Ticker: 'X', wealthmatica: WM } as Row, EN)
    expect(v.pass).toBe(true)
    expect(v.label).toBe('Pass')
    expect(verdictLines('Wealthmatica', { Ticker: 'X', wealthmatica: WM } as Row, EN)[0].label).toBe('Pass · 5/6')
    expect(v.drivers.map((d) => d.label)).toEqual([
      'Revenue growth',
      'Growth vs prior year',
      'FCF margin',
      'FCF − stock comp',
      'Share count',
      'Gross margin',
      'Operating margin',
      'EPS',
      'Cash − debt',
    ])
  })

  it('marks an N/A check with a dash and no tone, never as a fail', () => {
    const v = wealthmaticaVerdict({ Ticker: 'X', wealthmatica: WM } as Row, EN)
    const sbc = v.drivers.find((d) => d.label === 'FCF − stock comp')
    expect(sbc).toEqual({ label: 'FCF − stock comp', value: '—', tone: 'slate' })
    expect(v.drivers.find((d) => d.label === 'Cash − debt')).toEqual({ label: 'Cash − debt', value: '−$2.00B', tone: 'red' })
  })

  it('fails on a failing verdict, and is N/A with no verdict or no block', () => {
    expect(wealthmaticaVerdict({ Ticker: 'X', wealthmatica: { ...WM, pass: false } } as Row, EN).label).toBe('Fail')
    for (const r of [{ Ticker: 'X', wealthmatica: { ...WM, pass: null } }, { Ticker: 'X' }] as Row[]) {
      const v = wealthmaticaVerdict(r, EN)
      expect([v.label, v.pass]).toEqual(['N/A', false])
    }
  })
})

describe('in Chinese', () => {
  it('translates the grade and the drivers, not the verdict', () => {
    const r = { Ticker: 'X', wealthmatica: WM, Lynch_Lynch_Status: 'Strong Buy' } as Row
    expect(verdictLines('Wealthmatica', r, ZH)[0].label).toBe('通過 · 5/6')
    expect(verdictLines('Lynch', r, ZH)[0].label).toBe('強力買進')
    expect(wealthmaticaVerdict(r, ZH).drivers.at(-1)).toEqual({ label: '現金 − 負債', value: '−$20億', tone: 'red' })
    expect(combinedVerdict(r).passCount).toBe(2)
  })
})

describe('the four-system gate', () => {
  it('needs all four for "passes all" and the green tone', () => {
    const four = { Ticker: 'X', ...ALL3, wealthmatica: WM } as Row
    const three = { Ticker: 'Y', ...ALL3, wealthmatica: { ...WM, pass: false } } as Row
    expect([passesAll(four), combinedVerdict(four)]).toEqual([true, { passCount: 4, tone: 'green' }])
    expect([passesAll(three), combinedVerdict(three)]).toEqual([false, { passCount: 3, tone: 'yellow' }])
  })
})
