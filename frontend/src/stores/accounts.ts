import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

export interface TradingAccount {
  id: string
  name: string
  accountType: 'live' | 'demo' | 'prop'
}

const SELECTED_KEY = 'tt.account'

function savedSelection() {
  try {
    return localStorage.getItem(SELECTED_KEY)
  } catch {
    return null
  }
}

// TODO(F-02, Phase 2): load from GET /accounts. Until then the list is empty and the switcher shows "All accounts".
export const useAccountsStore = defineStore('accounts', () => {
  const accounts = ref<TradingAccount[]>([])
  /** null = "All accounts" (F-02 AC3). */
  const selectedId = ref<string | null>(savedSelection())
  const selected = computed(() => accounts.value.find((a) => a.id === selectedId.value) ?? null)

  function select(id: string | null) {
    selectedId.value = id
    try {
      if (id) localStorage.setItem(SELECTED_KEY, id)
      else localStorage.removeItem(SELECTED_KEY)
    } catch {
      /* storage unavailable */
    }
  }

  return { accounts, selectedId, selected, select }
})
