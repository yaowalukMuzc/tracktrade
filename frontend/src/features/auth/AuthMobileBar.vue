<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import AppIcon from '@/components/AppIcon.vue'

// Mobile app bar of the inner auth screens (screens/mobile/02-Register.png): back to login + centred wordmark.
defineProps<{ query?: Record<string, unknown> }>()
const { t } = useI18n()
</script>

<template>
  <div class="tt-appbar border-0 lg:hidden">
    <RouterLink :to="{ name: 'login', query: query as never }" class="tt-iconbtn tt-iconbtn--bare" :aria-label="t('shell.back')">
      <AppIcon name="back" />
    </RouterLink>
    <span class="flex-1" />
    <span class="tt-wordmark">Track<b>Trade</b></span>
    <span class="flex-1" />
    <span class="w-10" />
  </div>
</template>
