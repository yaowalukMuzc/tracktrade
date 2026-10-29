import { describe, expect, it } from 'vitest'
import { distanceToSegment, logicalToTime, measure, rayEnd, snapTime, timeToLogical } from './geometry'

const H1 = 3600
// Friday 20:00 → Monday 00:00 gap like real FX data.
const times = [0, H1, 2 * H1, 3 * H1, 3 * H1 + 52 * H1, 3 * H1 + 53 * H1]

describe('time ↔ logical index', () => {
  it('maps bar times to their index and interpolates between bars', () => {
    expect(times.map((t) => timeToLogical(times, t))).toEqual([0, 1, 2, 3, 4, 5])
    expect(timeToLogical(times, H1 / 2)).toBe(0.5)
    // Inside the weekend gap: proportional within the gap.
    expect(timeToLogical(times, 3 * H1 + 26 * H1)).toBe(3.5)
  })

  it('extrapolates with the bar step beyond the data', () => {
    expect(timeToLogical(times, -2 * H1)).toBe(-2)
    expect(timeToLogical(times, times[5] + 3 * H1)).toBe(8)
  })

  it('round-trips', () => {
    for (const l of [-3, 0, 0.25, 2, 3.5, 5, 9]) expect(timeToLogical(times, logicalToTime(times, l))).toBeCloseTo(l, 6)
  })

  it('snaps to the nearest bar inside the data only', () => {
    expect(snapTime(times, H1 + 1000)).toBe(H1)
    expect(snapTime(times, H1 + 2000)).toBe(2 * H1)
    expect(snapTime(times, times[5] + 10 * H1)).toBe(times[5] + 10 * H1)
  })
})

describe('measure / hit tests', () => {
  it('measures price change, percent and bars', () => {
    expect(measure({ price: 4366, logical: 10 }, { price: 4437.5, logical: 34 })).toEqual({
      delta: 71.5,
      pct: (71.5 / 4366) * 100,
      bars: 24,
    })
  })

  it('distance to a segment vs a ray', () => {
    const a = { x: 0, y: 0 }
    const b = { x: 10, y: 0 }
    expect(distanceToSegment({ x: 5, y: 3 }, a, b)).toBe(3)
    expect(distanceToSegment({ x: 20, y: 0 }, a, b)).toBe(10)
    expect(distanceToSegment({ x: 20, y: 0 }, a, b, true)).toBe(0)
    expect(distanceToSegment({ x: -5, y: 0 }, a, b, true)).toBe(5)
  })

  it('extends a ray to the edge of the pane', () => {
    expect(rayEnd({ x: 0, y: 0 }, { x: 10, y: 5 }, 100)).toEqual({ x: 100, y: 50 })
    expect(rayEnd({ x: 50, y: 0 }, { x: 40, y: 10 }, 100)).toEqual({ x: 0, y: 50 })
  })
})
