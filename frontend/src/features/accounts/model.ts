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
