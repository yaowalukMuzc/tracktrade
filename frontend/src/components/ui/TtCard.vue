<script setup lang="ts">
// Border only, no shadow; radius 14px (CLAUDE.md › Cards).
withDefaults(defineProps<{ title?: string; flush?: boolean; as?: string }>(), { as: 'section' })
</script>

<template>
  <component :is="as" class="tt-card" :class="{ 'tt-card--flush': flush }">
    <header v-if="title || $slots.action" class="tt-card__head" :class="{ 'px-4 pt-4 md:px-5 md:pt-5': flush }">
      <h3 v-if="title" class="tt-card__title">{{ title }}</h3>
      <slot name="action" />
    </header>
    <slot />
  </component>
</template>
