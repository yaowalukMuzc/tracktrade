<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import AppIcon from '@/components/AppIcon.vue'
import type { Locale } from '@/i18n'
import { shortHash } from './status'
import { timeHm } from './display'

// components/PlanLock.md — lock time, short sha256 of the latest revision and its number (F-06 AC4).
const props = defineProps<{ lockedAt: string; hash: string | null; revision: number; short?: boolean }>()
const { t, locale } = useI18n()
const time = computed(() => timeHm(props.lockedAt, locale.value as Locale))
</script>

<template>
  <div class="tt-lock" data-testid="plan-lock">
    <span class="tt-lock__icon"><AppIcon name="planLocked" /></span>
    <div class="min-w-0 flex-1">
      <div class="text-body font-semibold">{{ short ? t('plans.lockBar.short', { time }) : t('plans.lockBar.title', { time }) }}</div>
      <div class="tt-lock__hash" :title="hash ?? undefined">{{ t('plans.lockBar.hash', { hash: shortHash(hash), rev: revision }) }}</div>
    </div>
    <slot />
  </div>
</template>
