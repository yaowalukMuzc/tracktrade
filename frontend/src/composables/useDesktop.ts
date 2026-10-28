import { useMediaQuery } from '@vueuse/core'

/** ≥1024px = desktop layout (sidebar, tables, modals); below = mobile (cards, sheets). PLAN §2.8. */
export function useDesktop() {
  return useMediaQuery('(min-width: 1024px)')
}
