import { expect, test, type Page } from '@playwright/test'
import { apiCall, prefs, seedTradingDay, signUp } from './helpers'

// Phase 3: /plans/:id vs screens/web/05-WPlan.png, screens/mobile/07-PlanForm.png, 08-PlanLocked.png → docs/qa/phase-3/.
// Needs the full stack (E2E_BASE_URL). Plan A stays "Locked" (the design shows "Triggered") until trades arrive in Phase 4.
test.skip(!process.env.E2E_BASE_URL, 'needs the full stack (set E2E_BASE_URL)')

const out = (name: string) => `../docs/qa/phase-3/${name}.png`

async function settle(page: Page) {
  await page.evaluate(() => document.fonts.ready)
  await page.waitForTimeout(400) // debounced calc + chart paint
}

for (const theme of ['light', 'dark'] as const) {
  test(`plan draft / locked / revision sheet (${theme})`, async ({ page }, info) => {
    await prefs(page, theme, 'th')
    const { token } = await signUp(page, { theme })
    const { planA, planB } = await seedTradingDay(page.request, token)

    // Draft (plan B, checklist 1/3).
    await page.goto(`/plans/${planB.id}`)
    await expect(page.getByTestId('plan-lock-btn')).toContainText('1/3')
    await expect(page.getByTestId('plan-calc')).not.toContainText('—')
    await settle(page)
    await page.screenshot({ path: out(`plan-${info.project.name}-${theme}`), fullPage: true })

    // Locked (plan A, pre-trade emotion logged).
    await page.goto(`/plans/${planA.id}`)
    await expect(page.getByTestId('plan-lock')).toContainText('rev 1')
    await settle(page)
    await page.screenshot({ path: out(`plan-locked-${info.project.name}-${theme}`), fullPage: true })

    // Revision sheet with a moved SL and the live risk delta.
    await page.getByTestId('plan-revise-btn').click()
    const dialog = page.getByRole('dialog')
    await dialog.getByLabel('SL ใหม่').fill('4,360.00')
    await expect(dialog.getByTestId('revision-delta')).toContainText('Risk')
    await settle(page)
    await page.screenshot({ path: out(`plan-revision-${info.project.name}-${theme}`), fullPage: !info.project.name.includes('mobile') })
  })
}

test('lock blocked by the checklist, then lock + revision with a reason (F-06 AC3–AC4)', async ({ page }) => {
  await prefs(page, 'light', 'th')
  const { token } = await signUp(page)
  const { planB } = await seedTradingDay(page.request, token)
  await page.goto(`/plans/${planB.id}`)

  // AC3: required items missing → warning + red checklist, nothing locked.
  const lockBtn = page.getByTestId('plan-lock-btn')
  await expect(lockBtn).toContainText('1/3')
  await lockBtn.click()
  await expect(page.getByTestId('plan-cant-lock')).toContainText('ยังล็อกไม่ได้')
  const checklist = page.getByTestId('plan-checklist')
  await expect(checklist.locator('.tt-check--missing')).toHaveCount(2)
  expect((await apiCall<{ status: string }>(page.request, token, 'GET', `/plans/${planB.id}`)).status).toBe('draft')

  // Tick the rest → lock (saves the answers first).
  const unchecked = checklist.getByRole('checkbox', { checked: false })
  while ((await unchecked.count()) > 0) await unchecked.first().click()
  await expect(lockBtn).toContainText('3/3')
  await lockBtn.click()
  await expect(page.getByTestId('plan-lock')).toContainText(/sha256 · \w{4}…\w{4} · rev 1/)
  await expect(page.getByTestId('plan-status')).toHaveText('Locked')

  // AC4: a change after the lock = a revision with a reason.
  await page.getByTestId('plan-revise-btn').click()
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel('SL ใหม่').fill('4,385.00')
  const saveBtn = dialog.getByRole('button', { name: 'บันทึก revision' })
  await expect(saveBtn).toBeDisabled()
  await dialog.getByLabel('เหตุผล').fill('ข่าวออกก่อนเวลา ขยับ SL ลดความเสี่ยง')
  await expect(dialog.getByTestId('revision-delta')).toBeVisible()
  await saveBtn.click()

  const revisions = page.getByTestId('plan-revisions')
  await expect(revisions.locator('[data-rev="2"]')).toContainText('rev 2')
  await expect(revisions.locator('[data-rev="2"]')).toContainText('SL 4,378.40 → 4,385.00')
  await expect(revisions.locator('[data-rev="2"]')).toContainText('ข่าวออกก่อนเวลา')
  await expect(page.getByTestId('plan-lock')).toContainText('rev 2')
  const plan = await apiCall<{ current_revision: number; stop_loss: string }>(page.request, token, 'GET', `/plans/${planB.id}`)
  expect(plan.current_revision).toBe(2)
  expect(Number(plan.stop_loss)).toBe(4385)
})
