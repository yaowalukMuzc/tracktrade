import type { Locale } from '@/i18n'

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
