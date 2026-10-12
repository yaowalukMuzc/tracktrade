import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { authApi, type RegisterInput, type User } from '@/api/auth'
import { onSessionLost, refreshAccessToken, setAccessToken } from '@/api/client'
import { realtime } from '@/api/ws'
import { router } from '@/router'
import { useUiStore, type ThemePref } from './ui'
import type { Locale } from '@/i18n'

type Status = 'unknown' | 'authenticated' | 'anonymous'

/** Signed-in user (F-01). Access token stays in memory (api/client); a reload restores it via the refresh cookie. */
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
  function signedIn(u: User, token?: string) {
    if (token) setAccessToken(token)
    user.value = u
    status.value = 'authenticated'
    const ui = useUiStore()
    ui.setLocale(u.locale)
    ui.setTheme(u.theme)
    realtime.connect()
  }

  function signedOut() {
    setAccessToken(null)
    user.value = null
    status.value = 'anonymous'
    realtime.disconnect()
  }

  /** Runs once per page load (router guard awaits it): refresh cookie → access token → /me. */
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

  async function login(email: string, password: string, remember: boolean) {
    const res = await authApi.login({ email, password, remember })
    signedIn(res.user, res.access_token)
  }

  async function register(input: RegisterInput) {
    const res = await authApi.register(input)
    signedIn(res.user, res.access_token)
  }

  async function logout() {
    try {
      await authApi.logout()
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

  return { user, status, isAuthenticated, initials, firstName, isMentor, restore, login, register, logout, updateProfile }
})
