<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import TtBadge from '@/components/ui/TtBadge.vue'
import type { PositionCalc } from '@/api/positions'
import { directionOf, formatMoney, formatR } from '@/lib/format'
import { fmtFixed } from './model'

// Complete class names so Tailwind / the purge keeps them. R shows 2 decimals like the design (+2.10R).
const DIR_CLASS = { up: 'tt-pnl--up', down: 'tt-pnl--down', flat: 'tt-pnl--flat' }

// "คำนวณให้อัตโนมัติ" (screens/mobile/10-ManualTrade.png, web/07 manual tab). Numbers come from
// POST /positions/preview — never computed in the browser (F-07 AC2).
const props = defineProps<{ calc: PositionCalc | null; loading: boolean; error: string | null; digits: number; title: string }>()
const { t } = useI18n()

const avg = computed(() => {
  const c = props.calc
  if (!c) return '—'
  const entry = fmtFixed(c.avg_entry, props.digits)
  return c.avg_exit === null ? entry : `${entry} / ${fmtFixed(c.avg_exit, props.digits)}`
})
const swap = computed(() => (props.calc ? Number(props.calc.swap) : 0))
</script>

<template>
  <section class="tt-card" data-testid="trade-calc" aria-live="polite">
    <div class="mb-1 flex items-center justify-between gap-2">
      <h2 class="m-0 text-h3">{{ title }}</h2>
      <TtBadge v-if="calc" variant="outline" data-testid="calc-status">{{ t(`tradeNew.calc.status.${calc.status}`) }}</TtBadge>
    </div>
    <p v-if="error" class="m-0 py-2 text-body-sm text-loss-ink" role="alert" data-testid="calc-error">{{ error }}</p>
    <p v-else-if="!calc" class="m-0 py-2 text-body-sm text-ink-muted">{{ loading ? t('tradeNew.calc.loading') : t('tradeNew.calc.waiting') }}</p>
    <dl v-else class="m-0" :class="{ 'opacity-60': loading }">
      <div class="kv-row">
        <dt>{{ t('tradeNew.calc.avg') }}</dt>
        <dd data-testid="calc-avg">{{ avg }}</dd>
      </div>
      <div class="kv-row">
        <dt>{{ t('tradeNew.calc.totalLot') }}</dt>
        <dd>
          {{ fmtFixed(calc.total_lot, 2) }}
          <span v-if="Number(calc.open_lot) > 0" class="font-normal text-ink-muted"> · {{ t('tradeNew.calc.openLot') }} {{ fmtFixed(calc.open_lot, 2) }}</span>
        </dd>
      </div>
      <div class="kv-row">
        <dt>{{ t('tradeNew.calc.commission') }}</dt>
        <dd>{{ formatMoney(Number(calc.commission), calc.currency) }}</dd>
      </div>
      <div v-if="swap !== 0" class="kv-row">
        <dt>{{ t('tradeNew.calc.swap') }}</dt>
        <dd>{{ formatMoney(swap, calc.currency) }}</dd>
      </div>
      <div class="kv-row">
        <dt>{{ t('tradeNew.calc.net') }}</dt>
        <dd data-testid="calc-net"><span class="tt-pnl" :class="DIR_CLASS[directionOf(Number(calc.net_pnl))]">{{ formatMoney(Number(calc.net_pnl), calc.currency) }}</span></dd>
      </div>
      <div class="kv-row">
        <dt>{{ t('tradeNew.calc.r') }}</dt>
        <dd data-testid="calc-r">
          <span v-if="calc.r_multiple !== null" class="tt-pnl" :class="DIR_CLASS[directionOf(Number(calc.r_multiple))]">{{ formatR(Number(calc.r_multiple), 2) }}</span>
          <span v-else class="font-normal text-ink-muted">{{ calc.status === 'open' ? '—' : t('tradeNew.calc.rNoSl') }}</span>
        </dd>
      </div>
    </dl>
  </section>
</template>

<style scoped>
/* screens.css .kv — label left (muted), value right (tabular). */
.kv-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid var(--border);
  font: 400 14px/22px var(--font-sans);
}
.kv-row:last-child {
  border-bottom: 0;
}
.kv-row dt {
  color: var(--ink-muted);
}
.kv-row dd {
  margin: 0;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  text-align: right;
}
</style>
