<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import TtMeter from '@/components/ui/TtMeter.vue'
import TtSkeleton from '@/components/ui/TtSkeleton.vue'
import type { RiskStatus } from '@/api/accounts'
import { formatAmount, formatNumber } from '@/lib/format'

// "วันนี้" — how much of today's limits are used (counts come from trades, Phase 4; 0 until then).
const props = defineProps<{ status: RiskStatus | null; compact?: boolean }>()
const { t } = useI18n()

const meters = computed(() => {
  const s = props.status
  if (!s) return []
  const money = (v: string) => formatAmount(v, s.currency, 0)
  return [
    {
      label: t(props.compact ? 'accounts.today.dailyLossToday' : 'accounts.today.dailyLoss'),
      value: `${money(s.daily_loss.used)} / ${money(s.daily_loss.limit)}`,
      used: Number(s.daily_loss.used),
      limit: Number(s.daily_loss.limit),
    },
    {
      label: t('accounts.today.drawdown'),
      value: `${formatNumber(s.drawdown_pct.used, 1)}% / ${formatNumber(s.drawdown_pct.limit, 1)}%`,
      used: Number(s.drawdown_pct.used),
      limit: Number(s.drawdown_pct.limit),
    },
    {
      label: t(props.compact ? 'accounts.today.tradesToday' : 'accounts.today.trades'),
      value: `${Number(s.trades_today.used)} / ${Number(s.trades_today.limit)}`,
      used: Number(s.trades_today.used),
      limit: Number(s.trades_today.limit),
    },
  ]
})
</script>

<template>
  <section class="tt-card tt-stack">
    <h2 v-if="!compact" class="m-0 text-h3">{{ t('accounts.today.title') }}</h2>
    <TtSkeleton v-if="!status" :lines="3" height="28px" />
    <TtMeter v-for="m in meters" :key="m.label" v-bind="m" />
  </section>
</template>
