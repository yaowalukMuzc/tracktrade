<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import TtBadge from '@/components/ui/TtBadge.vue'
import TtChip from '@/components/ui/TtChip.vue'
import TtMoodScale from '@/components/ui/TtMoodScale.vue'
import type { Locale } from '@/i18n'
import { useReferenceStore } from '@/stores/reference'
import type { EmotionModel } from './form'

// F-06 AC7 / F-11 AC1 — pre-trade mood, confidence and emotion tags (components/MoodScale.md, Chip.md).
// Editable until the entry (draft / locked); the parent saves it.
defineProps<{ readonly: boolean; error?: string | null }>()
const model = defineModel<EmotionModel>({ required: true })
const { t, locale } = useI18n()
const reference = useReferenceStore()

const tags = computed(() => reference.emotionTags)
const label = (id: string) => {
  const tag = reference.tagById.get(id)
  return tag ? reference.tagLabel(tag, locale.value as Locale) : ''
}

function toggle(id: string) {
  const on = model.value.tags.includes(id)
  model.value = { ...model.value, tags: on ? model.value.tags.filter((x) => x !== id) : [...model.value.tags, id] }
}
const setMood = (v: number | null) => (model.value = { ...model.value, mood: v })
const setConfidence = (v: number | null) => (model.value = { ...model.value, confidence: v })
</script>

<template>
  <section class="tt-card tt-stack" data-testid="plan-emotion">
    <div class="flex items-center justify-between gap-2">
      <h2 class="m-0 text-h3">{{ t('plans.sections.emotion') }}</h2>
      <TtBadge variant="outline">{{ t('plans.sections.preTrade') }}</TtBadge>
    </div>
    <TtMoodScale :model-value="model.mood" :label="t('plans.emotion.mood')" :disabled="readonly" @update:model-value="setMood" />
    <TtMoodScale :model-value="model.confidence" :label="t('plans.emotion.confidence')" :disabled="readonly" @update:model-value="setConfidence" />
    <div v-if="!readonly" class="tt-row" role="group" :aria-label="t('plans.emotion.tags')">
      <TtChip v-for="tag in tags" :key="tag.id" :selected="model.tags.includes(tag.id)" :valence="tag.valence" @click="toggle(tag.id)">
        {{ reference.tagLabel(tag, locale as Locale) }}
      </TtChip>
    </div>
    <div v-else-if="model.tags.length" class="tt-row" :aria-label="t('plans.emotion.tags')">
      <span
        v-for="id in model.tags"
        :key="id"
        class="tt-chip tt-chip--on"
        :class="{
          'tt-chip--pos': reference.tagById.get(id)?.valence === 'pos',
          'tt-chip--neg': reference.tagById.get(id)?.valence === 'neg',
        }"
      >
        {{ label(id) }}
      </span>
    </div>
    <p v-if="readonly" class="m-0 text-caption text-ink-subtle">{{ t('plans.emotion.closed') }}</p>
    <p v-if="error" class="tt-help tt-help--error m-0" role="alert">{{ error }}</p>
  </section>
</template>
