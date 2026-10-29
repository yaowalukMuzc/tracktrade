<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { watchDebounced } from '@vueuse/core'
import AppIcon from '@/components/AppIcon.vue'
import PageContent from '@/components/shell/PageContent.vue'
import TtAlert from '@/components/ui/TtAlert.vue'
import TtBadge from '@/components/ui/TtBadge.vue'
import TtButton from '@/components/ui/TtButton.vue'
import TtEmpty from '@/components/ui/TtEmpty.vue'
import TtField from '@/components/ui/TtField.vue'
import TtIconButton from '@/components/ui/TtIconButton.vue'
import TtInput from '@/components/ui/TtInput.vue'
import TtSelect from '@/components/ui/TtSelect.vue'
import TtSkeleton from '@/components/ui/TtSkeleton.vue'
import { ApiError } from '@/api/client'
import type { Direction } from '@/api/plans'
import { positionsApi, type MatchCandidate, type PositionCalc, type Side } from '@/api/positions'
import { useDesktop } from '@/composables/useDesktop'
import type { Locale } from '@/i18n'
import { formatMoney, intlLocale } from '@/lib/format'
import { browserTimezone } from '@/lib/timezones'
import { useAccountsStore } from '@/stores/accounts'
import { useReferenceStore } from '@/stores/reference'
import { useSessionStore } from '@/stores/session'
import CalcCard from './CalcCard.vue'
import ExecutionDialog from './ExecutionDialog.vue'
import {
  PLAN_LATER,
  PLAN_NONE,
  captions,
  emptyExecution,
  emptyForm,
  errorKey,
  firstEntry,
  fmtFixed,
  isBlank,
  localLabel,
  nowLocal,
  parseNum,
  sortExecutions,
  timeIn,
  toInput,
  validateForm,
  type ExecRow,
  type TradeForm,
} from './model'

// /trades/new?mode=manual|scan — screens/mobile/10-ManualTrade.png, screens/web/07-WAddTrade.png (manual tab).
// F-07 AC1–AC3: executions with scale-in / partial close, calc from the API, plan link or unplanned.
const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()
const desktop = useDesktop()
const accounts = useAccountsStore()
const reference = useReferenceStore()
const session = useSessionStore()

type Mode = 'manual' | 'scan'
const mode = computed<Mode>({
  get: () => (route.query.mode === 'scan' ? 'scan' : 'manual'),
  set: (v) => void router.replace({ query: { ...route.query, mode: v } }),
})
const tz = computed(() => session.user?.timezone || browserTimezone())
const intl = computed(() => intlLocale(locale.value as Locale))

const state = ref<'loading' | 'ready' | 'error'>('loading')
const form = ref<TradeForm>(emptyForm({ local: nowLocal(tz.value) }))
const needRate = ref(false)
const saving = ref(false)
const saveError = ref<string | null>(null)

async function load() {
  state.value = 'loading'
  try {
    await Promise.all([reference.ensureLoaded(), accounts.ensureLoaded()])
    form.value = emptyForm({
      accountId: accounts.selected?.id ?? accounts.active[0]?.id ?? null,
      symbolId: reference.symbolByCode.get('XAUUSD')?.id ?? reference.symbols[0]?.id ?? null,
      local: nowLocal(tz.value),
    })
    state.value = 'ready'
  } catch {
    state.value = 'error'
  }
}
onMounted(load)

/* ── Options / derived ─────────────────────────────────────── */

const accountOptions = computed(() => accounts.active.map((a) => ({ value: a.id, label: a.name })))
const symbolOptions = computed(() => reference.symbols.map((s) => ({ value: s.id, label: s.code })))
const account = computed(() => accounts.active.find((a) => a.id === form.value.accountId) ?? null)
const symbol = computed(() => reference.symbolById.get(form.value.symbolId))
const digits = computed(() => symbol.value?.digits ?? 2)
const currency = computed(() => account.value?.currency ?? 'USD')

const directions: { value: Direction; icon: 'up' | 'down' }[] = [
  { value: 'long', icon: 'up' },
  { value: 'short', icon: 'down' },
]
const sorted = computed(() => sortExecutions(form.value.executions))
const caps = computed(() => captions(form.value.executions))
const formErrors = computed(() => validateForm(form.value))
const fieldErr = (k: 'sl' | 'tp' | 'rate') => (formErrors.value[k] ? t(`tradeNew.errors.${formErrors.value[k]}`) : undefined)

function rowSub(r: ExecRow) {
  const cap = caps.value[r.key]
  const when = localLabel(r.local, intl.value)
  return cap ? `${when} · ${t(`tradeNew.executions.${cap}`)}` : when
}
const rowTitle = (r: ExecRow) => t('tradeNew.executions.row', { lot: fmtFixed(r.lot, 2), price: fmtFixed(r.price, digits.value) })
const costText = (r: ExecRow) => formatMoney(-(parseNum(r.commission) ?? 0), currency.value)

/* ── Execution dialog ──────────────────────────────────────── */

const dialogOpen = ref(false)
const dialogRow = ref<ExecRow | null>(null)
const dialogNew = ref(false)

function openAdd(side: Side) {
  const last = sorted.value[sorted.value.length - 1]
  dialogRow.value = emptyExecution(side, last?.local ?? nowLocal(tz.value))
  dialogNew.value = true
  dialogOpen.value = true
}
function openEdit(row: ExecRow) {
  dialogRow.value = row
  dialogNew.value = false
  dialogOpen.value = true
}
function onSaveRow(row: ExecRow) {
  const rows = form.value.executions
  const i = rows.findIndex((r) => r.key === row.key)
  form.value.executions = i === -1 ? [...rows, row] : rows.map((r) => (r.key === row.key ? row : r))
}
function onRemoveRow(key: string) {
  form.value.executions = form.value.executions.filter((r) => r.key !== key)
}

/* ── Auto calc (POST /positions/preview) ───────────────────── */

const calc = ref<PositionCalc | null>(null)
const calcError = ref<string | null>(null)
const calcLoading = ref(false)
let calcSeq = 0
let calcCtrl: AbortController | null = null

watchDebounced(
  () => (state.value === 'ready' && mode.value === 'manual' ? JSON.stringify(toInput(form.value, tz.value)) : 'null'),
  async (json) => {
    const mine = ++calcSeq
    calcCtrl?.abort()
    const body = JSON.parse(json) as ReturnType<typeof toInput>
    if (!body) {
      calc.value = null
      calcError.value = null
      calcLoading.value = false
      return
    }
    calcCtrl = new AbortController()
    calcLoading.value = true
    try {
      const res = await positionsApi.preview(body, calcCtrl.signal)
      if (mine !== calcSeq) return
      calc.value = res
      calcError.value = null
    } catch (e) {
      if (mine !== calcSeq || (e instanceof DOMException && e.name === 'AbortError')) return
      const code = e instanceof ApiError ? e.code : undefined
      if (code === 'conversion_rate_required') needRate.value = true
      calc.value = null
      calcError.value = t(errorKey(code))
    } finally {
      if (mine === calcSeq) calcLoading.value = false
    }
  },
  { debounce: 300, immediate: true },
)

/* ── Plan picker (GET /positions/plan-options) ─────────────── */

const planCandidates = ref<MatchCandidate[]>([])
watchDebounced(
  () => {
    const f = form.value
    const fe = state.value === 'ready' ? firstEntry(f, tz.value) : null
    return fe && f.accountId && f.symbolId ? JSON.stringify({ account_id: f.accountId, symbol_id: f.symbolId, direction: f.direction, ...fe }) : ''
  },
  async (key) => {
    try {
      planCandidates.value = key ? await positionsApi.planOptions(JSON.parse(key)) : []
    } catch {
      planCandidates.value = []
    }
    const p = form.value.plan
    if (p !== PLAN_LATER && p !== PLAN_NONE && !planCandidates.value.some((c) => c.plan.id === p)) form.value.plan = PLAN_LATER
  },
  { debounce: 300, immediate: true },
)

function planLabel(c: MatchCandidate) {
  const p = c.plan
  const stateText = p.status === 'draft' ? t('tradeNew.plan.draft') : p.locked_at ? t('tradeNew.plan.locked', { time: timeIn(p.locked_at, tz.value) }) : t(`trading.planStatus.${p.status}`)
  const label = t('tradeNew.plan.option', { label: p.scenario_label, symbol: symbol.value?.code ?? '', direction: t(`trading.direction.${form.value.direction}`), state: stateText })
  return c.recommended ? `${label} · ${t('tradeNew.plan.recommended')}` : label
}
const planOptions = computed(() => [
  { value: PLAN_LATER, label: t('tradeNew.plan.later') },
  ...planCandidates.value.map((c) => ({ value: c.plan.id, label: planLabel(c) })),
  { value: PLAN_NONE, label: t('tradeNew.plan.none') },
])
const planWarn = computed(() => (calc.value?.unplanned_reason ? t(`tradeNew.plan.warn.${calc.value.unplanned_reason}`) : null))
const planHelp = computed(() => (form.value.plan === PLAN_LATER ? t('tradeNew.plan.laterHelp') : undefined))

/* ── Save ──────────────────────────────────────────────────── */

const blocked = computed(() => {
  const first = (['account', 'symbol', 'executions', 'execution', 'sl', 'tp', 'rate'] as const).find((k) => formErrors.value[k])
  if (first) return t(`tradeNew.blocked.${first}`)
  return calcError.value ? t('tradeNew.blocked.calc') : null
})

async function save() {
  const body = toInput(form.value, tz.value)
  if (!body || blocked.value) return
  saving.value = true
  saveError.value = null
  try {
    const p = await positionsApi.create(body)
    await router.push(p.match_status === 'pending' ? { name: 'trades', query: { match: p.id } } : { name: 'trades' })
  } catch (e) {
    const code = e instanceof ApiError ? e.code : undefined
    if (code === 'conversion_rate_required') needRate.value = true
    saveError.value = t(errorKey(code))
  } finally {
    saving.value = false
  }
}

/** 4412.4 → 4,412.40 once the field is left (the symbol's digits, like the design). */
function tidy(key: 'sl' | 'tp') {
  const n = parseNum(form.value[key])
  if (n !== null && n > 0) form.value[key] = fmtFixed(n, digits.value)
}

const rateLabel = computed(() => t('tradeNew.fields.rate', { quote: symbol.value?.quote_currency ?? '', account: currency.value }))
const showRate = computed(() => needRate.value || !!form.value.rate)
</script>

<template>
  <!-- Desktop: Topbar with crumb + segmented (screens/source/WAddTrade.dc.html). Mobile: close · title · Scan. -->
  <header v-if="desktop" class="flex flex-wrap items-center gap-3 px-4 pt-4 md:px-6 lg:tt-topbar lg:sticky lg:top-0 lg:z-nav lg:px-8 lg:py-4">
    <div class="min-w-[200px] flex-1">
      <RouterLink :to="{ name: 'trades' }" class="tt-crumb"><AppIcon name="back" :size="16" />{{ t('tradeNew.crumb') }}</RouterLink>
      <h1 class="m-0 text-h2 lg:text-h1">{{ t('tradeNew.title') }}</h1>
    </div>
    <div class="tt-seg" role="radiogroup" :aria-label="t('tradeNew.mode.label')">
      <button type="button" role="radio" class="tt-seg__item inline-flex items-center gap-1.5" :class="{ 'tt-seg__item--on': mode === 'scan' }" :aria-checked="mode === 'scan'" @click="mode = 'scan'">
        <AppIcon name="scan" :size="16" />{{ t('tradeNew.mode.scan') }}
      </button>
      <button type="button" role="radio" class="tt-seg__item inline-flex items-center gap-1.5" :class="{ 'tt-seg__item--on': mode === 'manual' }" :aria-checked="mode === 'manual'" @click="mode = 'manual'">
        <AppIcon name="edit" :size="16" />{{ t('tradeNew.mode.manual') }}
      </button>
    </div>
  </header>
  <header v-else class="flex items-center gap-2 px-2 pt-2">
    <TtIconButton icon="close" bare :label="t('tradeNew.close')" :to="{ name: 'trades' }" />
    <h1 class="m-0 flex-1 text-h2">{{ t('tradeNew.title') }}</h1>
    <TtButton v-if="mode === 'manual'" variant="ghost" size="sm" icon="scan" @click="mode = 'scan'">{{ t('tradeNew.mode.scanAction') }}</TtButton>
  </header>

  <PageContent>
    <div v-if="!desktop" class="tt-seg tt-seg--block" role="radiogroup" :aria-label="t('tradeNew.mode.label')">
      <button type="button" role="radio" class="tt-seg__item" :class="{ 'tt-seg__item--on': mode === 'manual' }" :aria-checked="mode === 'manual'" @click="mode = 'manual'">
        {{ t('tradeNew.mode.manual') }}
      </button>
      <button type="button" role="radio" class="tt-seg__item" :class="{ 'tt-seg__item--on': mode === 'scan' }" :aria-checked="mode === 'scan'" @click="mode = 'scan'">
        {{ t('tradeNew.mode.scanShort') }}
      </button>
    </div>

    <!-- Loading / error / no account -->
    <div v-if="state === 'loading'" class="grid gap-6 lg:grid-cols-[1fr_360px]" aria-busy="true" :aria-label="t('ui.loading')">
      <div class="flex flex-col gap-6">
        <div class="tt-card"><TtSkeleton :lines="4" height="20px" /></div>
        <div class="tt-card"><TtSkeleton :lines="4" height="20px" /></div>
      </div>
      <div class="tt-card"><TtSkeleton :lines="5" height="20px" /></div>
    </div>
    <TtAlert v-else-if="state === 'error'" variant="loss" :title="t('tradeNew.errors.load')">
      <template #action><TtButton size="sm" @click="load">{{ t('tradeNew.retry') }}</TtButton></template>
    </TtAlert>
    <section v-else-if="mode === 'scan'" class="tt-card" data-testid="trade-scan">
      <TtEmpty icon="scan" :message="t('tradeNew.scan.message')">
        <TtButton variant="primary" @click="mode = 'manual'">{{ t('tradeNew.scan.back') }}</TtButton>
      </TtEmpty>
    </section>
    <section v-else-if="!accountOptions.length" class="tt-card" data-testid="trade-no-account">
      <TtEmpty icon="accounts" :message="t('tradeNew.noAccount.body')">
        <TtButton variant="primary" :to="{ name: 'accounts' }">{{ t('tradeNew.noAccount.action') }}</TtButton>
      </TtEmpty>
    </section>

    <template v-else>
      <TtAlert v-if="saveError" variant="loss" :title="saveError" dismissible data-testid="trade-save-error" @dismiss="saveError = null" />

      <div class="grid items-start gap-3 md:gap-6" :class="{ 'grid-cols-[minmax(0,1fr)_360px]': desktop }">
        <div class="flex min-w-0 flex-col gap-3 md:gap-6">
          <!-- ── Trade fields ───────────────────────────────── -->
          <section class="tt-card tt-stack" data-testid="trade-fields">
            <div class="grid gap-3" :class="desktop ? 'grid-cols-3 gap-4' : 'grid-cols-2'">
              <TtField :label="t('tradeNew.fields.account')" required>
                <TtSelect v-model="form.accountId" :options="accountOptions" data-testid="trade-account" />
              </TtField>
              <TtField :label="t('tradeNew.fields.symbol')" required>
                <TtSelect v-model="form.symbolId" :options="symbolOptions" data-testid="trade-symbol" />
              </TtField>
              <TtField v-if="desktop" :label="t('tradeNew.fields.direction')">
                <div class="tt-seg tt-seg--block" role="radiogroup" :aria-label="t('tradeNew.fields.direction')">
                  <button
                    v-for="d in directions"
                    :key="d.value"
                    type="button"
                    role="radio"
                    class="tt-seg__item"
                    :class="{
                      'tt-seg__item--on': form.direction === d.value,
                      'text-profit-ink': form.direction === d.value && d.value === 'long',
                      'text-loss-ink': form.direction === d.value && d.value === 'short',
                    }"
                    :aria-checked="form.direction === d.value"
                    :data-testid="`trade-dir-${d.value}`"
                    @click="form.direction = d.value"
                  >
                    {{ t(`trading.direction.${d.value}`) }}
                  </button>
                </div>
              </TtField>
            </div>

            <div v-if="!desktop" class="grid grid-cols-2 gap-2" role="radiogroup" :aria-label="t('tradeNew.fields.direction')">
              <button
                v-for="d in directions"
                :key="d.value"
                type="button"
                role="radio"
                class="flex h-12 items-center justify-center gap-1.5 rounded-md border text-[15px] font-bold leading-none transition-colors"
                :class="
                  form.direction === d.value
                    ? d.value === 'long'
                      ? 'border-profit bg-profit-100 text-profit-ink'
                      : 'border-loss bg-loss-100 text-loss-ink'
                    : 'border-border-strong bg-surface text-ink-muted'
                "
                :aria-checked="form.direction === d.value"
                :data-testid="`trade-dir-${d.value}`"
                @click="form.direction = d.value"
              >
                <AppIcon :name="d.icon" />{{ t(`trading.direction.${d.value}`) }}
              </button>
            </div>

            <div class="grid gap-3" :class="desktop ? 'grid-cols-3 gap-4' : 'grid-cols-2'">
              <TtField :label="t('tradeNew.fields.initialSl')" :error="fieldErr('sl')">
                <TtInput v-model="form.sl" numeric inputmode="decimal" data-testid="trade-sl" @blur="tidy('sl')" />
              </TtField>
              <TtField :label="t('tradeNew.fields.initialTp')" :error="fieldErr('tp')">
                <TtInput v-model="form.tp" numeric inputmode="decimal" data-testid="trade-tp" @blur="tidy('tp')" />
              </TtField>
              <div v-if="desktop" class="tt-field">
                <TtField :label="t('tradeNew.fields.plan')" :help="planWarn ? undefined : planHelp">
                  <TtSelect v-model="form.plan" :options="planOptions" data-testid="trade-plan" />
                </TtField>
                <span v-if="planWarn" class="tt-help tt-help--warn" data-testid="trade-plan-warn">{{ planWarn }}</span>
              </div>
            </div>

            <TtField v-if="showRate" :label="rateLabel" :help="t('tradeNew.fields.rateHelp')" :error="fieldErr('rate')">
              <TtInput v-model="form.rate" numeric inputmode="decimal" data-testid="trade-rate" />
            </TtField>
          </section>

          <!-- ── Executions: table on desktop, list on mobile ── -->
          <section v-if="desktop" class="tt-card overflow-hidden !p-0" data-testid="trade-executions">
            <div class="tt-card__head px-5 pt-4">
              <h2 class="tt-card__title">{{ t('tradeNew.executions.title') }}</h2>
              <div class="tt-row">
                <TtButton size="sm" icon="add" data-testid="add-entry" @click="openAdd('in')">{{ t('tradeNew.executions.addIn') }}</TtButton>
                <TtButton size="sm" icon="add" data-testid="add-exit" @click="openAdd('out')">{{ t('tradeNew.executions.addOut') }}</TtButton>
              </div>
            </div>
            <div class="tt-tblwrap">
              <table class="tt-tbl min-w-[560px]">
                <thead>
                  <tr>
                    <th scope="col">{{ t('tradeNew.executions.cols.side') }}</th>
                    <th scope="col">{{ t('tradeNew.executions.cols.time') }}</th>
                    <th scope="col" class="tt-tbl__r">{{ t('tradeNew.executions.cols.lot') }}</th>
                    <th scope="col" class="tt-tbl__r">{{ t('tradeNew.executions.cols.price') }}</th>
                    <th scope="col" class="tt-tbl__r">{{ t('tradeNew.executions.cols.commission') }}</th>
                    <th scope="col"><span class="sr-only">{{ t('tradeNew.dialog.edit') }}</span></th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(r, i) in sorted" :key="r.key" class="tt-tbl__link" data-testid="exec-row" @click="openEdit(r)">
                    <td><TtBadge :variant="r.side === 'in' ? 'brand' : 'outline'">{{ t(`tradeNew.executions.side.${r.side}`) }}</TtBadge></td>
                    <td>{{ rowSub(r) }}</td>
                    <template v-if="isBlank(r)">
                      <td colspan="3" class="tt-tbl__r text-warning-ink">{{ t('tradeNew.executions.blank') }}</td>
                    </template>
                    <template v-else>
                      <td class="tt-tbl__r">{{ fmtFixed(r.lot, 2) }}</td>
                      <td class="tt-tbl__r">{{ fmtFixed(r.price, digits) }}</td>
                      <td class="tt-tbl__r">{{ costText(r) }}</td>
                    </template>
                    <td class="tt-tbl__r w-12">
                      <TtIconButton icon="editRow" bare class="!size-8 text-ink-subtle" :label="t('tradeNew.executions.edit', { n: i + 1 })" @click.stop="openEdit(r)" />
                    </td>
                  </tr>
                  <tr v-if="!sorted.length">
                    <td colspan="6" class="tt-tbl__empty">{{ t('tradeNew.executions.empty') }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <section v-else class="flex flex-col gap-3" data-testid="trade-executions">
            <div class="flex items-center justify-between gap-2">
              <h2 class="m-0 text-h3">{{ t('tradeNew.executions.title') }}</h2>
              <span class="text-caption text-ink-muted">{{ t('tradeNew.executions.hint') }}</span>
            </div>
            <ul class="tt-list">
              <li v-for="(r, i) in sorted" :key="r.key" class="border-b border-border last:border-0">
                <button
                  type="button"
                  class="tt-list__row w-full !items-start !border-0 bg-transparent text-left"
                  data-testid="exec-row"
                  :aria-label="t('tradeNew.executions.edit', { n: i + 1 })"
                  @click="openEdit(r)"
                >
                  <TtBadge :variant="r.side === 'in' ? 'brand' : 'outline'" class="mt-0.5">{{ t(`tradeNew.executions.side.${r.side}`) }}</TtBadge>
                  <span class="flex min-w-0 flex-1 flex-col">
                    <span v-if="isBlank(r)" class="text-[14px] font-semibold leading-5 text-warning-ink">{{ t('tradeNew.executions.blank') }}</span>
                    <span v-else class="tt-num text-[14px] font-semibold leading-5">{{ rowTitle(r) }}</span>
                    <span class="text-caption text-ink-muted">{{ rowSub(r) }}</span>
                  </span>
                  <AppIcon name="editRow" :size="16" class="mt-1 text-ink-subtle" />
                </button>
              </li>
              <li v-if="!sorted.length" class="tt-list__row text-body-sm text-ink-muted">{{ t('tradeNew.executions.empty') }}</li>
            </ul>
            <div class="grid grid-cols-2 gap-3">
              <TtButton size="sm" icon="add" data-testid="add-entry" @click="openAdd('in')">{{ t('tradeNew.executions.addIn') }}</TtButton>
              <TtButton size="sm" icon="add" data-testid="add-exit" @click="openAdd('out')">{{ t('tradeNew.executions.addOut') }}</TtButton>
            </div>
          </section>

          <template v-if="!desktop">
            <CalcCard :calc="calc" :loading="calcLoading" :error="calcError" :digits="digits" :title="t('tradeNew.calc.title')" />
            <div class="tt-field">
              <TtField :label="t('tradeNew.fields.plan')" :help="planWarn ? undefined : planHelp">
                <TtSelect v-model="form.plan" :options="planOptions" data-testid="trade-plan" />
              </TtField>
              <span v-if="planWarn" class="tt-help tt-help--warn" data-testid="trade-plan-warn">{{ planWarn }}</span>
            </div>
          </template>
        </div>

        <!-- Desktop aside: calc + save -->
        <aside v-if="desktop" class="sticky top-[96px] flex flex-col gap-4">
          <CalcCard :calc="calc" :loading="calcLoading" :error="calcError" :digits="digits" :title="t('tradeNew.calc.titleDesktop')" />
          <TtButton variant="primary" size="lg" block icon="check" :loading="saving" :disabled="!!blocked" data-testid="trade-save" @click="save">
            {{ t('tradeNew.save') }}
          </TtButton>
          <span v-if="blocked" class="tt-help text-center" data-testid="trade-blocked">{{ blocked }}</span>
        </aside>
      </div>

      <!-- Mobile: sticky save above the bottom nav -->
      <div
        v-if="!desktop"
        class="sticky bottom-[calc(64px+env(safe-area-inset-bottom))] z-20 -mx-4 -mb-4 flex flex-col gap-1.5 border-t border-border bg-surface px-4 pb-3 pt-2 md:-mx-6"
      >
        <span v-if="blocked" class="tt-help text-center" data-testid="trade-blocked">{{ blocked }}</span>
        <TtButton variant="primary" size="lg" block :loading="saving" :disabled="!!blocked" data-testid="trade-save" @click="save">{{ t('tradeNew.save') }}</TtButton>
      </div>
    </template>
  </PageContent>

  <ExecutionDialog v-model:open="dialogOpen" :row="dialogRow" :is-new="dialogNew" :tz="tz" @save="onSaveRow" @remove="onRemoveRow" />
</template>
