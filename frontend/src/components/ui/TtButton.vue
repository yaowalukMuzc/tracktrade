<script setup lang="ts">
import { computed } from 'vue'
import type { RouteLocationRaw } from 'vue-router'
import AppIcon from '@/components/AppIcon.vue'
import type { IconName } from '@/lib/icons'

// components/Button.md — one primary per screen; danger only for destructive actions.
const props = withDefaults(
  defineProps<{
    variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
    size?: 'sm' | 'md' | 'lg'
    block?: boolean
    icon?: IconName
    loading?: boolean
    disabled?: boolean
    type?: 'button' | 'submit' | 'reset'
    /** Renders a RouterLink instead of a <button>. */
    to?: RouteLocationRaw
  }>(),
  { variant: 'secondary', size: 'md', type: 'button' },
)

const classes = computed(() => [
  'tt-btn',
  `tt-btn--${props.variant}`,
  props.size !== 'md' && `tt-btn--${props.size}`,
  props.block && 'tt-btn--block',
])
const iconSize = computed(() => (props.size === 'sm' ? 16 : 20))
</script>

<template>
  <RouterLink v-if="to && !disabled" :to="to" :class="classes">
    <AppIcon v-if="icon" :name="icon" :size="iconSize" />
    <slot />
  </RouterLink>
  <button v-else :type="type" :class="classes" :disabled="disabled || loading" :aria-busy="loading || undefined">
    <AppIcon v-if="loading" name="loading" :size="iconSize" class="tt-spin" />
    <AppIcon v-else-if="icon" :name="icon" :size="iconSize" />
    <slot />
  </button>
</template>
