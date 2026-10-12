import { expect, test } from '@playwright/test'

// Phase 1 visual check: /login and /register at 1440 (desktop project) and 390 (mobile project), both themes.
// Screenshots go to docs/qa/phase-1/ to be compared by eye with screens/web/01-WLogin.png,
// screens/mobile/01-Main.png and screens/mobile/02-Register.png (the mocks use fallback fonts, so no pixel diff).
const out = (name: string) => `../docs/qa/phase-1/${name}.png`

for (const theme of ['light', 'dark'] as const) {
  test(`login + register (${theme})`, async ({ page }, info) => {
    await page.addInitScript((t) => {
      localStorage.setItem('tt.theme', t)
      localStorage.setItem('tt.locale', 'th')
    }, theme)

    await page.goto('/login')
    await expect(page.getByRole('heading', { name: 'เข้าสู่ระบบ' })).toBeVisible()
    await page.evaluate(() => document.fonts.ready)
    await page.screenshot({ path: out(`login-${info.project.name}-${theme}`), fullPage: true })

    // No white text on the lavender brand fill (CLAUDE.md non-negotiable).
    const whiteOnBrand = await page.evaluate(() => {
      const brand = getComputedStyle(document.documentElement).getPropertyValue('--brand-600').trim()
      const toRgb = (c: string) => {
        const el = document.createElement('i')
        el.style.color = c
        document.body.append(el)
        const v = getComputedStyle(el).color
        el.remove()
        return v
      }
      const brandRgb = toRgb(brand)
      return [...document.querySelectorAll<HTMLElement>('body *')].filter((el) => {
        const s = getComputedStyle(el)
        return s.backgroundColor === brandRgb && s.color === 'rgb(255, 255, 255)' && el.innerText?.trim()
      }).length
    })
    expect(whiteOnBrand).toBe(0)

    await page.goto('/register')
    await expect(page.getByRole('heading', { name: 'สร้างบัญชี' })).toBeVisible()
    await page.getByLabel('รหัสผ่าน', { exact: true }).fill('trade1')
    await page.getByLabel('รหัสผ่าน', { exact: true }).blur()
    await expect(page.getByText('รหัสผ่านต้องยาวอย่างน้อย 8 ตัวอักษร (ตอนนี้ 6)')).toBeVisible()
    await page.screenshot({ path: out(`register-${info.project.name}-${theme}`), fullPage: true })
  })
}

test('language switches without reload (F-01 AC3)', async ({ page }) => {
  await page.goto('/login')
  await page.evaluate(() => ((window as unknown as { __marker: number }).__marker = 1))
  await page.getByRole('radio', { name: 'EN' }).first().click()
  await expect(page.getByRole('heading', { name: 'Log in' })).toBeVisible()
  expect(await page.evaluate(() => (window as unknown as { __marker?: number }).__marker)).toBe(1)
  expect(await page.evaluate(() => document.documentElement.lang)).toBe('en')
})
