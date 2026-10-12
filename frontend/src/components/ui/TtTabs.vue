<script setup lang="ts" generic="T extends string">
// components/Tabs.md — underline tabs for sibling sections; scrolls horizontally, never wraps.
defineProps<{ items: { value: T; label: string; count?: number }[]; label: string }>()
const model = defineModel<T>({ required: true })
</script>

<template>
  <div class="tt-tabs" role="tablist" :aria-label="label">
    <button
      v-for="it in items"
      :key="it.value"
      type="button"
      role="tab"
      class="tt-tab"
      :class="{ 'tt-tab--on': model === it.value }"
      :aria-selected="model === it.value"
      @click="model = it.value"
    >
      {{ it.label }}
      <span v-if="it.count !== undefined" class="tt-badge" :class="{ 'tt-badge--brand': model === it.value }">{{ it.count }}</span>
    </button>
  </div>
</template>
