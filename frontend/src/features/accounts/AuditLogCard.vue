<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import TtEmpty from '@/components/ui/TtEmpty.vue'
import TtSkeleton from '@/components/ui/TtSkeleton.vue'
import type { AuditEntry } from '@/api/accounts'
import { intlLocale } from '@/lib/format'
import type { Locale } from '@/i18n'

// F-02 AC4 / NFR Auditability: who changed what, with before → after per field.
const props = defineProps<{ entries: AuditEntry[] | null; limit?: number }>()
const { t, te, locale } = useI18n()

const FIELD_LABELS: Record<string, string> = {
  risk_per_trade_pct: 'accounts.risk.riskPerTrade',
  max_daily_loss_pct: 'accounts.risk.maxDailyLoss',
  max_drawdown_pct: 'accounts.risk.maxDrawdown',
  max_trades_per_day: 'accounts.risk.maxTrades',
  revenge_cooldown_min: 'accounts.risk.cooldown',
  news_blackout_min: 'accounts.risk.blackout',
  name: 'accounts.form.name',
  broker: 'accounts.form.broker',
  platform: 'accounts.form.platform',
  account_type: 'accounts.form.type',
  account_number: 'accounts.form.number',
  currency: 'accounts.form.currency',
  initial_balance: 'accounts.form.balance',
  broker_symbol: 'accounts.symbols.brokerSymbol',
  contract_size: 'accounts.symbols.contractSize',
  tick_value: 'accounts.symbols.tickValue',
  severity: 'accounts.rules.severityField',
}
// Bookkeeping fields that would only add noise.
const HIDDEN = new Set(['id', 'version', 'account_id', 'user_id', 'created_by_user_id', 'archived_at', 'symbol_id', 'params', 'code', 'created_by'])

const fmt = (v: unknown) => (v === null || v === undefined || v === '' ? '—' : typeof v === 'object' ? JSON.stringify(v) : String(v))

const rows = computed(() =>
  (props.entries ?? []).slice(0, props.limit ?? Infinity).map((e) => {
    const changes =
      e.action === 'update'
        ? Object.keys(e.after ?? {})
            .filter((k) => !HIDDEN.has(k))
            .map((k) => t('accounts.audit.change', { field: FIELD_LABELS[k] ? t(FIELD_LABELS[k]) : k, before: fmt(e.before?.[k]), after: fmt(e.after?.[k]) }))
        : []
    const entityKey = `accounts.audit.entity.${e.entity}`
    return {
      id: e.id,
      title: `${t(`accounts.audit.action.${e.action}`)} · ${te(entityKey) ? t(entityKey) : e.entity}`,
      at: new Intl.DateTimeFormat(intlLocale(locale.value as Locale), { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(e.created_at)),
      changes,
    }
  }),
)
</script>

<template>
  <section class="tt-card tt-card--flush overflow-hidden">
    <header class="tt-card__head px-4 pt-4 md:px-5 md:pt-5">
      <h2 class="tt-card__title">{{ t('accounts.audit.title') }}</h2>
      <slot name="action" />
    </header>
    <div v-if="!entries" class="p-4 md:p-5"><TtSkeleton :lines="4" /></div>
    <TtEmpty v-else-if="!rows.length" icon="review" :message="t('accounts.audit.empty')" />
    <ol v-else class="m-0 list-none p-0">
      <li v-for="r in rows" :key="r.id" class="flex flex-col gap-1 border-t border-border px-4 py-3 md:px-5">
        <div class="flex flex-wrap items-baseline justify-between gap-2">
          <span class="text-body font-semibold">{{ r.title }}</span>
          <time class="tt-num text-caption text-ink-muted">{{ r.at }}</time>
        </div>
        <span v-for="c in r.changes" :key="c" class="tt-num text-body-sm text-ink-muted">{{ c }}</span>
      </li>
    </ol>
  </section>
</template>
