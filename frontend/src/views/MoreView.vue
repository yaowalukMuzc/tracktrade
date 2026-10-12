<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { ArrowRight01Icon } from '@hugeicons/core-free-icons'
import TtIcon from '@/components/TtIcon.vue'
import PageHeader from '@/components/shell/PageHeader.vue'
import PageContent from '@/components/shell/PageContent.vue'
import LocaleSwitch from '@/components/shell/LocaleSwitch.vue'
import { moreNav } from '@/router/nav'
import { useUiStore } from '@/stores/ui'
import { useInboxStore } from '@/stores/inbox'

// Mobile "More": the sidebar's tools + account destinations, plus language and theme.
const { t } = useI18n()
const ui = useUiStore()
const inbox = useInboxStore()
</script>

<template>
  <PageHeader :title="t('pages.more')" />
  <PageContent>
    <section v-for="(group, gi) in moreNav" :key="gi" class="flex flex-col gap-2">
      <h2 v-if="group.titleKey" class="tt-side__group m-0 px-1 pb-0 pt-2">{{ t(group.titleKey) }}</h2>
      <ul class="m-0 list-none overflow-hidden rounded-lg border border-border bg-surface p-0">
        <li v-for="item in group.items" :key="item.id" class="border-b border-border last:border-b-0">
          <RouterLink :to="item.to" class="flex min-h-[52px] items-center gap-3 px-4 text-body text-ink no-underline">
            <span class="text-brand-700"><TtIcon :icon="item.icon" /></span>
            <span class="flex-1">{{ t(item.labelKey) }}</span>
            <span
              v-if="item.badge && inbox[item.badge.source] > 0"
              class="tt-badge"
              :class="`tt-badge--${item.badge.tone}`"
            >
              {{ inbox[item.badge.source] }}
            </span>
            <span class="text-ink-subtle"><TtIcon :icon="ArrowRight01Icon" :size="16" /></span>
          </RouterLink>
        </li>
      </ul>
    </section>

    <section class="tt-card flex flex-col gap-4">
      <div class="flex items-center justify-between gap-3">
        <span class="text-body">{{ t('shell.language') }}</span>
        <LocaleSwitch />
      </div>
      <div class="flex items-center justify-between gap-3">
        <span class="text-body">{{ t('shell.appearance') }}</span>
        <div class="tt-seg" role="group" :aria-label="t('shell.appearance')">
          <button
            v-for="th in (['light', 'dark'] as const)"
            :key="th"
            type="button"
            class="tt-seg__item"
            :class="{ 'tt-seg__item--on': ui.theme === th }"
            :aria-pressed="ui.theme === th"
            @click="ui.setTheme(th)"
          >
            {{ th === 'light' ? t('shell.themeLight') : t('shell.themeDark') }}
          </button>
        </div>
      </div>
    </section>
  </PageContent>
</template>
