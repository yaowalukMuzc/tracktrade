import { expect, test, type Page } from '@playwright/test'
import { apiCall, prefs, signUp } from './helpers'

// Phase 2 onboarding (F-02 AC1–AC2): screenshots to docs/qa/phase-2/ to compare by eye with
// screens/web/02-WOnboarding.png, screens/mobile/03-Onboarding.png and 04-ConnectBroker.png, plus the save flow.
test.skip(!process.env.E2E_BASE_URL, 'needs the full stack (set E2E_BASE_URL)')

const out = (name: string) => `../docs/qa/phase-2/onboarding-${name}.png`

/** No white text on the lavender brand fill (CLAUDE.md non-negotiable). */
async function whiteOnBrand(page: Page) {
  return page.evaluate(() => {
    const el = document.createElement('i')
    el.style.color = getComputedStyle(document.documentElement).getPropertyValue('--brand-600').trim()
    document.body.append(el)
    const brand = getComputedStyle(el).color
    el.remove()
    return [...document.querySelectorAll<HTMLElement>('body *')].filter((n) => {
      const s = getComputedStyle(n)
      return s.backgroundColor === brand && s.color === 'rgb(255, 255, 255)' && n.innerText?.trim()
    }).length
  })
}

/** Grow the viewport to the content so the sticky mobile footer lands at the end, like the design artboards. */
async function shot(page: Page, name: string) {
  const vp = page.viewportSize()!
  const height = await page.evaluate(() => document.documentElement.scrollHeight)
  await page.setViewportSize({ width: vp.width, height: Math.max(vp.height, height) })
  await page.screenshot({ path: out(name), fullPage: true })
  await page.setViewportSize(vp)
}

async function fillAccount(page: Page) {
  await page.getByLabel('ชื่อบัญชี').fill('FTMO 100K Challenge')
  await page.getByRole('radio', { name: 'Prop' }).click()
  await page.getByLabel('Broker').fill('FTMO')
  await page.getByLabel('Initial balance').fill('100000')
  await page.getByLabel('Initial balance').blur()
}

for (const theme of ['light', 'dark'] as const) {
  test(`onboarding screens (${theme})`, async ({ page, isMobile }) => {
    await prefs(page, theme, 'th')
    // The saved user theme wins over the stored pref once signed in, so set it on the account too.
    await signUp(page, { email: `nook+${Date.now()}@email.com`, theme })
    await page.goto('/')
    await expect(page).toHaveURL((u) => u.pathname === '/onboarding')
    await fillAccount(page)
    // Live preview: 1% of $100,000 (F-02 AC2 defaults).
    await expect(page.getByText('1% ของ $100,000 = $1,000 ต่อเทรด')).toBeVisible()
    await expect(page.getByText('Daily loss $3,000 · DD limit $10,000')).toBeVisible()
    await page.evaluate(() => document.fonts.ready)

    if (!isMobile) {
      await page.getByText('MT5 (EA)').click()
      await expect(page.getByText('การซิงก์อัตโนมัติจะเปิดในอัปเดตถัดไป')).toBeVisible()
      expect(await whiteOnBrand(page)).toBe(0)
      await shot(page, `desktop-${theme}`)
      return
    }
    expect(await whiteOnBrand(page)).toBe(0)
    await shot(page, `mobile-${theme}`)
    await page.getByRole('button', { name: 'ถัดไป: เชื่อมต่อ Broker' }).click()
    await expect(page.getByRole('heading', { name: 'เลือกวิธีบันทึกเทรด' })).toBeVisible()
    await page.getByText('MT5 (EA)').click()
    await expect(page.getByText('การซิงก์อัตโนมัติจะเปิดในอัปเดตถัดไป')).toBeVisible()
    await shot(page, `mobile-step2-${theme}`)
  })
}

test('validates, then saves the account with its risk profile in one go', async ({ page, isMobile }) => {
  await prefs(page, 'light', 'th')
  const { token } = await signUp(page)
  await page.goto('/onboarding?redirect=/calendar')

  const save = isMobile ? 'ถัดไป: เชื่อมต่อ Broker' : 'บันทึกและเริ่มใช้งาน'
  await page.getByRole('button', { name: save }).click()
  await expect(page.getByText('กรุณากรอกช่องนี้')).toHaveCount(3)
  await expect(page.getByLabel('ชื่อบัญชี')).toBeFocused()

  await fillAccount(page)
  const risk: [string, string][] = [
    ['Risk ต่อเทรด', '0.5'],
    ['Max daily loss', '12'],
    ['Max drawdown', '8'],
    ['Max trades / วัน', '3'],
    ['Revenge cooldown', '45'],
    ['News blackout', '20'],
  ]
  for (const [label, value] of risk) await page.getByLabel(label).fill(value)
  // Daily loss above drawdown is rejected like the backend does.
  await expect(page.getByText('Max daily loss ต้องไม่เกิน Max drawdown')).toBeVisible()
  await page.getByLabel('Max daily loss').fill('2')
  await expect(page.getByText('0.5% ของ $100,000 = $500 ต่อเทรด')).toBeVisible()

  await page.getByRole('button', { name: save }).click()
  if (isMobile) await page.getByRole('button', { name: 'เริ่มใช้งาน' }).click()
  await expect(page).toHaveURL((u) => u.pathname === '/calendar')

  const accounts = await apiCall<{ id: string; name: string; broker: string; account_type: string; platform: string; currency: string; initial_balance: string }[]>(
    page.request,
    token,
    'GET',
    '/accounts',
  )
  expect(accounts).toHaveLength(1)
  expect(accounts[0]).toMatchObject({ name: 'FTMO 100K Challenge', broker: 'FTMO', account_type: 'prop', platform: 'mt5', currency: 'USD' })
  expect(Number(accounts[0].initial_balance)).toBe(100000)
  const rp = await apiCall<Record<string, string | number>>(page.request, token, 'GET', `/accounts/${accounts[0].id}/risk-profile`)
  expect([rp.risk_per_trade_pct, rp.max_daily_loss_pct, rp.max_drawdown_pct].map(Number)).toEqual([0.5, 2, 8])
  expect([rp.max_trades_per_day, rp.revenge_cooldown_min, rp.news_blackout_min]).toEqual([3, 45, 20])
})

test('skip for now goes to the redirect target', async ({ page, isMobile }) => {
  await prefs(page, 'light', 'en')
  await signUp(page, { locale: 'en' })
  await page.goto('/onboarding?redirect=/stats')
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(isMobile ? 'Set up trading account' : 'Set up your first trading account')
  await page.getByRole('button', { name: 'Skip for now' }).click()
  await expect(page).toHaveURL((u) => u.pathname === '/stats')
})
