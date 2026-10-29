<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import TtBadge from '@/components/ui/TtBadge.vue'
import TtTable, { type Column } from '@/components/ui/TtTable.vue'
import type { PlanBrief } from '@/api/plans'
import { PLAN_STATUS_BADGE, directionBadge } from '@/features/plans/status'
import { useReferenceStore } from '@/stores/reference'
import { formatPrice, lastTakeProfit } from './model'

// "แผนการเทรดวันนี้" table (screens/source/WToday.dc.html). Row → /plans/:id.
const props = defineProps<{ plans: PlanBrief[] }>()
const { t } = useI18n()
const router = useRouter()
const reference = useReferenceStore()

type Row = { id: string; plan: PlanBrief }
const rows = computed<Row[]>(() => props.plans.map((p) => ({ id: p.id, plan: p })))
const columns = computed<Column[]>(() => [
  { key: 'plan', label: t('today.plans.cols.plan') },
  { key: 'direction', label: t('today.plans.cols.direction') },
  { key: 'setup', label: t('today.plans.cols.setup') },
  { key: 'entry', label: t('today.plans.cols.entry'), align: 'right' },
  { key: 'sl', label: t('today.plans.cols.sl'), align: 'right' },
  { key: 'tp', label: t('today.plans.cols.tp'), align: 'right' },
  { key: 'rr', label: t('today.plans.cols.rr'), align: 'right' },
  { key: 'status', label: t('today.plans.cols.status') },
])

const digits = (p: PlanBrief) => reference.symbolById.get(p.symbol_id)?.digits ?? 2
const price = (p: PlanBrief, v: string | null) => (v == null ? '—' : formatPrice(v, digits(p)))
const rr = (p: PlanBrief) => (p.planned_rr == null ? '—' : formatPrice(p.planned_rr, 2))
function statusLabel(p: PlanBrief) {
  const s = t(`trading.planStatus.${p.status}`)
  return p.status === 'draft' ? t('today.plans.draftChecklist', { status: s, done: p.checklist.done, total: p.checklist.total }) : s
}
</script>

<template>
  <TtTable :columns="columns" :rows="rows" row-key="id" :caption="t('today.plans.title')" clickable min-width="720px" @row-click="(r) => router.push(`/plans/${r.id}`)">
    <template #cell-plan="{ row }">
      <RouterLink :to="`/plans/${row.id}`" class="whitespace-nowrap font-semibold text-ink no-underline" tabindex="-1">
        {{ t('today.plans.name', { label: row.plan.scenario_label, symbol: row.plan.symbol_code }) }}
      </RouterLink>
    </template>
    <template #cell-direction="{ row }">
      <TtBadge :variant="directionBadge(row.plan.direction)">{{ t(`trading.direction.${row.plan.direction}`) }}</TtBadge>
    </template>
    <template #cell-setup="{ row }">{{ row.plan.setup_name }}</template>
    <template #cell-entry="{ row }">{{ price(row.plan, row.plan.entry_price) }}</template>
    <template #cell-sl="{ row }">{{ price(row.plan, row.plan.stop_loss) }}</template>
    <template #cell-tp="{ row }">{{ price(row.plan, lastTakeProfit(row.plan)) }}</template>
    <template #cell-rr="{ row }">{{ rr(row.plan) }}</template>
    <template #cell-status="{ row }">
      <TtBadge :variant="PLAN_STATUS_BADGE[row.plan.status]" :icon="row.plan.status === 'locked' ? 'planLocked' : undefined" class="whitespace-nowrap">{{ statusLabel(row.plan) }}</TtBadge>
    </template>
  </TtTable>
</template>
