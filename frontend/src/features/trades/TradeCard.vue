<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import TtBadge from '@/components/ui/TtBadge.vue'
import TtGrade from '@/components/ui/TtGrade.vue'
import type { PositionSummary } from '@/api/positions'
import type { Locale } from '@/i18n'
import { formatR } from '@/lib/format'
import { STATE_BADGE, gradeOf, holdParts, pnlDirection, pnlText, timeHm, tradeState, type PnlMode } from './model'

// components/TradeCard.md — one trade on mobile (screens/mobile/09-Trades.png). Whole card = tap target.
const props = defineProps<{ trade: PositionSummary; mode: PnlMode; tz: string }>()
const { t, locale } = useI18n()

const p = computed(() => props.trade)
const dir = computed(() => pnlDirection(p.value))
const hold = computed(() => {
  const h = holdParts(p.value.opened_at, p.value.closed_at)
  if (!h) return t('trades.hold.open')
  return h.h ? t('trades.hold.hm', h) : t('trades.hold.m', { m: h.m })
})
const state = computed(() => tradeState(p.value))
// The other unit under the main figure ("+0.51R" under "+$517.30").
const secondary = computed(() => {
  if (p.value.status !== 'closed') return ''
  if (props.mode === 'r') return pnlText(p.value, 'money')
  return p.value.r_multiple === null ? '' : formatR(Number(p.value.r_multiple), 2)
})
const pnlClass = { up: 'tt-pnl--up', down: 'tt-pnl--down', flat: 'tt-pnl--flat' }
</script>

<template>
  <RouterLink :to="`/trades/${p.id}`" class="tt-trade" data-testid="trade-card">
    <div class="tt-trade__sym">
      {{ p.symbol_code }}
      <TtBadge :variant="p.direction">{{ t(`trading.direction.${p.direction}`) }}</TtBadge>
    </div>
    <div class="tt-trade__right">
      <span class="tt-pnl text-num" :class="pnlClass[dir]">{{ pnlText(p, mode) }}</span>
      <div v-if="secondary" class="text-caption text-ink-muted">{{ secondary }}</div>
    </div>
    <div class="tt-trade__meta">
      <span>{{ timeHm(p.opened_at, tz, locale as Locale) }}</span>
      <span>{{ hold }}</span>
      <span>{{ p.plan ? p.plan.setup_name : '—' }}</span>
      <TtBadge variant="outline">{{ t(`trades.source.${p.source}`) }}</TtBadge>
    </div>
    <div class="tt-trade__scores">
      <TtBadge :variant="p.adherence_pct === null ? 'neutral' : 'brand'">
        {{ t('trades.adherence', { v: p.adherence_pct === null ? '—' : `${Math.round(Number(p.adherence_pct))}%` }) }}
      </TtBadge>
      <TtGrade v-if="gradeOf(p.quality_grade)" :grade="gradeOf(p.quality_grade)!" class="!size-[22px] !text-[12px]" />
      <TtBadge v-if="state !== 'reviewed'" :variant="STATE_BADGE[state]">{{ t(`trades.state.${state}`) }}</TtBadge>
      <TtBadge v-if="p.is_unplanned && state !== 'pending'" variant="warning">{{ t('trades.tag.unplanned') }}</TtBadge>
    </div>
  </RouterLink>
</template>
