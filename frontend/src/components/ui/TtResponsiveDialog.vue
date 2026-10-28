<script setup lang="ts">
import TtModal from './TtModal.vue'
import TtSheet from './TtSheet.vue'
import { useDesktop } from '@/composables/useDesktop'

// Forms that are a centered modal on desktop and a bottom sheet on mobile (README › Screen patterns).
defineProps<{ title: string; subtitle?: string; size?: 'sm' | 'md' | 'lg' }>()
const open = defineModel<boolean>('open', { default: false })
const desktop = useDesktop()
</script>

<template>
  <TtModal v-if="desktop" v-model:open="open" :title="title" :subtitle="subtitle" :size="size">
    <slot />
    <template v-if="$slots.footer" #footer><slot name="footer" /></template>
  </TtModal>
  <TtSheet v-else v-model:open="open" :title="title" :subtitle="subtitle">
    <div class="max-h-[60dvh] overflow-y-auto"><slot /></div>
    <template v-if="$slots.footer" #footer><slot name="footer" /></template>
  </TtSheet>
</template>
