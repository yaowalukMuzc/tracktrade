import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { authApi, type User } from '@/api/auth'
import { authClient, unwrap } from '@/api/authClient'
import { onSessionLost, refreshAccessToken, setAccessToken } from '@/api/client'
import { realtime } from '@/api/ws'
import { router } from '@/router'
import { useAccountsStore } from './accounts'
import { useUiStore, type ThemePref } from './ui'
import type { Locale } from '@/i18n'

type Status = 'unknown' | 'authenticated' | 'anonymous'

export interface RegisterInput {
  email: string
  password: string
  display_name: string
  locale: Locale
  timezone: string
}

/**
 * Signed-in user (F-01, Better Auth). The session is an httpOnly cookie of the auth service; the JWT used for
 * FastAPI stays in memory (api/client) and a reload gets a fresh one from that cookie.
 */
export const useSessionStore = defineStore('session', () => {
  const user = ref<User | null>(null)
  const status = ref<Status>('unknown')
  let restoring: Promise<void> | null = null

  const isAuthenticated = computed(() => status.value === 'authenticated')
  const initials = computed(() =>
    (user.value?.display_name ?? '')
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((w) => w.charAt(0).toUpperCase())
      .join(''),
  )
  const firstName = computed(() => user.value?.display_name.split(/\s+/)[0] ?? '')
  // Mentor workspace switching arrives with F-22 (Phase 8); everyone is in the trader workspace until then.
  const isMentor = computed(() => false)

  /** The user's saved locale/theme win over this device's defaults once known (syncs settings across devices). */
  function signedIn(u: User) {
    user.value = u
    status.value = 'authenticated'
    const ui = useUiStore()
    ui.setLocale(u.locale)
    ui.setTheme(u.theme)
    realtime.connect()
  }

  function signedOut() {
    setAccessToken(null)
    useAccountsStore().reset()
    user.value = null
    status.value = 'anonymous'
    realtime.disconnect()
  }

  /** Runs once per page load (router guard awaits it): session cookie → JWT → /me. */
  function restore() {
    restoring ??= (async () => {
      try {
        if (await refreshAccessToken()) return signedIn(await authApi.me())
      } catch {
        /* fall through to anonymous */
      }
      signedOut()
    })()
    return restoring
  }

  /** After Better Auth set the session cookie: get a JWT and load the profile from FastAPI. */
  async function startSession() {
    restoring = Promise.resolve()
    if (!(await refreshAccessToken())) throw new Error('no token after sign-in')
    signedIn(await authApi.me())
  }

  async function login(email: string, password: string, remember: boolean) {
    await unwrap(authClient.signIn.email({ email, password, rememberMe: remember }))
    await startSession()
  }

  async function register(input: RegisterInput) {
    await unwrap(
      authClient.signUp.email({
        email: input.email,
        password: input.password,
        name: input.display_name,
        locale: input.locale,
        timezone: input.timezone,
      }),
    )
    await startSession()
  }

  /** F-01 AC5: always resolves the same way whether or not the email exists. */
  async function requestPasswordReset(email: string) {
    await unwrap(authClient.requestPasswordReset({ email, redirectTo: '/reset-password' }))
  }

  /** F-01 AC6: the auth service revokes every session of the user. */
  async function resetPassword(token: string, newPassword: string) {
    await unwrap(authClient.resetPassword({ token, newPassword }))
    if (status.value === 'authenticated') signedOut()
  }

  async function logout() {
    try {
      await unwrap(authClient.signOut())
    } catch {
      /* already signed out on the server */
    } finally {
      signedOut()
      await router.push({ name: 'login' })
    }
  }

  /** Saves profile/preferences. Locale and theme apply locally first so the UI never waits on the network. */
  async function updateProfile(patch: { display_name?: string; locale?: Locale; timezone?: string; theme?: ThemePref }) {
    const ui = useUiStore()
    if (patch.locale) ui.setLocale(patch.locale)
    if (patch.theme) ui.setTheme(patch.theme)
    if (!isAuthenticated.value) return
    user.value = await authApi.updateMe(patch)
  }

  onSessionLost(() => {
    if (status.value !== 'authenticated') return
    signedOut()
    const current = router.currentRoute.value
    void router.push({ name: 'login', query: { redirect: current.fullPath } })
  })

  return {
    user,
    status,
    isAuthenticated,
    initials,
    firstName,
    isMentor,
    restore,
    login,
    register,
    requestPasswordReset,
    resetPassword,
    logout,
    updateProfile,
  }
})
