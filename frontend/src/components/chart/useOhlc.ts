import { ref, shallowRef, watch, type Ref } from 'vue'
import { marketDataApi, type Ohlc } from '@/api/analysis'
import type { Timeframe } from '@/api/playbook'

/** Bars for a symbol + timeframe, reloaded when either changes. Mock data until Phase 4. */
export function useOhlc(symbolId: Ref<string | null | undefined>, timeframe: Ref<Timeframe>, count = 300) {
  const data = shallowRef<Ohlc | null>(null)
  const loading = ref(false)
  const error = ref(false)
  let seq = 0

  async function load() {
    const id = symbolId.value
    if (!id) {
      data.value = null
      return
    }
    const mine = ++seq
    loading.value = true
    error.value = false
    try {
      const res = await marketDataApi.ohlc({ symbol_id: id, tf: timeframe.value, count })
      if (mine === seq) data.value = res
    } catch {
      if (mine === seq) error.value = true
    } finally {
      if (mine === seq) loading.value = false
    }
  }

  watch([symbolId, timeframe], load, { immediate: true })
  return { data, loading, error, reload: load }
}
