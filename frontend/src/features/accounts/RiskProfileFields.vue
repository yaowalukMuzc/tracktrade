<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import TtAlert from '@/components/ui/TtAlert.vue'
import TtField from '@/components/ui/TtField.vue'
import TtInput from '@/components/ui/TtInput.vue'
import type { RiskProfileInput } from '@/api/accounts'
import { formatAmount } from '@/lib/format'
import type { Errors, RiskField } from './model'

// The six limits of a Risk Profile (F-02 AC2) + what they mean in money for this balance.
const props = defineProps<{ balance: number; currency: string; errors: Errors<RiskField>; columns?: 2 | 3 }>()
const model = defineModel<RiskProfileInput>({ required: true })
const { t } = useI18n()

const fields: { key: RiskField; label: string; suffix?: string }[] = [
  { key: 'risk_per_trade_pct', label: 'accounts.risk.riskPerTrade', suffix: '%' },
  { key: 'max_daily_loss_pct', label: 'accounts.risk.maxDailyLoss', suffix: '%' },
  { key: 'max_drawdown_pct', label: 'accounts.risk.maxDrawdown', suffix: '%' },
  { key: 'max_trades_per_day', label: 'accounts.risk.maxTrades' },
  { key: 'revenge_cooldown_min', label: 'accounts.risk.cooldown', suffix: 'accounts.risk.minutes' },
  { key: 'news_blackout_min', label: 'accounts.risk.blackout', suffix: 'accounts.risk.minutes' },
]

const money = (pct: unknown) => {
  const n = Number(pct)
  return Number.isFinite(n) && props.balance > 0 ? formatAmount((props.balance * n) / 100, props.currency) : '—'
}
const explain = computed(() =>
  t('accounts.risk.explain', {
    pct: Number(model.value.risk_per_trade_pct) || 0,
    balance: formatAmount(props.balance, props.currency),
    amount: money(model.value.risk_per_trade_pct),
  }),
)
const limits = computed(() =>
  t('accounts.risk.explainLimits', { daily: money(model.value.max_daily_loss_pct), dd: money(model.value.max_drawdown_pct) }),
)

function update(key: RiskField, value: string | number | null | undefined) {
  model.value = { ...model.value, [key]: value ?? '' }
}
</script>

<template>
  <div class="flex flex-col gap-4">
    <div class="grid grid-cols-2 gap-x-3 gap-y-4" :class="{ 'lg:grid-cols-3 lg:gap-x-4': columns !== 2 }">
      <TtField v-for="f in fields" :key="f.key" :label="t(f.label)" :error="errors[f.key] ? t(errors[f.key]!.key, errors[f.key]!.params ?? {}) : undefined">
        <TtInput
          :model-value="model[f.key]"
          numeric
          :suffix="f.suffix ? (f.suffix.startsWith('accounts.') ? t(f.suffix) : f.suffix) : undefined"
          @update:model-value="update(f.key, $event)"
        />
      </TtField>
    </div>
    <TtAlert v-if="balance > 0" :title="explain" :body="limits" />
  </div>
</template>
