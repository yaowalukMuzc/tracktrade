// Header hint "London เปิดอีก 1 ชม." (screens/source/WToday.dc.html). Opening times are local wall-clock
// times in each market's own timezone, so Intl does the DST work (London BST/GMT and New York EDT/EST
// switch on different dates; Tokyo has no DST).

export type MarketSession = 'tokyo' | 'london' | 'new_york'

interface SessionDef {
  id: MarketSession
  tz: string
  /** Minutes after local midnight. */
  open: number
  close: number
}

export const MARKET_SESSIONS: SessionDef[] = [
  { id: 'tokyo', tz: 'Asia/Tokyo', open: 9 * 60, close: 18 * 60 },
  { id: 'london', tz: 'Europe/London', open: 8 * 60, close: 17 * 60 },
  { id: 'new_york', tz: 'America/New_York', open: 8 * 60, close: 17 * 60 },
]

/** Show an upcoming opening only when it is this close. */
export const UPCOMING_WINDOW_MIN = 180

export type SessionHint =
  | { kind: 'opensIn'; session: MarketSession; minutes: number }
  | { kind: 'open'; session: MarketSession }
  | null

const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']
const formatters = new Map<string, Intl.DateTimeFormat>()

/** Wall-clock weekday + minutes after midnight (with seconds as a fraction) in `tz`. */
export function localClock(now: Date, tz: string): { weekday: string; minutes: number } {
  let f = formatters.get(tz)
  if (!f) {
    f = new Intl.DateTimeFormat('en-US', { timeZone: tz, weekday: 'short', hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23' })
    formatters.set(tz, f)
  }
  const parts = Object.fromEntries(f.formatToParts(now).map((p) => [p.type, p.value]))
  return { weekday: parts.weekday, minutes: Number(parts.hour) * 60 + Number(parts.minute) + Number(parts.second) / 60 }
}

/**
 * The next session opening within `window` minutes (earliest first) — otherwise the session that is open now
 * (the most recently opened one during an overlap) — otherwise null. Markets are closed on local weekends.
 */
export function sessionHint(now: Date, window = UPCOMING_WINDOW_MIN): SessionHint {
  let upcoming: { session: MarketSession; minutes: number } | null = null
  let open: { session: MarketSession; since: number } | null = null
  for (const s of MARKET_SESSIONS) {
    const { weekday, minutes } = localClock(now, s.tz)
    if (!WEEKDAYS.includes(weekday)) continue
    if (minutes < s.open) {
      // Openings are ≥ 08:00 local, so tomorrow's is always further away than the window.
      const until = Math.ceil(s.open - minutes)
      if (until <= window && (!upcoming || until < upcoming.minutes)) upcoming = { session: s.id, minutes: until }
    } else if (minutes < s.close) {
      const since = minutes - s.open
      if (!open || since < open.since) open = { session: s.id, since }
    }
  }
  if (upcoming) return { kind: 'opensIn', ...upcoming }
  if (open) return { kind: 'open', session: open.session }
  return null
}

/** Split minutes for "1 ชม. 30 นาที" style labels. */
export function splitMinutes(total: number): { h: number; m: number } {
  return { h: Math.floor(total / 60), m: total % 60 }
}
