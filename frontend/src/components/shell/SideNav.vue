<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Logout01Icon } from '@hugeicons/core-free-icons'
import TtIcon from '@/components/TtIcon.vue'
import AccountSwitcher from './AccountSwitcher.vue'
import ThemeToggle from './ThemeToggle.vue'
import LocaleSwitch from './LocaleSwitch.vue'
import { mentorSideNav, traderSideNav } from '@/router/nav'
import { useSessionStore } from '@/stores/session'
import { useInboxStore } from '@/stores/inbox'

// screens/source/WSide.dc.html — 240px sidebar for ≥ 1024px.
const route = useRoute()
const { t } = useI18n()
const session = useSessionStore()
const inbox = useInboxStore()

const groups = computed(() => (session.isMentor ? mentorSideNav : traderSideNav))
const roleLine = computed(() => {
  const u = session.user
  if (!u) return ''
  if (u.role === 'mentor') return t('shell.mentorTraderCount', { n: u.traderCount ?? 0 })
  return `${t('shell.role.trader')} · ${t(`shell.tier.${u.planTier}`)}`
})
</script>

<template>
  <nav
    :aria-label="t('shell.mainNav')"
    class="flex h-full w-60 flex-col gap-0.5 overflow-y-auto border-r border-border bg-surface px-3 py-5"
  >
    <RouterLink to="/" class="px-3 pb-3 pt-1 no-underline">
      <span class="tt-wordmark text-[20px]">Track<b>Trade</b></span>
    </RouterLink>

    <div class="mx-1 mb-3">
      <AccountSwitcher block />
    </div>

    <template v-for="(group, gi) in groups" :key="gi">
      <span v-if="group.titleKey" class="tt-side__group">{{ t(group.titleKey) }}</span>
      <RouterLink
        v-for="item in group.items"
        :key="item.id"
        :to="item.to"
        class="tt-side__item"
        :class="{ 'tt-side__item--on': route.meta.nav === item.id }"
        :aria-current="route.meta.nav === item.id ? 'page' : undefined"
      >
        <TtIcon :icon="item.icon" />
        <span class="flex-1">{{ t(item.labelKey) }}</span>
        <span
          v-if="item.badge && inbox[item.badge.source] > 0"
          class="tt-badge"
          :class="`tt-badge--${item.badge.tone}`"
        >
          {{ inbox[item.badge.source] }}
        </span>
      </RouterLink>
    </template>

    <div class="mt-auto flex flex-col gap-3 border-t border-border px-1 pt-3">
      <div class="flex items-center justify-between gap-2">
        <LocaleSwitch />
        <ThemeToggle />
      </div>
      <div v-if="session.user" class="flex items-center gap-2.5 px-2">
        <span class="tt-avatar">{{ session.initials }}</span>
        <div class="flex min-w-0 flex-1 flex-col">
          <span class="truncate text-[14px] font-semibold leading-5">{{ session.user.displayName }}</span>
          <span class="truncate text-caption text-ink-muted">{{ roleLine }}</span>
        </div>
        <RouterLink
          to="/login"
          class="tt-iconbtn tt-iconbtn--bare"
          :aria-label="t('shell.logout')"
          :title="t('shell.logout')"
          @click="session.logout()"
        >
          <TtIcon :icon="Logout01Icon" />
        </RouterLink>
      </div>
    </div>
  </nav>
</template>
