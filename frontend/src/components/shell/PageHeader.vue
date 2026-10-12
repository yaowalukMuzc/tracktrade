<script setup lang="ts">
import type { RouteLocationRaw } from 'vue-router'
import AppIcon from '@/components/AppIcon.vue'

// Desktop: sticky Topbar (screens.css .topbar — optional crumb, h1, actions). Mobile: page title under the AppBar.
defineProps<{ title: string; overline?: string; crumb?: { to: RouteLocationRaw; label: string } }>()
</script>

<template>
  <header class="flex flex-wrap items-center gap-3 px-4 pt-4 md:px-6 lg:tt-topbar lg:sticky lg:top-0 lg:z-nav lg:px-8 lg:py-4">
    <div class="min-w-[200px] flex-1">
      <RouterLink v-if="crumb" :to="crumb.to" class="tt-crumb"><AppIcon name="back" :size="16" />{{ crumb.label }}</RouterLink>
      <div v-else-if="overline" class="text-caption text-ink-muted">{{ overline }}</div>
      <h1 class="m-0 text-h2 lg:text-h1">{{ title }}</h1>
    </div>
    <slot name="actions" />
  </header>
</template>
