<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import TtAlert from '@/components/ui/TtAlert.vue'
import TtButton from '@/components/ui/TtButton.vue'
import TtResponsiveDialog from '@/components/ui/TtResponsiveDialog.vue'
import TtSkeleton from '@/components/ui/TtSkeleton.vue'
import { ApiError } from '@/api/client'
import type { RiskProfile, RiskProfileInput } from '@/api/accounts'
import { useDesktop } from '@/composables/useDesktop'
import { intlLocale } from '@/lib/format'
import type { Locale } from '@/i18n'
import RiskProfileFields from './RiskProfileFields.vue'
import { pctText, riskPayload, serverFieldErrors, validateRisk, type Errors, type RiskField } from './model'

// screens/web/14-WAccounts.png (editable card) · screens/mobile/23-Accounts.png (values + "แก้ Risk Profile").
// Saving creates a new profile version: older trades keep the limits they were taken under (F-02 AC4).
const props = defineProps<{ profile: RiskProfile | null; balance: number; currency: string; save: (body: RiskProfileInput) => Promise<void> }>()
const { t, locale } = useI18n()
const desktop = useDesktop()

const draft = ref<RiskProfileInput>(blank())
const errors = ref<Errors<RiskField>>({})
const formError = ref('')
const saving = ref(false)
const sheetOpen = ref(false)

function blank(): RiskProfileInput {
  const p = props.profile
  return p
    ? {
        risk_per_trade_pct: pctText(p.risk_per_trade_pct),
        max_daily_loss_pct: pctText(p.max_daily_loss_pct),
        max_drawdown_pct: pctText(p.max_drawdown_pct),
        max_trades_per_day: p.max_trades_per_day,
        revenge_cooldown_min: p.revenge_cooldown_min,
        news_blackout_min: p.news_blackout_min,
      }
    : { risk_per_trade_pct: '', max_daily_loss_pct: '', max_drawdown_pct: '', max_trades_per_day: 0, revenge_cooldown_min: 0, news_blackout_min: 0 }
}
function reset() {
  draft.value = blank()
  errors.value = {}
  formError.value = ''
}
watch(() => props.profile, reset, { immediate: true })

const dirty = computed(() => JSON.stringify(draft.value) !== JSON.stringify(blank()))
const editedAt = computed(() =>
  props.profile
    ? new Intl.DateTimeFormat(intlLocale(locale.value as Locale), { day: 'numeric', month: 'short' }).format(new Date(props.profile.updated_at))
    : '',
)

async function submit() {
  formError.value = ''
  errors.value = validateRisk(draft.value)
  if (Object.keys(errors.value).length) return
  saving.value = true
  try {
    await props.save(riskPayload(draft.value))
    sheetOpen.value = false
  } catch (e) {
    if (e instanceof ApiError && e.status === 422) errors.value = serverFieldErrors(e.details, Object.keys(draft.value) as RiskField[])
    if (!Object.keys(errors.value).length) formError.value = t('accounts.errors.generic')
  } finally {
    saving.value = false
  }
}

const rows = computed(() => {
  const p = props.profile
  if (!p) return []
  return [
    { label: t('accounts.risk.riskPerTrade'), value: `${pctText(p.risk_per_trade_pct)}%` },
    { label: t('accounts.risk.maxDailyLoss'), value: `${pctText(p.max_daily_loss_pct)}%` },
    { label: t('accounts.risk.maxDrawdown'), value: `${pctText(p.max_drawdown_pct)}%` },
    { label: t('accounts.risk.maxTrades'), value: String(p.max_trades_per_day) },
    { label: t('accounts.risk.cooldown'), value: t('accounts.risk.minutesValue', { n: p.revenge_cooldown_min }) },
    { label: t('accounts.risk.blackout'), value: t('accounts.risk.blackoutValue', { n: p.news_blackout_min }) },
  ]
})
</script>

<template>
  <!-- Desktop: the form is the card. -->
  <section v-if="desktop" class="tt-card tt-stack">
    <div class="flex flex-wrap items-baseline justify-between gap-2">
      <h2 class="m-0 text-h3">{{ t('accounts.risk.title') }}</h2>
      <span v-if="profile" class="text-caption text-ink-muted">{{ t('accounts.risk.edited', { date: editedAt }) }}</span>
    </div>
    <TtSkeleton v-if="!profile" :lines="4" height="44px" />
    <form v-else class="tt-stack" novalidate @submit.prevent="submit">
      <TtAlert v-if="formError" variant="loss" :title="formError" />
      <RiskProfileFields v-model="draft" :balance="balance" :currency="currency" :errors="errors" />
      <div class="flex justify-end gap-2">
        <TtButton variant="secondary" :disabled="!dirty || saving" @click="reset">{{ t('accounts.cancel') }}</TtButton>
        <TtButton type="submit" variant="primary" :disabled="!dirty" :loading="saving">{{ t('ui.save') }}</TtButton>
      </div>
    </form>
  </section>

  <!-- Mobile: values list + edit sheet. -->
  <section v-else class="tt-card flex flex-col">
    <TtSkeleton v-if="!profile" :lines="6" height="20px" />
    <template v-else>
      <dl class="m-0 flex flex-col">
        <div v-for="r in rows" :key="r.label" class="flex items-center justify-between gap-3 border-b border-border py-3 first:pt-0">
          <dt class="text-body text-ink-muted">{{ r.label }}</dt>
          <dd class="tt-num m-0 font-semibold">{{ r.value }}</dd>
        </div>
      </dl>
      <TtButton class="mt-3" variant="secondary" block icon="edit" @click="sheetOpen = true">{{ t('accounts.risk.edit') }}</TtButton>
      <p class="m-0 mt-2 text-center text-caption text-ink-muted">{{ t('accounts.risk.auditNote') }}</p>
    </template>
    <TtResponsiveDialog v-model:open="sheetOpen" :title="t('accounts.risk.edit')" :subtitle="t('accounts.risk.auditNote')">
      <form id="risk-form-m" class="tt-stack pt-2" novalidate @submit.prevent="submit">
        <TtAlert v-if="formError" variant="loss" :title="formError" />
        <RiskProfileFields v-model="draft" :balance="balance" :currency="currency" :errors="errors" :columns="2" />
      </form>
      <template #footer>
        <TtButton variant="secondary" class="flex-1" @click="sheetOpen = false">{{ t('accounts.cancel') }}</TtButton>
        <TtButton type="submit" form="risk-form-m" variant="primary" class="flex-1" :loading="saving">{{ t('ui.save') }}</TtButton>
      </template>
    </TtResponsiveDialog>
  </section>
</template>
