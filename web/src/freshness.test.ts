import { describe, expect, it } from 'vitest'
import { freshness, isNewerDataset, nextScreenRun, relativeAge } from './freshness'

const HOUR = 3_600_000
const DAY = 24 * HOUR

describe('relativeAge', () => {
  it('rounds down into the largest whole unit', () => {
    expect(relativeAge(20_000)).toBe('just now')
    expect(relativeAge(5 * 60_000)).toBe('5 min ago')
    expect(relativeAge(3 * HOUR + 59 * 60_000)).toBe('3 hr ago')
    expect(relativeAge(DAY)).toBe('1 day ago')
    expect(relativeAge(9 * DAY)).toBe('9 days ago')
  })
  it('never claims a future timestamp is old', () => {
    expect(relativeAge(-5 * 60_000)).toBe('just now')
  })
})

describe('freshness', () => {
  const now = new Date('2026-09-28T13:00:00Z') // Monday

  it('is null for a missing or unparseable timestamp — never a fabricated date', () => {
    expect(freshness(undefined, now)).toBeNull()
    expect(freshness('not a date', now)).toBeNull()
  })

  it("does not flag Friday's data as stale on Monday morning", () => {
    const f = freshness('2026-09-25T15:59:05Z', now)!
    expect(f.stale).toBe(false)
    expect(f.relative).toBe('2 days ago')
  })

  it('flags data older than a week (five missed weekday runs)', () => {
    expect(freshness(new Date(now.getTime() - 7 * DAY - HOUR).toISOString(), now)!.stale).toBe(true)
    expect(freshness(new Date(now.getTime() - 7 * DAY + HOUR).toISOString(), now)!.stale).toBe(false)
  })
})

describe('nextScreenRun (cron 0 11 * * 1-5, UTC)', () => {
  it('is later the same weekday when before 11:00 UTC', () => {
    expect(nextScreenRun(new Date('2026-09-28T08:00:00Z')).toISOString()).toBe('2026-09-28T11:00:00.000Z')
  })
  it('rolls to the next day once 11:00 UTC has passed', () => {
    expect(nextScreenRun(new Date('2026-09-28T11:00:00Z')).toISOString()).toBe('2026-09-29T11:00:00.000Z')
  })
  it('skips the weekend', () => {
    expect(nextScreenRun(new Date('2026-09-25T12:00:00Z')).toISOString()).toBe('2026-09-28T11:00:00.000Z') // Fri -> Mon
    expect(nextScreenRun(new Date('2026-09-26T09:00:00Z')).toISOString()).toBe('2026-09-28T11:00:00.000Z') // Sat -> Mon
  })
})

describe('isNewerDataset', () => {
  it('only reports a strictly newer, parseable timestamp', () => {
    expect(isNewerDataset('2026-09-25T15:59:05Z', '2026-09-28T15:00:00Z')).toBe(true)
    expect(isNewerDataset('2026-09-25T15:59:05Z', '2026-09-25T15:59:05Z')).toBe(false)
    expect(isNewerDataset('2026-09-25T15:59:05Z', '2026-09-24T15:00:00Z')).toBe(false)
    expect(isNewerDataset('2026-09-25T15:59:05Z', 'garbage')).toBe(false)
    expect(isNewerDataset(undefined, '2026-09-25T15:59:05Z')).toBe(true)
  })
})
