<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import TtAlert from '@/components/ui/TtAlert.vue'
import TtButton from '@/components/ui/TtButton.vue'
import TtField from '@/components/ui/TtField.vue'
import TtInput from '@/components/ui/TtInput.vue'
import TtResponsiveDialog from '@/components/ui/TtResponsiveDialog.vue'
import TtSegmented from '@/components/ui/TtSegmented.vue'
import TtSelect from '@/components/ui/TtSelect.vue'
import { ApiError } from '@/api/client'
import type { Account, AccountInput, AccountType, Platform } from '@/api/accounts'
import { serverFieldErrors, validateAccount, type AccountField, type Errors } from './model'

// Add / edit a trading account (F-02 AC1). New accounts get the default Risk Profile server-side.
const open = defineModel<boolean>('open', { default: false })
const props = defineProps<{ account?: Account | null; submit: (body: AccountInput) => Promise<void> }>()
const { t } = useI18n()

const CURRENCIES = ['USD', 'EUR', 'GBP', 'JPY', 'AUD', 'CAD', 'CHF', 'THB']
const form = reactive({ name: '', broker: '', platform: 'mt5' as Platform, account_type: 'prop' as AccountType, account_number: '', currency: 'USD', initial_balance: '' })
const errors = ref<Errors<AccountField>>({})
const formError = ref('')
const saving = ref(false)

watch(open, (o) => {
  if (!o) return
  const a = props.account
  Object.assign(form, {
    name: a?.name ?? '',
    broker: a?.broker ?? '',
    platform: a?.platform ?? 'mt5',
    account_type: a?.account_type ?? 'prop',
    account_number: a?.account_number ?? '',
    currency: a?.currency ?? 'USD',
    initial_balance: a ? String(Number(a.initial_balance)) : '',
  })
  errors.value = {}
  formError.value = ''
})

const typeOptions = computed(() => (['live', 'demo', 'prop'] as AccountType[]).map((v) => ({ value: v, label: t(`accounts.type.${v}`) })))
const platformOptions = computed(() => (['mt5', 'ctrader', 'manual'] as Platform[]).map((v) => ({ value: v, label: t(`accounts.platform.${v}`) })))
const currencyOptions = computed(() => [...new Set([...CURRENCIES, form.currency])].map((c) => ({ value: c, label: c })))
const msg = (f: AccountField) => (errors.value[f] ? t(errors.value[f]!.key, errors.value[f]!.params ?? {}) : undefined)

async function onSubmit() {
  formError.value = ''
  errors.value = validateAccount(form)
  if (Object.keys(errors.value).length) return
  saving.value = true
  try {
    await props.submit({
      name: form.name.trim(),
      broker: form.broker.trim(),
      platform: form.platform,
      account_type: form.account_type,
      account_number: form.account_number.trim() || null,
      currency: form.currency,
      initial_balance: String(Number(form.initial_balance)),
    })
    open.value = false
  } catch (e) {
    if (e instanceof ApiError && e.status === 422) errors.value = serverFieldErrors(e.details, ['name', 'broker', 'currency', 'initial_balance'] as const)
    if (!Object.keys(errors.value).length) formError.value = t('accounts.errors.generic')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <TtResponsiveDialog
    v-model:open="open"
    :title="account ? t('accounts.form.editTitle') : t('accounts.form.createTitle')"
    :subtitle="account ? undefined : t('accounts.form.createSub')"
  >
    <form id="account-form" class="tt-stack pt-2" novalidate @submit.prevent="onSubmit">
      <TtAlert v-if="formError" variant="loss" :title="formError" />
      <TtField :label="t('accounts.form.name')" :error="msg('name')">
        <TtInput v-model="form.name" maxlength="100" :placeholder="t('accounts.form.namePlaceholder')" />
      </TtField>
      <TtField :label="t('accounts.form.type')">
        <TtSegmented v-model="form.account_type" :options="typeOptions" :label="t('accounts.form.type')" block />
      </TtField>
      <div class="grid grid-cols-2 gap-3">
        <TtField :label="t('accounts.form.platform')">
          <TtSelect v-model="form.platform" :options="platformOptions" />
        </TtField>
        <TtField :label="t('accounts.form.broker')" :error="msg('broker')">
          <TtInput v-model="form.broker" maxlength="100" />
        </TtField>
        <TtField :label="t('accounts.form.currency')" :error="msg('currency')">
          <TtSelect v-model="form.currency" :options="currencyOptions" />
        </TtField>
        <TtField :label="t('accounts.form.balance')" :error="msg('initial_balance')">
          <TtInput v-model="form.initial_balance" numeric :suffix="form.currency" />
        </TtField>
      </div>
      <TtField :label="t('accounts.form.number')" :help="t('accounts.form.numberHelp')">
        <TtInput v-model="form.account_number" maxlength="50" inputmode="numeric" />
      </TtField>
    </form>
    <template #footer>
      <TtButton variant="secondary" class="flex-1 lg:flex-none" @click="open = false">{{ t('accounts.cancel') }}</TtButton>
      <TtButton type="submit" form="account-form" variant="primary" class="flex-1 lg:flex-none" :loading="saving">
        {{ account ? t('accounts.form.save') : t('accounts.form.create') }}
      </TtButton>
    </template>
  </TtResponsiveDialog>
</template>
