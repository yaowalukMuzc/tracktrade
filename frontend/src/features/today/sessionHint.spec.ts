import { describe, expect, it } from 'vitest'
import { localClock, sessionHint, splitMinutes } from './sessionHint'

// 2026: UK clocks go back on Sun 25 Oct, US clocks on Sun 1 Nov — the week in between is the DST gap.
const at = (iso: string) => new Date(iso)

describe('localClock', () => {
  it('follows each market timezone incl. DST', () => {
    expect(localClock(at('2026-10-21T07:00:00Z'), 'Europe/London')).toEqual({ weekday: 'Wed', minutes: 8 * 60 }) // BST
    expect(localClock(at('2026-10-28T07:00:00Z'), 'Europe/London')).toEqual({ weekday: 'Wed', minutes: 7 * 60 }) // GMT
    expect(localClock(at('2026-10-28T12:00:00Z'), 'America/New_York').minutes).toBe(8 * 60) // EDT
    expect(localClock(at('2026-11-04T12:00:00Z'), 'America/New_York').minutes).toBe(7 * 60) // EST
  })
})

describe('sessionHint', () => {
  it('announces London one hour before the open (GMT)', () => {
    expect(sessionHint(at('2026-10-28T07:00:00Z'))).toEqual({ kind: 'opensIn', session: 'london', minutes: 60 })
  })

  it('says London is open at the same UTC time a week earlier (BST)', () => {
    expect(sessionHint(at('2026-10-21T07:00:00Z'))).toEqual({ kind: 'open', session: 'london' })
  })

  it('prefers an upcoming opening over an open session', () => {
    expect(sessionHint(at('2026-10-28T10:30:00Z'))).toEqual({ kind: 'opensIn', session: 'new_york', minutes: 90 })
    // New York on EST a week later: opens 13:00 UTC.
    expect(sessionHint(at('2026-11-04T10:30:00Z'))).toEqual({ kind: 'opensIn', session: 'new_york', minutes: 150 })
  })

  it('ignores openings beyond the window and shows the open session', () => {
    expect(sessionHint(at('2026-10-28T20:00:00Z'))).toEqual({ kind: 'open', session: 'new_york' })
  })

  it('rounds partial minutes up', () => {
    expect(sessionHint(at('2026-10-28T07:59:30Z'))).toEqual({ kind: 'opensIn', session: 'london', minutes: 1 })
  })

  it('announces Tokyo on Sunday evening (UTC) because it is Monday in Tokyo', () => {
    expect(sessionHint(at('2026-11-01T23:30:00Z'))).toEqual({ kind: 'opensIn', session: 'tokyo', minutes: 30 })
  })

  it('returns null on the weekend and late at night', () => {
    expect(sessionHint(at('2026-10-31T07:00:00Z'))).toBeNull() // Saturday
    expect(sessionHint(at('2026-10-28T22:30:00Z'))).toEqual({ kind: 'opensIn', session: 'tokyo', minutes: 90 })
    expect(sessionHint(at('2026-10-30T22:30:00Z'))).toBeNull() // Friday night: NY closed, Tokyo is on Saturday
  })
})

describe('splitMinutes', () => {
  it('splits into hours and minutes', () => {
    expect(splitMinutes(60)).toEqual({ h: 1, m: 0 })
    expect(splitMinutes(95)).toEqual({ h: 1, m: 35 })
    expect(splitMinutes(45)).toEqual({ h: 0, m: 45 })
  })
})
