<script setup lang="ts" generic="T extends string | number">
import AppIcon from '@/components/AppIcon.vue'
import TtBadge, { type BadgeVariant } from './TtBadge.vue'
import type { IconName } from '@/lib/icons'

// Selectable option card (screens/web/02-WOnboarding.png › import method). A native radio underneath gives
// grouping + arrow keys for free: give every card of one group the same `name` and wrap them in role="radiogroup".
// Selected = 2px brand-700 outline (brand text/outline colour, never the lavender fill) and a brand icon tile.
defineProps<{
  value: T
  name: string
  icon: IconName
  title: string
  subtitle?: string
  badge?: string
  badgeVariant?: BadgeVariant
}>()
const model = defineModel<T>()
</script>

<template>
  <label class="tt-radio-card" :class="{ 'tt-radio-card--on': model === value }">
    <input v-model="model" type="radio" class="sr-only" :name="name" :value="value" />
    <span class="tt-radio-card__ic" aria-hidden="true"><AppIcon :name="icon" /></span>
    <span class="flex min-w-0 flex-1 flex-col">
      <span class="text-[14px] font-semibold leading-5 text-ink">{{ title }}</span>
      <span v-if="subtitle" class="text-caption font-normal text-ink-muted">{{ subtitle }}</span>
    </span>
    <TtBadge v-if="badge" :variant="badgeVariant ?? 'neutral'" class="flex-none">{{ badge }}</TtBadge>
  </label>
</template>

<style scoped>
.tt-radio-card {
  display: flex; align-items: center; gap: var(--space-3); min-height: 72px; padding: var(--space-4);
  background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-lg);
  cursor: pointer;
}
.tt-radio-card:hover { border-color: var(--border-strong); }
/* Outline instead of a thicker border keeps the content from shifting when selected. */
.tt-radio-card--on, .tt-radio-card--on:hover { border-color: var(--brand-700); outline: 1px solid var(--brand-700); }
.tt-radio-card:has(:focus-visible) { outline: 2px solid var(--focus-ring); outline-offset: 2px; }
.tt-radio-card__ic {
  width: 36px; height: 36px; border-radius: var(--radius-md); display: grid; place-items: center; flex: none;
  background: var(--surface-sunken); color: var(--ink-muted);
}
.tt-radio-card--on .tt-radio-card__ic { background: var(--brand-100); color: var(--brand-700); }
</style>
