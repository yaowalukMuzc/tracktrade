import pg from 'pg'
import { createAuth } from '../src/auth.js'
import { loadConfig, type AuthConfig } from '../src/config.js'
import type { Mail } from '../src/mailer.js'
import { TEST_DB_URL } from './global-setup.js'

export const ORIGIN = 'http://localhost:5179'
export const PASSWORD = 'correct-horse-1'
/** argon2-cffi `PasswordHasher().hash(PASSWORD)` — what Phase 1 stored in users.password_hash. */
export const PHASE1_HASH = '$argon2id$v=19$m=65536,t=3,p=4$jEpJWGllzOBjiPHyDJfC9w$pX5lzuVhCYsoKwRRZQAjhZD5GR6OLXcnoSsfefAg9YE'

export function testConfig(overrides: Partial<AuthConfig> = {}): AuthConfig {
  return {
    ...loadConfig({ ENV: 'test', DATABASE_URL: TEST_DB_URL, BETTER_AUTH_URL: ORIGIN, RATE_LIMIT_AUTH: 'off' }),
    ...overrides,
  }
}

/** An auth instance whose emails land in `outbox` and whose background work can be awaited. */
export function setupAuth(overrides: Partial<AuthConfig> = {}) {
  const outbox: Mail[] = []
  const pending: Promise<unknown>[] = []
  const pool = new pg.Pool({ connectionString: TEST_DB_URL, max: 4 })
  const { auth } = createAuth(testConfig(overrides), {
    pool,
    mailer: { send: async (mail) => void outbox.push(mail) },
    background: (task) => void pending.push(task),
  })

  /** Cookie jar of one browser. */
  function browser() {
    const jar = new Map<string, string>()
    async function call(method: 'GET' | 'POST', path: string, body?: unknown, ip = '203.0.113.7') {
      const headers: Record<string, string> = { origin: ORIGIN, 'x-forwarded-for': ip }
      if (body !== undefined) headers['content-type'] = 'application/json'
      if (jar.size) headers.cookie = [...jar].map(([k, v]) => `${k}=${v}`).join('; ')
      const res = await auth.handler(
        new Request(`${ORIGIN}/api/auth${path}`, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) }),
      )
      for (const cookie of res.headers.getSetCookie()) {
        const [pair] = cookie.split(';')
        const [name, ...rest] = (pair ?? '').split('=')
        if (!name) continue
        const value = rest.join('=')
        if (value === '' || /max-age=0/i.test(cookie)) jar.delete(name)
        else jar.set(name, value)
      }
      const text = await res.text()
      return { status: res.status, body: text ? (JSON.parse(text) as Record<string, any>) : null, headers: res.headers }
    }
    return { call, jar }
  }

  return {
    auth,
    pool,
    outbox,
    browser,
    flush: () => Promise.all(pending.splice(0)),
    close: () => pool.end(),
  }
}

export async function resetData(pool: pg.Pool) {
  // users cascades to auth_sessions / auth_accounts; verifications + keys are independent.
  await pool.query('DELETE FROM users; DELETE FROM auth_verifications; DELETE FROM auth_jwks;')
}

export const signUpBody = (email = 'nook@example.com', extra: Record<string, unknown> = {}) => ({
  email,
  password: PASSWORD,
  name: 'Nook Knight',
  locale: 'th',
  timezone: 'Asia/Bangkok',
  ...extra,
})
