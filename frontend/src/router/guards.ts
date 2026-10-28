import type { Router } from 'vue-router'
import { useAccountsStore } from '@/stores/accounts'
import { useSessionStore } from '@/stores/session'

const SKIP_KEY = 'tt.onboarding.skipped'

/** "Skip for now" on onboarding: don't force it again in this browser session. */
export function skipOnboarding() {
  try {
    sessionStorage.setItem(SKIP_KEY, '1')
  } catch {
    /* storage unavailable */
  }
}

function onboardingSkipped() {
  try {
    return sessionStorage.getItem(SKIP_KEY) === '1'
  } catch {
    return false
  }
}

/** Only same-app paths (`/x`, not `//host` or `https://…`) are honoured as post-login redirects. */
export function safeRedirect(value: unknown): string {
  return typeof value === 'string' && /^\/(?![/\\])/.test(value) ? value : '/'
}

/**
 * Auth guard (F-01 AC7): waits for the one-time session restore, then
 * - any route not marked `public` (only login/register/forgot/reset are) + signed out → /login?redirect=<path>
 * - guest-only route (login/register/forgot) + signed in → redirect target or /
 * - signed in without any trading account → /onboarding (unless skipped this session)
 */
export function installGuards(router: Router) {
  router.beforeEach(async (to) => {
    const session = useSessionStore()
    await session.restore()

    if (!to.meta.public && !session.isAuthenticated) {
      return { name: 'login', query: to.fullPath === '/' ? {} : { redirect: to.fullPath } }
    }
    if (to.meta.guestOnly && session.isAuthenticated) {
      return safeRedirect(to.query.redirect)
    }
    if (session.isAuthenticated && !to.meta.public && to.name !== 'onboarding' && !onboardingSkipped()) {
      const accounts = useAccountsStore()
      try {
        await accounts.ensureLoaded()
      } catch {
        return // API down: let the page show its own error state
      }
      if (accounts.accounts.length === 0) return { name: 'onboarding', query: to.fullPath === '/' ? {} : { redirect: to.fullPath } }
    }
  })
}
