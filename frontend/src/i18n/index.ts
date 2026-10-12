import { createI18n } from 'vue-i18n'
import th from './locales/th.json'
import en from './locales/en.json'

export type Locale = 'th' | 'en'
export const LOCALES: Locale[] = ['th', 'en']
export const LOCALE_KEY = 'tt.locale'

type MessageSchema = typeof th

function savedLocale(): Locale {
  try {
    const v = localStorage.getItem(LOCALE_KEY)
    if (v === 'th' || v === 'en') return v
  } catch {
    /* storage unavailable */
  }
  return 'th'
}

export const i18n = createI18n<[MessageSchema], Locale, false>({
  legacy: false,
  locale: savedLocale(),
  fallbackLocale: 'en',
  messages: { th, en },
})
