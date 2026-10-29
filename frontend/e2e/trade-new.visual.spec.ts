import { expect, test, type Page } from '@playwright/test'
import { prefs, seedAccounts, signUp } from './helpers'
import { fillDesignTrade } from './trade-new.helpers'

// Phase 4: /trades/new?mode=manual vs screens/mobile/10-ManualTrade.png and screens/web/07-WAddTrade.png
// (manual tab) → docs/qa/phase-4/trade-new-{desktop,mobile}-{light,dark}.png. Needs the full stack.
test.skip(!process.env.E2E_BASE_URL, 'needs the full stack (set E2E_BASE_URL)')

const out = (name: string) => `../docs/qa/phase-4/${name}.png`

async function settle(page: Page) {
  await page.evaluate(() => document.fonts.ready)
  await page.waitForTimeout(500) // debounced preview + plan options
}

for (const theme of ['light', 'dark'] as const) {
  test(`add trade — manual (${theme})`, async ({ page }, info) => {
    await prefs(page, theme, 'th')
    const { token } = await signUp(page, { theme })
    await seedAccounts(page.request, token)
    await page.goto('/trades/new?mode=manual')
    await fillDesignTrade(page)
    await expect(page.getByTestId('calc-net')).toHaveText('+$968.00')
    await settle(page)
    await page.screenshot({ path: out(`trade-new-${info.project.name}-${theme}`), fullPage: true })
  })
}
