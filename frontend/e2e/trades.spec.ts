import { expect, test, type APIRequestContext, type Page } from '@playwright/test'
import { apiCall, prefs, seedTradingDay, signUp } from './helpers'

// /trades + match queue (screens/web/06-WTrades.png, screens/mobile/09-Trades.png, 12-MatchQueue.png).
// Needs the full stack: E2E_BASE_URL=http://localhost:5180 npx playwright test e2e/trades

test.skip(!process.env.E2E_BASE_URL, 'needs the full stack (E2E_BASE_URL)')

const OUT = '../docs/qa/phase-4'
const iso = (d: Date) => d.toISOString()
const unix = (d: Date) => Math.floor(d.getTime() / 1000)

/**
 * The design's day: plan A (locked, from seedTradingDay) + plan C (locked market 4392) → an MT5 fill at
 * 4,387.60 fits both → waits for the trader; an MT5 EURUSD short with no plan → waits too; an open manual
 * SHORT linked to draft plan B (unplanned); two closed trades yesterday.
 */
async function seedTrades(request: APIRequestContext, token: string) {
  const call = <T>(method: 'GET' | 'POST' | 'PUT', path: string, data?: unknown) => apiCall<T>(request, token, method, path, data)
  const day = await seedTradingDay(request, token)
  const sym = (code: string) => day.symbols.find((s) => s.code === code)!.id
  const london = (await call<{ checklist: { id: string }[] }>('GET', `/setups/${day.london.id}`)).checklist
  const c = await call<{ id: string }>('POST', '/plans', {
    analysis_id: day.xau.id, setup_id: day.london.id, account_id: day.ftmo.id, symbol_id: sym('XAUUSD'), direction: 'long',
    entry_type: 'market', entry_price: '4392.00', stop_loss: '4371.05', take_profits: [{ price: '4430' }], planned_risk_pct: '1',
    checklist_answers: london.map((i) => ({ checklist_item_id: i.id, checked: true })),
  })
  await call('POST', `/plans/${c.id}/lock`)

  // Plans were locked just now; the MT5 fills come after the lock (as in the design: locked 09:12, fill 10:05).
  const now = new Date()
  const ago = (min: number) => new Date(now.getTime() - min * 60_000)
  const later = (sec: number) => new Date(now.getTime() + sec * 1000)
  const yesterday = (h: number, m: number) => {
    const d = new Date(now.getTime() - 86_400_000)
    d.setHours(h, m, 0, 0)
    return d
  }
  // Closed yesterday: a full SL loss and a small NY Reversal loss.
  await call('POST', '/positions', {
    account_id: day.ftmo.id, symbol_id: sym('XAUUSD'), direction: 'long', initial_sl: '4350.12', initial_tp: '4413.36', unplanned: true,
    executions: [
      { side: 'in', lot: '0.48', price: '4371.20', executed_at: iso(yesterday(15, 0)) },
      { side: 'out', lot: '0.48', price: '4350.12', executed_at: iso(yesterday(16, 12)) },
    ],
  })
  await call('POST', '/positions', {
    account_id: day.ftmo.id, symbol_id: sym('GBPUSD'), direction: 'short', initial_sl: '1.33541', unplanned: true,
    executions: [
      { side: 'in', lot: '0.10', price: '1.33410', executed_at: iso(yesterday(9, 30)) },
      { side: 'out', lot: '0.10', price: '1.33541', executed_at: iso(yesterday(9, 32)) },
    ],
  })
  // Open manual SHORT on draft plan B → unplanned.
  await call('POST', '/positions', {
    account_id: day.ftmo.id, symbol_id: sym('XAUUSD'), direction: 'short', initial_sl: '4412.40', initial_tp: '4371.00', plan_id: day.planB.id,
    executions: [
      { side: 'in', lot: '0.30', price: '4402.10', executed_at: iso(ago(30)) },
      { side: 'in', lot: '0.20', price: '4404.80', executed_at: iso(ago(9)) },
    ],
  })
  // MT5: two synced trades that wait for the trader.
  const key = (await call<{ api_key: string }>('POST', `/accounts/${day.ftmo.id}/connections/mt5`)).api_key
  const deal = (ticket: string, pos: string, symbol: string, entry: 'in' | 'out', type: 'buy' | 'sell', volume: string, price: string, t: Date, profit = '0', sl = '0') =>
    ({ ticket, position_id: pos, symbol, entry, type, volume, price, time: unix(t), commission: '-1.68', profit, sl })
  const res = await request.post('/api/v1/ingest/events', {
    headers: { 'X-Api-Key': key },
    data: {
      ea_version: '1.0.0',
      account: { login: '5120934', server: 'FTMO-Demo', currency: 'USD', balance: '101240.00', equity: '101757.00' },
      deals: [
        deal('1001', 'P1', 'XAUUSD', 'in', 'buy', '0.48', '4387.60', later(1), '0', '4367.60'),
        deal('1002', 'P1', 'XAUUSD', 'out', 'sell', '0.48', '4398.38', later(90), '517.44'),
        deal('2001', 'P2', 'EURUSD', 'in', 'sell', '0.50', '1.08402', later(3), '0', '1.10352'),
        deal('2002', 'P2', 'EURUSD', 'out', 'buy', '0.50', '1.08597', later(60), '-97.50'),
      ],
    },
  })
  expect(res.ok(), await res.text()).toBeTruthy()
  return { ...day, planC: c }
}

async function signIn(page: Page, theme: 'light' | 'dark' = 'light') {
  await prefs(page, theme)
  const { token } = await signUp(page, { theme })
  return token
}

test('desktop: list, tabs, and the match queue modal', async ({ page }, info) => {
  test.skip(info.project.name !== 'desktop', 'desktop layout')
  const token = await signIn(page)
  await seedTrades(page.request, token)
  await page.goto('/trades')

  await expect(page.getByRole('tab', { name: /ทั้งหมด/ })).toContainText('5')
  await expect(page.getByRole('tab', { name: /รอจับคู่/ })).toContainText('2')
  await expect(page.getByTestId('pending-alert')).toContainText('2 เทรดรอจับคู่กับแผน')
  await expect(page.locator('tbody tr')).toHaveCount(5)
  await expect(page.locator('tbody')).toContainText('+$514.08') // 517.44 − 1.68 × 2
  await expect(page.locator('tbody')).toContainText('−$1,011.84') // −21.08 × 0.48 × 100
  // Sidebar badge = trades waiting for a plan.
  await expect(page.locator('nav').getByText('2', { exact: true }).first()).toBeVisible()

  // Tabs filter the table.
  await page.getByRole('tab', { name: /เปิดอยู่/ }).click()
  await expect(page).toHaveURL(/tab=open/)
  await expect(page.locator('tbody tr')).toHaveCount(1)
  await page.getByRole('tab', { name: /ทั้งหมด/ }).click()

  // Match queue: the XAUUSD fill fits plans A and C — A is closer and recommended.
  await page.getByRole('button', { name: 'จับคู่ตอนนี้' }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog).toContainText('1 จาก 2')
  await expect(dialog).toContainText('A · Buy limit 4,387.52')
  await expect(dialog).toContainText('ห่าง entry 0.08 (0.4% ของระยะ SL)')
  await expect(dialog.getByText('แนะนำ')).toBeVisible()
  await page.screenshot({ path: `${OUT}/trades-modal-desktop-light.png`, fullPage: false })
  await dialog.getByTestId('match-confirm').click()

  // EURUSD: no plan → "no plan" is preselected.
  await expect(dialog).toContainText('2 จาก 2')
  await expect(dialog.getByTestId('match-option-unplanned').locator('input')).toBeChecked()
  await dialog.getByTestId('match-confirm').click()
  await expect(dialog).toBeHidden()
  await expect(page.getByTestId('pending-alert')).toBeHidden()
  await expect(page.getByRole('tab', { name: /รอจับคู่/ })).toContainText('0')
  await expect(page.locator('tbody')).toContainText('London Breakout · A')

  // $ / R toggle remembered.
  await page.getByRole('radio', { name: 'R' }).click()
  await expect(page.locator('tbody')).toContainText('+0.54R')
  await page.reload()
  await expect(page.getByRole('radio', { name: 'R' })).toHaveAttribute('aria-checked', 'true')
})

test('desktop: search and CSV export', async ({ page }, info) => {
  test.skip(info.project.name !== 'desktop', 'desktop layout')
  const token = await signIn(page)
  await seedTrades(page.request, token)
  await page.goto('/trades')
  await page.getByTestId('trades-search').fill('eur')
  await expect(page).toHaveURL(/q=eur/)
  await expect(page.locator('tbody tr')).toHaveCount(1)
  const download = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Export CSV' }).click()
  expect((await download).suggestedFilename()).toBe('tracktrade-trades.csv')
})

test('mobile: cards by day and the full-screen match queue', async ({ page }, info) => {
  test.skip(info.project.name !== 'mobile', 'mobile layout')
  const token = await signIn(page)
  await seedTrades(page.request, token)
  await page.goto('/trades')
  await expect(page.getByTestId('trade-card')).toHaveCount(5)
  await expect(page.getByText(/^วันนี้ · /)).toBeVisible()
  await expect(page.getByText(/^เมื่อวาน · /)).toBeVisible()
  await page.getByTestId('pending-alert').click()
  await expect(page).toHaveURL(/\/trades\/match/)
  await expect(page.getByTestId('match-counter')).toHaveText('1 / 2')
  await expect(page.getByText('แนะนำ · ตรงที่สุด')).toBeVisible()
  await page.screenshot({ path: `${OUT}/trades-match-mobile-light.png`, fullPage: true })
  await page.getByTestId('match-confirm').click()
  await expect(page.getByTestId('match-counter')).toHaveText('2 / 2')
  await page.getByRole('button', { name: 'ข้าม' }).click()
  await expect(page).toHaveURL(/\/trades$/)
  await expect(page.getByTestId('pending-alert')).toContainText('1 เทรดรอจับคู่กับแผน')
})

for (const theme of ['light', 'dark'] as const) {
  test(`screenshot ${theme}`, async ({ page }, info) => {
    const token = await signIn(page, theme)
    await seedTrades(page.request, token)
    await page.goto('/trades')
    await expect(page.getByTestId('pending-alert')).toBeVisible()
    await page.screenshot({ path: `${OUT}/trades-${info.project.name}-${theme}.png`, fullPage: true })
  })
}
