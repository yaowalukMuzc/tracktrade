<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { loadImage } from '@/api/playbook'

// Image from an owner-only API URL (needs the bearer token, so a plain <img src> can't load it).
const props = defineProps<{ src: string; alt: string }>()
const objectUrl = ref<string>()
const failed = ref(false)

function release() {
  if (objectUrl.value) URL.revokeObjectURL(objectUrl.value)
  objectUrl.value = undefined
}

watch(
  () => props.src,
  async (src) => {
    release()
    failed.value = false
    try {
      objectUrl.value = await loadImage(src)
    } catch {
      failed.value = true
    }
  },
  { immediate: true },
)
onBeforeUnmount(release)
</script>

<template>
  <img v-if="objectUrl" :src="objectUrl" :alt="alt" class="block h-full w-full object-cover" />
  <div v-else class="h-full w-full bg-surface-sunken" :class="{ 'animate-pulse motion-reduce:animate-none': !failed }" role="img" :aria-label="alt" />
</template>
