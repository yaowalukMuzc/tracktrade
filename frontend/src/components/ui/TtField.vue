<script setup lang="ts">
import { computed, provide, useId } from 'vue'
import { fieldKey } from './field'

// components/Field.md — label above, control, then one help line (error > low-confidence warning > help).
const props = defineProps<{
  label?: string
  required?: boolean
  help?: string
  /** Validation message; also turns the control red. */
  error?: string
  /** OCR low-confidence warning (F-09 AC3); highlights the control. */
  lowConfidence?: string
  id?: string
}>()

const uid = useId()
const id = props.id ?? `f-${uid}`
const helpId = `${id}-help`
const message = computed(() => props.error || props.lowConfidence || props.help)

provide(fieldKey, {
  id,
  helpId,
  invalid: computed(() => !!props.error),
  lowConfidence: computed(() => !!props.lowConfidence),
  hasHelp: computed(() => !!message.value),
  required: computed(() => props.required),
})
</script>

<template>
  <div class="tt-field">
    <label v-if="label" class="tt-label" :for="id">
      {{ label }}<span v-if="required" class="tt-req" aria-hidden="true"> *</span>
    </label>
    <slot />
    <slot name="after" />
    <span
      v-if="message"
      :id="helpId"
      class="tt-help"
      :class="{ 'tt-help--error': !!error, 'tt-help--warn': !error && !!lowConfidence }"
      :role="error ? 'alert' : undefined"
    >
      {{ message }}
    </span>
  </div>
</template>
