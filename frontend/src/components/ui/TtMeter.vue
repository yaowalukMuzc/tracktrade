<script setup lang="ts">
import { computed } from 'vue'

// Usage of a limit (daily loss, drawdown, trades today): label + "used / limit" + bar.
// The bar is brand-700; it turns warning from 80% used and loss at/over the limit — meaning, not decoration.
const props = defineProps<{ label: string; value: string; used: number; limit: number }>()
const pct = computed(() => (props.limit > 0 ? Math.max(0, Math.min(100, (props.used / props.limit) * 100)) : 0))
const tone = computed(() => (pct.value >= 100 ? 'bg-loss' : pct.value >= 80 ? 'bg-warning' : 'bg-brand-700'))
</script>

<template>
  <div class="tt-meter">
    <div class="flex items-baseline justify-between gap-3 text-[14px]">
      <span class="text-ink-muted">{{ label }}</span>
      <span class="tt-num font-semibold">{{ value }}</span>
    </div>
    <div class="tt-meter__track" role="meter" :aria-label="label" aria-valuemin="0" :aria-valuemax="limit" :aria-valuenow="used" :aria-valuetext="value">
      <!-- A sliver stays visible at 0 so the track reads as a meter. -->
      <div class="tt-meter__fill" :class="tone" :style="{ width: `max(${pct}%, 4px)` }" />
    </div>
  </div>
</template>
