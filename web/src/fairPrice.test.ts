import { describe, expect, it } from 'vitest'
import { fairPrices } from './fairPrice'
import type { Row } from './types'

// AAPL as published 2026-10-07.
const aapl: Row = {
  Ticker: 'AAPL',
  Price: 336.04,
  Lynch_FV_GplusD: 52.98,
  Graham_Graham_FV: 120.27,
  DCF_Intrinsic_Value: 87.26,
  DCF_Value_Low: 70.02,
  DCF_Value_High: 104.98,
}

describe('fairPrices', () => {
  it('lists the Lynch, Graham and DCF fair prices with the DCF range', () => {
    const fp = fairPrices(aapl)
    expect(fp.map((f) => [f.method, f.value])).toEqual([
      ['Lynch', 52.98],
      ['Graham', 120.27],
      ['DCF', 87.26],
    ])
    expect(fp[2].range).toEqual({ low: 70.02, high: 104.98 })
    expect(fp[0].range).toBeNull()
  })

  it('gives each one as a percent above (+) or below (−) today’s price', () => {
    const [lynch, graham] = fairPrices({ Ticker: 'X', Price: 50, Lynch_FV_GplusD: 75, Graham_Graham_FV: 40 })
    expect(lynch.vsPrice).toBeCloseTo(50)
    expect(graham.vsPrice).toBeCloseTo(-20)
  })

  it('keeps a method it could not value as null — never 0 — with no gap', () => {
    const [lynch, graham, dcf] = fairPrices({ Ticker: 'JPM', Price: 329.07, Graham_Graham_FV: 576.18 })
    expect(lynch).toEqual({ method: 'Lynch', value: null, vsPrice: null, range: null })
    expect(graham.value).toBe(576.18)
    expect(dcf).toEqual({ method: 'DCF', value: null, vsPrice: null, range: null })
  })

  it('has no gap when there is no price', () => {
    expect(fairPrices({ Ticker: 'X', Graham_Graham_FV: 40 })[1].vsPrice).toBeNull()
  })
})
