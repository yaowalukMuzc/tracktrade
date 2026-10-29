import { expect, test, type Page } from '@playwright/test'
import { prefs, seedTradingDay, signUp } from './helpers'

// Phase 3: Today (/) vs screens/web/03-WToday.png and screens/mobile/05-Today.png → docs/qa/phase-3/.
// Honest data only: P/L $0.00 · 0 trades and adherence "—" until trades exist; no news provider yet,
// so the news banner is hidden and the news card is empty; plan A is Locked (no trade has triggered it).
test.skip(!process.env.E2E_BASE_URL, 'needs the full stack (set E2E_BASE_URL)')

const out = (name: string) => `../docs/qa/phase-3/${name}.png`

async function ready(page: Page) {
  await expect(page.getByTestId('today-plans').getByText('B · XAUUSD')).toBeVisible()
  await page.evaluate(() => document.fonts.ready)
}

for (const theme of ['light', 'dark'] as const) {
  test(`today (${theme})`, async ({ page, isMobile }, info) => {
    await prefs(page, theme, 'th')
    const { token } = await signUp(page, { theme })
    await seedTradingDay(page.request, token)

    await page.goto('/')
    await ready(page)
    if (!isMobile) {
      // Read-only chart with the analysis' drawings; let it paint.
      await expect(page.getByTestId('trade-chart').locator('canvas').first()).toBeVisible()
      await page.waitForTimeout(500)
    }
    await page.screenshot({ path: out(`today-${info.project.name}-${theme}`), fullPage: true })
  })
}

test('daily mood is saved and still there after reload (F-11 AC5)', async ({ page }) => {
  await prefs(page, 'light', 'th')
  const { token } = await signUp(page)
  await seedTradingDay(page.request, token)
  await page.goto('/')
  await ready(page)

  const card = page.getByTestId('daily-mood')
  await card.getByRole('button', { name: 'อารมณ์วันนี้ 7' }).click()
  await card.getByRole('button', { name: 'มีสมาธิ' }).click()
  await expect(card.getByText('บันทึกแล้ว')).toBeVisible()

  await page.reload()
  await ready(page)
  await expect(card.getByRole('button', { name: 'อารมณ์วันนี้ 7' })).toHaveAttribute('aria-pressed', 'true')
  await expect(card.getByRole('button', { name: 'มีสมาธิ' })).toHaveAttribute('aria-pressed', 'true')
})

test('account switcher filters analyses and plans (F-02 AC3)', async ({ page }) => {
  await prefs(page, 'light', 'th')
  const { token } = await signUp(page)
  await seedTradingDay(page.request, token)
  await page.goto('/')
  await ready(page)

  const plans = page.getByTestId('today-plans')
  const choose = async (name: string) => {
    await page.getByRole('button', { name: 'เลือกบัญชี' }).click()
    await page.getByRole('option', { name }).click()
  }

  await choose('Demo Practice')
  await expect(plans.getByText('ยังไม่มีแผนของวันนี้')).toBeVisible()
  await expect(plans.getByText('XAUUSD')).toHaveCount(0)
  await expect(page.getByTestId('today-analysis-empty')).toBeVisible()

  await choose('ทุกบัญชี')
  await expect(plans.getByText('B · XAUUSD')).toBeVisible()
  await expect(page.getByTestId('today-analysis').first()).toBeVisible()
})
