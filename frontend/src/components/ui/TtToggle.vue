<script setup lang="ts">
// Switch for on/off settings (management plan, rules, notifications). `label` is the accessible name.
defineProps<{ label: string; disabled?: boolean }>()
const model = defineModel<boolean>({ default: false })
</script>

<template>
  <button
    type="button"
    role="switch"
    class="tt-toggle"
    :class="{ 'tt-toggle--on': model }"
    :aria-checked="model"
    :aria-label="label"
    :disabled="disabled"
    @click="model = !model"
  />
</template>
