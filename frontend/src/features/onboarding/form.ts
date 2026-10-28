import { RISK_DEFAULTS, type AccountInput, type AccountType, type Platform, type RiskProfileInput } from '@/api/accounts'
import { ApiError } from '@/api/client'

/** Onboarding draft: everything the user types stays a string until submit (inputs accept `100,000`). */
export interface OnboardingForm {
  name: string
  broker: string
  platform: Platform
  account_type: AccountType
  currency: string
  initial_balance: string
  risk: Record<keyof RiskProfileInput, string>
}

export type RiskKey = keyof RiskProfileInput
export type FieldKey = 'name' | 'broker' | 'platform' | 'account_type' | 'currency' | 'initial_balance' | RiskKey
/** An i18n key (under `onboarding.errors`) + its params — translated where it is shown, so a locale switch re-renders it. */
export interface FieldError {
  key: string
  params?: Record<string, number | string>
}
export type FieldErrors = Partial<Record<FieldKey, FieldError>>

export const CURRENCIES = ['USD', 'EUR', 'GBP', 'JPY', 'AUD', 'CAD', 'CHF', 'THB'] as const
export const RISK_KEYS: RiskKey[] = [
  'risk_per_trade_pct',
  'max_daily_loss_pct',
  'max_drawdown_pct',
  'max_trades_per_day',
  'revenge_cooldown_min',
  'news_blackout_min',
]

export function emptyForm(): OnboardingForm {
  const r = RISK_DEFAULTS
  return {
    name: '',
    broker: '',
    platform: 'mt5',
    account_type: 'live',
    currency: 'USD',
    initial_balance: '',
    risk: {
      risk_per_trade_pct: r.risk_per_trade_pct,
      max_daily_loss_pct: r.max_daily_loss_pct,
      max_drawdown_pct: r.max_drawdown_pct,
      max_trades_per_day: String(r.max_trades_per_day),
      revenge_cooldown_min: String(r.revenge_cooldown_min),
      news_blackout_min: String(r.news_blackout_min),
    },
  }
}

/** `100,000.5` → 100000.5; anything that is not a plain non-negative decimal → NaN. */
export function parseNum(value: string | number | null | undefined): number {
  const s = String(value ?? '').replace(/,/g, '').trim()
  return /^\d+(\.\d+)?$/.test(s) ? Number(s) : NaN
}

const decimals = (value: string) => (String(value).replace(/,/g, '').split('.')[1] ?? '').length
const err = (key: string, params?: FieldError['params']): FieldError => ({ key, params })

function text(value: string, max = 100): FieldError | undefined {
  const v = value.trim()
  if (!v) return err('required')
  if (v.length > max) return err('tooLong', { max })
}

function positive(value: string, max?: number): FieldError | undefined {
  if (!String(value).trim()) return err('required')
  const n = parseNum(value)
  if (Number.isNaN(n)) return err('number')
  if (n <= 0) return err('positive')
  if (max !== undefined && n > max) return err('rangePct', { max })
  if (decimals(value) > 2) return err('decimals')
}

function int(value: string, min: number, max: number): FieldError | undefined {
  if (!String(value).trim()) return err('required')
  const n = parseNum(value)
  if (Number.isNaN(n) || !Number.isInteger(n) || decimals(value) > 0) return err('integer')
  if (n < min || n > max) return err('range', { min, max })
}

/** Mirrors backend `AccountCreate` + `RiskProfileIn` (accounts/schemas.py). */
export function validate(f: OnboardingForm): FieldErrors {
  const r = f.risk
  const e: FieldErrors = {
    name: text(f.name),
    broker: text(f.broker),
    currency: /^[A-Z]{3}$/.test(f.currency) ? undefined : err('invalid'),
    initial_balance: positive(f.initial_balance) ?? (Math.trunc(parseNum(f.initial_balance)).toString().length > 16 ? err('invalid') : undefined),
    risk_per_trade_pct: positive(r.risk_per_trade_pct, 10),
    max_daily_loss_pct: positive(r.max_daily_loss_pct, 100),
    max_drawdown_pct: positive(r.max_drawdown_pct, 100),
    max_trades_per_day: int(r.max_trades_per_day, 1, 100),
    revenge_cooldown_min: int(r.revenge_cooldown_min, 0, 1440),
    news_blackout_min: int(r.news_blackout_min, 0, 240),
  }
  const [risk, daily, dd] = [r.risk_per_trade_pct, r.max_daily_loss_pct, r.max_drawdown_pct].map(parseNum)
  if (!e.max_daily_loss_pct && !e.max_drawdown_pct && daily > dd) e.max_daily_loss_pct = err('dailyVsDrawdown')
  if (!e.risk_per_trade_pct && !e.max_daily_loss_pct && risk > daily) e.risk_per_trade_pct = err('riskVsDaily')
  for (const k of Object.keys(e) as FieldKey[]) if (!e[k]) delete e[k]
  return e
}

/** One POST creates the account and its risk profile (F-02 AC1–AC2). Call only after `validate` passes. */
export function toPayload(f: OnboardingForm): AccountInput {
  const r = f.risk
  return {
    name: f.name.trim(),
    broker: f.broker.trim(),
    platform: f.platform,
    account_type: f.account_type,
    currency: f.currency,
    initial_balance: String(parseNum(f.initial_balance)),
    risk_profile: {
      risk_per_trade_pct: String(parseNum(r.risk_per_trade_pct)),
      max_daily_loss_pct: String(parseNum(r.max_daily_loss_pct)),
      max_drawdown_pct: String(parseNum(r.max_drawdown_pct)),
      max_trades_per_day: parseNum(r.max_trades_per_day),
      revenge_cooldown_min: parseNum(r.revenge_cooldown_min),
      news_blackout_min: parseNum(r.news_blackout_min),
    },
  }
}

const FIELD_KEYS = new Set<string>(['name', 'broker', 'platform', 'account_type', 'currency', 'initial_balance', ...RISK_KEYS])

/**
 * Maps an API failure to field errors (validation `details[].loc`, e.g. `["body","risk_profile","max_trades_per_day"]`)
 * or one form-level message. Server texts are English-only, so fields get a generic localized message.
 */
export function apiErrors(e: unknown): { fields: FieldErrors; form?: FieldError } {
  const fields: FieldErrors = {}
  let form: FieldError | undefined
  if (e instanceof ApiError && e.code === 'validation_error' && Array.isArray(e.details)) {
    for (const d of e.details as { loc?: unknown[] }[]) {
      const last = String(d.loc?.[d.loc.length - 1] ?? '')
      if (FIELD_KEYS.has(last)) fields[last as FieldKey] ??= err('invalid')
      else if (last === 'risk_profile') form = err('riskConsistency')
      else form ??= err('saveFailed')
    }
    if (Object.keys(fields).length && !form) form = err('fixFields')
    return { fields, form: form ?? err('saveFailed') }
  }
  return { fields, form: err('saveFailed') }
}
