<script setup lang="ts">
import { useI18n } from 'vue-i18n'

// Quality grade A–D (A profit · B brand · C warning · D loss). Never derived from P/L (F-14 AC5).
const props = defineProps<{ grade: 'A' | 'B' | 'C' | 'D'; score?: number }>()
const { t } = useI18n()
</script>

<template>
  <span
    class="tt-grade"
    :class="`tt-grade--${props.grade}`"
    :title="score !== undefined ? t('ui.gradeScore', { grade, score }) : undefined"
    :aria-label="t('ui.grade', { grade })"
  >
    {{ grade }}
  </span>
</template>
