import { describe, expect, it } from 'vitest'
import { DEFAULT_PREFS, parsePrefs } from './prefs'

describe('parsePrefs', () => {
  it('opens on the all-three short list when nothing is saved', () => {
    expect(parsePrefs(null)).toEqual(DEFAULT_PREFS)
    expect(DEFAULT_PREFS).toEqual({ minPass: 3, pool: null, sort: 'best' })
  })

  it('restores a saved filter, pool and sort', () => {
    expect(parsePrefs(JSON.stringify({ minPass: 1, pool: 'Dow30', sort: 'peg' }))).toEqual({ minPass: 1, pool: 'Dow30', sort: 'peg' })
  })

  it('falls back field by field on anything it does not recognise', () => {
    expect(parsePrefs(JSON.stringify({ minPass: 7, pool: 'FTSE', sort: 'peg' }))).toEqual({ minPass: 3, pool: null, sort: 'peg' })
    expect(parsePrefs(JSON.stringify({ sort: 'toString' }))).toEqual(DEFAULT_PREFS)
    expect(parsePrefs('{not json')).toEqual(DEFAULT_PREFS)
    expect(parsePrefs('[1,2]')).toEqual(DEFAULT_PREFS)
  })
})
