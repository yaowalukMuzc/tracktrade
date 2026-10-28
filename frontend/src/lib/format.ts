import type { Locale } from '@/i18n'

/** U+2212 — every negative P/L uses the true minus sign (CLAUDE.md, README › Numbers). */
export const MINUS = '−'

/** BCP-47 tag per app locale. Thai uses the Gregorian calendar (README › Numbers: `9 ก.ย. 2026`). */
export const intlLocale = (l: Locale) => (l === 'th' ? 'th-TH-u-ca-gregory' : 'en-US')

export function formatLongDate(d: Date, l: Locale) {
  return new Intl.DateTimeFormat(intlLocale(l), {
    weekday: 'long',
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).format(d)
}

export function greetingKey(d: Date) {
  const h = d.getHours()
  return h < 12 ? 'greeting.morning' : h < 18 ? 'greeting.afternoon' : 'greeting.evening'
}

export type Direction = 'up' | 'down' | 'flat'
export const directionOf = (n: number): Direction => (n > 0 ? 'up' : n < 0 ? 'down' : 'flat')

/** `+` / `−` prefix for a non-zero value; zero gets no sign. */
const signOf = (n: number) => (n > 0 ? '+' : n < 0 ? MINUS : '')

/** `+$1,669.98`, `−$486.00`, `$0.00` — always 2 decimals, thousands separators, signed. */
export function formatMoney(value: number, currency = 'USD', opts: { compact?: boolean } = {}) {
  const abs = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    currencyDisplay: 'narrowSymbol',
    minimumFractionDigits: opts.compact ? 0 : 2,
    maximumFractionDigits: opts.compact ? 1 : 2,
    notation: opts.compact ? 'compact' : 'standard',
  }).format(Math.abs(value))
  return signOf(value) + abs
}

/** `+1.5R`, `−1.0R` — 1 decimal by default, 2 when needed. */
export function formatR(value: number, digits = 1) {
  return signOf(value) + Math.abs(value).toFixed(digits) + 'R'
}

/** `62.5%` — rates are unsigned unless asked. */
export function formatPct(value: number, digits = 1, signed = false) {
  return (signed ? signOf(value) : value < 0 ? MINUS : '') + Math.abs(value).toFixed(digits) + '%'
}

/** Unsigned amount (balances, limits — not a P/L): `$100,000`, `$1,000.50`. Decimals only when present. */
export function formatAmount(value: number | string, currency = 'USD', maxDigits = 2) {
  const n = typeof value === 'string' ? Number(value) : value
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    currencyDisplay: 'narrowSymbol',
    minimumFractionDigits: 0,
    maximumFractionDigits: maxDigits,
  }).format(n)
}

/** Plain number with separators for inputs/labels: `100,000`, `1.5`. */
export function formatNumber(value: number | string, maxDigits = 2) {
  const n = typeof value === 'string' ? Number(value) : value
  return new Intl.NumberFormat('en-US', { maximumFractionDigits: maxDigits }).format(n)
}
