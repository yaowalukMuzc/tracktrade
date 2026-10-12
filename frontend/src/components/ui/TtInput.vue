<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AppIcon from '@/components/AppIcon.vue'
import { useFieldControl } from './field'

defineOptions({ inheritAttrs: false })

// Text/number input. `numeric` = right-aligned tabular value with a unit `suffix` (USD, %, R, lot).
const props = defineProps<{
  type?: 'text' | 'email' | 'password' | 'number' | 'search' | 'tel' | 'url'
  suffix?: string
  numeric?: boolean
  /** Adds a show/hide button to password inputs. */
  revealable?: boolean
  error?: boolean
  lowConfidence?: boolean
  id?: string
}>()
const model = defineModel<string | number | null>()

const { t } = useI18n()
const { stateClass, aria } = useFieldControl(props)
const revealed = ref(false)
const inputType = computed(() => (props.type === 'password' && revealed.value ? 'text' : (props.type ?? 'text')))
const wrapped = computed(() => !!props.suffix || (props.revealable && props.type === 'password'))
</script>

<template>
  <div v-if="wrapped" class="tt-input-wrap" :class="{ 'tt-input-wrap--action': revealable }">
    <input
      v-model="model"
      v-bind="{ ...$attrs, ...aria }"
      :type="inputType"
      class="tt-input"
      :class="[stateClass, { 'tt-input--num': numeric }]"
      :inputmode="numeric ? 'decimal' : undefined"
    />
    <span v-if="suffix" class="tt-suffix">{{ suffix }}</span>
    <button
      v-if="revealable && type === 'password'"
      type="button"
      class="tt-input-wrap__action"
      :aria-label="revealed ? t('ui.hidePassword') : t('ui.showPassword')"
      :aria-pressed="revealed"
      @click="revealed = !revealed"
    >
      <AppIcon :name="revealed ? 'hide' : 'show'" />
    </button>
  </div>
  <input
    v-else
    v-model="model"
    v-bind="{ ...$attrs, ...aria }"
    :type="inputType"
    class="tt-input"
    :class="[stateClass, { 'tt-input--num': numeric }]"
    :inputmode="numeric ? 'decimal' : undefined"
  />
</template>
