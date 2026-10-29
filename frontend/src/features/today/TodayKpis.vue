<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import TtPnl from '@/components/ui/TtPnl.vue'
import TtStat from '@/components/ui/TtStat.vue'
import { formatAmount, formatNumber, formatR } from '@/lib/format'
import type { TodayKpis } from './model'

// KPI row of screens/web/03-WToday.png (4 tiles) / screens/mobile/05-Today.png (3 compact tiles).
// P/L is $0.00 · 0 trades until trades exist (Phase 4); adherence "—" until Phase 6. Never invented.
const props = defineProps<{ kpis: TodayKpis; compact?: boolean }>()
const { t } = useI18n()

const pnlDelta = computed(() => {
  const p = props.kpis.pnl
  const parts = [t('today.kpi.tradeCount', { n: p.trades }, p.trades)]
  if (p.trades > 0) parts.unshift(formatR(p.r, 2))
  if (p.otherCurrencies) parts.push(t('today.kpi.otherCurrencies', { n: p.otherCurrencies }, p.otherCurrencies))
  return parts.join(' · ')
})
const tradesMeter = computed(() => {
  const { used, limit } = props.kpis.trades
  return limit > 0 ? Math.min(100, (used / limit) * 100) : 0
})
const loss = computed(() => props.kpis.dailyLoss)
const lossValue = computed(() => (loss.value ? `${formatNumber(loss.value.usedPct, 1)}%` : '—'))
const lossDelta = computed(() => {
  const l = loss.value
  if (!l) return t('today.kpi.noAccount')
  const limit = t('today.kpi.dailyLossLimit', { pct: formatNumber(l.limitPct, 1), amount: formatAmount(l.limitAmount, l.currency, 0) })
  return l.accountName ? `${limit} · ${l.accountName}` : limit
})
const adherenceDelta = computed(() =>
  props.kpis.goal != null ? t('today.kpi.goal', { pct: formatNumber(props.kpis.goal, 0) }) : props.kpis.adherence == null ? t('today.kpi.adherencePending') : undefined,
)
</script>

<template>
  <div v-if="compact" class="grid grid-cols-3 gap-2" data-testid="today-kpis">
    <div class="tt-stat !px-3 !py-2.5">
      <span class="tt-stat__label">{{ t('today.kpi.pnl') }}</span>
      <TtPnl :money="kpis.pnl.amount" :currency="kpis.pnl.currency" size="md" />
    </div>
    <div class="tt-stat !px-3 !py-2.5">
      <span class="tt-stat__label">{{ t('today.kpi.tradesShort') }}</span>
      <span class="tt-num text-num">{{ kpis.trades.used }} / {{ kpis.trades.limit }}</span>
    </div>
    <div class="tt-stat !px-3 !py-2.5">
      <span class="tt-stat__label">{{ t('today.kpi.dailyLossShort') }}</span>
      <span class="tt-num text-num">{{ lossValue }}</span>
      <div v-if="loss" class="tt-meter__track mt-1 !h-1" role="meter" :aria-label="t('today.kpi.dailyLoss')" aria-valuemin="0" aria-valuemax="100" :aria-valuenow="Math.round(loss.usage)">
        <div class="tt-meter__fill" :style="{ width: `max(${loss.usage}%, 4px)` }" />
      </div>
    </div>
  </div>

  <div v-else class="grid grid-cols-[repeat(auto-fit,minmax(170px,1fr))] gap-3" data-testid="today-kpis">
    <TtStat :label="t('today.kpi.pnl')" :delta="pnlDelta">
      <TtPnl :money="kpis.pnl.amount" :currency="kpis.pnl.currency" size="lg" />
    </TtStat>
    <TtStat :label="t('today.kpi.trades')" :meter="tradesMeter">
      <span class="tt-num">{{ kpis.trades.used }} / {{ kpis.trades.limit }}</span>
    </TtStat>
    <TtStat :label="t('today.kpi.dailyLoss')" :delta="lossDelta">
      <span class="tt-num">{{ lossValue }}</span>
    </TtStat>
    <TtStat :label="t('today.kpi.adherence')" :delta="adherenceDelta">
      <span class="tt-num" :class="{ 'text-ink-subtle': kpis.adherence == null }">{{ kpis.adherence == null ? '—' : `${formatNumber(kpis.adherence, 0)}%` }}</span>
    </TtStat>
  </div>
</template>
