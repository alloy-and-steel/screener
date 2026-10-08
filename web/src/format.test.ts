import { describe, expect, it } from 'vitest'
import { capB, compactUsd } from './format'

// Chinese counts in 萬 (1e4), 億 (1e8) and 兆 (1e12), not thousands: $268B is
// 2680億, so a wrong power of ten here misstates a company's size tenfold.
describe('money magnitudes', () => {
  it('keeps the K/M/B/T convention in English', () => {
    expect(capB(4920, 'en')).toBe('$4.92T')
    expect(capB(268, 'en')).toBe('$268B')
    expect(capB(1.23, 'en')).toBe('$1.2B')
    expect(compactUsd(2.0e9, 'en')).toBe('2.00B')
  })

  it('uses 億 and 兆 in Chinese, at the same precision', () => {
    expect(capB(4920, 'zh-TW')).toBe('$4.92兆')
    expect(capB(268, 'zh-TW')).toBe('$2680億')
    expect(capB(1.23, 'zh-TW')).toBe('$12.3億')
    expect(compactUsd(2.0e9, 'zh-TW')).toBe('20億')
    expect(compactUsd(-1.5e8, 'zh-TW')).toBe('-1.5億')
    expect(compactUsd(12345, 'zh-TW')).toBe('1.23萬')
  })

  it('is a dash, never zero, when the value is missing', () => {
    expect(capB(null, 'zh-TW')).toBe('—')
    expect(compactUsd(undefined, 'zh-TW')).toBe('—')
  })
})
