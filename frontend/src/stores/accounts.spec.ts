import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { Account } from '@/api/accounts'
import { setAccessToken } from '@/api/client'
import { useAccountsStore } from './accounts'

const acc = (id: string, over: Partial<Account> = {}): Account => ({
  id,
  name: id.toUpperCase(),
  broker: 'B',
  platform: 'mt5',
  account_type: 'prop',
  account_number: null,
  currency: 'USD',
  initial_balance: '1000',
  is_active: true,
  archived_at: null,
  created_at: '2026-10-01T00:00:00Z',
  ...over,
})

// F-02 AC3: "All accounts" or one account, remembered per device; archived/unknown ids fall back to All.
describe('accounts store (account switcher)', () => {
  const fetchMock = vi.fn<typeof fetch>()
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    setAccessToken('t')
    vi.stubGlobal('fetch', fetchMock)
  })
  afterEach(() => {
    fetchMock.mockReset()
    vi.unstubAllGlobals()
  })
  const respond = (body: unknown) => fetchMock.mockResolvedValueOnce(new Response(JSON.stringify(body), { status: 200 }))

  it('defaults to all accounts and builds the API filter', async () => {
    respond([acc('a'), acc('b')])
    const store = useAccountsStore()
    await store.ensureLoaded()
    expect(String(fetchMock.mock.calls[0][0])).toBe('/api/v1/accounts?include_archived=true')
    expect(store.selected).toBeNull()
    expect(store.accountParam).toEqual({})
    store.select('b')
    expect(store.accountParam).toEqual({ account_id: 'b' })
    expect(localStorage.getItem('tt.account')).toBe('b')
  })

  it('restores a saved selection, but drops one that is archived or unknown', async () => {
    localStorage.setItem('tt.account', 'b')
    respond([acc('a'), acc('b')])
    const store = useAccountsStore()
    await store.ensureLoaded()
    expect(store.selected?.id).toBe('b')

    setActivePinia(createPinia())
    localStorage.setItem('tt.account', 'b')
    respond([acc('a'), acc('b', { is_active: false })])
    const again = useAccountsStore()
    await again.ensureLoaded()
    expect(again.selectedId).toBeNull()
    expect(again.active.map((a) => a.id)).toEqual(['a'])
  })

  it('archiving the selected account switches back to all', async () => {
    respond([acc('a')])
    const store = useAccountsStore()
    await store.ensureLoaded()
    store.select('a')
    store.upsert(acc('a', { is_active: false }))
    expect(store.selectedId).toBeNull()
  })

  it('loads once per session and can be reset on sign-out', async () => {
    respond([acc('a')])
    const store = useAccountsStore()
    await Promise.all([store.ensureLoaded(), store.ensureLoaded()])
    expect(fetchMock).toHaveBeenCalledTimes(1)
    store.reset()
    expect(store.accounts).toEqual([])
    expect(store.loaded).toBe(false)
  })
})
