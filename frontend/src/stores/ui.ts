import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import { i18n, LOCALE_KEY, type Locale } from '@/i18n'

export type Theme = 'light' | 'dark'
const THEME_KEY = 'tt.theme'

function read(key: string) {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}
function write(key: string, value: string) {
  try {
    localStorage.setItem(key, value)
  } catch {
    /* storage unavailable — preference lasts for this session only */
  }
}

function initialTheme(): Theme {
  const saved = read(THEME_KEY)
  if (saved === 'light' || saved === 'dark') return saved
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export const useUiStore = defineStore('ui', () => {
  const theme = ref<Theme>(initialTheme())
  const locale = ref<Locale>(i18n.global.locale.value)

  watch(
    theme,
    (t) => {
      document.documentElement.dataset.theme = t
      document
        .querySelector('meta[name="theme-color"]')
        ?.setAttribute('content', t === 'dark' ? '#1A1718' : '#F6F7F0')
    },
    { immediate: true },
  )

  // F-01 AC3: language switches instantly, no reload.
  watch(
    locale,
    (l) => {
      i18n.global.locale.value = l
      document.documentElement.lang = l
    },
    { immediate: true },
  )

  function setTheme(t: Theme) {
    theme.value = t
    write(THEME_KEY, t)
  }
  function toggleTheme() {
    setTheme(theme.value === 'dark' ? 'light' : 'dark')
  }
  function setLocale(l: Locale) {
    locale.value = l
    write(LOCALE_KEY, l)
  }

  return { theme, locale, setTheme, toggleTheme, setLocale }
})
