import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'
import { usePreferredDark } from '@vueuse/core'
import { i18n, LOCALE_KEY, type Locale } from '@/i18n'

export type ThemePref = 'light' | 'dark' | 'system'
export type ResolvedTheme = 'light' | 'dark'
export const THEME_KEY = 'tt.theme'

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

function savedTheme(): ThemePref {
  const saved = read(THEME_KEY)
  return saved === 'light' || saved === 'dark' || saved === 'system' ? saved : 'system'
}

/**
 * Viewer preferences applied to <html>: `data-theme` (always resolved to light/dark), `lang`, theme-color meta.
 * Saved to localStorage immediately; the session store also syncs them to `PATCH /me` when signed in.
 */
export const useUiStore = defineStore('ui', () => {
  const theme = ref<ThemePref>(savedTheme())
  const locale = ref<Locale>(i18n.global.locale.value)
  const prefersDark = usePreferredDark()
  const resolvedTheme = computed<ResolvedTheme>(() =>
    theme.value === 'system' ? (prefersDark.value ? 'dark' : 'light') : theme.value,
  )

  watch(
    resolvedTheme,
    (t) => {
      const root = document.documentElement
      root.dataset.theme = t
      // theme-color follows the --bg token of the active theme.
      const bg = getComputedStyle(root).getPropertyValue('--bg').trim()
      if (bg) document.querySelector('meta[name="theme-color"]')?.setAttribute('content', bg)
    },
    { immediate: true, flush: 'post' },
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

  function setTheme(t: ThemePref) {
    theme.value = t
    write(THEME_KEY, t)
  }
  function toggleTheme() {
    setTheme(resolvedTheme.value === 'dark' ? 'light' : 'dark')
  }
  function setLocale(l: Locale) {
    locale.value = l
    write(LOCALE_KEY, l)
  }

  return { theme, resolvedTheme, locale, setTheme, toggleTheme, setLocale }
})
