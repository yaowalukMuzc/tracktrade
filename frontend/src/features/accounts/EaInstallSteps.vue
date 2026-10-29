<script setup lang="ts">
import { useI18n } from 'vue-i18n'

// The three install steps under the key (screens/mobile/04-ConnectBroker.png).
const { t } = useI18n()
const host = typeof window !== 'undefined' ? window.location.host : ''
</script>

<template>
  <ol class="m-0 flex list-decimal flex-col gap-1 pl-5 text-body-sm text-ink-muted" :aria-label="t('connections.mt5.stepsTitle')">
    <li>{{ t('connections.mt5.step1') }}</li>
    <li>{{ t('connections.mt5.step2', { host }) }}</li>
    <li>{{ t('connections.mt5.step3') }}</li>
  </ol>
</template>
