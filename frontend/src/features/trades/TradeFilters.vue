<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AppIcon from '@/components/AppIcon.vue'
import TtButton from '@/components/ui/TtButton.vue'
import TtChip from '@/components/ui/TtChip.vue'
import TtField from '@/components/ui/TtField.vue'
import TtInput from '@/components/ui/TtInput.vue'
import TtResponsiveDialog from '@/components/ui/TtResponsiveDialog.vue'
import type { SymbolSpec } from '@/api/accounts'
import type { SetupSummary } from '@/api/playbook'
import type { Locale } from '@/i18n'
import { intlLocale } from '@/lib/format'
import { localDay, type TradeQuery } from './model'

// Filter chips (screens/web/06-WTrades.png: dates · Symbol · Setup · Quadrant · Emotion tag). Each chip opens a
// small picker (modal on desktop, sheet on mobile). Quadrant / Emotion wait for the Phase 6 scores.
const props = defineProps<{ state: TradeQuery; symbols: SymbolSpec[]; setups: SetupSummary[]; tz: string }>()
const emit = defineEmits<{ change: [patch: Partial<TradeQuery>] }>()
const { t, locale } = useI18n()

type Panel = 'dates' | 'symbol' | 'setup' | null
const panel = ref<Panel>(null)
const open = computed({ get: () => panel.value !== null, set: (v) => !v && (panel.value = null) })
const from = ref('')
const to = ref('')
const symbolSearch = ref('')

const fmt = (d: string) => {
  const [y, m, day] = d.split('-').map(Number)
  return new Intl.DateTimeFormat(intlLocale(locale.value as Locale), { day: 'numeric', month: 'short' }).format(new Date(y, m - 1, day))
}
const datesLabel = computed(() => {
  const { from: f, to: tt } = props.state
  if (!f && !tt) return t('trades.filters.allDates')
  return `${f ? fmt(f) : '…'} – ${tt ? fmt(tt) : '…'}`
})
const symbolLabel = computed(() => props.symbols.find((s) => s.id === props.state.symbol_id)?.code ?? t('trades.filters.allSymbols'))
const setupLabel = computed(() => props.setups.find((s) => s.id === props.state.setup_id)?.name ?? t('trades.filters.allSetups'))
const filteredSymbols = computed(() => {
  const q = symbolSearch.value.trim().toUpperCase()
  return q ? props.symbols.filter((s) => s.code.includes(q)) : props.symbols
})

function openDates() {
  from.value = props.state.from ?? ''
  to.value = props.state.to ?? ''
  panel.value = 'dates'
}
function preset(kind: 'last30' | 'thisMonth') {
  const now = new Date()
  const today = localDay(now.toISOString(), props.tz)
  if (kind === 'last30') {
    emit('change', { from: localDay(new Date(now.getTime() - 29 * 86_400_000).toISOString(), props.tz), to: today })
  } else {
    emit('change', { from: `${today.slice(0, 8)}01`, to: today })
  }
  panel.value = null
}
function applyDates() {
  emit('change', { from: from.value || null, to: to.value || null })
  panel.value = null
}
function pick(patch: Partial<TradeQuery>) {
  emit('change', patch)
  panel.value = null
}
const title = computed(() =>
  panel.value === 'dates' ? t('trades.filters.dates') : panel.value === 'symbol' ? t('trades.filters.symbol') : t('trades.filters.setup'),
)
</script>

<template>
  <div class="flex min-w-0 flex-nowrap gap-2 overflow-x-auto lg:flex-wrap lg:overflow-visible" :aria-label="t('trades.filters.label')" role="group">
    <TtChip :selected="!!(state.from || state.to)" data-testid="filter-dates" @click="openDates">
      <AppIcon name="calendar" :size="16" />{{ datesLabel }}
    </TtChip>
    <TtChip :selected="!!state.symbol_id" @click="panel = 'symbol'">
      {{ symbolLabel }}<AppIcon name="chevronDown" :size="16" />
    </TtChip>
    <TtChip :selected="!!state.setup_id" @click="panel = 'setup'">
      {{ setupLabel }}<AppIcon name="chevronDown" :size="16" />
    </TtChip>
    <TtChip disabled :title="t('trades.filters.later')" class="opacity-60">
      {{ t('trades.filters.quadrant') }}<AppIcon name="chevronDown" :size="16" />
    </TtChip>
    <TtChip disabled :title="t('trades.filters.later')" class="hidden opacity-60 lg:inline-flex">
      {{ t('trades.filters.emotion') }}<AppIcon name="chevronDown" :size="16" />
    </TtChip>
  </div>

  <TtResponsiveDialog v-model:open="open" :title="title" size="sm">
    <div v-if="panel === 'dates'" class="flex flex-col gap-3">
      <div class="tt-row">
        <TtChip @click="preset('last30')">{{ t('trades.filters.last30') }}</TtChip>
        <TtChip @click="preset('thisMonth')">{{ t('trades.filters.thisMonth') }}</TtChip>
        <TtChip @click="pick({ from: null, to: null })">{{ t('trades.filters.allDates') }}</TtChip>
      </div>
      <div class="grid grid-cols-2 gap-3">
        <TtField :label="t('trades.filters.from')"><input v-model="from" type="date" class="tt-input" /></TtField>
        <TtField :label="t('trades.filters.to')"><input v-model="to" type="date" class="tt-input" /></TtField>
      </div>
    </div>
    <div v-else-if="panel === 'symbol'" class="flex flex-col gap-2">
      <TtInput v-model="symbolSearch" type="search" :placeholder="t('trades.filters.searchSymbol')" :aria-label="t('trades.filters.searchSymbol')" />
      <div class="flex max-h-[320px] flex-wrap gap-2 overflow-y-auto">
        <TtChip :selected="!state.symbol_id" @click="pick({ symbol_id: null })">{{ t('trades.filters.allSymbols') }}</TtChip>
        <TtChip v-for="s in filteredSymbols" :key="s.id" :selected="state.symbol_id === s.id" @click="pick({ symbol_id: s.id })">{{ s.code }}</TtChip>
      </div>
    </div>
    <div v-else-if="panel === 'setup'" class="flex flex-wrap gap-2">
      <TtChip :selected="!state.setup_id" @click="pick({ setup_id: null })">{{ t('trades.filters.allSetups') }}</TtChip>
      <TtChip v-for="s in setups" :key="s.id" :selected="state.setup_id === s.id" @click="pick({ setup_id: s.id })">{{ s.name }}</TtChip>
    </div>
    <template v-if="panel === 'dates'" #footer>
      <TtButton variant="ghost" @click="pick({ from: null, to: null })">{{ t('trades.filters.clear') }}</TtButton>
      <TtButton variant="primary" @click="applyDates">{{ t('trades.filters.apply') }}</TtButton>
    </template>
  </TtResponsiveDialog>
</template>
