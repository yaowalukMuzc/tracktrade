import { defineStore } from 'pinia'
import { ref } from 'vue'
import { positionsApi } from '@/api/positions'
import { realtime } from '@/api/ws'

// Events that can change the number of trades waiting for a plan.
const TRADE_EVENTS = new Set(['position.created', 'position.updated', 'position.deleted', 'match.pending'])

/**
 * Nav badge counts. `pendingTrades` = trades waiting for a plan (F-10 AC2) — fetched once signed in and
 * refreshed on realtime trade events. Alerts (F-20) and the mentor queue (F-22) arrive in Phase 6 / 8.
 */
export const useInboxStore = defineStore('inbox', () => {
  const pendingTrades = ref(0)
  const unreadAlerts = ref(0)
  const mentorQueue = ref(0)
  let stop: (() => void) | null = null
  let timer: ReturnType<typeof setTimeout> | undefined

  async function refreshTrades() {
    try {
      pendingTrades.value = (await positionsApi.list({ tab: 'pending' }, 0, 1)).counts.pending
    } catch {
      /* keep the last value; the badge is a hint */
    }
  }

  /** Start listening (AppLayout mounts it); several events in a burst cause one refetch. */
  function start() {
    void refreshTrades()
    stop ??= realtime.on((msg) => {
      if (!TRADE_EVENTS.has(msg.type)) return
      clearTimeout(timer)
      timer = setTimeout(refreshTrades, 300)
    })
  }

  function reset() {
    stop?.()
    stop = null
    pendingTrades.value = 0
  }

  return { pendingTrades, unreadAlerts, mentorQueue, refreshTrades, start, reset }
})
