<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import UiKit from './dev/UiKit.vue'

// /dev/ui (dev builds only): every ui/ component in both themes side by side, to compare with design-system/components/*.md.
// Each column sets data-theme so tokens.css resolves that theme's values locally.
const { t } = useI18n()
</script>

<template>
  <div class="min-h-dvh bg-bg">
    <header class="tt-topbar">
      <div class="flex-1">
        <h1 class="m-0 text-h1">{{ t('devUi.title') }}</h1>
        <p class="m-0 text-body-sm text-ink-muted">{{ t('devUi.sub') }}</p>
      </div>
    </header>
    <div class="grid xl:grid-cols-2">
      <section data-theme="light" class="bg-bg p-4 text-ink md:p-6">
        <h2 class="tt-side__group m-0 px-0 pb-3 pt-0">{{ t('devUi.light') }}</h2>
        <UiKit />
      </section>
      <section data-theme="dark" class="bg-bg p-4 text-ink md:p-6">
        <h2 class="tt-side__group m-0 px-0 pb-3 pt-0">{{ t('devUi.dark') }}</h2>
        <UiKit />
      </section>
    </div>
  </div>
</template>
