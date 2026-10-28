import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { accountsApi, type Account, type AccountInput } from '@/api/accounts'

const SELECTED_KEY = 'tt.account'

function savedSelection() {
  try {
    return localStorage.getItem(SELECTED_KEY)
  } catch {
    return null
  }
}

/**
 * The signed-in user's trading accounts + the account filter (F-02 AC3).
 * `selectedId === null` means "All accounts"; every list/report sends `accountParam` to the API.
 */
export const useAccountsStore = defineStore('accounts', () => {
  const accounts = ref<Account[]>([])
  const loaded = ref(false)
  const selectedId = ref<string | null>(savedSelection())
  let loading: Promise<void> | null = null

  /** Active accounts only — archived ones are hidden from the switcher. */
  const active = computed(() => accounts.value.filter((a) => a.is_active))
  const selected = computed(() => active.value.find((a) => a.id === selectedId.value) ?? null)
  /** Query param for API calls: `{ account_id }` or `{}` for all accounts. */
  const accountParam = computed<{ account_id?: string }>(() => (selected.value ? { account_id: selected.value.id } : {}))

  function select(id: string | null) {
    selectedId.value = id
    try {
      if (id) localStorage.setItem(SELECTED_KEY, id)
      else localStorage.removeItem(SELECTED_KEY)
    } catch {
      /* storage unavailable */
    }
  }

  async function load() {
    accounts.value = await accountsApi.list(true)
    loaded.value = true
    // A remembered account that was archived or belongs to someone else falls back to "All".
    if (selectedId.value && !selected.value) select(null)
  }

  /** Loads once per session (router guard awaits it). */
  function ensureLoaded() {
    loading ??= load().catch((e) => {
      loading = null
      throw e
    })
    return loading
  }

  async function create(body: AccountInput) {
    const account = await accountsApi.create(body)
    accounts.value = [...accounts.value, account]
    loaded.value = true
    return account
  }

  /** Replace one account in the list after an update / archive. */
  function upsert(account: Account) {
    const i = accounts.value.findIndex((a) => a.id === account.id)
    if (i === -1) accounts.value = [...accounts.value, account]
    else accounts.value = accounts.value.map((a) => (a.id === account.id ? account : a))
    if (selectedId.value === account.id && !account.is_active) select(null)
  }

  function reset() {
    accounts.value = []
    loaded.value = false
    loading = null
  }

  return { accounts, active, loaded, selectedId, selected, accountParam, select, load, ensureLoaded, create, upsert, reset }
})
