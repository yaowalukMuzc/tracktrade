<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import AppIcon from '@/components/AppIcon.vue'
import type { IconName } from '@/lib/icons'

// components/Alert.md — info (brand) · loss (breach/error) · warning (news/pending) · profit (success) · gold (Pro).
const props = withDefaults(
  defineProps<{
    variant?: 'info' | 'loss' | 'warning' | 'profit' | 'gold'
    icon?: IconName
    title?: string
    body?: string
    dismissible?: boolean
  }>(),
  { variant: 'info' },
)
defineEmits<{ dismiss: [] }>()
const { t } = useI18n()

const defaultIcon: Record<string, IconName> = { info: 'info', loss: 'ruleBreach', warning: 'ruleBreach', profit: 'success', gold: 'info' }
const iconName = computed(() => props.icon ?? defaultIcon[props.variant])
</script>

<template>
  <div class="tt-alert" :class="variant !== 'info' && `tt-alert--${variant}`" :role="variant === 'loss' ? 'alert' : 'status'">
    <AppIcon :name="iconName" class="mt-0.5" />
    <div class="min-w-0 flex-1">
      <span v-if="title" class="tt-alert__title">{{ title }}</span>
      <span v-if="body" class="tt-alert__body">{{ body }}</span>
      <slot />
    </div>
    <slot name="action" />
    <button v-if="dismissible" type="button" class="tt-iconbtn tt-iconbtn--bare -my-2 -mr-2 text-current" :aria-label="t('ui.dismiss')" @click="$emit('dismiss')">
      <AppIcon name="close" :size="16" />
    </button>
  </div>
</template>
