import type { Row } from './types'
import { changeSince } from './selection'

// What each method says the stock is worth, side by side. Deliberately never
// blended into one number: the three routinely disagree by 2x or more, and that
// spread is information. Lynch is the PEGY = 1 value (EPS x (growth + yield))
// that his grade is measured against; Graham the rate-adjusted 1974 formula;
// DCF the screen-grade FCFF/WACC value with its stressed-to-optimistic range.
export type FairMethod = 'Lynch' | 'Graham' | 'DCF'

export interface FairPrice {
  method: FairMethod
  value: number | null
  vsPrice: number | null // percent from today's price to the fair price
  range: { low: number; high: number } | null
}

const val = (v: number | null | undefined): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null)

function estimate(method: FairMethod, v: number | null | undefined, price: number | null | undefined, range: FairPrice['range'] = null): FairPrice {
  const value = val(v)
  return { method, value, vsPrice: value === null ? null : changeSince(price, value), range: value === null ? null : range }
}

export function fairPrices(row: Row): FairPrice[] {
  const lo = val(row.DCF_Value_Low)
  const hi = val(row.DCF_Value_High)
  return [
    estimate('Lynch', row.Lynch_FV_GplusD, row.Price),
    estimate('Graham', row.Graham_Graham_FV, row.Price),
    estimate('DCF', row.DCF_Intrinsic_Value, row.Price, lo !== null && hi !== null ? { low: lo, high: hi } : null),
  ]
}
