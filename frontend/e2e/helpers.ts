import type { APIRequestContext, Page } from '@playwright/test'

/**
 * Full-stack helpers (need E2E_BASE_URL: auth service + API behind the same origin).
 * `page.request` shares the page's cookie jar, so signing up here signs the page in too.
 */
export const PASSWORD = 'correct-horse-9'

export function uniqueEmail(prefix = 'e2e') {
  return `${prefix}+${Date.now()}-${Math.random().toString(36).slice(2, 7)}@example.com`
}

/**
 * Sign up through Better Auth (cookie lands in the page context) and return a JWT for API seeding.
 * The app applies the user's saved theme after sign-in (it wins over localStorage), so pass `theme`
 * for dark screenshots.
 */
export async function signUp(page: Page, opts: { email?: string; name?: string; locale?: 'th' | 'en'; theme?: 'light' | 'dark' } = {}) {
  const email = opts.email ?? uniqueEmail()
  const res = await page.request.post('/api/auth/sign-up/email', {
    data: { email, password: PASSWORD, name: opts.name ?? 'Nook Knight', locale: opts.locale ?? 'th', timezone: 'Asia/Bangkok' },
  })
  if (!res.ok()) throw new Error(`sign-up failed: ${res.status()} ${await res.text()}`)
  const token = ((await (await page.request.get('/api/auth/token')).json()) as { token: string }).token
  if (opts.theme) await apiCall(page.request, token, 'PATCH', '/me', { theme: opts.theme })
  return { email, token }
}

/** Authenticated JSON call to FastAPI (`/api/v1/...`). */
export async function apiCall<T>(request: APIRequestContext, token: string, method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE', path: string, data?: unknown): Promise<T> {
  const res = await request.fetch(`/api/v1${path}`, { method, data, headers: { Authorization: `Bearer ${token}` } })
  if (!res.ok()) throw new Error(`${method} ${path} -> ${res.status()} ${await res.text()}`)
  return (res.status() === 204 ? undefined : await res.json()) as T
}

/** The demo data of the designs (screens/web/14-WAccounts.png): FTMO prop, IC Markets live, demo. */
export async function seedAccounts(request: APIRequestContext, token: string) {
  const ftmo = await apiCall<{ id: string }>(request, token, 'POST', '/accounts', {
    name: 'FTMO 100K Challenge', broker: 'FTMO', platform: 'mt5', account_type: 'prop', account_number: '5120934', currency: 'USD', initial_balance: '100000',
  })
  const ic = await apiCall<{ id: string }>(request, token, 'POST', '/accounts', {
    name: 'IC Markets Live', broker: 'IC Markets', platform: 'ctrader', account_type: 'live', account_number: '8830211', currency: 'USD', initial_balance: '8412',
  })
  const demo = await apiCall<{ id: string }>(request, token, 'POST', '/accounts', {
    name: 'Demo Practice', broker: 'Demo', platform: 'manual', account_type: 'demo', currency: 'USD', initial_balance: '10517',
  })
  return { ftmo, ic, demo }
}

/** Freeze theme + locale before the app boots. */
export async function prefs(page: Page, theme: 'light' | 'dark' = 'light', locale: 'th' | 'en' = 'th') {
  await page.addInitScript(
    ([t, l]) => {
      localStorage.setItem('tt.theme', t)
      localStorage.setItem('tt.locale', l)
    },
    [theme, locale] as const,
  )
}
