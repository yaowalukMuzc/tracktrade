import { expect, test } from '@playwright/test'
import { apiCall, prefs, seedAccounts, signUp } from './helpers'

// Phase 3 flow (docs/prompts/phase-3.md): analysis → plan A → tick checklist → lock → move SL via a revision.
// Everything through the UI except the account and setup (Phase 2 screens, covered by their own specs).
test.skip(!process.env.E2E_BASE_URL, 'needs the full stack (set E2E_BASE_URL)')

test('analysis → plan → checklist → lock → revision', async ({ page, isMobile }) => {
  test.skip(isMobile, 'one run is enough; the screens have their own mobile specs')
  await prefs(page, 'light', 'en')
  const { token } = await signUp(page, { locale: 'en' })
  await seedAccounts(page.request, token)
  await apiCall(page.request, token, 'POST', '/setups', {
    name: 'London Breakout',
    timeframes: ['M15', 'H1'],
    sessions: ['london'],
    default_risk_pct: '1',
    management_rules: { partial: { pct: '50', at_r: '1.5' }, break_even: { at_r: '1' }, trailing: null },
    checklist: [
      { text: 'H4 bias in the trade direction', is_required: true },
      { text: 'Price inside the demand zone' },
      { text: 'M15 confirmation candle', is_required: true },
    ],
  })

  // 1. Analysis (F-05).
  await page.goto('/analysis/new?symbol=XAUUSD')
  await expect(page.getByTestId('trade-chart').locator('canvas').first()).toBeVisible()
  await page.getByRole('radio', { name: 'Bull' }).click()
  await page.getByRole('button', { name: 'Save', exact: true }).click()
  await expect(page).toHaveURL(/\/analysis\/[0-9a-f-]{36}$/)
  const analysisId = page.url().split('/').pop()!

  // 2. Plan A from the analysis (F-05 AC3, F-06 AC1–AC2).
  await page.getByRole('button', { name: 'Create plan from this analysis' }).click()
  await expect(page).toHaveURL(new RegExp(`/plans/new\\?analysis=${analysisId}`))
  const prices = page.getByTestId('plan-prices')
  await prices.getByLabel('Entry').fill('4387.52')
  await prices.getByLabel('Stop loss').fill('4366.78')
  await page.getByLabel('TP1 price').fill('4418')
  // Lot / risk / R:R are calculated while typing: 1% of $100,000 over 20.74 → 0.48 lot.
  await expect(page.getByTestId('plan-calc').first()).toContainText('0.48')
  await page.getByRole('button', { name: 'Save draft' }).click()
  await expect(page).toHaveURL(/\/plans\/[0-9a-f-]{36}$/)
  const planId = page.url().split('/').pop()!
  const draft = await apiCall<{ scenario_label: string; analysis_id: string; planned_lot: string }>(page.request, token, 'GET', `/plans/${planId}`)
  expect(draft).toMatchObject({ scenario_label: 'A', analysis_id: analysisId, planned_lot: '0.48' })

  // 3. Checklist → lock (F-06 AC3–AC4).
  const lockBtn = page.getByTestId('plan-lock-btn')
  await expect(lockBtn).toContainText('0/3')
  const checklist = page.getByTestId('plan-checklist')
  const unchecked = checklist.getByRole('checkbox', { checked: false })
  while ((await unchecked.count()) > 0) await unchecked.first().click()
  await lockBtn.click()
  await expect(page.getByTestId('plan-status')).toHaveText('Locked')
  await expect(page.getByTestId('plan-lock')).toContainText(/sha256 · \w{4}…\w{4} · rev 1/)

  // 4. Move the SL through a revision with a reason (F-06 AC4).
  await page.getByTestId('plan-revise-btn').click()
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel('New SL').fill('4360')
  await dialog.getByLabel('Reason').fill('Stop hunt risk before the news')
  await dialog.getByRole('button', { name: 'Save revision' }).click()
  await expect(page.getByTestId('plan-revisions').locator('[data-rev="2"]')).toContainText('Stop hunt risk before the news')

  const plan = await apiCall<{ current_revision: number; stop_loss: string; planned_lot: string; lock_hash: string; current_hash: string }>(
    page.request,
    token,
    'GET',
    `/plans/${planId}`,
  )
  expect(plan.current_revision).toBe(2)
  expect(Number(plan.stop_loss)).toBe(4360)
  expect(plan.planned_lot).toBe('0.36') // before the entry the lot follows the 1% risk
  expect(plan.current_hash).not.toBe(plan.lock_hash)

  // The analysis lists the plan.
  await page.goto(`/analysis/${analysisId}`)
  await expect(page.getByRole('link', { name: /A.*Buy limit 4,387\.52/ })).toBeVisible()
})
