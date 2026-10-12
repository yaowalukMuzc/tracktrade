<script setup lang="ts">
import { watchEffect } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useUiStore } from '@/stores/ui'

const route = useRoute()
const { t } = useI18n()
useUiStore() // applies theme + locale to <html>

watchEffect(() => {
  const page = route.meta.titleKey ? t(route.meta.titleKey) : ''
  document.title = page ? `${page} · ${t('app.name')}` : t('app.name')
})
</script>

<template>
  <RouterView />
</template>
