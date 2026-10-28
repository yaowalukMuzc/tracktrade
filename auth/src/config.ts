/** Settings for the auth service, read from environment variables. */

export interface RateRule {
  max: number
  window: number // seconds
}

export interface AuthConfig {
  env: 'dev' | 'test' | 'prod'
  port: number
  databaseUrl: string
  secret: string
  /** Public origin of the web app (the browser reaches `/api/auth/*` through it). */
  baseUrl: string
  trustedOrigins: string[]
  cookieSecure: boolean
  jwtIssuer: string
  jwtAudience: string
  /** Rate limit for sign-in / sign-up / password reset routes. `null` = off. */
  authRate: RateRule | null
  smtp: { host: string; port: number; secure: boolean; user?: string; password?: string }
  mailFrom: string
}

const DEV_SECRET = 'dev-only-better-auth-secret-change-me-0123456789'

const PERIODS: Record<string, number> = { s: 1, sec: 1, second: 1, m: 60, min: 60, minute: 60, h: 3600, hour: 3600 }

/** `"10/min"` → `{ max: 10, window: 60 }`; `"off"` → null. Same format as the backend's RATE_LIMIT_AUTH. */
export function parseRate(value: string): RateRule | null {
  if (value.trim().toLowerCase() === 'off') return null
  const match = /^\s*(\d+)\s*\/\s*([a-z]+)\s*$/.exec(value)
  const window = match?.[2] ? PERIODS[match[2]] : undefined
  if (!match || !window) throw new Error(`invalid rate limit ${JSON.stringify(value)}; expected e.g. "10/min"`)
  return { max: Number(match[1]), window }
}

/** `postgresql+asyncpg://…` (backend style) also works: the driver suffix is dropped. */
export function toPgUrl(url: string): string {
  return url.replace(/^postgres(ql)?\+[a-z0-9]+:\/\//, 'postgresql://')
}

const list = (value: string | undefined) => (value ?? '').split(',').map((v) => v.trim()).filter(Boolean)
const bool = (value: string | undefined, fallback: boolean) => (value === undefined ? fallback : /^(1|true|yes)$/i.test(value))

export function loadConfig(env: NodeJS.ProcessEnv = process.env): AuthConfig {
  const mode = (env.ENV ?? 'dev') as AuthConfig['env']
  const secret = env.BETTER_AUTH_SECRET ?? DEV_SECRET
  if (secret.length < 32) throw new Error('BETTER_AUTH_SECRET must be at least 32 characters')
  if (mode === 'prod' && secret === DEV_SECRET) throw new Error('BETTER_AUTH_SECRET must be set in prod')

  const baseUrl = (env.BETTER_AUTH_URL ?? 'http://localhost:5178').replace(/\/$/, '')
  return {
    env: mode,
    port: Number(env.PORT ?? 3000),
    databaseUrl: toPgUrl(env.DATABASE_URL ?? 'postgresql://tracktrade:tracktrade@localhost:5432/tracktrade'),
    secret,
    baseUrl,
    trustedOrigins: [...new Set([baseUrl, ...list(env.TRUSTED_ORIGINS)])],
    cookieSecure: bool(env.COOKIE_SECURE, mode === 'prod'),
    jwtIssuer: env.JWT_ISSUER ?? 'tracktrade-auth',
    jwtAudience: env.JWT_AUDIENCE ?? 'tracktrade-api',
    authRate: parseRate(env.RATE_LIMIT_AUTH ?? '10/min'),
    smtp: {
      host: env.SMTP_HOST ?? 'localhost',
      port: Number(env.SMTP_PORT ?? 1025),
      secure: bool(env.SMTP_SECURE, false),
      user: env.SMTP_USER || undefined,
      password: env.SMTP_PASSWORD || undefined,
    },
    mailFrom: env.MAIL_FROM ?? 'TrackTrade <no-reply@tracktrade.local>',
  }
}
