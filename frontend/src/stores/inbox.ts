import { defineStore } from 'pinia'
import { ref } from 'vue'

// Nav badge counts. TODO: feed from the API / WebSocket (F-10 match queue, F-12 reviews, F-20 alerts).
export const useInboxStore = defineStore('inbox', () => {
  const pendingTrades = ref(0)
  const unreadAlerts = ref(0)
  const mentorQueue = ref(0)
  return { pendingTrades, unreadAlerts, mentorQueue }
})
