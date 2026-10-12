<script setup lang="ts">
defineOptions({ inheritAttrs: false })
const model = defineModel<boolean>({ default: false })
</script>

<template>
  <label class="tt-checkbox">
    <input v-model="model" v-bind="$attrs" type="checkbox" />
    <span><slot /></span>
  </label>
</template>
