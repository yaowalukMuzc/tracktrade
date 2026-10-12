<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import AppIcon from '@/components/AppIcon.vue'
import PageHeader from '@/components/shell/PageHeader.vue'
import PageContent from '@/components/shell/PageContent.vue'
import { useSessionStore } from '@/stores/session'
import { useUiStore } from '@/stores/ui'
import { useInboxStore } from '@/stores/inbox'
import { formatLongDate, greetingKey } from '@/lib/format'

// Header actions from screens/source/WToday.dc.html. Body content comes with F-05/F-06 (spec Phase 3).
const { t } = useI18n()
const session = useSessionStore()
const ui = useUiStore()
const inbox = useInboxStore()

const now = new Date()
const dateLine = computed(() => formatLongDate(now, ui.locale))
const greeting = computed(() => t(greetingKey(now), { name: session.firstName }))
</script>

<template>
  <PageHeader :title="greeting" :overline="dateLine">
    <template #actions>
      <div class="relative hidden w-[260px] items-center xl:flex">
        <span class="pointer-events-none absolute left-3 text-ink-subtle"><AppIcon name="search" /></span>
        <input
          type="search"
          :aria-label="t('shell.search')"
          :placeholder="t('shell.searchPlaceholder')"
          class="h-11 w-full rounded-md border border-border-strong bg-surface pl-10 pr-3 text-body text-ink placeholder:text-ink-subtle"
        />
      </div>
      <RouterLink to="/alerts" class="tt-iconbtn hidden lg:inline-grid" :aria-label="t('shell.notifications')">
        <AppIcon name="alerts" />
        <i v-if="inbox.unreadAlerts > 0" class="tt-nav__dot !right-1.5 !top-1.5 !m-0" />
      </RouterLink>
      <RouterLink to="/trades/new" class="tt-btn tt-btn--secondary hidden md:inline-flex">
        <AppIcon name="add" />{{ t('shell.addTrade') }}
      </RouterLink>
      <RouterLink to="/plans/new" class="tt-btn tt-btn--primary hidden md:inline-flex">
        <AppIcon name="plan" />{{ t('shell.newPlan') }}
      </RouterLink>
    </template>
  </PageHeader>
  <PageContent>
    <section class="tt-card">
      <h2 class="m-0 text-h3">{{ t('placeholder.title') }}</h2>
      <p class="m-0 mt-1 text-body text-ink-muted">
        {{ t('placeholder.body', { features: 'F-05, F-06, F-11 AC5, F-21' }) }}
      </p>
    </section>
  </PageContent>
</template>
