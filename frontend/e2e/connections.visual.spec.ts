import { expect, test, type APIRequestContext, type Page } from '@playwright/test'
import { apiCall, prefs, seedAccounts, signUp } from './helpers'

// Phase 4 broker connections (F-08 AC1, AC6): screenshots for screens/web/14-WAccounts.png and
// screens/mobile/24-Connections.png, plus key create / rotate, sync now, cTrader and live status updates.
// The MT5 connection is made "connected" by posting PROTOCOL-shaped batches (connectors/mt5-ea/PROTOCOL.md) to /ingest.
test.skip(!process.env.E2E_BASE_URL, 'needs the full stack (set E2E_BASE_URL)')

const out = (name: string) => `../docs/qa/phase-4/${name}.png`
const unix = (d: Date) => Math.floor(d.getTime() / 1000)

async function ingest(request: APIRequestContext, key: string, body: Record<string, unknown>) {
  const res = await request.post('/api/v1/ingest/events', {
    headers: { 'X-Api-Key': key },
    data: {
      ea_version: '1.0.0',
      account: { login: '5120934', server: 'FTMO-Demo', currency: 'USD', balance: '101240.00', equity: '101757.00' },
      ...body,
    },
  })
  if (!res.ok()) throw new Error(`ingest ${res.status()} ${await res.text()}`)
  return res.json()
}

const deal = (ticket: string, pos: string, entry: 'in' | 'out', at: Date, price: string, extra: Record<string, string> = {}) => ({
  ticket,
  position_id: pos,
  symbol: 'XAUUSD.m',
  entry,
  type: entry === 'in' ? 'buy' : 'sell',
  volume: '0.48',
  price,
  time: unix(at),
  commission: '-1.68',
  sl: '4367.60',
  tp: '4418.00',
  ...extra,
})

/** FTMO (MT5) with a 90-day import + today's trades and an SL change, so the card reads "Connected · 14 · 3"-like. */
async function seedConnected(request: APIRequestContext, token: string) {
  const accounts = await seedAccounts(request, token)
  const { api_key } = await apiCall<{ api_key: string }>(request, token, 'POST', `/accounts/${accounts.ftmo.id}/connections/mt5`)
  const now = new Date()
  const days = (n: number) => new Date(now.getTime() - n * 86_400_000)
  const history = [
    deal('H1', 'HP1', 'in', days(20), '4311.40'),
    deal('H2', 'HP1', 'out', new Date(days(20).getTime() + 3_600_000), '4355.82', { profit: '2132.16' }),
    deal('H3', 'HP2', 'in', days(9), '4358.30'),
    deal('H4', 'HP2', 'out', new Date(days(9).getTime() + 1_800_000), '4377.20', { profit: '907.20' }),
  ]
  await ingest(request, api_key, {
    symbols: [{ name: 'XAUUSD.m', digits: 2, point: '0.01', contract_size: '100', tick_size: '0.01', tick_value: '1' }],
    deals: history,
    history: { from: unix(days(90)), to: unix(now), final: true },
  })
  const t = new Date(now.getTime() - 40 * 60_000)
  await ingest(request, api_key, {
    deals: [deal('D1', 'P1', 'in', t, '4387.60'), deal('D2', 'P1', 'out', new Date(t.getTime() + 20 * 60_000), '4398.38', { profit: '517.44' }), deal('D3', 'P2', 'in', new Date(t.getTime() + 25 * 60_000), '4392.00')],
    positions: [{ position_id: 'P2', symbol: 'XAUUSD.m', type: 'buy', volume: '0.48', price_open: '4392.00', sl: '4380.00', tp: '4418.00', time: unix(t) }],
    modifications: [
      { id: 'P2:sl:1', position_id: 'P2', field: 'sl', old: '4367.60', new: '4380.00', time: unix(new Date(t.getTime() + 26 * 60_000)) },
    ],
  })
  return { ...accounts, apiKey: api_key }
}

/** Grow the viewport to the content so the fixed bottom nav lands at the end, like the design artboards. */
async function shot(page: Page, name: string) {
  // Wait for the per-account risk numbers (table daily loss / drawdown) so they aren't captured as "—".
  await page.waitForLoadState('networkidle')
  await page.evaluate(() => document.fonts.ready)
  const vp = page.viewportSize()!
  const height = await page.evaluate(() => document.documentElement.scrollHeight)
  await page.setViewportSize({ width: vp.width, height: Math.max(vp.height, height) })
  await page.screenshot({ path: out(name), fullPage: true })
  await page.setViewportSize(vp)
}

for (const theme of ['light', 'dark'] as const) {
  test(`connections screens (${theme})`, async ({ page, isMobile }) => {
    await prefs(page, theme, 'th')
    const { token } = await signUp(page, { theme })
    const { ftmo } = await seedConnected(page.request, token)

    if (isMobile) {
      await page.goto(`/accounts/connections?account=${ftmo.id}`)
      const mt5 = page.getByTestId('connection-mt5')
      await expect(mt5.getByText('Connected')).toBeVisible()
      await expect(mt5.getByText('90 วัน')).toBeVisible()
      await expect(page.getByTestId('connection-ctrader').getByRole('button', { name: 'เชื่อมต่อ cTrader' })).toBeVisible()
      await expect(page.getByText('Initial import · MT5')).toBeVisible()
      await shot(page, `connections-mobile-${theme}`)
      return
    }

    await page.goto(`/accounts?account=${ftmo.id}`)
    const card = page.getByTestId('connection-mt5')
    await expect(card.getByText('Connected')).toBeVisible()
    await expect(card.getByTestId('api-key')).toHaveText(/^tt_live_.{4}•+.{4}$/)
    await expect(card.getByText(/^\d+ · 1$/)).toBeVisible() // deals today · SL/TP mods
    await expect(page.getByRole('row', { name: /FTMO 100K Challenge/ }).getByText(/^Synced/)).toBeVisible()
    await expect(page.getByRole('row', { name: /Demo Practice/ }).getByText('ไม่เชื่อมต่อ')).toBeVisible()
    await shot(page, `connections-desktop-${theme}`)

    await page.getByRole('tab', { name: 'การเชื่อมต่อ' }).click()
    await expect(page.getByTestId('ingestion-history').getByText('Initial import · MT5')).toBeVisible()
    await shot(page, `connections-desktop-tab-${theme}`)
  })
}

test('create the key, see it once, rotate it, sync now; cTrader without an app is explained', async ({ page, isMobile }) => {
  test.skip(isMobile, 'same component on both sizes; desktop covers the flow')
  await prefs(page, 'light', 'th')
  const { token } = await signUp(page)
  const { ftmo, ic } = await seedAccounts(page.request, token)
  await page.goto(`/accounts?account=${ftmo.id}&tab=connections`)

  const card = page.getByTestId('connection-mt5')
  await card.getByRole('button', { name: 'สร้าง API key' }).click()
  const dialog = page.getByRole('dialog')
  const full = (await dialog.getByTestId('api-key').innerText()).trim()
  expect(full).toMatch(/^tt_live_[\w-]{32}$/)
  await expect(dialog.getByText('แสดงครั้งเดียว', { exact: false })).toBeVisible()
  await dialog.getByRole('button', { name: 'เสร็จแล้ว' }).click()

  // Waiting for the EA until it calls in — then the card turns Connected live (WS sync.status).
  await expect(card.getByText('รอสัญญาณจาก EA…')).toBeVisible()
  await ingest(page.request, full, { deals: [deal('D1', 'P1', 'in', new Date(), '4387.60')] })
  await expect(card.getByText('Connected')).toBeVisible({ timeout: 10_000 })
  await expect(page.getByTestId('ingestion-history').getByText('Sync · MT5')).toBeVisible()

  // Rotate: confirm, new key, the old one stops working.
  await card.getByRole('button', { name: 'สร้าง key ใหม่' }).click()
  await page.getByRole('dialog').getByRole('button', { name: 'สร้าง key ใหม่' }).click()
  const rotated = (await page.getByRole('dialog').getByTestId('api-key').innerText()).trim()
  expect(rotated).not.toBe(full)
  await page.getByRole('dialog').getByRole('button', { name: 'เสร็จแล้ว' }).click()
  const old = await page.request.post('/api/v1/ingest/events', { headers: { 'X-Api-Key': full }, data: { account: {} } })
  expect(old.status()).toBe(401)

  await card.getByRole('button', { name: 'Sync ตอนนี้' }).click()
  await expect(card.getByText('ส่งคำสั่งแล้ว', { exact: false })).toBeVisible()
  const beat = await ingest(page.request, rotated, {})
  expect(beat.commands).toEqual([expect.objectContaining({ kind: 'resync', params: { days: 7 } })])

  await page.goto(`/accounts?account=${ic.id}&tab=connections`)
  await page.getByTestId('connection-ctrader').getByRole('button', { name: 'เชื่อมต่อ cTrader' }).click()
  await expect(page.getByText('ยังไม่ได้ตั้งค่า cTrader Open API', { exact: false })).toBeVisible()
})

test('back from cTrader consent shows the result and cleans the URL', async ({ page, isMobile }) => {
  test.skip(isMobile, 'desktop only')
  await prefs(page, 'light', 'en')
  const { token } = await signUp(page, { locale: 'en' })
  const { ic } = await seedAccounts(page.request, token)
  await page.goto(`/accounts?account=${ic.id}&tab=connections&ctrader=error&reason=access_denied`)
  await expect(page.getByText('Could not connect cTrader')).toBeVisible()
  await expect(page.getByText('Reason: access_denied')).toBeVisible()
  await expect(page).toHaveURL((u) => !u.searchParams.has('ctrader') && u.searchParams.get('tab') === 'connections')
})
