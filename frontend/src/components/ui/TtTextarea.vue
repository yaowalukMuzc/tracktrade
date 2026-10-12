<script setup lang="ts">
import { useFieldControl } from './field'

defineOptions({ inheritAttrs: false })

const props = defineProps<{ error?: boolean; lowConfidence?: boolean; id?: string }>()
const model = defineModel<string>()
const { stateClass, aria } = useFieldControl(props)
</script>

<template>
  <textarea v-model="model" v-bind="{ ...$attrs, ...aria }" class="tt-textarea" :class="stateClass" />
</template>
