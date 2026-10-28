import { expect, test } from '@playwright/test'
import { apiCall, prefs, seedAccounts, signUp } from './helpers'

// Phase 2: /accounts vs screens/web/14-WAccounts.png and screens/mobile/23-Accounts.png → docs/qa/phase-2/.
// Needs the full stack (E2E_BASE_URL). Usage numbers stay 0 until trades exist (Phase 4).
test.skip(!process.env.E2E_BASE_URL, 'needs the full stack (set E2E_BASE_URL)')

const out = (name: string) => `../docs/qa/phase-2/${name}.png`

for (const theme of ['light', 'dark'] as const) {
  test(`accounts (${theme})`, async ({ page }, info) => {
    await prefs(page, theme, 'th')
    const { token } = await signUp(page, { theme })
    const { ftmo } = await seedAccounts(page.request, token)
    const symbols = await apiCall<{ id: string; code: string }[]>(page.request, token, 'GET', '/symbols')
    const sym = (code: string) => symbols.find((s) => s.code === code)!.id
    await apiCall(page.request, token, 'POST', `/accounts/${ftmo.id}/rules`, { code: 'no_trading_window', params: { days: [4], after: '20:00' }, severity: 'high' })
    await apiCall(page.request, token, 'POST', `/accounts/${ftmo.id}/rules`, { code: 'max_lot_vs_plan', params: { ratio: '1.2' }, severity: 'medium' })
    await apiCall(page.request, token, 'PUT', `/accounts/${ftmo.id}/symbol-overrides`, { broker_symbol: 'XAUUSD.m', symbol_id: sym('XAUUSD') })
    await apiCall(page.request, token, 'PUT', `/accounts/${ftmo.id}/symbol-overrides`, { broker_symbol: 'EURUSD.m', symbol_id: sym('EURUSD') })

    await page.goto(`/accounts?account=${ftmo.id}`)
    await expect(page.getByText('ห้ามเทรดศุกร์หลัง 20:00')).toBeVisible()
    await page.evaluate(() => document.fonts.ready)
    await page.screenshot({ path: out(`accounts-${info.project.name}-${theme}`), fullPage: true })
  })
}

test('edit risk profile → new version + audit entry; add rule; archive (F-02 AC1, AC4)', async ({ page, isMobile }) => {
  await prefs(page, 'light', 'en')
  const { token } = await signUp(page, { locale: 'en' })
  const { ftmo, demo } = await seedAccounts(page.request, token)
  await page.goto(`/accounts?account=${ftmo.id}`)

  if (isMobile) await page.getByRole('button', { name: 'Edit Risk Profile' }).click()
  const risk = page.getByLabel('Risk per trade')
  await risk.fill('0.75')
  await page.getByLabel('Max trades / day').fill('4')
  await page.getByRole('button', { name: 'Save', exact: true }).click()
  await expect.poll(async () => (await apiCall<{ version: number }>(page.request, token, 'GET', `/accounts/${ftmo.id}/risk-profile`)).version).toBe(2)

  // The explanation follows the values: 0.75% of $100,000 = $750.
  if (!isMobile) await expect(page.getByText('0.75% of $100,000 = $750 per trade')).toBeVisible()

  if (!isMobile) {
    await page.getByRole('tab', { name: 'Audit log' }).click()
    await expect(page.getByText('Risk per trade: 1.00 → 0.75')).toBeVisible()
  } else {
    await expect(page.getByText('Risk per trade: 1.00 → 0.75')).toBeVisible()
  }

  // Add a custom rule.
  if (!isMobile) await page.getByRole('tab', { name: 'Extra rules' }).click()
  await page.getByRole('button', { name: isMobile ? 'Rule' : 'Add rule' }).first().click()
  await page.getByLabel('Rule type').selectOption('custom')
  await page.getByLabel('Rule', { exact: true }).fill('No trading on less than 6 hours of sleep')
  await page.getByRole('button', { name: 'Add rule' }).last().click()
  await expect(page.getByText('No trading on less than 6 hours of sleep')).toBeVisible()

  // Archive the demo account: hidden from the list, data kept.
  await page.goto(`/accounts?account=${demo.id}`)
  if (isMobile) {
    await page.getByRole('button', { name: 'Archive account' }).click()
  } else {
    await page.getByRole('button', { name: 'Options for Demo Practice' }).click()
    await page.getByRole('menuitem', { name: 'Archive account' }).click()
  }
  await page.getByRole('dialog').getByRole('button', { name: 'Archive account' }).click()
  await expect(page.getByText('Demo Practice')).toHaveCount(0)
  const all = await apiCall<{ id: string; is_active: boolean }[]>(page.request, token, 'GET', '/accounts?include_archived=true')
  expect(all.find((a) => a.id === demo.id)?.is_active).toBe(false)
})
