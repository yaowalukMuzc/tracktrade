import { expect, test } from '@playwright/test'

// Phase 2 visual check of the Better Auth screens without a mock (PLAN §8.2): /forgot-password and
// /reset-password reuse the Login split layout. 1440 (desktop) + 390 (mobile), both themes → docs/qa/phase-2/.
const out = (name: string) => `../docs/qa/phase-2/${name}.png`

for (const theme of ['light', 'dark'] as const) {
  test(`forgot + reset password (${theme})`, async ({ page }, info) => {
    await page.addInitScript((t) => {
      localStorage.setItem('tt.theme', t)
      localStorage.setItem('tt.locale', 'th')
    }, theme)

    await page.goto('/login')
    await page.getByRole('link', { name: 'ลืมรหัสผ่าน?' }).click()
    await expect(page.getByRole('heading', { name: 'ลืมรหัสผ่าน' })).toBeVisible()
    await page.evaluate(() => document.fonts.ready)
    await page.screenshot({ path: out(`forgot-${info.project.name}-${theme}`), fullPage: true })

    await page.goto('/reset-password?token=demo')
    await expect(page.getByRole('heading', { name: 'ตั้งรหัสผ่านใหม่' })).toBeVisible()
    await page.getByLabel('รหัสผ่านใหม่', { exact: true }).fill('short')
    await page.getByLabel('ยืนยันรหัสผ่านใหม่').fill('other')
    await page.getByRole('button', { name: 'บันทึกรหัสผ่านใหม่' }).click()
    await expect(page.getByText('รหัสผ่านทั้งสองช่องไม่ตรงกัน')).toBeVisible()
    await page.screenshot({ path: out(`reset-${info.project.name}-${theme}`), fullPage: true })

    // Without a token the page explains and offers a new link.
    await page.goto('/reset-password')
    await expect(page.getByRole('link', { name: 'ขอลิงก์ใหม่' })).toBeVisible()
  })
}
