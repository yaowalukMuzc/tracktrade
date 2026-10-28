<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AppIcon from '@/components/AppIcon.vue'
import TtAlert from '@/components/ui/TtAlert.vue'
import TtButton from '@/components/ui/TtButton.vue'
import TtEmpty from '@/components/ui/TtEmpty.vue'
import TtField from '@/components/ui/TtField.vue'
import TtIconButton from '@/components/ui/TtIconButton.vue'
import TtInput from '@/components/ui/TtInput.vue'
import TtResponsiveDialog from '@/components/ui/TtResponsiveDialog.vue'
import TtSelect from '@/components/ui/TtSelect.vue'
import TtSkeleton from '@/components/ui/TtSkeleton.vue'
import { ApiError } from '@/api/client'
import type { SymbolOverride, SymbolSpec } from '@/api/accounts'
import { formatNumber } from '@/lib/format'

// F-03 AC2: broker symbol (XAUUSD.m) → standard symbol, optional broker contract size / tick value.
const props = defineProps<{
  overrides: SymbolOverride[] | null
  symbols: SymbolSpec[]
  save: (body: { broker_symbol: string; symbol_id: string; contract_size: string | null; tick_value: string | null }) => Promise<void>
  remove: (o: SymbolOverride) => Promise<void>
  bare?: boolean
}>()
const { t } = useI18n()

const open = ref(false)
const form = reactive({ broker_symbol: '', symbol_id: '', contract_size: '', tick_value: '' })
const errors = ref<Record<string, string>>({})
const formError = ref('')
const saving = ref(false)

const symbolOptions = computed(() => props.symbols.map((s) => ({ value: s.id, label: s.code })))
const byId = computed(() => new Map(props.symbols.map((s) => [s.id, s])))

/** "XAUUSD · 100 oz", "EURUSD · 100k" (screens/mobile/23-Accounts.png). */
function spec(o: SymbolOverride) {
  const s = byId.value.get(o.symbol_id)
  const size = Number(o.contract_size ?? s?.contract_size ?? 0)
  const sizeText = s?.asset_class === 'metal' ? t('accounts.symbols.oz', { n: formatNumber(size) }) : size >= 1000 ? `${formatNumber(size / 1000)}k` : formatNumber(size)
  return t('accounts.symbols.spec', { code: o.symbol_code, size: sizeText })
}

function openDialog() {
  Object.assign(form, { broker_symbol: '', symbol_id: props.symbols[0]?.id ?? '', contract_size: '', tick_value: '' })
  errors.value = {}
  formError.value = ''
  open.value = true
}
defineExpose({ openDialog })

async function submit() {
  const e: Record<string, string> = {}
  const sym = form.broker_symbol.trim()
  if (!sym) e.broker_symbol = t('accounts.errors.required')
  else if (/\s/.test(sym)) e.broker_symbol = t('accounts.errors.symbol')
  for (const k of ['contract_size', 'tick_value'] as const) {
    if (form[k] !== '' && !(Number(form[k]) > 0)) e[k] = t('accounts.errors.positive')
  }
  errors.value = e
  if (Object.keys(e).length) return
  saving.value = true
  formError.value = ''
  try {
    await props.save({
      broker_symbol: sym,
      symbol_id: form.symbol_id,
      contract_size: form.contract_size === '' ? null : String(Number(form.contract_size)),
      tick_value: form.tick_value === '' ? null : String(Number(form.tick_value)),
    })
    open.value = false
  } catch (err) {
    formError.value = err instanceof ApiError && err.status === 409 ? t('accounts.errors.exists') : t('accounts.errors.generic')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <section class="tt-card tt-card--flush overflow-hidden">
    <header v-if="!bare" class="tt-card__head px-4 pt-4 md:px-5 md:pt-5">
      <div class="flex min-w-0 flex-col gap-1">
        <h2 class="tt-card__title">{{ t('accounts.symbols.title') }}</h2>
        <p class="m-0 text-body-sm text-ink-muted">{{ t('accounts.symbols.help') }}</p>
      </div>
      <TtButton variant="ghost" size="sm" icon="add" @click="openDialog">{{ t('accounts.symbols.add') }}</TtButton>
    </header>
    <div v-if="!overrides" class="p-4 md:p-5"><TtSkeleton :lines="2" /></div>
    <TtEmpty v-else-if="!overrides.length" icon="link" :message="t('accounts.symbols.empty')" />
    <ul v-else class="m-0 list-none p-0">
      <li v-for="(o, i) in overrides" :key="o.id" class="flex min-h-[52px] items-center gap-3 px-4 py-2 md:px-5" :class="{ 'border-t border-border': i > 0 || !bare }">
        <span class="tt-num min-w-0 flex-1 truncate font-semibold">{{ o.broker_symbol }}</span>
        <AppIcon name="forward" :size="16" class="flex-none text-ink-subtle" />
        <span class="tt-num flex-none whitespace-nowrap text-right font-semibold">{{ spec(o) }}</span>
        <TtIconButton icon="delete" bare :label="t('accounts.symbols.delete', { symbol: o.broker_symbol })" @click="remove(o)" />
      </li>
    </ul>

    <TtResponsiveDialog v-model:open="open" :title="t('accounts.symbols.add')" :subtitle="t('accounts.symbols.help')">
      <form id="symbol-form" class="tt-stack pt-2" novalidate @submit.prevent="submit">
        <TtAlert v-if="formError" variant="loss" :title="formError" />
        <div class="grid grid-cols-2 gap-3">
          <TtField :label="t('accounts.symbols.brokerSymbol')" :error="errors.broker_symbol">
            <TtInput v-model="form.broker_symbol" placeholder="XAUUSD.m" autocapitalize="characters" />
          </TtField>
          <TtField :label="t('accounts.symbols.standard')">
            <TtSelect v-model="form.symbol_id" :options="symbolOptions" />
          </TtField>
          <TtField :label="t('accounts.symbols.contractSize')" :help="t('accounts.symbols.optional')" :error="errors.contract_size">
            <TtInput v-model="form.contract_size" numeric />
          </TtField>
          <TtField :label="t('accounts.symbols.tickValue')" :help="t('accounts.symbols.optional')" :error="errors.tick_value">
            <TtInput v-model="form.tick_value" numeric />
          </TtField>
        </div>
      </form>
      <template #footer>
        <TtButton variant="secondary" class="flex-1 lg:flex-none" @click="open = false">{{ t('accounts.cancel') }}</TtButton>
        <TtButton type="submit" form="symbol-form" variant="primary" class="flex-1 lg:flex-none" :loading="saving">{{ t('accounts.symbols.save') }}</TtButton>
      </template>
    </TtResponsiveDialog>
  </section>
</template>
