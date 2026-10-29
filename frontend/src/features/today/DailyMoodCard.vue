<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import AppIcon from '@/components/AppIcon.vue'
import TtChip from '@/components/ui/TtChip.vue'
import TtMoodScale from '@/components/ui/TtMoodScale.vue'
import { todayApi, type Daily } from '@/api/analysis'
import type { Locale } from '@/i18n'
import { useReferenceStore } from '@/stores/reference'

// F-11 AC5: optional daily mood (1–10) + a few emotion tags, saved per local day with a debounce.
// The entry is per user (not per account), so the account filter never resets it.
const props = defineProps<{ date: string; daily: Daily | null; compact?: boolean }>()
const { t, locale } = useI18n()
const reference = useReferenceStore()

/** Shown before "more" (screens/source/WToday.dc.html shows three: rested / focused / anxious). */
const SHORTLIST = ['calm', 'focused', 'fear']
const SAVE_DELAY = 600

const mood = ref<number | null>(null)
const tags = ref<string[]>([])
const expanded = ref(false)
const state = ref<'idle' | 'saving' | 'saved' | 'error'>('idle')
let dirty = false
let timer: ReturnType<typeof setTimeout> | null = null
let loadedFor: string | null = null

watch(
  () => [props.date, props.daily] as const,
  ([date, daily]) => {
    // Server state only replaces local state for a new day or when nothing is waiting to be saved.
    if (loadedFor === date && (dirty || state.value === 'saving')) return
    loadedFor = date
    mood.value = daily?.mood ?? null
    tags.value = [...(daily?.tags ?? [])]
    state.value = daily?.logged_at ? 'saved' : 'idle'
  },
  { immediate: true },
)

const shownTags = computed(() => {
  const all = reference.emotionTags
  if (expanded.value) return all
  return all.filter((tag) => SHORTLIST.includes(tag.code) || tags.value.includes(tag.id))
})

function schedule() {
  dirty = true
  state.value = 'saving'
  if (timer) clearTimeout(timer)
  timer = setTimeout(save, SAVE_DELAY)
}

async function save() {
  timer = null
  dirty = false
  const date = props.date
  state.value = 'saving'
  try {
    await todayApi.putDaily(date, { mood: mood.value, tags: tags.value, note: props.daily?.note ?? '' })
    if (!dirty) state.value = 'saved'
  } catch {
    if (!dirty) state.value = 'error'
  }
}

function setMood(v: number | null) {
  mood.value = v
  schedule()
}
function toggle(id: string) {
  tags.value = tags.value.includes(id) ? tags.value.filter((x) => x !== id) : [...tags.value, id]
  schedule()
}

onBeforeUnmount(() => {
  if (timer) {
    clearTimeout(timer)
    void save()
  }
})
</script>

<template>
  <section class="tt-card flex flex-col" :class="compact ? 'gap-2.5' : 'gap-3'" data-testid="daily-mood">
    <div class="flex items-center justify-between gap-2">
      <h2 class="m-0" :class="compact ? 'text-[15px] font-semibold leading-6' : 'text-h3'">{{ t('today.mood.title') }}</h2>
      <span class="text-caption text-ink-subtle" aria-live="polite">
        <template v-if="state === 'saving'">{{ t('today.mood.saving') }}</template>
        <span v-else-if="state === 'saved'" class="inline-flex items-center gap-1"><AppIcon name="check" :size="16" />{{ t('today.mood.saved') }}</span>
        <span v-else-if="state === 'error'" class="inline-flex items-center gap-1 text-loss-ink">
          {{ t('today.mood.error') }}
          <button type="button" class="tt-link border-0 bg-transparent p-0 text-caption" @click="save">{{ t('today.mood.retry') }}</button>
        </span>
        <template v-else>{{ t(compact ? 'today.mood.optionalMobile' : 'today.mood.optional') }}</template>
      </span>
    </div>
    <TtMoodScale :model-value="mood" :label="t('today.mood.label')" hide-label @update:model-value="setMood" />
    <div v-if="reference.emotionTags.length" class="tt-row" role="group" :aria-label="t('today.mood.tags')">
      <TtChip
        v-for="tag in shownTags"
        :key="tag.id"
        :valence="tag.valence"
        :selected="tags.includes(tag.id)"
        @click="toggle(tag.id)"
      >
        {{ reference.tagLabel(tag, locale as Locale) }}
      </TtChip>
      <TtChip size="sm" :add="!expanded" @click="expanded = !expanded">{{ expanded ? t('today.mood.less') : t('today.mood.more') }}</TtChip>
    </div>
  </section>
</template>
