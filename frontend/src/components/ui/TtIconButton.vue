<script setup lang="ts">
import type { RouteLocationRaw } from 'vue-router'
import AppIcon from '@/components/AppIcon.vue'
import type { IconName } from '@/lib/icons'

// 40px square icon button (app bars, chart toolbar). `label` is required — it becomes aria-label + tooltip.
withDefaults(
  defineProps<{
    icon: IconName
    label: string
    active?: boolean
    bare?: boolean
    /** Shows a loss-colored dot (unread). */
    dot?: boolean
    disabled?: boolean
    to?: RouteLocationRaw
  }>(),
  {},
)
</script>

<template>
  <component
    :is="to ? 'RouterLink' : 'button'"
    :to="to"
    :type="to ? undefined : 'button'"
    class="tt-iconbtn"
    :class="{ 'tt-iconbtn--active': active, 'tt-iconbtn--bare': bare }"
    :aria-label="label"
    :title="label"
    :aria-pressed="active === undefined || to ? undefined : active"
    :disabled="to ? undefined : disabled"
  >
    <AppIcon :name="icon" />
    <i v-if="dot" class="tt-nav__dot !right-1.5 !top-1.5 !m-0" />
  </component>
</template>
