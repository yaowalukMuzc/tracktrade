import { expect, test } from '@playwright/test'

// Full-stack flow (needs the API): register → empty shell → logout → login → reload keeps session → logout.
// Run against docker compose: E2E_BASE_URL=http://localhost:8080 npx playwright test auth.flow
test.skip(!process.env.E2E_BASE_URL, 'needs the full stack (set E2E_BASE_URL)')

test('register, logout, login, refresh-on-reload, logout', async ({ page, isMobile }) => {
  const email = `e2e+${Date.now()}-${Math.random().toString(36).slice(2, 7)}@example.com`
  const password = 'correct-horse-9'

  await page.addInitScript(() => localStorage.setItem('tt.locale', 'en'))
  await page.goto('/')
  await expect(page).toHaveURL(/\/login/)

  await page.goto('/register')
  await page.getByLabel('Display name').fill('E2E Trader')
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password', { exact: true }).fill(password)
  await page.getByRole('checkbox').check()
  await page.getByRole('button', { name: 'Create account' }).click()

  // Empty shell
  await expect(page).toHaveURL(/\/$/)
  await expect(page.getByRole('heading', { level: 1 })).toContainText('E2E')
  const nav = isMobile ? page.getByRole('navigation', { name: 'Bottom menu' }) : page.getByRole('navigation', { name: 'Main menu' })
  await expect(nav).toBeVisible()

  // Session survives a reload via the refresh cookie (access token is memory-only).
  await page.reload()
  await expect(page).toHaveURL(/\/$/)

  const logout = async () => {
    if (isMobile) {
      await page.goto('/more')
      await page.getByRole('button', { name: 'Log out' }).click()
    } else {
      await page.getByRole('button', { name: 'Log out' }).click()
    }
    await expect(page).toHaveURL((url) => url.pathname === '/login')
  }
  await logout()

  // Logged out: private routes bounce to /login with a redirect back.
  await page.goto('/settings')
  await expect(page).toHaveURL(/\/login\?redirect=(%2F|\/)settings$/)

  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'Log in' }).click()
  // Match the pathname: `/login?redirect=/settings` must not count as arriving.
  await expect(page).toHaveURL((url) => url.pathname === '/settings')
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  await logout()
})

test('wrong password shows an error', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('tt.locale', 'en'))
  await page.goto('/login')
  await page.getByLabel('Email').fill('nobody@example.com')
  await page.getByLabel('Password', { exact: true }).fill('wrong-password')
  await page.getByRole('button', { name: 'Log in' }).click()
  await expect(page.getByText('Email or password is incorrect')).toBeVisible()
})
