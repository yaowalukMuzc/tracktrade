import type { Locale } from '@/i18n'
import { MINUS, formatAmount, intlLocale } from '@/lib/format'

// Display helpers of the plan page (money in the calc box, times in the lock bar / revisions).

/** Unsigned money: whole units from 100 up ("$1,012"), cents below ("$4.80"). */
export function money(v: string | number | null | undefined, currency: string) {
  const n = Number(v ?? 0)
  return Math.abs(n) >= 100 ? formatAmount(Math.round(n), currency, 0) : cents(n, currency)
}

/** Signed money delta for the revision preview: "+$335", "−$120". */
export function moneyDelta(v: string | number, currency: string) {
  const n = Number(v)
  const sign = n > 0 ? '+' : n < 0 ? MINUS : ''
  return sign + money(Math.abs(n), currency)
}

const cents = (n: number, currency: string) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency, currencyDisplay: 'narrowSymbol', minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n)

/** Tick value per lot: always 2 decimals ("$1.00"). */
export function tickValue(v: string | number, currency: string) {
  return cents(Number(v), currency)
}

export const lotText = (v: string | number) => Number(v).toFixed(2)
export const rrText = (v: string | number | null | undefined) => (v === null || v === undefined ? '—' : Number(v).toFixed(2))

/** "09:12" in the user's clock. */
export function timeHm(iso: string, l: Locale) {
  return new Intl.DateTimeFormat(intlLocale(l), { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(new Date(iso))
}

/** "9 ต.ค." / "Oct 9" from a plain date (YYYY-MM-DD, no time zone shift). */
export function dayMonth(date: string, l: Locale) {
  const [y, m, d] = date.split('-').map(Number)
  return new Intl.DateTimeFormat(intlLocale(l), { day: 'numeric', month: 'short' }).format(new Date(y, m - 1, d))
}

/** "9 ต.ค. 22:00" from an ISO timestamp. */
export function dayTime(iso: string, l: Locale) {
  return new Intl.DateTimeFormat(intlLocale(l), { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(new Date(iso))
}
