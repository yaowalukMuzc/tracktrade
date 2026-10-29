import { onBeforeUnmount, onMounted, ref, watch, type Ref } from 'vue'
import { useDocumentVisibility, useIntervalFn } from '@vueuse/core'
import { ApiError } from '@/api/client'
import { connectionsApi, type Connection, type IngestionJob } from '@/api/connections'
import { realtime } from '@/api/ws'

/** Realtime events that change what a connection card / the import history shows. */
const REFRESH_ON = new Set(['sync.status', 'sync.first_deal', 'position.created', 'position.updated'])

/** A clock that ticks every 10 s while the tab is visible ("10 วินาทีที่แล้ว" stays true). */
export function useNow(intervalMs = 10_000) {
  const now = ref(Date.now())
  const visibility = useDocumentVisibility()
  const { pause, resume } = useIntervalFn(() => (now.value = Date.now()), intervalMs)
  watch(visibility, (v) => (v === 'visible' ? ((now.value = Date.now()), resume()) : pause()))
  return now
}

/**
 * Connections + import history of a set of accounts (F-08 AC6), kept fresh by WS events.
 * `accountIds` is reactive: the Accounts tab passes the selected account, the mobile page all linked ones.
 */
export function useConnections(accountIds: Ref<string[]>, opts: { jobs?: boolean } = {}) {
  const connections = ref<Record<string, Connection[]>>({})
  const jobs = ref<Record<string, IngestionJob[]>>({})
  const loaded = ref(false)
  const error = ref(false)
  let seq = 0

  async function load() {
    const ids = accountIds.value
    const mine = ++seq
    error.value = false
    try {
      const [conns, hist] = await Promise.all([
        Promise.all(ids.map((id) => connectionsApi.list(id))),
        opts.jobs ? Promise.all(ids.map((id) => connectionsApi.jobs(id))) : Promise.resolve([] as IngestionJob[][]),
      ])
      if (mine !== seq) return
      connections.value = Object.fromEntries(ids.map((id, i) => [id, conns[i]!]))
      if (opts.jobs) jobs.value = Object.fromEntries(ids.map((id, i) => [id, hist[i]!]))
      loaded.value = true
    } catch {
      if (mine === seq) error.value = true
    }
  }

  function replace(conn: Connection) {
    const list = connections.value[conn.account_id] ?? []
    const rest = list.filter((c) => c.id !== conn.id)
    connections.value = { ...connections.value, [conn.account_id]: [...rest, conn] }
  }

  let off: (() => void) | undefined
  let timer: ReturnType<typeof setTimeout> | undefined
  onMounted(() => {
    off = realtime.on((msg) => {
      if (!REFRESH_ON.has(msg.type)) return
      clearTimeout(timer)
      timer = setTimeout(() => void load(), 400) // a burst of events → one reload
    })
  })
  onBeforeUnmount(() => {
    off?.()
    clearTimeout(timer)
  })
  watch(accountIds, () => void load(), { immediate: true, deep: true })

  return { connections, jobs, loaded, error, load, replace }
}

/** API error → i18n key for an action that failed (cTrader not configured is expected in dev). */
export function actionErrorKey(e: unknown) {
  if (e instanceof ApiError && e.code === 'ctrader_not_configured') return 'connections.ctrader.notConfigured'
  return 'connections.actionError'
}
