<script setup lang="ts">
import { computed } from 'vue'
import AppIcon from '@/components/AppIcon.vue'

// Multi-step flow progress (screens/web/02-WOnboarding.png, screens/mobile/03-Onboarding.png).
// `list` = vertical step card (done ✓ on profit-100, current on brand-50 with a brand-600 number, upcoming on sunken);
// `bar` = 4px progress bar under a mobile app bar (the "1 / 2" count lives in the app bar).
const props = withDefaults(
  defineProps<{
    steps: { title: string; subtitle?: string }[]
    /** 0-based index of the current step; earlier steps count as done. */
    current: number
    variant?: 'list' | 'bar'
    /** Accessible name, e.g. "Setup progress". */
    label: string
    /** Screen-reader suffix for completed steps, e.g. "done". */
    doneLabel?: string
  }>(),
  { variant: 'list' },
)
const pct = computed(() => Math.round(((props.current + 1) / props.steps.length) * 100))
</script>

<template>
  <ol v-if="variant === 'list'" class="tt-card m-0 flex list-none flex-col gap-1 !p-2" :aria-label="label">
    <li
      v-for="(s, i) in steps"
      :key="i"
      class="flex items-start gap-3 rounded-md p-3"
      :class="{ 'bg-brand-50': i === current }"
      :aria-current="i === current ? 'step' : undefined"
    >
      <span
        class="grid size-7 flex-none place-items-center rounded-full text-[13px] font-bold leading-none tabular-nums"
        :class="i < current ? 'bg-profit-100 text-profit-ink' : i === current ? 'bg-brand-600 text-on-brand' : 'bg-surface-sunken text-ink-muted'"
        aria-hidden="true"
      >
        <AppIcon v-if="i < current" name="check" :size="16" />
        <template v-else>{{ i + 1 }}</template>
      </span>
      <div class="flex min-w-0 flex-col">
        <span class="text-[15px] font-semibold leading-6">
          {{ s.title }}<span v-if="i < current && doneLabel" class="sr-only"> · {{ doneLabel }}</span>
        </span>
        <span v-if="s.subtitle" class="truncate text-caption font-normal text-ink-muted">{{ s.subtitle }}</span>
      </div>
    </li>
  </ol>
  <div
    v-else
    class="h-1 bg-surface-sunken"
    role="progressbar"
    :aria-label="label"
    aria-valuemin="1"
    :aria-valuemax="steps.length"
    :aria-valuenow="current + 1"
    :aria-valuetext="steps[current]?.title"
  >
    <div class="h-1 bg-brand-700" :style="{ width: `${pct}%` }" />
  </div>
</template>
