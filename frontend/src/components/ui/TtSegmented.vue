<script setup lang="ts" generic="T extends string | number">
import { ref } from 'vue'

// components/SegmentedControl.md — 2–4 views of the same data. Radio-group semantics with arrow-key support.
const props = defineProps<{
  options: { value: T; label: string }[]
  label: string
  block?: boolean
}>()
const model = defineModel<T>({ required: true })
const buttons = ref<HTMLButtonElement[]>([])

function onKey(e: KeyboardEvent, i: number) {
  const step = e.key === 'ArrowRight' || e.key === 'ArrowDown' ? 1 : e.key === 'ArrowLeft' || e.key === 'ArrowUp' ? -1 : 0
  if (!step) return
  e.preventDefault()
  const next = (i + step + props.options.length) % props.options.length
  model.value = props.options[next].value
  buttons.value[next]?.focus()
}
</script>

<template>
  <div class="tt-seg" :class="{ 'tt-seg--block': block }" role="radiogroup" :aria-label="label">
    <button
      v-for="(o, i) in options"
      :key="o.value"
      ref="buttons"
      type="button"
      role="radio"
      class="tt-seg__item"
      :class="{ 'tt-seg__item--on': model === o.value }"
      :aria-checked="model === o.value"
      :tabindex="model === o.value ? 0 : -1"
      @click="model = o.value"
      @keydown="onKey($event, i)"
    >
      {{ o.label }}
    </button>
  </div>
</template>
