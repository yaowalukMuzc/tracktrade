<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import AppIcon from '@/components/AppIcon.vue'

// components/MoodScale.md — 1–10 rating (mood / confidence) for pre-trade, in-trade, review and daily mood.
// Numbers stay visible; steps up to the value are filled, the value itself is solid. Click the value again to clear.
const props = withDefaults(
  defineProps<{
    label: string
    /** Show the sad / smile icons under the scale. */
    ends?: boolean
    /** Allow clearing the value (optional fields such as daily mood). */
    clearable?: boolean
    disabled?: boolean
    hideLabel?: boolean
  }>(),
  { ends: false, clearable: true, disabled: false, hideLabel: false },
)
const model = defineModel<number | null>({ default: null })
const { t } = useI18n()

function pick(n: number) {
  if (props.disabled) return
  model.value = props.clearable && model.value === n ? null : n
}

function onKey(e: KeyboardEvent) {
  const step = e.key === 'ArrowRight' || e.key === 'ArrowUp' ? 1 : e.key === 'ArrowLeft' || e.key === 'ArrowDown' ? -1 : 0
  if (!step || props.disabled) return
  e.preventDefault()
  model.value = Math.min(10, Math.max(1, (model.value ?? (step > 0 ? 0 : 11)) + step))
}
</script>

<template>
  <div class="tt-mood" role="group" :aria-label="label">
    <span v-if="!hideLabel" class="text-sm font-medium text-ink-muted">{{ label }}</span>
    <div class="tt-mood__scale" @keydown="onKey">
      <button
        v-for="n in 10"
        :key="n"
        type="button"
        class="tt-mood__step"
        :class="{ 'tt-mood__step--on': model === n, 'tt-mood__step--fill': model !== null && n < model }"
        :aria-label="t('mood.step', { label, n })"
        :aria-pressed="model === n"
        :disabled="disabled"
        :tabindex="(model ?? 1) === n ? 0 : -1"
        @click="pick(n)"
      >
        {{ n }}
      </button>
    </div>
    <div v-if="ends" class="tt-mood__ends" aria-hidden="true">
      <AppIcon name="moodSad" :size="16" />
      <AppIcon name="moodHappy" :size="16" />
    </div>
  </div>
</template>
