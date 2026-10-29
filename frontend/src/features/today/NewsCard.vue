<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import TtEmpty from '@/components/ui/TtEmpty.vue'

// "ข่าววันนี้" (screens/source/WToday.dc.html). No economic-calendar provider until Phase 6 (F-21),
// so this is an honest empty state — never sample news.
const { t } = useI18n()
</script>

<template>
  <section class="tt-card tt-stack" data-testid="today-news">
    <div class="flex items-center justify-between gap-2">
      <h2 class="m-0 text-h3">{{ t('today.news.title') }}</h2>
      <RouterLink to="/alerts" class="tt-link text-body-sm">{{ t('today.news.all') }}</RouterLink>
    </div>
    <TtEmpty icon="news" :message="t('today.news.empty')" class="!py-4" />
  </section>
</template>
