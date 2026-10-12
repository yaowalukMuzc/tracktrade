<script setup lang="ts">
import { Moon02Icon, Sun03Icon } from '@hugeicons/core-free-icons'
import { useI18n } from 'vue-i18n'
import TtIcon from '@/components/TtIcon.vue'
import { useUiStore } from '@/stores/ui'

defineProps<{ bare?: boolean }>()

const ui = useUiStore()
const { t } = useI18n()
</script>

<template>
  <button
    type="button"
    class="tt-iconbtn"
    :class="{ 'tt-iconbtn--bare': bare }"
    :aria-label="ui.theme === 'dark' ? t('shell.themeToLight') : t('shell.themeToDark')"
    :title="ui.theme === 'dark' ? t('shell.themeToLight') : t('shell.themeToDark')"
    @click="ui.toggleTheme()"
  >
    <TtIcon :icon="ui.theme === 'dark' ? Sun03Icon : Moon02Icon" />
  </button>
</template>
