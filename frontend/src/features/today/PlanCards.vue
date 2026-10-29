<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import TtBadge from '@/components/ui/TtBadge.vue'
import type { PlanBrief } from '@/api/plans'
import { PLAN_STATUS_BADGE, directionBadge } from '@/features/plans/status'
import type { Locale } from '@/i18n'
import { formatNumber, intlLocale } from '@/lib/format'
import { useReferenceStore } from '@/stores/reference'
import { formatPrice, lastTakeProfit } from './model'

// Mobile plan cards (screens/source/Today.dc.html): locked / triggered → numbers; draft → dashed card with
// checklist progress; finished (skipped, missed, …) → one compact line.
defineProps<{ plans: PlanBrief[]; timezone?: string }>()
const { t, locale } = useI18n()
const reference = useReferenceStore()

const digits = (p: PlanBrief) => reference.symbolById.get(p.symbol_id)?.digits ?? 2
const price = (p: PlanBrief, v: string | null) => (v == null ? '—' : formatPrice(v, digits(p)))
const kind = (p: PlanBrief) => (p.status === 'locked' || p.status === 'triggered' ? 'full' : p.status === 'draft' ? 'draft' : 'compact')
const name = (p: PlanBrief) => t('today.plans.name', { label: p.scenario_label, symbol: p.symbol_code })

function time(iso: string, tz?: string) {
  return new Intl.DateTimeFormat(intlLocale(locale.value as Locale), { hour: '2-digit', minute: '2-digit', hourCycle: 'h23', timeZone: tz }).format(new Date(iso))
}
function meta(p: PlanBrief, tz?: string) {
  const parts = [t('today.plans.meta', { setup: p.setup_name, risk: formatNumber(p.planned_risk_pct, 2), lot: formatNumber(p.planned_lot, 2) })]
  if (p.valid_until) parts.push(t('today.plans.expires', { time: time(p.valid_until, tz) }))
  return parts.join(' · ')
}
</script>

<template>
  <RouterLink
    v-for="p in plans"
    :key="p.id"
    :to="`/plans/${p.id}`"
    class="tt-card flex flex-col text-ink no-underline"
    :class="{ 'gap-2.5': kind(p) === 'full', 'gap-2 border-dashed': kind(p) === 'draft', '!px-4 !py-3': kind(p) === 'compact' }"
    data-testid="today-plan"
  >
    <div class="flex items-center gap-2">
      <span class="font-semibold" :class="kind(p) === 'compact' ? 'text-[14px]' : 'text-[15px]'">{{ kind(p) === 'compact' ? p.symbol_code : name(p) }}</span>
      <TtBadge :variant="directionBadge(p.direction)">{{ t(`trading.direction.${p.direction}`) }}</TtBadge>
      <span class="flex-1" />
      <TtBadge :variant="PLAN_STATUS_BADGE[p.status]" :icon="p.status === 'locked' ? 'planLocked' : undefined">{{ t(`trading.planStatus.${p.status}`) }}</TtBadge>
    </div>
    <template v-if="kind(p) === 'full'">
      <dl class="m-0 grid grid-cols-4 gap-2 rounded-md bg-surface-sunken p-3">
        <div class="flex min-w-0 flex-col">
          <dt class="text-[11px] font-medium leading-4 text-ink-muted">{{ t(`trading.entryOrder.${p.direction}.${p.entry_type}`) }}</dt>
          <dd class="tt-num m-0 text-num">{{ price(p, p.entry_price) }}</dd>
        </div>
        <div class="flex min-w-0 flex-col">
          <dt class="text-[11px] font-medium leading-4 text-ink-muted">{{ t('today.plans.cols.sl') }}</dt>
          <dd class="tt-num m-0 text-num">{{ price(p, p.stop_loss) }}</dd>
        </div>
        <div class="flex min-w-0 flex-col">
          <dt class="text-[11px] font-medium leading-4 text-ink-muted">{{ t('today.plans.cols.tp') }}</dt>
          <dd class="tt-num m-0 text-num">{{ price(p, lastTakeProfit(p)) }}</dd>
        </div>
        <div class="flex min-w-0 flex-col">
          <dt class="text-[11px] font-medium leading-4 text-ink-muted">{{ t('today.plans.cols.rr') }}</dt>
          <dd class="tt-num m-0 text-num">{{ p.planned_rr == null ? '—' : formatPrice(p.planned_rr, 2) }}</dd>
        </div>
      </dl>
      <span class="text-caption text-ink-muted">{{ meta(p, timezone) }}</span>
    </template>
    <span v-else-if="kind(p) === 'draft'" class="text-caption text-ink-muted">
      {{ p.setup_name }} · {{ t('today.plans.checklist', { done: p.checklist.done, total: p.checklist.total }) }} · {{ t('today.plans.notLocked') }}
    </span>
  </RouterLink>
</template>
