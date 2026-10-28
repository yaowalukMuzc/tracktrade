import { expect, test, type APIRequestContext } from '@playwright/test'

// F-01 AC5–AC6 full stack: forgot → email (Mailpit API) → reset → old sessions revoked → login with new password.
// Run against the stack: E2E_BASE_URL=http://localhost:8080 E2E_MAIL_API=http://localhost:8025 npx playwright test password-reset
test.skip(!process.env.E2E_BASE_URL, 'needs the full stack (set E2E_BASE_URL)')

const MAIL_API = process.env.E2E_MAIL_API ?? 'http://localhost:8025'

/** Newest reset link sent to `email` (Mailpit `/api/v1/messages` + `/api/v1/message/:id`). */
async function resetLink(request: APIRequestContext, email: string): Promise<string> {
  for (let i = 0; i < 40; i++) {
    const list = (await (await request.get(`${MAIL_API}/api/v1/messages`)).json()) as {
      messages: { ID: string; To: { Address: string }[] }[]
    }
    const msg = list.messages.find((m) => m.To.some((t) => t.Address === email))
    if (msg) {
      const body = (await (await request.get(`${MAIL_API}/api/v1/message/${msg.ID}`)).json()) as { Text: string }
      const link = body.Text.match(/https?:\/\/\S+\/reset-password\?token=[\w-]+/)?.[0]
      if (link) return link
    }
    await new Promise((r) => setTimeout(r, 250))
  }
  throw new Error(`no reset email for ${email}`)
}

test('forgot → reset link → every session revoked → login with the new password', async ({ page, browser, request }) => {
  const email = `reset+${Date.now()}-${Math.random().toString(36).slice(2, 7)}@example.com`
  await page.addInitScript(() => localStorage.setItem('tt.locale', 'en'))

  // Device 1: register (stays signed in).
  await page.goto('/register')
  await page.getByLabel('Display name').fill('Reset Trader')
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password', { exact: true }).fill('old-password-1')
  await page.getByRole('checkbox').check()
  await page.getByRole('button', { name: 'Create account' }).click()
  // A new user without a trading account lands on onboarding (covered by onboarding.visual).
  await expect(page).toHaveURL((url) => url.pathname === '/onboarding')

  // Device 2: forgot password. Same answer for an unknown email.
  const other = await browser.newContext()
  const p2 = await other.newPage()
  await p2.addInitScript(() => localStorage.setItem('tt.locale', 'en'))
  await p2.goto('/login')
  await p2.getByRole('link', { name: 'Forgot password?' }).click()
  await expect(p2).toHaveURL(/\/forgot-password/)
  await p2.getByLabel('Email').fill('nobody-here@example.com')
  await p2.getByRole('button', { name: 'Send reset link' }).click()
  const unknownText = await p2.getByRole('status').innerText()
  await p2.goto('/forgot-password')
  await p2.getByLabel('Email').fill(email)
  await p2.getByRole('button', { name: 'Send reset link' }).click()
  await expect(p2.getByText('Check your email')).toBeVisible()
  expect((await p2.getByRole('status').innerText()).replace(email, '')).toBe(unknownText.replace('nobody-here@example.com', ''))

  // Open the emailed link and set a new password.
  const link = await resetLink(request, email)
  await p2.goto(new URL(link).pathname + new URL(link).search)
  await p2.getByLabel('New password', { exact: true }).fill('new-password-2')
  await p2.getByLabel('Confirm new password').fill('new-password-2')
  await p2.getByRole('button', { name: 'Save new password' }).click()
  await expect(p2.getByText('Password updated')).toBeVisible()

  // The link works once.
  await p2.goto(new URL(link).pathname + new URL(link).search)
  await p2.getByLabel('New password', { exact: true }).fill('another-pass-3')
  await p2.getByLabel('Confirm new password').fill('another-pass-3')
  await p2.getByRole('button', { name: 'Save new password' }).click()
  await expect(p2.getByText('This reset link is not valid')).toBeVisible()

  // Device 1 was signed out: the next navigation lands on /login.
  await page.goto('/settings')
  await expect(page).toHaveURL(/\/login\?redirect=/)

  // Old password fails, new one works.
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password', { exact: true }).fill('old-password-1')
  await page.getByRole('button', { name: 'Log in' }).click()
  await expect(page.getByText('Email or password is incorrect')).toBeVisible()
  await page.getByLabel('Password', { exact: true }).fill('new-password-2')
  await page.getByRole('button', { name: 'Log in' }).click()
  // Signed in with the new password; no trading account yet, so onboarding first (redirect kept).
  await expect(page).toHaveURL((url) => url.pathname === '/onboarding' && url.searchParams.get('redirect') === '/settings')
  await other.close()
})
