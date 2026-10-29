<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import AppIcon from '@/components/AppIcon.vue'
import TtBadge from '@/components/ui/TtBadge.vue'
import type { Today } from '@/api/analysis'
import type { IconName } from '@/lib/icons'
import { todoTotal } from './model'

// "ต้องจัดการ" (screens/source/WToday.dc.html). Matching / reviews / inbox arrive in Phase 4–5; all 0 → a calm empty line.
const props = defineProps<{ todo: Today['todo'] }>()
const { t } = useI18n()

const total = computed(() => todoTotal(props.todo))
const rows = computed(() =>
  [
    { n: props.todo.pending_match, key: 'match', to: '/trades?match=1', icon: 'link' as IconName, tone: 'bg-warning-100 text-warning-ink' },
    { n: props.todo.pending_review, key: 'review', to: '/trades?tab=review', icon: 'review' as IconName, tone: 'bg-brand-100 text-brand-700' },
    { n: props.todo.inbox, key: 'inbox', to: '/alerts', icon: 'alerts' as IconName, tone: 'bg-surface-sunken text-ink-muted' },
  ].filter((r) => r.n > 0),
)
</script>

<template>
  <section class="tt-card tt-stack" data-testid="today-todo">
    <div class="flex items-center justify-between gap-2">
      <h2 class="m-0 text-h3">{{ t('today.todo.title') }}</h2>
      <TtBadge v-if="total > 0" variant="warning">{{ total }}</TtBadge>
    </div>
    <div v-if="!rows.length" class="flex items-center gap-3 py-1 text-body-sm text-ink-muted">
      <span class="grid size-9 flex-none place-items-center rounded-md bg-surface-sunken text-ink-subtle"><AppIcon name="success" /></span>
      {{ t('today.todo.empty') }}
    </div>
    <div v-else class="flex flex-col">
      <RouterLink
        v-for="(r, i) in rows"
        :key="r.key"
        :to="r.to"
        class="flex items-center gap-3 py-2 text-ink no-underline"
        :class="{ 'border-b border-border': i < rows.length - 1 }"
      >
        <span class="grid size-9 flex-none place-items-center rounded-md" :class="r.tone"><AppIcon :name="r.icon" /></span>
        <span class="min-w-0 flex-1 text-[14px] font-semibold leading-5">{{ t(`today.todo.${r.key}`, { n: r.n }, r.n) }}</span>
        <AppIcon name="forward" class="text-ink-subtle" />
      </RouterLink>
    </div>
  </section>
</template>
