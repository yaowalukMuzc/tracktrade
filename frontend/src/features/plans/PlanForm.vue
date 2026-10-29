<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import AppIcon from '@/components/AppIcon.vue'
import TtButton from '@/components/ui/TtButton.vue'
import TtField from '@/components/ui/TtField.vue'
import TtIconButton from '@/components/ui/TtIconButton.vue'
import TtInput from '@/components/ui/TtInput.vue'
import TtSegmented from '@/components/ui/TtSegmented.vue'
import TtSelect from '@/components/ui/TtSelect.vue'
import TtToggle from '@/components/ui/TtToggle.vue'
import type { PlanLines } from '@/components/chart/TradeChart.vue'
import type { Direction, EntryType, ManagementPlan } from '@/api/plans'
import type { ManagementRules } from '@/api/playbook'
import { formatNumber } from '@/lib/format'
import { MAX_TPS, splitShares, type FormErrors, type PlanFormModel } from './form'
import { lotText, money, rrText, tickValue } from './display'
import PlanChart from './PlanChart.vue'

/** Numbers behind the calc box (live calc while editing, the plan's own numbers once locked). */
export interface CalcView {
  riskAmount: string
  lot: string
  rr: string | null
  currency: string
  balance: string | null
  contract: string | null
  tick: string | null
}

// The editable plan (screens/web/05-WPlan.png left column, screens/mobile/07-PlanForm.png). Read-only once locked.
const props = defineProps<{
  layout: 'desktop' | 'mobile'
  readonly: boolean
  errors: FormErrors
  setupOptions: { value: string; label: string }[]
  scenarios: string[]
  rules: ManagementRules | null
  calc: CalcView | null
  calcError: string | null
  accountName: string
  symbolId: string | null
  symbolCode: string
  digits: number
  chartPlan: PlanLines | null
  /** New plan without an analysis: choose account + symbol. */
  context?: { accounts: { value: string; label: string }[]; symbols: { value: string; label: string }[] } | null
}>()
const model = defineModel<PlanFormModel>({ required: true })
const accountId = defineModel<string | null>('accountId', { default: null })
const symbolIdModel = defineModel<string | null>('symbolIdModel', { default: null })
const emit = defineEmits<{ setup: [id: string] }>()
const { t } = useI18n()

const err = (key: string) => (props.errors[key] ? t(`plans.errors.${props.errors[key]}`) : undefined)
const entryTypes = computed(() => (['market', 'limit', 'stop'] as EntryType[]).map((v) => ({ value: v, label: t(`trading.entryType.${v}`) })))
const scenarioOpts = computed(() => props.scenarios.map((s) => ({ value: s, label: s })))
const directions: { value: Direction; icon: 'up' | 'down' }[] = [
  { value: 'long', icon: 'up' },
  { value: 'short', icon: 'down' },
]

const num = (v: string) => formatNumber(v, 2)
const mgmt = computed(() => {
  const r = props.rules
  const out: { key: keyof ManagementPlan; title: string; sub?: string; full: string }[] = []
  if (r?.partial) {
    const s = t('plans.management.partial', { pct: num(r.partial.pct), r: num(r.partial.at_r) })
    out.push({ key: 'partial', title: s, full: s })
  }
  if (r?.break_even) {
    const s = t('plans.management.breakEven', { r: num(r.break_even.at_r) })
    out.push({ key: 'break_even', title: s, full: s })
  }
  if (r?.trailing) {
    out.push({
      key: 'trailing',
      title: t('plans.management.trailing'),
      sub: t('plans.management.trailingBy', { method: r.trailing.method }),
      full: t('plans.management.trailingFull', { method: r.trailing.method }),
    })
  }
  return out
})

function setMgmt(key: keyof ManagementPlan, on: boolean) {
  model.value.management = { ...model.value.management, [key]: on }
}
function addTp() {
  if (model.value.tps.length >= MAX_TPS) return
  const shares = splitShares(model.value.tps.length + 1)
  model.value.tps = [...model.value.tps.map((tp, i) => ({ ...tp, pct: shares[i] })), { price: '', pct: shares[shares.length - 1] }]
}
function removeTp(i: number) {
  const rest = model.value.tps.filter((_, j) => j !== i)
  const shares = splitShares(rest.length)
  model.value.tps = rest.map((tp, j) => ({ ...tp, pct: shares[j] }))
}

const calcMeta = computed(() => {
  const c = props.calc
  if (!c || c.contract === null || c.tick === null) return ''
  const tick = tickValue(c.tick, c.currency)
  const contract = formatNumber(c.contract, 2)
  return props.layout === 'desktop' && c.balance !== null
    ? t('plans.calc.meta', { balance: money(c.balance, c.currency), contract, tick })
    : t('plans.calc.metaShort', { contract, tick })
})
const riskHead = computed(() =>
  props.calc?.balance ? t('plans.calc.accountBalance', { account: props.accountName, balance: money(props.calc.balance, props.calc.currency) }) : props.accountName,
)
</script>

<template>
  <!-- ── Setup & Direction ─────────────────────────────── -->
  <div :class="layout === 'desktop' ? 'grid grid-cols-1 items-start gap-6 xl:grid-cols-2' : 'contents'">
    <section class="tt-card tt-stack" data-testid="plan-setup">
      <h2 class="m-0 text-h3">{{ t('plans.sections.setupDirection') }}</h2>

      <div v-if="context" class="grid grid-cols-2 gap-3">
        <TtField :label="t('plans.fields.account')" required>
          <TtSelect :model-value="accountId ?? undefined" :options="context.accounts" :disabled="readonly" @update:model-value="accountId = String($event)" />
        </TtField>
        <TtField :label="t('plans.fields.symbol')" required>
          <TtSelect :model-value="symbolIdModel ?? undefined" :options="context.symbols" :disabled="readonly" @update:model-value="symbolIdModel = String($event)" />
        </TtField>
      </div>

      <div :class="layout === 'mobile' ? 'grid grid-cols-2 gap-3' : 'contents'">
        <TtField :label="t('plans.fields.setup')" required :error="err('setup')">
          <TtSelect :model-value="model.setupId" :options="setupOptions" :disabled="readonly" @update:model-value="emit('setup', String($event))" />
        </TtField>
        <TtField v-if="layout === 'mobile'" :label="t('plans.fields.scenario')">
          <div :class="{ 'pointer-events-none opacity-70': readonly }">
            <TtSegmented v-model="model.scenario" :options="scenarioOpts" :label="t('plans.fields.scenario')" block />
          </div>
        </TtField>
      </div>

      <div class="grid grid-cols-2 gap-2" role="radiogroup" :aria-label="t('plans.fields.direction')">
        <button
          v-for="d in directions"
          :key="d.value"
          type="button"
          role="radio"
          class="flex h-12 items-center justify-center gap-1.5 rounded-md border text-[15px] font-bold leading-none transition-colors disabled:cursor-default"
          :class="
            model.direction === d.value
              ? d.value === 'long'
                ? 'border-profit bg-profit-100 text-profit-ink'
                : 'border-loss bg-loss-100 text-loss-ink'
              : 'border-border-strong bg-surface text-ink-muted'
          "
          :aria-checked="model.direction === d.value"
          :disabled="readonly"
          @click="model.direction = d.value"
        >
          <AppIcon :name="d.icon" />{{ t(`trading.direction.${d.value}`) }}
        </button>
      </div>

      <div v-if="layout === 'desktop'" class="grid grid-cols-2 gap-3">
        <TtField :label="t('plans.fields.entryType')">
          <TtSelect v-model="model.entryType" :options="entryTypes" :disabled="readonly" />
        </TtField>
        <TtField :label="t('plans.fields.scenario')">
          <div :class="{ 'pointer-events-none opacity-70': readonly }">
            <TtSegmented v-model="model.scenario" :options="scenarioOpts" :label="t('plans.fields.scenario')" block />
          </div>
        </TtField>
      </div>
      <TtField v-else :label="t('plans.fields.entryType')">
        <div :class="{ 'pointer-events-none opacity-70': readonly }">
          <TtSegmented v-model="model.entryType" :options="entryTypes" :label="t('plans.fields.entryType')" block />
        </div>
      </TtField>

      <template v-if="layout === 'desktop'">
        <TtField :label="t('plans.fields.invalidation')">
          <TtInput v-model="model.invalidation" :maxlength="300" :placeholder="t('plans.fields.invalidationPlaceholder')" :disabled="readonly" />
        </TtField>
        <TtField :label="t('plans.fields.validUntil')" :help="readonly ? undefined : t('plans.fields.validUntilHelp')">
          <input v-model="model.validUntil" type="datetime-local" class="tt-input" :disabled="readonly" />
        </TtField>
      </template>
    </section>

    <!-- ── Prices (& Risk on desktop) ──────────────────────── -->
    <section class="tt-card tt-stack" data-testid="plan-prices">
      <h2 class="m-0 text-h3">{{ layout === 'desktop' ? t('plans.sections.pricesRisk') : t('plans.sections.prices') }}</h2>
      <div class="grid grid-cols-2 gap-3">
        <TtField :label="t('plans.fields.entry')" required :error="err('entry')">
          <TtInput v-model="model.entry" numeric :disabled="readonly" />
        </TtField>
        <TtField :label="t('plans.fields.stopLoss')" required :error="err('stopLoss')">
          <TtInput v-model="model.stopLoss" numeric :disabled="readonly" />
        </TtField>
      </div>

      <div class="tt-field">
        <span class="tt-label">{{ t('plans.fields.takeProfit') }}<span class="tt-req" aria-hidden="true"> *</span></span>
        <div class="flex flex-col gap-2">
          <div v-for="(tp, i) in model.tps" :key="i" class="flex flex-col gap-1">
            <div class="grid items-center gap-2" :class="readonly ? 'grid-cols-[1fr_88px]' : 'grid-cols-[1fr_88px_32px]'">
              <TtInput v-model="tp.price" numeric :error="!!errors[`tp.${i}`]" :aria-label="t('plans.fields.tpPrice', { n: i + 1 })" :disabled="readonly" />
              <TtInput v-model="tp.pct" numeric suffix="%" :error="!!errors[`tpPct.${i}`]" :aria-label="t('plans.fields.tpPct', { n: i + 1 })" :disabled="readonly" />
              <TtIconButton
                v-if="!readonly"
                icon="close"
                bare
                class="!size-8"
                :label="t('plans.fields.removeTp', { n: i + 1 })"
                :disabled="model.tps.length <= 1"
                @click="removeTp(i)"
              />
            </div>
            <span v-if="errors[`tp.${i}`] || errors[`tpPct.${i}`]" class="tt-help tt-help--error" role="alert">
              {{ err(`tp.${i}`) ?? err(`tpPct.${i}`) }}
            </span>
          </div>
          <span v-if="errors.tps || errors.tpShare" class="tt-help tt-help--error" role="alert">{{ err('tps') ?? err('tpShare') }}</span>
          <TtButton v-if="!readonly && model.tps.length < MAX_TPS" variant="ghost" size="sm" icon="add" class="self-start" @click="addTp">
            {{ t('plans.fields.addTp') }}
          </TtButton>
        </div>
      </div>

      <template v-if="layout === 'mobile'">
        <TtField :label="t('plans.fields.invalidation')">
          <TtInput v-model="model.invalidation" :maxlength="300" :placeholder="t('plans.fields.invalidationPlaceholder')" :disabled="readonly" />
        </TtField>
        <TtField :label="t('plans.fields.validUntil')" :help="readonly ? undefined : t('plans.fields.validUntilHelp')">
          <input v-model="model.validUntil" type="datetime-local" class="tt-input" :disabled="readonly" />
        </TtField>
      </template>

      <template v-if="layout === 'desktop'">
        <TtField :label="t('plans.fields.riskPct')" required :error="err('riskPct')">
          <TtInput v-model="model.riskPct" numeric suffix="%" :disabled="readonly" />
        </TtField>
        <div class="grid grid-cols-3 gap-2 rounded-md bg-surface-sunken p-3" data-testid="plan-calc" aria-live="polite">
          <div class="flex flex-col">
            <span class="text-[11px] font-medium leading-4 text-ink-muted">{{ t('plans.calc.riskAmount') }}</span>
            <b class="tt-num text-[15px] font-semibold leading-[22px]">{{ calc ? money(calc.riskAmount, calc.currency) : '—' }}</b>
          </div>
          <div class="flex flex-col">
            <span class="text-[11px] font-medium leading-4 text-ink-muted">{{ t('plans.calc.lot') }}</span>
            <b class="tt-num text-[15px] font-semibold leading-[22px]">{{ calc ? lotText(calc.lot) : '—' }}</b>
          </div>
          <div class="flex flex-col">
            <span class="text-[11px] font-medium leading-4 text-ink-muted">{{ t('plans.calc.rr') }}</span>
            <b class="tt-num text-[15px] font-semibold leading-[22px]">{{ calc ? rrText(calc.rr) : '—' }}</b>
          </div>
        </div>
        <span v-if="calcError" class="tt-help tt-help--error" role="alert">{{ calcError }}</span>
        <span v-else-if="calcMeta" class="tt-help">{{ calcMeta }}</span>
        <span v-else-if="!readonly" class="tt-help">{{ t('plans.calc.waiting') }}</span>
      </template>
    </section>
  </div>

  <!-- ── Desktop: chart preview + management ─────────────── -->
  <template v-if="layout === 'desktop'">
    <PlanChart :symbol-id="symbolId" :symbol-code="symbolCode" :digits="digits" :plan="chartPlan" />
    <section class="tt-card" data-testid="plan-management">
      <h2 class="tt-card__title mb-1">{{ t('plans.sections.management') }}</h2>
      <p v-if="!mgmt.length" class="m-0 py-2 text-body-sm text-ink-muted">{{ t('plans.management.none') }}</p>
      <div v-for="m in mgmt" :key="m.key" class="flex items-center gap-3 border-b border-border py-2.5 last:border-0">
        <span class="flex-1 text-[14px] font-semibold leading-5">{{ m.full }}</span>
        <TtToggle :model-value="model.management[m.key]" :label="m.full" :disabled="readonly" @update:model-value="setMgmt(m.key, $event)" />
      </div>
    </section>
  </template>

  <!-- ── Mobile: Risk card (risk %, calc, management) ────── -->
  <section v-else class="tt-card tt-stack" data-testid="plan-risk">
    <div class="flex items-center justify-between gap-2">
      <h2 class="m-0 text-h3">{{ t('plans.sections.risk') }}</h2>
      <span class="truncate text-caption text-ink-muted">{{ riskHead }}</span>
    </div>
    <TtField :label="t('plans.fields.riskPct')" required :error="err('riskPct')">
      <TtInput v-model="model.riskPct" numeric suffix="%" :disabled="readonly" />
    </TtField>
    <div class="grid grid-cols-3 gap-2 rounded-md bg-surface-sunken p-3" data-testid="plan-calc" aria-live="polite">
      <div class="flex flex-col">
        <span class="text-[11px] font-medium leading-4 text-ink-muted">{{ t('plans.calc.riskAmount') }}</span>
        <b class="tt-num text-[15px] font-semibold leading-[22px]">{{ calc ? money(calc.riskAmount, calc.currency) : '—' }}</b>
      </div>
      <div class="flex flex-col">
        <span class="text-[11px] font-medium leading-4 text-ink-muted">{{ t('plans.calc.lot') }}</span>
        <b class="tt-num text-[15px] font-semibold leading-[22px]">{{ calc ? lotText(calc.lot) : '—' }}</b>
      </div>
      <div class="flex flex-col">
        <span class="text-[11px] font-medium leading-4 text-ink-muted">{{ t('plans.calc.rr') }}</span>
        <b class="tt-num text-[15px] font-semibold leading-[22px]">{{ calc ? rrText(calc.rr) : '—' }}</b>
      </div>
    </div>
    <span v-if="calcError" class="tt-help tt-help--error" role="alert">{{ calcError }}</span>
    <span v-else-if="calcMeta" class="tt-help">{{ calcMeta }}</span>
    <span v-else-if="!readonly" class="tt-help">{{ t('plans.calc.waiting') }}</span>
    <div class="tt-field">
      <span class="tt-label">{{ t('plans.sections.management') }}</span>
      <p v-if="!mgmt.length" class="m-0 text-body-sm text-ink-muted">{{ t('plans.management.none') }}</p>
      <div v-else class="overflow-hidden rounded-lg border border-border">
        <div v-for="m in mgmt" :key="m.key" class="flex items-center gap-3 border-b border-border px-3 py-2.5 last:border-0">
          <div class="flex min-w-0 flex-1 flex-col">
            <span class="text-[14px] font-semibold leading-5">{{ m.title }}</span>
            <span v-if="m.sub" class="text-caption font-normal text-ink-muted">{{ m.sub }}</span>
          </div>
          <TtToggle :model-value="model.management[m.key]" :label="m.full" :disabled="readonly" @update:model-value="setMgmt(m.key, $event)" />
        </div>
      </div>
    </div>
  </section>
</template>
