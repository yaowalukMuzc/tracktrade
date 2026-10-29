<script setup lang="ts">
import AppIcon from '@/components/AppIcon.vue'
import type { IconName } from '@/lib/icons'

// components/Badge.md — read-only status label; meaning → variant table lives there.
export type BadgeVariant = 'neutral' | 'solid' | 'brand' | 'outline' | 'warning' | 'loss' | 'profit' | 'long' | 'short' | 'gold'

withDefaults(defineProps<{ variant?: BadgeVariant; icon?: IconName }>(), { variant: 'neutral' })

// Complete class names so Tailwind's content scan keeps them (a `tt-badge--${variant}` template is purged).
const VARIANT_CLASS: Record<BadgeVariant, string> = {
  neutral: '',
  solid: 'tt-badge--solid',
  brand: 'tt-badge--brand',
  outline: 'tt-badge--outline',
  warning: 'tt-badge--warning',
  loss: 'tt-badge--loss',
  profit: 'tt-badge--profit',
  long: 'tt-badge--long',
  short: 'tt-badge--short',
  gold: 'tt-badge--gold',
}
</script>

<template>
  <span class="tt-badge" :class="VARIANT_CLASS[variant]">
    <AppIcon v-if="icon" :name="icon" :size="16" />
    <slot />
  </span>
</template>
