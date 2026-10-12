<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import TtSegmented from '@/components/ui/TtSegmented.vue'
import { LOCALES, type Locale } from '@/i18n'
import { useSessionStore } from '@/stores/session'
import { useUiStore } from '@/stores/ui'

// F-01 AC3: switches instantly; saved to the profile when signed in.
const ui = useUiStore()
const session = useSessionStore()
const { t } = useI18n()
// Language names are shown in their own script so either reader can find them.
const names: Record<Locale, string> = { th: 'ไทย', en: 'EN' }
const options = LOCALES.map((l) => ({ value: l, label: names[l] }))
const locale = computed({
  get: () => ui.locale,
  set: (l: Locale) => void session.updateProfile({ locale: l }).catch(() => {}),
})
</script>

<template>
  <TtSegmented v-model="locale" :options="options" :label="t('shell.language')" />
</template>
