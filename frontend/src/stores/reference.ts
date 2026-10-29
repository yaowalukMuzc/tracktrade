import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { accountsApi, type SymbolSpec } from '@/api/accounts'
import { api } from '@/api/client'
import type { Locale } from '@/i18n'

export interface EmotionTag {
  id: string
  code: string
  label_th: string
  label_en: string
  valence: 'pos' | 'neg' | 'neutral'
  is_system: boolean
}

/** Reference data shared by many screens: symbols (F-03) and emotion tags (F-11). Loaded once. */
export const useReferenceStore = defineStore('reference', () => {
  const symbols = ref<SymbolSpec[]>([])
  const emotionTags = ref<EmotionTag[]>([])
  let loading: Promise<void> | null = null

  const symbolById = computed(() => new Map(symbols.value.map((s) => [s.id, s])))
  const symbolByCode = computed(() => new Map(symbols.value.map((s) => [s.code, s])))
  const tagById = computed(() => new Map(emotionTags.value.map((t) => [t.id, t])))

  function ensureLoaded(): Promise<void> {
    if (!loading) {
      loading = Promise.all([accountsApi.symbols(), api<EmotionTag[]>('/emotion-tags')])
        .then(([s, t]) => {
          symbols.value = s
          emotionTags.value = t
        })
        .catch((e: unknown) => {
          loading = null
          throw e
        })
    }
    return loading
  }

  /** System tags come with both labels (F-11 AC4). */
  const tagLabel = (tag: EmotionTag, locale: Locale) => (locale === 'th' ? tag.label_th : tag.label_en)

  function reset() {
    symbols.value = []
    emotionTags.value = []
    loading = null
  }

  return { symbols, emotionTags, symbolById, symbolByCode, tagById, ensureLoaded, tagLabel, reset }
})
