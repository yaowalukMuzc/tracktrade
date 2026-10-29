<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { Locale } from '@/i18n'
import { intlLocale } from '@/lib/format'

// Date field that reads like the design ("9 ต.ค. 2026") but uses the native picker: a transparent
// input[type=date] sits over the formatted text, so keyboard, screen readers and mobile pickers keep working.
defineProps<{ id: string }>()
const model = defineModel<string>({ required: true })
const { locale } = useI18n()

const label = computed(() => {
  const [y, m, d] = model.value.split('-').map(Number)
  if (!y || !m || !d) return model.value
  return new Intl.DateTimeFormat(intlLocale(locale.value as Locale), { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(y, m - 1, d))
})

function onInput(e: Event) {
  const v = (e.target as HTMLInputElement).value
  if (v) model.value = v // clearing keeps the previous date (an analysis always has one)
}
function openPicker(e: MouseEvent) {
  const input = e.currentTarget as HTMLInputElement & { showPicker?: () => void }
  try {
    input.showPicker?.()
  } catch {
    /* not allowed (e.g. cross-origin iframe) — the field still accepts typing */
  }
}
</script>

<template>
  <div class="date-input relative">
    <div class="tt-input pointer-events-none flex items-center" aria-hidden="true">
      <span class="tt-num truncate">{{ label }}</span>
    </div>
    <input :id="id" :value="model" type="date" required class="absolute inset-0 h-full w-full cursor-pointer opacity-0" @input="onInput" @click="openPicker" />
  </div>
</template>

<style scoped>
.date-input:focus-within .tt-input { border-color: var(--brand-700); box-shadow: 0 0 0 3px var(--focus-ring); }
</style>
