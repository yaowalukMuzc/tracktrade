import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

export interface TradingAccount {
  id: string
  name: string
  accountType: 'live' | 'demo' | 'prop'
}

// TODO(F-02): load from /accounts. Dev fixtures until the API exists.
export const useAccountsStore = defineStore('accounts', () => {
  const accounts = ref<TradingAccount[]>([
    { id: 'ftmo-100k', name: 'FTMO 100K', accountType: 'prop' },
    { id: 'ic-live', name: 'IC Markets Live', accountType: 'live' },
  ])
  /** null = "All accounts" (F-02 AC3). */
  const selectedId = ref<string | null>(null)
  const selected = computed(() => accounts.value.find((a) => a.id === selectedId.value) ?? null)

  function select(id: string | null) {
    selectedId.value = id
  }

  return { accounts, selectedId, selected, select }
})
