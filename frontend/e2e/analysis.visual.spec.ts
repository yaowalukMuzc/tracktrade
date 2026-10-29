import { expect, test, type Page } from '@playwright/test'
import { apiCall, prefs, seedAccounts, seedTradingDay, signUp } from './helpers'

// Phase 3: /analysis/:id vs screens/web/04-WAnalysis.png and screens/mobile/06-Analysis.png → docs/qa/phase-3/.
// Needs the full stack (E2E_BASE_URL). Chart bars are the backend's deterministic mock OHLC until Phase 4.
test.skip(!process.env.E2E_BASE_URL, 'needs the full stack (set E2E_BASE_URL)')

const out = (name: string) => `../docs/qa/phase-3/${name}.png`

/** The chart canvas has painted (lightweight-charts draws into <canvas> after layout). */
async function chartReady(page: Page) {
  await expect(page.getByTestId('trade-chart').locator('canvas').first()).toBeVisible()
  await page.waitForTimeout(400)
}

for (const theme of ['light', 'dark'] as const) {
  test(`analysis (${theme})`, async ({ page }, info) => {
    await prefs(page, theme, 'th')
    const { token } = await signUp(page, { theme })
    const { xau } = await seedTradingDay(page.request, token)

    await page.goto(`/analysis/${xau.id}`)
    await expect(page.getByText('4,380 – 4,388')).toBeVisible()
    if (info.project.name === 'desktop') await expect(page.getByText('Buy limit 4,387.52')).toBeVisible()
    await expect(page.getByText('ถ้าปิด H1 ใต้ 4,366')).toBeVisible()
    await chartReady(page)
    await page.evaluate(() => document.fonts.ready)
    if (info.project.name === 'mobile') {
      // Grow the viewport to the page so the sticky action bar + bottom nav sit at the end, not over the form.
      const height = await page.evaluate(() => document.documentElement.scrollHeight)
      await page.setViewportSize({ width: 390, height })
      await page.waitForTimeout(300)
    }
    await page.screenshot({ path: out(`analysis-${info.project.name}-${theme}`), fullPage: true })
  })
}

test('new analysis: bias, key level, drawing and narrative survive a reload (F-05 AC1–AC2, F-19 AC3)', async ({ page, isMobile }) => {
  await prefs(page, 'light', 'en')
  const { token } = await signUp(page, { locale: 'en' })
  await seedAccounts(page.request, token)

  await page.goto('/analysis/new?symbol=XAUUSD')
  await chartReady(page)
  await expect(page.getByText('Not saved yet')).toBeVisible()

  await page.getByRole('radio', { name: 'Bear' }).click()
  await page.getByRole('button', { name: isMobile ? 'Add level' : 'Add', exact: true }).click()
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel('Type').selectOption('resistance')
  await dialog.getByLabel('Price').fill('4437.5')
  await dialog.getByLabel('Note').fill('previous high')
  await dialog.getByRole('button', { name: 'Add level' }).click()
  await expect(page.getByText('4,437.50')).toBeVisible()

  await page.getByRole('button', { name: 'Horizontal line' }).click()
  const box = (await page.getByTestId('trade-chart').boundingBox())!
  await page.mouse.click(box.x + box.width * 0.5, box.y + box.height * 0.5)

  const editor = page.getByRole('textbox', { name: /^Narrative/ })
  await editor.click()
  await page.keyboard.type('DXY strong, gold below 4,437 → wait for a retest')

  await page.getByRole('button', { name: 'Save', exact: true }).click()
  await expect(page).toHaveURL(/\/analysis\/[0-9a-f-]{36}$/)
  const id = page.url().split('/').pop()!
  await expect(page.getByText(/^Autosaved \d{2}:\d{2}$/)).toBeVisible()
  await expect
    .poll(async () => (await apiCall<unknown[]>(page.request, token, 'GET', `/chart-drawings?owner_type=analysis&owner_id=${id}`)).length)
    .toBe(1)

  await page.reload()
  await expect(page.getByRole('radio', { name: 'Bear' })).toHaveAttribute('aria-checked', 'true')
  await expect(page.getByText('4,437.50')).toBeVisible()
  await expect(page.getByText('Resistance · previous high')).toBeVisible()
  await expect(page.getByRole('textbox', { name: /^Narrative/ })).toContainText('DXY strong, gold below 4,437 → wait for a retest')
  const saved = await apiCall<{ htf_bias: string; narrative_text: string; key_levels: { price: string }[] }>(page.request, token, 'GET', `/analyses/${id}`)
  expect(saved.htf_bias).toBe('bear')
  expect(saved.key_levels).toHaveLength(1)
  expect(saved.narrative_text).toContain('wait for a retest')

  // Autosave: a later change is saved without pressing Save.
  await page.getByRole('radio', { name: 'Range' }).click()
  await expect.poll(async () => (await apiCall<{ htf_bias: string }>(page.request, token, 'GET', `/analyses/${id}`)).htf_bias, { timeout: 8000 }).toBe('range')
})
