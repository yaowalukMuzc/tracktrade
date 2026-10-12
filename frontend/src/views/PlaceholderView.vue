<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppIcon from '@/components/AppIcon.vue'
import PageHeader from '@/components/shell/PageHeader.vue'
import PageContent from '@/components/shell/PageContent.vue'

// Stand-in for screens not built yet. Replace per route as screens land.
const route = useRoute()
const { t } = useI18n()
const title = computed(() => t(route.meta.titleKey ?? 'pages.notFound'))
</script>

<template>
  <div :class="{ 'min-h-dvh bg-bg': !route.matched.some((r) => r.children?.length) }">
    <PageHeader :title="title" />
    <PageContent>
      <section class="tt-card flex flex-col items-start gap-3">
        <h2 class="m-0 text-h3">{{ t('placeholder.title') }}</h2>
        <p v-if="route.meta.features" class="m-0 text-body text-ink-muted">
          {{ t('placeholder.body', { features: route.meta.features }) }}
        </p>
        <RouterLink to="/" class="tt-btn tt-btn--ghost tt-btn--sm">
          <AppIcon name="today" :size="16" />{{ t('placeholder.backHome') }}
        </RouterLink>
      </section>
    </PageContent>
  </div>
</template>
