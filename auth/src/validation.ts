/** Minimal Standard Schema validators for Better Auth `additionalFields` (no schema library needed). */
import type { StandardSchemaV1 } from '@standard-schema/spec'

function schema(check: (value: unknown) => string | null): StandardSchemaV1<unknown, string> {
  return {
    '~standard': {
      version: 1,
      vendor: 'tracktrade',
      validate: (value) => {
        const message = check(value)
        return message === null ? { value: value as string } : { issues: [{ message }] }
      },
    },
  }
}

export const enumSchema = (allowed: readonly string[]) =>
  schema((value) => (typeof value === 'string' && allowed.includes(value) ? null : `must be one of: ${allowed.join(', ')}`))

/** Valid IANA zone (same rule as the backend's `Timezone` type). */
export function isTimezone(value: unknown): boolean {
  if (typeof value !== 'string' || value.length === 0 || value.length > 64) return false
  try {
    new Intl.DateTimeFormat('en', { timeZone: value })
    return true
  } catch {
    return false
  }
}

export const timezoneSchema = schema((value) => (isTimezone(value) ? null : "must be a valid IANA timezone, e.g. 'Asia/Bangkok'"))
