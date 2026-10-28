<script setup lang="ts">
// Loading placeholder shaped like the content (PLAN §8.2) on surface-sunken — no full-page spinners.
withDefaults(defineProps<{ lines?: number; height?: string }>(), { lines: 3, height: '16px' })
</script>

<template>
  <div class="flex flex-col gap-3" aria-hidden="true">
    <div
      v-for="n in lines"
      :key="n"
      class="animate-pulse rounded-sm bg-surface-sunken motion-reduce:animate-none"
      :style="{ height, width: n === lines && lines > 1 ? '60%' : '100%' }"
    />
  </div>
</template>
