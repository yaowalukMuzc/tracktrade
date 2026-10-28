import { api } from './client'
import type { Locale } from '@/i18n'

export type ThemePref = 'light' | 'dark' | 'system'

/** `GET /me` — mirrors backend `UserOut`. */
export interface User {
  id: string
  email: string
  display_name: string
  locale: Locale
  timezone: string
  theme: ThemePref
  plan_tier: 'free' | 'pro'
  is_mentor: boolean
}

export const authApi = {
  me: () => api<User>('/me'),
  updateMe: (body: Partial<Pick<User, 'display_name' | 'locale' | 'timezone' | 'theme'>>) =>
    api<User>('/me', { method: 'PATCH', body }),
}
