<script setup lang="ts">
// Desktop: sticky topbar (screens.css .topbar). Mobile: plain page title under the AppBar.
defineProps<{ title: string; overline?: string }>()
</script>

<template>
  <header
    class="flex flex-wrap items-center gap-3 px-4 pt-4 md:px-6 lg:sticky lg:top-0 lg:z-30 lg:border-b lg:border-border lg:bg-surface lg:px-8 lg:py-4"
  >
    <div class="min-w-[200px] flex-1">
      <div v-if="overline" class="text-caption text-ink-muted">{{ overline }}</div>
      <h1 class="m-0 text-h2 lg:text-h1">{{ title }}</h1>
    </div>
    <slot name="actions" />
  </header>
</template>
