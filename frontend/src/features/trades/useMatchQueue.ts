import { computed, ref } from 'vue'
import { positionsApi, type MatchQueueItem } from '@/api/positions'
import { UNPLANNED, defaultChoice } from './model'

/**
 * Walks the trades waiting for a plan (F-10 AC2–AC3): pick → confirm (PUT /match) → next, or skip.
 * `startId` puts that trade first; a trade that is not pending (re-matching an already linked one) is
 * loaded on its own with its candidates.
 */
export function useMatchQueue(opts: { accountId?: () => string | undefined; onMatched?: (id: string) => void } = {}) {
  const items = ref<MatchQueueItem[]>([])
  const index = ref(0)
  const choice = ref<string>(UNPLANNED)
  const state = ref<'idle' | 'loading' | 'ready' | 'error'>('idle')
  const saving = ref(false)
  const saveError = ref(false)

  const current = computed(() => items.value[index.value] ?? null)
  const done = computed(() => state.value === 'ready' && !current.value)

  function pickDefault() {
    choice.value = current.value ? (defaultChoice(current.value.candidates) ?? UNPLANNED) : UNPLANNED
  }

  async function single(id: string): Promise<MatchQueueItem> {
    const [position, candidates] = await Promise.all([positionsApi.get(id), positionsApi.candidates(id)])
    const first = [...position.executions].filter((e) => e.side === 'in').sort((a, b) => a.executed_at.localeCompare(b.executed_at))[0]
    return { position, first_entry: first?.price ?? position.avg_entry, candidates }
  }

  async function load(startId?: string | null) {
    state.value = 'loading'
    saveError.value = false
    try {
      let queue = await positionsApi.matchQueue(opts.accountId?.())
      if (startId) {
        const hit = queue.find((q) => q.position.id === startId)
        queue = hit ? [hit, ...queue.filter((q) => q !== hit)] : [await single(startId)]
      }
      items.value = queue
      index.value = 0
      pickDefault()
      state.value = 'ready'
    } catch {
      state.value = 'error'
    }
  }

  function next() {
    index.value += 1
    saveError.value = false
    pickDefault()
  }

  async function confirm() {
    const item = current.value
    if (!item || saving.value) return
    saving.value = true
    saveError.value = false
    try {
      await positionsApi.match(item.position.id, choice.value === UNPLANNED ? null : choice.value)
      opts.onMatched?.(item.position.id)
      next()
    } catch {
      saveError.value = true
    } finally {
      saving.value = false
    }
  }

  return { items, index, choice, state, saving, saveError, current, done, load, confirm, skip: next }
}
