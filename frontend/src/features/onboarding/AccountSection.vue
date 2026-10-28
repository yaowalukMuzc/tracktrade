<script setup lang="ts">
import { computed } from 'vue'
import type { AccountType, Platform } from '@/api/accounts'
import TtField from '@/components/ui/TtField.vue'
import TtInput from '@/components/ui/TtInput.vue'
import TtSegmented from '@/components/ui/TtSegmented.vue'
import TtSelect from '@/components/ui/TtSelect.vue'
import { formatNumber } from '@/lib/format'
import { CURRENCIES, parseNum } from './form'
import { useOnboarding } from './useOnboarding'

// Account card (F-02 AC1): name, type, platform, broker, currency, initial balance.
const { state, errorOf, t } = useOnboarding()
const form = state.form

const types = computed(() => (['live', 'demo', 'prop'] as AccountType[]).map((v) => ({ value: v, label: t(`onboarding.account.types.${v}`) })))
const platforms = computed(() => (['mt5', 'ctrader', 'manual'] as Platform[]).map((v) => ({ value: v, label: t(`onboarding.account.platforms.${v}`) })))
const currencies = CURRENCIES.map((c) => ({ value: c as string, label: c }))

/** `100000` → `100,000` once the user leaves the field (the API gets the plain number). */
function tidyBalance() {
  const n = parseNum(form.initial_balance)
  if (!Number.isNaN(n) && n > 0) form.initial_balance = formatNumber(n, 2)
}
</script>

<template>
  <section class="tt-card tt-stack" aria-labelledby="ob-account">
    <h2 id="ob-account" class="m-0 text-h3 max-lg:sr-only">{{ t('onboarding.account.title') }}</h2>
    <TtField :label="t('onboarding.account.name')" :error="errorOf('name')">
      <TtInput v-model="form.name" name="name" autocomplete="off" maxlength="100" :placeholder="t('onboarding.account.namePlaceholder')" />
    </TtField>
    <div class="tt-field">
      <span class="tt-label" aria-hidden="true">{{ t('onboarding.account.type') }}</span>
      <TtSegmented v-model="form.account_type" :options="types" :label="t('onboarding.account.type')" block />
    </div>
    <div class="grid grid-cols-2 gap-3">
      <TtField :label="t('onboarding.account.platform')">
        <TtSelect v-model="form.platform" name="platform" :options="platforms" />
      </TtField>
      <TtField :label="t('onboarding.account.broker')" :error="errorOf('broker')">
        <TtInput v-model="form.broker" name="broker" autocomplete="off" maxlength="100" :placeholder="t('onboarding.account.brokerPlaceholder')" />
      </TtField>
      <TtField :label="t('onboarding.account.currency')" :error="errorOf('currency')">
        <TtSelect v-model="form.currency" name="currency" :options="currencies" />
      </TtField>
      <TtField :label="t('onboarding.account.balance')" :error="errorOf('initial_balance')">
        <TtInput v-model="form.initial_balance" name="initial_balance" numeric :suffix="form.currency" placeholder="0" @blur="tidyBalance" />
      </TtField>
    </div>
  </section>
</template>
