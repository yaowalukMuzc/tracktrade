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

type Id = { id: string }
interface SymbolRow { id: string; code: string }
interface SetupRow { id: string; checklist: { id: string; is_required: boolean }[] }

/**
 * Phase 3 demo day from the designs (03-WToday / 04-WAnalysis / 05-WPlan): FTMO account, two setups,
 * XAUUSD analysis (bull, London, 7/10, key levels + drawings) with plan A (locked) and plan B (draft,
 * checklist 1/3), and an EURUSD analysis with a skipped plan A.
 */
export async function seedTradingDay(request: APIRequestContext, token: string) {
  const call = <T>(method: 'GET' | 'POST' | 'PUT' | 'PATCH', path: string, data?: unknown) => apiCall<T>(request, token, method, path, data)
  const { ftmo } = await seedAccounts(request, token)
  const symbols = await call<SymbolRow[]>('GET', '/symbols')
  const sym = (code: string) => symbols.find((s) => s.code === code)!.id
  const london = await call<SetupRow>('POST', '/setups', {
    name: 'London Breakout',
    description: 'รอ Asia range แล้วเข้าเมื่อ London เบรก high/low พร้อม pullback',
    timeframes: ['M15', 'H1'],
    sessions: ['london'],
    default_risk_pct: '1',
    management_rules: { partial: { pct: '50', at_r: '1.5' }, break_even: { at_r: '1' }, trailing: { method: 'Swing low M15' } },
    checklist: [
      { text: 'H4 bias ตรงทิศทาง', is_required: true },
      { text: 'ราคาอยู่ใน demand / supply zone', is_required: true },
      { text: 'มีแท่ง confirm บน M15', is_required: true },
    ],
  })
  const ny = await call<SetupRow>('POST', '/setups', {
    name: 'NY Reversal',
    timeframes: ['M5', 'M15'],
    sessions: ['new_york'],
    default_risk_pct: '0.5',
    management_rules: { partial: null, break_even: { at_r: '1' }, trailing: null },
    checklist: [{ text: 'Liquidity sweep ก่อนเข้า', is_required: true }],
  })
  const narrative = {
    type: 'doc',
    content: [
      {
        type: 'paragraph',
        content: [
          { type: 'text', text: 'DXY อ่อนตัวหลัง FOMC minutes ทองทำ higher low ที่ 4,366 บน H4 รอ pullback เข้า demand 4,380–4,388 ช่วง London แล้วดู confirm บน M15 ก่อนเข้า Long ' },
          { type: 'text', marks: [{ type: 'bold' }], text: 'ถ้าปิด H1 ใต้ 4,366 เปลี่ยนเป็น scenario B (Short)' },
        ],
      },
    ],
  }
  const xau = await call<Id & { analysis_date: string }>('POST', '/analyses', {
    account_id: ftmo.id,
    symbol_id: sym('XAUUSD'),
    htf_bias: 'bull',
    timeframes: ['M15', 'H1', 'H4'],
    session: 'london',
    confidence: 7,
    narrative,
    key_levels: [
      { price: '4366', kind: 'support', label: 'H4 swing low' },
      { price: '4380', price_to: '4388', kind: 'zone', label: 'Demand zone · H1' },
      { price: '4437.5', kind: 'resistance', label: 'Previous high' },
    ],
  })
  const ohlc = await call<{ bars: { time: number; low: string; high: string }[] }>('GET', `/market-data/ohlc?symbol_id=${sym('XAUUSD')}&tf=H1&count=120`)
  const b = ohlc.bars
  await call('PUT', `/chart-drawings?owner_type=analysis&owner_id=${xau.id}`, {
    drawings: [
      { tool: 'trendline', timeframe: 'H1', points: [{ time: b[30].time, price: b[30].low }, { time: b[100].time, price: b[100].low }], style: { color: 'ink', line: 'solid', width: 2 } },
      { tool: 'text', timeframe: 'H1', points: [{ time: b[60].time, price: b[60].high }], text: 'Higher low', style: { color: 'ink', line: 'solid', width: 1 } },
    ],
  })
  const plan = (body: Record<string, unknown>) => call<Id & { checklist_items: { id: string }[] }>('POST', '/plans', body)
  const a = await plan({
    analysis_id: xau.id, setup_id: london.id, account_id: ftmo.id, symbol_id: sym('XAUUSD'), direction: 'long', entry_type: 'limit',
    entry_price: '4387.52', stop_loss: '4366.78', take_profits: [{ price: '4418', pct: '50' }, { price: '4437.51', pct: '50' }],
    planned_risk_pct: '1', management_plan: { partial: true, break_even: true, trailing: true }, invalidation: 'ปิด H1 ต่ำกว่า 4,366',
    checklist_answers: london.checklist.map((c) => ({ checklist_item_id: c.id, checked: true })),
  })
  await call('POST', `/plans/${a.id}/lock`)
  const tags = await call<{ id: string; code: string }[]>('GET', '/emotion-tags')
  const tag = (code: string) => tags.find((t) => t.code === code)!.id
  await call('PUT', `/plans/${a.id}/pre-emotion`, { mood: 7, confidence: 7, tags: [tag('confident'), tag('patient')] })
  const bPlan = await plan({
    analysis_id: xau.id, setup_id: london.id, account_id: ftmo.id, symbol_id: sym('XAUUSD'), direction: 'short', entry_type: 'stop',
    entry_price: '4362', stop_loss: '4378.40', take_profits: [{ price: '4322' }], planned_risk_pct: '1',
    invalidation: 'H1 ปิดเหนือ 4,388', checklist_answers: [{ checklist_item_id: london.checklist[0].id, checked: true }],
  })
  const eur = await call<Id>('POST', '/analyses', { account_id: ftmo.id, symbol_id: sym('EURUSD'), htf_bias: 'bear', timeframes: ['M15', 'H1'], session: 'new_york', confidence: 5 })
  const eurA = await plan({
    analysis_id: eur.id, setup_id: ny.id, account_id: ftmo.id, symbol_id: sym('EURUSD'), direction: 'short', entry_type: 'limit',
    entry_price: '1.08420', stop_loss: '1.08610', take_profits: [{ price: '1.08040' }], planned_risk_pct: '0.5',
  })
  await call('POST', `/plans/${eurA.id}/status`, { status: 'skipped', reason: 'ข่าว CPI ใกล้เวลาเข้า' })
  return { ftmo, london, ny, xau, eur, planA: a, planB: bPlan, eurA, symbols, tag }
}
