<script setup lang="ts">
import AppIcon from '@/components/AppIcon.vue'
import type { IconName } from '@/lib/icons'

// Empty state (PLAN §8.2): one sentence + one primary action, 24px ink-subtle icon.
defineProps<{ icon?: IconName; message: string }>()
</script>

<template>
  <div class="flex flex-col items-center gap-3 px-4 py-8 text-center">
    <AppIcon v-if="icon" :name="icon" :size="24" class="text-ink-subtle" />
    <p class="m-0 max-w-[360px] text-body text-ink-muted">{{ message }}</p>
    <slot />
  </div>
</template>
