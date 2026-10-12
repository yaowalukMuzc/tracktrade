import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

export type Role = 'trader' | 'mentor'

export interface SessionUser {
  displayName: string
  role: Role
  planTier: 'free' | 'pro'
  traderCount?: number
}

// TODO(F-01): replace the dev user with the authenticated profile from /auth.
export const useSessionStore = defineStore('session', () => {
  const user = ref<SessionUser | null>({ displayName: 'Nook Knight', role: 'trader', planTier: 'free' })

  const initials = computed(() =>
    (user.value?.displayName ?? '')
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((w) => w.charAt(0).toUpperCase())
      .join(''),
  )
  const firstName = computed(() => user.value?.displayName.split(/\s+/)[0] ?? '')
  const isMentor = computed(() => user.value?.role === 'mentor')

  function logout() {
    user.value = null
  }

  return { user, initials, firstName, isMentor, logout }
})
