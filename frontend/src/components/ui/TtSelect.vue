<script setup lang="ts" generic="T extends string | number">
import { useFieldControl } from './field'

defineOptions({ inheritAttrs: false })

const props = defineProps<{
  options: { value: T; label: string }[]
  error?: boolean
  lowConfidence?: boolean
  id?: string
}>()
const model = defineModel<T>()
const { stateClass, aria } = useFieldControl(props)
</script>

<template>
  <select v-model="model" v-bind="{ ...$attrs, ...aria }" class="tt-select" :class="stateClass">
    <option v-for="o in options" :key="o.value" :value="o.value">{{ o.label }}</option>
  </select>
</template>
