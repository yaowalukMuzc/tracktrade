import { AuthError } from '@/api/authClient'
import { ApiError } from '@/api/client'

/** Better Auth error code → `auth.errors.*` key. */
const AUTH_CODES: Record<string, string> = {
  INVALID_EMAIL_OR_PASSWORD: 'invalid_credentials',
  USER_ALREADY_EXISTS: 'email_taken',
  USER_ALREADY_EXISTS_USE_ANOTHER_EMAIL: 'email_taken',
  PASSWORD_TOO_SHORT: 'password_short',
  INVALID_TOKEN: 'reset_link_invalid',
}

/** Maps an auth failure (Better Auth or FastAPI) to an `auth.errors.*` i18n key. */
export function authErrorKey(e: unknown): string {
  if (e instanceof AuthError) {
    const known = AUTH_CODES[e.code]
    if (known) return `auth.errors.${known}`
    if (e.status === 0) return 'auth.errors.network'
    if (e.status === 429) return 'auth.errors.rate_limited'
    if (e.status === 401) return 'auth.errors.invalid_credentials'
    return 'auth.errors.generic'
  }
  if (e instanceof ApiError) return e.status === 429 ? 'auth.errors.rate_limited' : 'auth.errors.generic'
  return 'auth.errors.network'
}

/** F-01 AC1 — same rule as the auth service (`minPasswordLength`). */
export const MIN_PASSWORD = 8

export const isEmail = (v: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v.trim())

/** 0–4 bars for the register strength meter. Length ≥ 8 is the only hard rule (F-01 AC1). */
export function passwordStrength(pw: string): 0 | 1 | 2 | 3 | 4 {
  if (!pw) return 0
  if (pw.length < 8) return pw.length < 5 ? 1 : 2
  const classes = [/[a-z]/, /[A-Z]/, /\d/, /[^A-Za-z0-9]/].filter((r) => r.test(pw)).length
  return classes >= 3 && pw.length >= 12 ? 4 : classes >= 2 ? 3 : 2
}
