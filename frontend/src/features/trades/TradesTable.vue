<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import TtBadge from '@/components/ui/TtBadge.vue'
import TtGrade from '@/components/ui/TtGrade.vue'
import TtTable, { type Column } from '@/components/ui/TtTable.vue'
import type { PositionSummary } from '@/api/positions'
import type { Locale } from '@/i18n'
import { STATE_BADGE, dayMonth, gradeOf, entryExit, lot, pnlDirection, pnlText, rText, timeHm, tradeState, type PnlMode } from './model'

// Desktop trades table, 12 columns (screens/web/06-WTrades.png). Adherence / Quality / Quadrant show "—"
// until the Phase 6 engines fill them. The table scrolls sideways inside its card on narrow screens.
const props = defineProps<{ trades: PositionSummary[]; mode: PnlMode; tz: string; empty: string }>()
const { t, locale } = useI18n()
const router = useRouter()
const l = computed(() => locale.value as Locale)

const columns = computed<Column[]>(() => [
  { key: 'opened', label: t('trades.cols.opened') },
  { key: 'symbol', label: t('trades.cols.symbol') },
  { key: 'plan', label: t('trades.cols.plan') },
  { key: 'source', label: t('trades.cols.source') },
  { key: 'lot', label: t('trades.cols.lot'), align: 'right' },
  { key: 'px', label: t('trades.cols.entryExit'), align: 'right' },
  { key: 'adherence', label: t('trades.cols.adherence'), align: 'right' },
  { key: 'quality', label: t('trades.cols.quality') },
  { key: 'quadrant', label: t('trades.cols.quadrant') },
  { key: 'status', label: t('trades.cols.status') },
  { key: 'pnl', label: t('trades.cols.pnl'), align: 'right' },
  { key: 'r', label: t('trades.cols.r'), align: 'right' },
])

const rows = computed(() => props.trades.map((p) => ({ id: p.id, p })))
const pnlClass = { up: 'tt-pnl--up', down: 'tt-pnl--down', flat: 'tt-pnl--flat' }
</script>

<template>
  <TtTable
    :columns="columns"
    :rows="rows"
    row-key="id"
    :empty="empty"
    :caption="t('trades.table')"
    min-width="1100px"
    clickable
    @row-click="(r) => router.push(`/trades/${r.id}`)"
  >
    <template #cell-opened="{ row }">
      <div class="whitespace-nowrap leading-5">
        <div>{{ dayMonth(row.p.opened_at, tz, l) }}</div>
        <div>{{ timeHm(row.p.opened_at, tz, l) }}</div>
      </div>
    </template>
    <template #cell-symbol="{ row }">
      <div class="flex flex-col items-start gap-1">
        <b class="text-ink">{{ row.p.symbol_code }}</b>
        <TtBadge :variant="row.p.direction">{{ t(`trading.direction.${row.p.direction}`) }}</TtBadge>
      </div>
    </template>
    <template #cell-plan="{ row }">
      <span class="block max-w-[180px]">
        {{ row.p.plan ? t('trades.planLabel', { setup: row.p.plan.setup_name, label: row.p.plan.scenario_label }) : t('trades.unplanned') }}
      </span>
    </template>
    <template #cell-source="{ row }">
      <TtBadge variant="outline">{{ t(`trades.source.${row.p.source}`) }}</TtBadge>
    </template>
    <template #cell-lot="{ row }">{{ lot(row.p.total_lot) }}</template>
    <template #cell-px="{ row }">
      <span class="whitespace-pre-line">{{ entryExit(row.p).replace(' → ', ' →\n') }}</span>
    </template>
    <template #cell-adherence="{ row }">{{ row.p.adherence_pct === null ? '—' : `${Math.round(Number(row.p.adherence_pct))}%` }}</template>
    <template #cell-quality="{ row }">
      <TtGrade v-if="gradeOf(row.p.quality_grade)" :grade="gradeOf(row.p.quality_grade)!" class="!size-6 !text-[12px]" />
      <span v-else>—</span>
    </template>
    <template #cell-quadrant="{ row }">
      <TtBadge>{{ row.p.quadrant ?? '—' }}</TtBadge>
    </template>
    <template #cell-status="{ row }">
      <TtBadge :variant="STATE_BADGE[tradeState(row.p)]">{{ t(`trades.state.${tradeState(row.p)}`) }}</TtBadge>
    </template>
    <template #cell-pnl="{ row }">
      <span class="tt-pnl text-num" :class="pnlClass[pnlDirection(row.p)]">{{ pnlText(row.p, mode) }}</span>
    </template>
    <template #cell-r="{ row }">{{ row.p.status === 'closed' ? rText(row.p.r_multiple) : '—' }}</template>
  </TtTable>
</template>
