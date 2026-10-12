<script setup lang="ts">
import AppIcon from '@/components/AppIcon.vue'
import type { IconName } from '@/lib/icons'

// components/Badge.md — read-only status label; meaning → variant table lives there.
export type BadgeVariant = 'neutral' | 'solid' | 'brand' | 'outline' | 'warning' | 'loss' | 'profit' | 'long' | 'short' | 'gold'

withDefaults(defineProps<{ variant?: BadgeVariant; icon?: IconName }>(), { variant: 'neutral' })
</script>

<template>
  <span class="tt-badge" :class="variant !== 'neutral' && `tt-badge--${variant}`">
    <AppIcon v-if="icon" :name="icon" :size="16" />
    <slot />
  </span>
</template>
