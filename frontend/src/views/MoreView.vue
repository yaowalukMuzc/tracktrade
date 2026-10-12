<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import AppIcon from '@/components/AppIcon.vue'
import PageHeader from '@/components/shell/PageHeader.vue'
import PageContent from '@/components/shell/PageContent.vue'
import LocaleSwitch from '@/components/shell/LocaleSwitch.vue'
import TtButton from '@/components/ui/TtButton.vue'
import TtSegmented from '@/components/ui/TtSegmented.vue'
import { moreNav } from '@/router/nav'
import { useSessionStore } from '@/stores/session'
import { useInboxStore } from '@/stores/inbox'
import { useUiStore, type ThemePref } from '@/stores/ui'

// Mobile "More" (screens/mobile/27-More.png): the sidebar's tools + account destinations, language, theme, logout.
const { t } = useI18n()
const session = useSessionStore()
const inbox = useInboxStore()
const ui = useUiStore()

const themeOptions = computed(() => [
  { value: 'light' as const, label: t('shell.themeLight') },
  { value: 'dark' as const, label: t('shell.themeDark') },
  { value: 'system' as const, label: t('shell.themeSystem') },
])
const theme = computed({
  get: () => ui.theme,
  set: (th: ThemePref) => void session.updateProfile({ theme: th }).catch(() => {}),
})
</script>

<template>
  <PageHeader :title="t('pages.more')" />
  <PageContent>
    <section v-for="(group, gi) in moreNav" :key="gi" class="flex flex-col gap-2">
      <h2 v-if="group.titleKey" class="tt-side__group m-0 px-1 pb-0 pt-2">{{ t(group.titleKey) }}</h2>
      <ul class="tt-list">
        <li v-for="item in group.items" :key="item.id">
          <RouterLink :to="item.to" class="tt-list__row">
            <span class="text-brand-700"><AppIcon :name="item.icon" /></span>
            <span class="flex-1 text-body">{{ t(item.labelKey) }}</span>
            <span v-if="item.badge && inbox[item.badge.source] > 0" class="tt-badge" :class="`tt-badge--${item.badge.tone}`">
              {{ inbox[item.badge.source] }}
            </span>
            <span class="text-ink-subtle"><AppIcon name="forward" :size="16" /></span>
          </RouterLink>
        </li>
      </ul>
    </section>

    <section class="tt-card flex flex-col gap-4">
      <div class="flex items-center justify-between gap-3">
        <span class="text-body">{{ t('shell.language') }}</span>
        <LocaleSwitch />
      </div>
      <div class="flex flex-wrap items-center justify-between gap-3">
        <span class="text-body">{{ t('shell.appearance') }}</span>
        <TtSegmented v-model="theme" :options="themeOptions" :label="t('shell.appearance')" />
      </div>
    </section>

    <TtButton variant="secondary" icon="logout" block @click="session.logout()">{{ t('shell.logout') }}</TtButton>
  </PageContent>
</template>
