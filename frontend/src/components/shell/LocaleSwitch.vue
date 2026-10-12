<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { LOCALES } from '@/i18n'
import { useUiStore } from '@/stores/ui'

const ui = useUiStore()
const { t } = useI18n()
// Language names are shown in their own script so either can find them.
const label = { th: 'ไทย', en: 'EN' } as const
</script>

<template>
  <div class="tt-seg" role="group" :aria-label="t('shell.language')">
    <button
      v-for="l in LOCALES"
      :key="l"
      type="button"
      class="tt-seg__item"
      :class="{ 'tt-seg__item--on': ui.locale === l }"
      :aria-pressed="ui.locale === l"
      :lang="l"
      @click="ui.setLocale(l)"
    >
      {{ label[l] }}
    </button>
  </div>
</template>
