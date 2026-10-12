<script setup lang="ts">
import { HugeiconsIcon } from '@hugeicons/vue'
import type { Icon } from '@/router/nav'

// Hugeicons Stroke Rounded, 1.5px stroke; sizes 16 (badges/chips), 20 (default), 24 (nav/empty states).
withDefaults(defineProps<{ icon: Icon; size?: 16 | 20 | 24 }>(), { size: 20 })
</script>

<template>
  <HugeiconsIcon :icon="icon" :size="size" :stroke-width="1.5" class="flex-none" aria-hidden="true" />
</template>
