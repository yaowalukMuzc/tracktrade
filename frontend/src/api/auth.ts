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

export interface AuthResult {
  user: User
  access_token: string
}

export interface RegisterInput {
  email: string
  password: string
  display_name: string
  locale: Locale
  timezone: string
  accept_terms: boolean
}

export const authApi = {
  register: (body: RegisterInput) => api<AuthResult>('/auth/register', { method: 'POST', body, auth: false }),
  login: (body: { email: string; password: string; remember: boolean }) =>
    api<AuthResult>('/auth/login', { method: 'POST', body, auth: false }),
  logout: () => api<void>('/auth/logout', { method: 'POST', auth: false }),
  me: () => api<User>('/me'),
  updateMe: (body: Partial<Pick<User, 'display_name' | 'locale' | 'timezone' | 'theme'>>) =>
    api<User>('/me', { method: 'PATCH', body }),
}
