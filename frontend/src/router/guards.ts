import type { Router } from 'vue-router'
import { useSessionStore } from '@/stores/session'

/** Only same-app paths (`/x`, not `//host` or `https://…`) are honoured as post-login redirects. */
export function safeRedirect(value: unknown): string {
  return typeof value === 'string' && /^\/(?![/\\])/.test(value) ? value : '/'
}

/**
 * Auth guard (F-01): waits for the one-time session restore, then
 * - private route + signed out → /login?redirect=<path>
 * - guest-only route (login/register) + signed in → redirect target or /
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
  })
}
