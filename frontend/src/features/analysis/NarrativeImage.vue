<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { NodeViewWrapper, nodeViewProps } from '@tiptap/vue-3'
import TtAuthedImage from '@/components/ui/TtAuthedImage.vue'

// Tiptap image node view: attachment URLs need the bearer token, so the image is loaded as a blob URL.
const props = defineProps(nodeViewProps)
const { t } = useI18n()
const src = computed(() => String(props.node.attrs.src ?? ''))
const alt = computed(() => String(props.node.attrs.alt || t('analysis.narrative.imageAlt')))
</script>

<template>
  <NodeViewWrapper
    as="figure"
    class="narrative-image my-2 overflow-hidden rounded-md border border-border"
    :class="{ 'outline outline-2 outline-offset-2 outline-brand-700': selected }"
    data-drag-handle
  >
    <TtAuthedImage v-if="src" :src="src" :alt="alt" />
  </NodeViewWrapper>
</template>

<style scoped>
.narrative-image { min-height: 64px; max-width: 100%; }
.narrative-image :deep(img) { height: auto; max-height: 480px; object-fit: contain; }
</style>
