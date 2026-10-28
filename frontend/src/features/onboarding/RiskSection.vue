<script setup lang="ts">
import { computed } from 'vue'
import TtAlert from '@/components/ui/TtAlert.vue'
import TtBadge from '@/components/ui/TtBadge.vue'
import TtField from '@/components/ui/TtField.vue'
import TtInput from '@/components/ui/TtInput.vue'
import { formatAmount, formatNumber } from '@/lib/format'
import { parseNum, type RiskKey } from './form'
import { useOnboarding } from './useOnboarding'

// Risk Profile card (F-02 AC2): prefilled with the defaults 1% / 3% / 10% / 5 trades / 30 / 15 min.
const { state, errorOf, t } = useOnboarding()
const risk = state.form.risk

const fields = computed<{ key: RiskKey; label: string; suffix?: string }[]>(() => [
  { key: 'risk_per_trade_pct', label: t('onboarding.risk.perTrade'), suffix: '%' },
  { key: 'max_daily_loss_pct', label: t('onboarding.risk.dailyLoss'), suffix: '%' },
  { key: 'max_drawdown_pct', label: t('onboarding.risk.drawdown'), suffix: '%' },
  { key: 'max_trades_per_day', label: t('onboarding.risk.maxTrades'), suffix: t('onboarding.risk.unitTrades') },
  { key: 'revenge_cooldown_min', label: t('onboarding.risk.cooldown'), suffix: t('onboarding.risk.unitMin') },
  { key: 'news_blackout_min', label: t('onboarding.risk.blackout'), suffix: t('onboarding.risk.unitMin') },
])

/** Live money preview: risk % × balance. Limits are amounts, not P/L, so they stay unsigned. */
const preview = computed(() => {
  const balance = parseNum(state.form.initial_balance)
  const [pct, daily, dd] = [risk.risk_per_trade_pct, risk.max_daily_loss_pct, risk.max_drawdown_pct].map(parseNum)
  if (!(balance > 0) || [pct, daily, dd].some((n) => Number.isNaN(n))) return null
  const money = (p: number) => formatAmount((balance * p) / 100, state.form.currency)
  return {
    title: t('onboarding.risk.previewTitle', { pct: formatNumber(pct, 2), balance: formatAmount(balance, state.form.currency), amount: money(pct) }),
    body: t('onboarding.risk.previewBody', { daily: money(daily), dd: money(dd) }),
  }
})
</script>

<template>
  <section class="tt-card tt-stack" aria-labelledby="ob-risk">
    <div class="flex items-center justify-between gap-2">
      <h2 id="ob-risk" class="m-0 text-h3">{{ t('onboarding.risk.title') }}</h2>
      <TtBadge variant="brand">{{ t('onboarding.risk.defaults') }}</TtBadge>
    </div>
    <p class="m-0 text-body-sm text-ink-muted lg:hidden">{{ t('onboarding.risk.sub') }}</p>
    <div class="grid grid-cols-2 gap-3">
      <TtField v-for="f in fields" :key="f.key" :label="f.label" :error="errorOf(f.key)">
        <TtInput v-model="risk[f.key]" :name="f.key" numeric :suffix="f.suffix" />
      </TtField>
    </div>
    <TtAlert v-if="preview" :title="preview.title" :body="preview.body" class="ob-preview" aria-live="polite" />
    <TtAlert v-else :body="t('onboarding.risk.previewEmpty')" class="ob-preview" />
  </section>
</template>

<style scoped>
/* The design sets this alert in the 13/20 caption size. */
.ob-preview { font-size: 13px; line-height: 20px; }
</style>
