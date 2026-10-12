<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import AppIcon from '@/components/AppIcon.vue'
import AccountSwitcher from './AccountSwitcher.vue'
import { useInboxStore } from '@/stores/inbox'

// Mobile root app bar (components/AppBar.md): wordmark + account switcher + alerts.
const { t } = useI18n()
const inbox = useInboxStore()
</script>

<template>
  <header class="tt-appbar sticky top-0 z-30">
    <RouterLink to="/" class="no-underline"><span class="tt-wordmark">Track<b>Trade</b></span></RouterLink>
    <span class="flex-1" />
    <AccountSwitcher />
    <RouterLink to="/alerts" class="tt-iconbtn" :aria-label="t('shell.notifications')">
      <AppIcon name="alerts" />
      <i v-if="inbox.unreadAlerts > 0" class="tt-nav__dot !right-1.5 !top-1.5 !m-0" />
    </RouterLink>
  </header>
</template>
