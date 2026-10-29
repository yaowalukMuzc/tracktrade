import type { LocationQuery } from 'vue-router'
import type { Locale } from '@/i18n'
import { MINUS, formatMoney, formatR, intlLocale } from '@/lib/format'
import { TRADE_TABS, type MatchCandidate, type PositionSummary, type TradeFilters, type TradeTab } from '@/api/positions'

// Pure helpers of the Trades screens (screens/web/06-WTrades.png, screens/mobile/09-Trades.png, 12-MatchQueue.png).

export type PnlMode = 'money' | 'r'

/** The part of the filters kept in the URL (the account filter is global — accounts store). */
export interface TradeQuery {
  tab: TradeTab
  q: string
  from: string | null
  to: string | null
  symbol_id: string | null
  setup_id: string | null
  page: number
}

const str = (v: unknown) => (typeof v === 'string' && v ? v : null)
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/

export function queryToState(q: LocationQuery): TradeQuery {
  const tab = str(q.tab) as TradeTab | null
  const date = (v: unknown) => {
    const s = str(v)
    return s && DATE_RE.test(s) ? s : null
  }
  const page = Number(str(q.page) ?? 1)
  return {
    tab: tab && TRADE_TABS.includes(tab) ? tab : 'all',
    q: str(q.q) ?? '',
    from: date(q.from),
    to: date(q.to),
    symbol_id: str(q.symbol),
    setup_id: str(q.setup),
    page: Number.isInteger(page) && page > 0 ? page : 1,
  }
}

/** Back to a URL query; defaults are left out so the URL stays short. */
export function stateToQuery(s: TradeQuery, keep: LocationQuery = {}): LocationQuery {
  const out: LocationQuery = { ...keep }
  for (const k of ['tab', 'q', 'from', 'to', 'symbol', 'setup', 'page']) delete out[k]
  if (s.tab !== 'all') out.tab = s.tab
  if (s.q.trim()) out.q = s.q.trim()
  if (s.from) out.from = s.from
  if (s.to) out.to = s.to
  if (s.symbol_id) out.symbol = s.symbol_id
  if (s.setup_id) out.setup = s.setup_id
  if (s.page > 1) out.page = String(s.page)
  return out
}

export function toFilters(s: TradeQuery, accountId?: string): TradeFilters {
  return {
    tab: s.tab,
    q: s.q.trim() || undefined,
    from: s.from ?? undefined,
    to: s.to ?? undefined,
    symbol_id: s.symbol_id ?? undefined,
    setup_id: s.setup_id ?? undefined,
    account_id: accountId,
  }
}

// ------------------------------------------------------------------ numbers / times

/** Price with the symbol's digits and separators: 4,387.60 · 1.08402. */
export function price(v: string | null | undefined, digits: number) {
  if (v === null || v === undefined) return '—'
  return new Intl.NumberFormat('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(Number(v))
}

/** "4,387.60 → 4,398.40", open trades "4,403.18 → —". */
export function entryExit(p: Pick<PositionSummary, 'avg_entry' | 'avg_exit' | 'digits'>) {
  return `${price(p.avg_entry, p.digits)} → ${price(p.avg_exit, p.digits)}`
}

export const lot = (v: string) => Number(v).toFixed(2)

/** Closed trade P/L in the chosen unit; open trades have no result yet. */
export function pnlText(p: Pick<PositionSummary, 'status' | 'net_pnl' | 'r_multiple' | 'currency'>, mode: PnlMode) {
  if (p.status !== 'closed') return '—'
  if (mode === 'r') return p.r_multiple === null ? '—' : formatR(Number(p.r_multiple), 2)
  return formatMoney(Number(p.net_pnl), p.currency)
}

/** R column: "+0.51", "−1.00" (no unit, like the design table). */
export function rText(v: string | null) {
  if (v === null) return '—'
  const n = Number(v)
  return (n > 0 ? '+' : n < 0 ? MINUS : '') + Math.abs(n).toFixed(2)
}

export function pnlDirection(p: Pick<PositionSummary, 'status' | 'net_pnl'>): 'up' | 'down' | 'flat' {
  if (p.status !== 'closed') return 'flat'
  const n = Number(p.net_pnl)
  return n > 0 ? 'up' : n < 0 ? 'down' : 'flat'
}

/** Calendar day of an instant in the trader's timezone: "2026-10-09". */
export function localDay(iso: string, tz: string) {
  return new Intl.DateTimeFormat('en-CA', { timeZone: tz, year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date(iso))
}

/** "09:12" in the trader's timezone. */
export function timeHm(iso: string, tz: string, l: Locale) {
  return new Intl.DateTimeFormat(intlLocale(l), { timeZone: tz, hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(new Date(iso))
}

/** "9 ต.ค." / "Oct 9" in the trader's timezone. */
export function dayMonth(iso: string, tz: string, l: Locale) {
  return new Intl.DateTimeFormat(intlLocale(l), { timeZone: tz, day: 'numeric', month: 'short' }).format(new Date(iso))
}

/** Hold time split into hours + minutes (the view words it: "2 ชม. 47 น."). */
export function holdParts(openedAt: string, closedAt: string | null): { h: number; m: number } | null {
  if (!closedAt) return null
  const mins = Math.max(0, Math.round((Date.parse(closedAt) - Date.parse(openedAt)) / 60_000))
  return { h: Math.floor(mins / 60), m: mins % 60 }
}

// ------------------------------------------------------------------ grouping (mobile cards)

export interface DayTotal {
  currency: string
  money: number
  r: number
}

export interface DayGroup {
  day: string // YYYY-MM-DD, trader's timezone
  items: PositionSummary[]
  totals: DayTotal[] // closed trades only, per account currency
}

export function groupByDay(items: PositionSummary[], tz: string): DayGroup[] {
  const groups: DayGroup[] = []
  for (const p of items) {
    const day = localDay(p.opened_at, tz)
    let g = groups[groups.length - 1]
    if (!g || g.day !== day) {
      g = { day, items: [], totals: [] }
      groups.push(g)
    }
    g.items.push(p)
    if (p.status === 'closed') {
      let t = g.totals.find((x) => x.currency === p.currency)
      if (!t) {
        t = { currency: p.currency, money: 0, r: 0 }
        g.totals.push(t)
      }
      t.money = Math.round((t.money + Number(p.net_pnl)) * 100) / 100
      t.r = Math.round((t.r + Number(p.r_multiple ?? 0)) * 100) / 100
    }
  }
  return groups
}

/** today / yesterday / a date, for the group heading. */
export function dayLabelKind(day: string, tz: string, now = new Date()): 'today' | 'yesterday' | 'date' {
  const today = localDay(now.toISOString(), tz)
  const yesterday = localDay(new Date(now.getTime() - 86_400_000).toISOString(), tz)
  return day === today ? 'today' : day === yesterday ? 'yesterday' : 'date'
}

// ------------------------------------------------------------------ status

export type TradeState = 'pending' | 'open' | 'review' | 'reviewed'

/** One status per row (table "สถานะ"): matching first, then open, then review. */
export function tradeState(p: Pick<PositionSummary, 'match_status' | 'status' | 'review_status'>): TradeState {
  if (p.match_status === 'pending') return 'pending'
  if (p.status === 'open') return 'open'
  return p.review_status === 'done' ? 'reviewed' : 'review'
}

export type Grade = 'A' | 'B' | 'C' | 'D'
/** Quality grade for <TtGrade>, or null until the Phase 6 engine scores the trade. */
export const gradeOf = (g: string | null): Grade | null => (g === 'A' || g === 'B' || g === 'C' || g === 'D' ? g : null)

export const STATE_BADGE: Record<TradeState, 'warning' | 'brand' | 'outline'> = {
  pending: 'warning',
  open: 'brand',
  review: 'warning',
  reviewed: 'outline',
}

// ------------------------------------------------------------------ match picker

/** Picker value for "no plan" (sent to the API as plan_id: null). */
export const UNPLANNED = '__unplanned__'

/** i18n key of the plan's entry wording ("Buy limit", "Sell market") — shared with the plan screen. */
export function entryKey(c: MatchCandidate, direction: 'long' | 'short') {
  return `trading.entryOrder.${direction}.${c.plan.entry_type}`
}

/** Default choice in the picker: the recommended plan, else the closest eligible, else unplanned. */
export function defaultChoice(candidates: MatchCandidate[]): string | null {
  return (candidates.find((c) => c.recommended) ?? candidates.find((c) => c.eligible))?.plan.id ?? null
}

/** "0.4" → "0.4", "21.0" → "21" (design: "0.4% ของระยะ SL", "21% ของระยะ SL"). */
export const pctText = (v: string) => String(Number(v))

// ------------------------------------------------------------------ $ / R preference

const PNL_KEY = 'tt.trades.pnl'

/** Remembered per user on this device (Phase 4 prompt: "Toggle $/R จำค่าต่อผู้ใช้"). */
export function loadPnlMode(userId: string | undefined): PnlMode {
  try {
    return localStorage.getItem(`${PNL_KEY}.${userId ?? 'anon'}`) === 'r' ? 'r' : 'money'
  } catch {
    return 'money'
  }
}

export function savePnlMode(userId: string | undefined, mode: PnlMode) {
  try {
    localStorage.setItem(`${PNL_KEY}.${userId ?? 'anon'}`, mode)
  } catch {
    /* storage unavailable */
  }
}
