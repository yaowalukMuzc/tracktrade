import { ApiError } from '@/api/client'

const KNOWN = new Set(['invalid_credentials', 'email_taken', 'rate_limited'])

/** Maps an auth API failure to an `auth.errors.*` i18n key. */
export function authErrorKey(e: unknown): string {
  if (e instanceof ApiError) {
    if (KNOWN.has(e.code)) return `auth.errors.${e.code}`
    if (e.status === 409) return 'auth.errors.email_taken'
    if (e.status === 429) return 'auth.errors.rate_limited'
    if (e.status === 401) return 'auth.errors.invalid_credentials'
    return 'auth.errors.generic'
  }
  return 'auth.errors.network'
}

export const isEmail = (v: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v.trim())

/** 0–4 bars for the register strength meter. Length ≥ 8 is the only hard rule (F-01 AC1). */
export function passwordStrength(pw: string): 0 | 1 | 2 | 3 | 4 {
  if (!pw) return 0
  if (pw.length < 8) return pw.length < 5 ? 1 : 2
  const classes = [/[a-z]/, /[A-Z]/, /\d/, /[^A-Za-z0-9]/].filter((r) => r.test(pw)).length
  return classes >= 3 && pw.length >= 12 ? 4 : classes >= 2 ? 3 : 2
}
