import { expect, test } from '@playwright/test'
import { apiCall, prefs, seedAccounts, signUp } from './helpers'
import { fillDesignTrade, fillDialog } from './trade-new.helpers'

// Phase 4 / F-07: manual trade with scale-in + partial close (screens/mobile/10-ManualTrade.png).
// Needs the full stack (E2E_BASE_URL).
test.skip(!process.env.E2E_BASE_URL, 'needs the full stack (set E2E_BASE_URL)')

test('manual SHORT with scale-in + partial close: calc from the API, then saved (F-07 AC1–AC3)', async ({ page }) => {
  await prefs(page, 'light', 'th')
  const { token } = await signUp(page)
  await seedAccounts(page.request, token)
  await page.goto('/trades/new?mode=manual')

  await fillDesignTrade(page)
  const rows = page.getByTestId('exec-row')
  await expect(rows.nth(1)).toContainText('scale-in')
  await expect(rows.nth(2)).toContainText('partial')

  const calc = page.getByTestId('trade-calc')
  await expect(calc.getByTestId('calc-avg')).toHaveText('4,403.18 / 4,383.75')
  await expect(calc.getByTestId('calc-net')).toHaveText('+$968.00')
  await expect(calc.getByTestId('calc-r')).toHaveText('+2.10R')
  await expect(calc.getByTestId('calc-status')).toHaveText('Closed')
  await expect(calc).toContainText('−$3.50')

  // No plan exists → "decide later" → it waits in the match queue.
  await page.getByTestId('trade-save').click()
  // Saved as pending → /trades?match=<id>: desktop opens the match dialog over /trades,
  // mobile continues to the full-screen /trades/match.
  await expect(page).toHaveURL(/\/trades(\/match)?(\?|$)/)

  const list = await apiCall<{ items: { net_pnl: string; r_multiple: string; match_status: string; direction: string }[] }>(page.request, token, 'GET', '/positions')
  expect(list.items).toHaveLength(1)
  expect(list.items[0]).toMatchObject({ net_pnl: '968.00', r_multiple: '2.10', direction: 'short', match_status: 'pending' })
})

test('unplanned choice warns, validation blocks saving', async ({ page }) => {
  await prefs(page, 'light', 'th')
  const { token } = await signUp(page)
  await seedAccounts(page.request, token)
  await page.goto('/trades/new')

  // The blank starting row blocks saving, with the reason.
  await expect(page.getByTestId('trade-save')).toBeDisabled()
  await expect(page.getByTestId('trade-blocked').first()).toContainText('กรอก lot และราคา')

  await page.getByTestId('exec-row').first().click()
  await fillDialog(page, { side: 'in', lot: '1', price: '4380', time: '2026-10-09T10:00' })
  await page.getByTestId('add-exit').click()
  await fillDialog(page, { side: 'out', lot: '2', price: '4390', time: '2026-10-09T11:00' })
  // The API rejects closing more than is open.
  await expect(page.getByTestId('calc-error')).toContainText('Exit ปิด lot มากกว่า')
  await expect(page.getByTestId('trade-save')).toBeDisabled()

  await page.getByTestId('exec-row').nth(1).click()
  await page.getByTestId('exec-lot').fill('1')
  await page.getByTestId('exec-save').click()
  await expect(page.getByTestId('calc-net')).toHaveText('+$1,000.00')

  await page.getByTestId('trade-plan').selectOption('none')
  await expect(page.getByTestId('trade-plan-warn')).toContainText('นอกแผน')
  await page.getByTestId('trade-save').click()
  await expect(page).toHaveURL(/\/trades$/)
  const list = await apiCall<{ items: { is_unplanned: boolean; match_status: string }[] }>(page.request, token, 'GET', '/positions')
  expect(list.items[0]).toMatchObject({ is_unplanned: true, match_status: 'manual' })
})

test('scan tab is a calm placeholder', async ({ page }) => {
  await prefs(page, 'light', 'th')
  const { token } = await signUp(page)
  await seedAccounts(page.request, token)
  await page.goto('/trades/new?mode=scan')
  await expect(page.getByTestId('trade-scan')).toContainText('ยังไม่เปิดใช้')
  await page.getByTestId('trade-scan').getByRole('button').click()
  await expect(page).toHaveURL(/mode=manual/)
})
