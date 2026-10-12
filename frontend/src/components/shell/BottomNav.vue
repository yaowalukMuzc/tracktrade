<script setup lang="ts">
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppIcon from '@/components/AppIcon.vue'
import { bottomNav, moreNav } from '@/router/nav'
import { useInboxStore } from '@/stores/inbox'

// components/BottomNav.md — five items, < 1024px.
const route = useRoute()
const { t } = useI18n()
const inbox = useInboxStore()

const moreIds = new Set(moreNav.flatMap((g) => g.items.map((i) => i.id)))
const isOn = (id: string) => route.meta.nav === id || (id === 'more' && !!route.meta.nav && moreIds.has(route.meta.nav))
</script>

<template>
  <nav class="tt-nav" :aria-label="t('shell.bottomNav')">
    <RouterLink
      v-for="item in bottomNav"
      :key="item.id"
      :to="item.to"
      class="tt-nav__item"
      :class="{ 'tt-nav__item--on': isOn(item.id) }"
      :aria-current="isOn(item.id) ? 'page' : undefined"
    >
      <AppIcon :name="item.icon" :size="24" />
      {{ t(item.labelKey) }}
      <i v-if="item.badge && inbox[item.badge.source] > 0" class="tt-nav__dot" />
    </RouterLink>
  </nav>
</template>
