/**
 * Accounts form rules (mirror backend `modules/accounts/schemas.py`) and display helpers.
 * Validators return i18n keys + params so components stay string-free.
 */
import type { AccountInput, Rule, RiskProfileInput } from '@/api/accounts'

export type Msg = { key: string; params?: Record<string, string | number> }
export type Errors<K extends string> = Partial<Record<K, Msg>>

const num = (v: unknown) => (v === '' || v === null || v === undefined ? NaN : Number(v))

function range(value: unknown, min: number, max: number, opts: { int?: boolean; exclusiveMin?: boolean } = {}): Msg | undefined {
  const n = num(value)
  if (Number.isNaN(n)) return { key: 'accounts.errors.required' }
  if (opts.int && !Number.isInteger(n)) return { key: 'accounts.errors.integer' }
  if ((opts.exclusiveMin ? n <= min : n < min) || n > max) return { key: 'accounts.errors.range', params: { min, max } }
  return undefined
}

export type RiskField = keyof RiskProfileInput

export function validateRisk(r: RiskProfileInput): Errors<RiskField> {
  const e: Errors<RiskField> = {
    risk_per_trade_pct: range(r.risk_per_trade_pct, 0, 10, { exclusiveMin: true }),
    max_daily_loss_pct: range(r.max_daily_loss_pct, 0, 100, { exclusiveMin: true }),
    max_drawdown_pct: range(r.max_drawdown_pct, 0, 100, { exclusiveMin: true }),
    max_trades_per_day: range(r.max_trades_per_day, 1, 100, { int: true }),
    revenge_cooldown_min: range(r.revenge_cooldown_min, 0, 1440, { int: true }),
    news_blackout_min: range(r.news_blackout_min, 0, 240, { int: true }),
  }
  if (!e.max_daily_loss_pct && !e.max_drawdown_pct && num(r.max_daily_loss_pct) > num(r.max_drawdown_pct)) {
    e.max_daily_loss_pct = { key: 'accounts.errors.dailyOverDd' }
  }
  if (!e.risk_per_trade_pct && !e.max_daily_loss_pct && num(r.risk_per_trade_pct) > num(r.max_daily_loss_pct)) {
    e.risk_per_trade_pct = { key: 'accounts.errors.riskOverDaily' }
  }
  return clean(e)
}

export type AccountField = 'name' | 'broker' | 'currency' | 'initial_balance'

export function validateAccount(a: Pick<AccountInput, AccountField>): Errors<AccountField> {
  return clean({
    name: a.name.trim() ? undefined : { key: 'accounts.errors.required' },
    broker: a.broker.trim() ? undefined : { key: 'accounts.errors.required' },
    currency: /^[A-Z]{3}$/.test(a.currency) ? undefined : { key: 'accounts.errors.currency' },
    initial_balance: Number.isNaN(num(a.initial_balance))
      ? { key: 'accounts.errors.required' }
      : num(a.initial_balance) > 0
        ? undefined
        : { key: 'accounts.errors.positive' },
  })
}

function clean<K extends string>(e: Errors<K>): Errors<K> {
  return Object.fromEntries(Object.entries(e).filter(([, v]) => v)) as Errors<K>
}

/** Normalised payload for the API (numbers as strings/ints). */
export function riskPayload(r: RiskProfileInput): RiskProfileInput {
  return {
    risk_per_trade_pct: String(num(r.risk_per_trade_pct)),
    max_daily_loss_pct: String(num(r.max_daily_loss_pct)),
    max_drawdown_pct: String(num(r.max_drawdown_pct)),
    max_trades_per_day: Math.trunc(num(r.max_trades_per_day)),
    revenge_cooldown_min: Math.trunc(num(r.revenge_cooldown_min)),
    news_blackout_min: Math.trunc(num(r.news_blackout_min)),
  }
}

/** API `details` (pydantic loc paths) → field errors. */
export function serverFieldErrors<K extends string>(details: unknown, fields: readonly K[]): Errors<K> {
  const out: Errors<K> = {}
  if (!Array.isArray(details)) return out
  for (const d of details as { loc?: unknown[]; msg?: string }[]) {
    const field = [...(d.loc ?? [])].reverse().find((p): p is K => typeof p === 'string' && (fields as readonly string[]).includes(p))
    if (field && !out[field]) out[field] = { key: 'accounts.errors.generic' }
  }
  return out
}

/** "1.00" → "1.0", "10.00" → "10.0", "0.75" → "0.75" (design shows one decimal minimum). */
export function pctText(value: string | number) {
  const n = Number(value)
  return Number.isInteger(n) ? n.toFixed(1) : String(n)
}

export const SEVERITY_TONE: Record<Rule['severity'], 'loss' | 'warn' | 'brand'> = { high: 'loss', medium: 'warn', low: 'brand' }

/** i18n key + params of a rule's one-line description. */
export function describeRule(rule: Pick<Rule, 'code' | 'params'>, weekday: (d: number) => string, locale: string): Msg {
  const p = rule.params
  switch (rule.code) {
    case 'no_trading_window': {
      const days = ((p.days as number[]) ?? []).map(weekday).join(locale === 'th' ? ' ' : ', ')
      return { key: 'accounts.rules.describe.no_trading_window', params: { days, after: String(p.after ?? '') } }
    }
    case 'max_lot_vs_plan':
      return { key: 'accounts.rules.describe.max_lot_vs_plan', params: { ratio: String(Number(p.ratio)) } }
    case 'max_consecutive_losses':
      return { key: 'accounts.rules.describe.max_consecutive_losses', params: { n: Number(p.n) } }
    default:
      return { key: '', params: { text: String(p.text ?? '') } }
  }
}

// ---------------------------------------------------------------- broker connections (F-08)

/** Error codes that mean the OAuth link is dead — only reconnecting helps (design 24: "OAuth token หมดอายุ"). */
const AUTH_ERRORS = ['CH_ACCESS_TOKEN_INVALID', 'OA_AUTH_TOKEN_EXPIRED', 'ACCESS_TOKEN_INVALID', 'INVALID_TOKEN', 'invalid_grant', 'NOT_CONNECTED']

export function isAuthError(lastError: string | null | undefined) {
  return !!lastError && AUTH_ERRORS.some((c) => lastError.startsWith(c))
}

/** Broker symbols the server could not map, from `last_error` = "unknown_symbols: US30.cash, …". */
export function unknownSymbols(lastError: string | null | undefined): string[] {
  if (!lastError?.startsWith('unknown_symbols:')) return []
  return lastError.slice('unknown_symbols:'.length).split(',').map((s) => s.trim()).filter(Boolean)
}

/** Short date + time in the app locale: "8 ต.ค. 22:14" / "Oct 8, 22:14". */
export function shortDateTime(iso: string, locale: string, withTime = true) {
  return new Intl.DateTimeFormat(locale === 'th' ? 'th-TH-u-ca-gregory' : 'en-US', {
    day: 'numeric',
    month: 'short',
    ...(withTime ? { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' as const } : {}),
  }).format(new Date(iso))
}

/** "10 วินาทีที่แล้ว" / "5 min. ago" within a day, else the short date ("8 ต.ค. 22:14"). */
export function relativeTime(iso: string, now: number, locale: string) {
  const diff = Math.round((new Date(iso).getTime() - now) / 1000)
  const abs = Math.abs(diff)
  if (abs >= 86_400) return shortDateTime(iso, locale)
  const rtf = new Intl.RelativeTimeFormat(locale === 'th' ? 'th' : 'en', { numeric: 'always', style: 'short' })
  if (abs < 60) return rtf.format(Math.min(diff, -1), 'second')
  if (abs < 3600) return rtf.format(Math.round(diff / 60), 'minute')
  return rtf.format(Math.round(diff / 3600), 'hour')
}

/** Compact "10 วิ" for the accounts table badge ("Synced 10 วิ"). */
export function agoShort(iso: string, now: number, locale: string) {
  const s = Math.max(1, Math.round((now - new Date(iso).getTime()) / 1000))
  const unit = s < 60 ? ['second', s] : s < 3600 ? ['minute', Math.round(s / 60)] : s < 86_400 ? ['hour', Math.round(s / 3600)] : ['day', Math.round(s / 86_400)]
  // Thai "10 วิ" (design) is the short form; English stays compact "10s".
  const th = locale === 'th'
  return new Intl.NumberFormat(th ? 'th' : 'en', { style: 'unit', unit: unit[0] as string, unitDisplay: th ? 'short' : 'narrow' }).format(unit[1] as number)
}

export type ConnBadge = { variant: 'profit' | 'loss' | 'warning' | 'neutral' | 'outline'; key: string; params?: Record<string, string> }

/** Table / list badge for an account's connection (screens/web/14-WAccounts.png "การเชื่อมต่อ" column). */
export function connectionBadge(
  platform: 'mt5' | 'ctrader' | 'manual',
  conn: { status: 'pending' | 'connected' | 'offline' | 'error'; last_error: string | null; last_seen_at: string | null; last_sync_at: string | null } | undefined,
  now: number,
  locale: string,
): ConnBadge {
  if (platform === 'manual' || !conn) return { variant: 'outline', key: 'connections.badge.none' }
  switch (conn.status) {
    case 'connected': {
      const at = conn.last_seen_at ?? conn.last_sync_at
      return at ? { variant: 'profit', key: 'connections.badge.synced', params: { ago: agoShort(at, now, locale) } } : { variant: 'profit', key: 'connections.status.connected' }
    }
    case 'pending':
      return { variant: 'warning', key: platform === 'mt5' ? 'connections.badge.waitingEa' : 'connections.badge.syncing' }
    case 'offline':
      return { variant: 'neutral', key: 'connections.status.offline' }
    default:
      return { variant: 'loss', key: isAuthError(conn.last_error) ? 'connections.badge.tokenExpired' : 'connections.status.error' }
  }
}

interface JobLike {
  kind: string
  source: string
  status: string
  attempts: number
  error: string | null
  started_at: string
  stats: { deals?: number; positions?: number; new_positions?: number; modifications?: number; days?: number; unknown_symbols?: string[] }
}

/** One "ประวัติการนำเข้า" row: title + detail parts (all i18n keys / params, the caller joins with " · "). */
export function describeJob(job: JobLike, historyDays: number | null): { title: Msg; parts: Msg[]; ok: boolean } {
  const SOURCE: Record<string, string> = { mt5: 'MT5', ctrader: 'cTrader', ocr: 'OCR', manual: 'Manual' }
  const kindKey = job.kind === 'history' ? 'connections.job.history' : job.kind === 'resync' ? 'connections.job.resync' : 'connections.job.sync'
  const parts: Msg[] = []
  const ok = job.status === 'success' || job.status === 'warning'
  if (!ok) {
    parts.push({ key: 'connections.job.failed', params: { n: job.attempts, max: Math.max(job.attempts, 3) } })
  } else {
    const s = job.stats
    if (job.kind === 'history') {
      parts.push({ key: 'connections.job.deals', params: { n: s.deals ?? 0 } })
      if (historyDays) parts.push({ key: 'connections.job.days', params: { n: historyDays } })
    } else if (s.positions) {
      parts.push({ key: 'connections.job.positions', params: { n: s.positions } })
    } else if (s.modifications) {
      parts.push({ key: 'connections.job.mods', params: { n: s.modifications } })
    } else {
      parts.push({ key: 'connections.job.deals', params: { n: s.deals ?? 0 } })
    }
    if (s.unknown_symbols?.length) parts.push({ key: 'connections.job.unknown', params: { list: s.unknown_symbols.join(', ') } })
  }
  return { title: { key: kindKey, params: { source: SOURCE[job.source] ?? job.source } }, parts, ok }
}
