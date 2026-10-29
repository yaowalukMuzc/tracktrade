<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import TtBadge from '@/components/ui/TtBadge.vue'
import type { Plan } from '@/api/plans'
import type { Locale } from '@/i18n'
import { formatPct, formatPrice } from './form'
import { dayTime, lotText, money } from './display'
import { directionBadge } from './status'

// Mobile locked plan (screens/mobile/08-PlanLocked.png): "LONG · Buy limit · London Breakout" + the levels.
const props = defineProps<{ plan: Plan; digits: number }>()
const { t, locale } = useI18n()

const rows = computed(() => {
  const p = props.plan
  const out = [
    { k: t('plans.fields.entry'), v: formatPrice(p.entry_price, props.digits) },
    { k: t('plans.fields.stopLoss'), v: formatPrice(p.stop_loss, props.digits) },
    ...p.take_profits.map((tp, i) => ({ k: t('plans.fields.tpLabel', { n: i + 1, pct: formatPct(tp.pct) }), v: formatPrice(tp.price, props.digits) })),
    {
      k: t('plans.fields.risk'),
      v: t('plans.fields.riskValue', { pct: formatPct(p.planned_risk_pct), amount: money(p.planned_risk_amount, p.currency), lot: lotText(p.planned_lot) }),
    },
  ]
  if (p.invalidation) out.push({ k: t('plans.fields.invalidation'), v: p.invalidation })
  if (p.valid_until) out.push({ k: t('plans.fields.validUntil'), v: dayTime(p.valid_until, locale.value as Locale) })
  return out
})
</script>

<template>
  <section class="tt-card" data-testid="plan-summary">
    <div class="mb-2 flex items-center gap-2">
      <TtBadge :variant="directionBadge(plan.direction)">{{ t(`trading.direction.${plan.direction}`) }}</TtBadge>
      <span class="text-body font-semibold">{{ t(`trading.entryOrder.${plan.direction}.${plan.entry_type}`) }} · {{ plan.setup_name }}</span>
    </div>
    <dl class="m-0">
      <div v-for="r in rows" :key="r.k" class="flex justify-between gap-3 border-b border-border py-2.5 text-[14px] leading-[22px] last:border-0">
        <dt class="text-ink-muted">{{ r.k }}</dt>
        <dd class="tt-num m-0 text-right font-semibold">{{ r.v }}</dd>
      </div>
    </dl>
  </section>
</template>
