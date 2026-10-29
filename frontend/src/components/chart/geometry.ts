/**
 * Pure helpers for chart drawings: time ↔ logical bar index, measurements, hit tests.
 * Drawings are stored in time/price so they appear on every timeframe; the chart positions
 * bars by logical index, so times between or beyond bars are interpolated / extrapolated.
 */

export interface Pt {
  x: number
  y: number
}

/** Fractional bar index for a unix time. `times` must be ascending. */
export function timeToLogical(times: readonly number[], time: number, step?: number): number {
  const n = times.length
  if (n === 0) return 0
  const s = step ?? (n > 1 ? times[n - 1] - times[n - 2] : 60)
  if (time <= times[0]) return (time - times[0]) / s
  if (time >= times[n - 1]) return n - 1 + (time - times[n - 1]) / s
  let lo = 0
  let hi = n - 1
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1
    if (times[mid] <= time) lo = mid
    else hi = mid
  }
  const span = times[hi] - times[lo]
  return lo + (span > 0 ? (time - times[lo]) / span : 0)
}

/** Unix time for a (fractional) bar index; inverse of `timeToLogical`. */
export function logicalToTime(times: readonly number[], logical: number, step?: number): number {
  const n = times.length
  if (n === 0) return 0
  const s = step ?? (n > 1 ? times[n - 1] - times[n - 2] : 60)
  if (logical <= 0) return Math.round(times[0] + logical * s)
  if (logical >= n - 1) return Math.round(times[n - 1] + (logical - (n - 1)) * s)
  const lo = Math.floor(logical)
  const frac = logical - lo
  return Math.round(times[lo] + frac * (times[lo + 1] - times[lo]))
}

/** Snap a time to the nearest bar's time when inside the data. */
export function snapTime(times: readonly number[], time: number): number {
  if (times.length === 0) return time
  const i = Math.round(timeToLogical(times, time))
  if (i < 0 || i >= times.length) return time
  return times[i]
}

export interface Measure {
  /** price2 − price1 */
  delta: number
  pct: number
  bars: number
}

export function measure(p1: { price: number; logical: number }, p2: { price: number; logical: number }): Measure {
  const delta = p2.price - p1.price
  return {
    delta,
    pct: p1.price !== 0 ? (delta / p1.price) * 100 : 0,
    bars: Math.round(Math.abs(p2.logical - p1.logical)),
  }
}

/** Distance from p to segment ab (or to the ray from a through b when `ray`). */
export function distanceToSegment(p: Pt, a: Pt, b: Pt, ray = false): number {
  const dx = b.x - a.x
  const dy = b.y - a.y
  const len2 = dx * dx + dy * dy
  if (len2 === 0) return Math.hypot(p.x - a.x, p.y - a.y)
  let t = ((p.x - a.x) * dx + (p.y - a.y) * dy) / len2
  t = ray ? Math.max(0, t) : Math.min(1, Math.max(0, t))
  return Math.hypot(p.x - (a.x + t * dx), p.y - (a.y + t * dy))
}

/** Where the ray from a through b leaves the box x ∈ [0, width] (to the right or left). */
export function rayEnd(a: Pt, b: Pt, width: number): Pt {
  const dx = b.x - a.x
  if (dx === 0) return b
  const x = dx > 0 ? width : 0
  return { x, y: a.y + ((b.y - a.y) * (x - a.x)) / dx }
}

export function insideRect(p: Pt, a: Pt, b: Pt, pad = 0): boolean {
  return (
    p.x >= Math.min(a.x, b.x) - pad &&
    p.x <= Math.max(a.x, b.x) + pad &&
    p.y >= Math.min(a.y, b.y) - pad &&
    p.y <= Math.max(a.y, b.y) + pad
  )
}

/** Distance to the border of the rectangle ab (0 inside the border band). */
export function distanceToRectEdge(p: Pt, a: Pt, b: Pt): number {
  const corners = [a, { x: b.x, y: a.y }, b, { x: a.x, y: b.y }]
  return Math.min(...corners.map((c, i) => distanceToSegment(p, c, corners[(i + 1) % 4])))
}
