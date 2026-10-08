import { describe, expect, it } from 'vitest'
import { combinedVerdict, passesAll, verdictLines, wealthmaticaVerdict } from './score'
import { MESSAGES } from './messages'
import type { Row, Wealthmatica } from './types'

const EN = MESSAGES.en
const ZH = MESSAGES['zh-TW']

const az = (tier: 'a' | 'c') => ({ score: 50, tier, passes: 0, total: 6, parts: {}, pctiles: {} }) as unknown as Row['azqato']

const check = (value: number | null, pass: boolean | null) => ({ value, pass })

// A bank-like row: both margins N/A, 4 of the 5 that apply pass (4 needed).
const WM: Wealthmatica = {
  checks: {
    revGrowth: check(18.2, true),
    revAccel: check(-3.1, false),
    fcf: check(12.0, true),
    fcfSbc: check(8.0, true),
    grossMargin: check(null, null),
    opMargin: check(null, null),
    eps: check(4.2, true),
  },
  passed: 4,
  applicable: 5,
  pass: true,
}

const ALL3 = { azqato: az('a'), Lynch_Lynch_Status: 'Buy', Graham_Graham_Status: 'Buy' }

describe('wealthmaticaVerdict', () => {
  it('passes on the backend verdict and shows the count over the checks that apply', () => {
    const v = wealthmaticaVerdict({ Ticker: 'X', wealthmatica: WM } as Row, EN)
    expect(v.pass).toBe(true)
    expect(v.label).toBe('Pass')
    expect(verdictLines('Wealthmatica', { Ticker: 'X', wealthmatica: WM } as Row, EN)[0].label).toBe('Pass · 4/5')
    expect(v.drivers.map((d) => d.label)).toEqual([
      'Revenue growth',
      'Growth vs prior year',
      'FCF margin',
      'FCF − stock comp',
      'Gross margin',
      'Operating margin',
      'EPS',
    ])
  })

  it('marks an N/A check with a dash and no tone, never as a fail', () => {
    const v = wealthmaticaVerdict({ Ticker: 'X', wealthmatica: WM } as Row, EN)
    const gm = v.drivers.find((d) => d.label === 'Gross margin')
    expect(gm).toEqual({ label: 'Gross margin', value: '—', tone: 'slate' })
    expect(v.drivers.find((d) => d.label === 'Growth vs prior year')).toEqual({
      label: 'Growth vs prior year',
      value: '-3.1 pts',
      tone: 'red',
    })
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
    expect(verdictLines('Wealthmatica', r, ZH)[0].label).toBe('通過 · 4/5')
    expect(verdictLines('Lynch', r, ZH)[0].label).toBe('強力買進')
    expect(wealthmaticaVerdict(r, ZH).drivers[0]).toEqual({ label: '營收成長', value: '+18.2%', tone: 'green' })
    expect(combinedVerdict(r).passCount).toBe(2)
  })

  it('says N/A in Chinese, still without a count when the checklist could not judge', () => {
    const r = { Ticker: 'X', wealthmatica: { ...WM, pass: null } } as Row
    expect(verdictLines('Wealthmatica', r, ZH)[0].label).toBe('不適用')
    expect(verdictLines('Graham', r, ZH).map((l) => l.label)).toEqual(['不適用', '不適用'])
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
