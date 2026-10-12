<script setup lang="ts">
import AppIcon from '@/components/AppIcon.vue'
import type { IconName } from '@/lib/icons'

// components/StatTile.md — label, value (slot), one line of context. Color the value only when it IS a P/L.
defineProps<{ label: string; icon?: IconName; delta?: string; /** 0–100 progress meter under the value. */ meter?: number }>()
</script>

<template>
  <div class="tt-stat">
    <span class="tt-stat__label"><AppIcon v-if="icon" :name="icon" :size="16" />{{ label }}</span>
    <span class="tt-stat__value"><slot /></span>
    <div v-if="meter !== undefined" class="tt-meter__track mt-1" role="meter" :aria-valuenow="meter" aria-valuemin="0" aria-valuemax="100" :aria-label="label">
      <div class="tt-meter__fill" :style="{ width: `${Math.max(0, Math.min(100, meter))}%` }" />
    </div>
    <span v-if="delta" class="tt-stat__delta">{{ delta }}</span>
  </div>
</template>
