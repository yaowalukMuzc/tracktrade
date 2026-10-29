<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter, type RouteLocationRaw } from 'vue-router'
import { onClickOutside, watchDebounced } from '@vueuse/core'
import AppIcon from '@/components/AppIcon.vue'
import PageContent from '@/components/shell/PageContent.vue'
import TtAlert from '@/components/ui/TtAlert.vue'
import TtBadge from '@/components/ui/TtBadge.vue'
import TtButton from '@/components/ui/TtButton.vue'
import TtEmpty from '@/components/ui/TtEmpty.vue'
import TtIconButton from '@/components/ui/TtIconButton.vue'
import TtModal from '@/components/ui/TtModal.vue'
import TtSkeleton from '@/components/ui/TtSkeleton.vue'
import type { PlanLines } from '@/components/chart/TradeChart.vue'
import { ApiError } from '@/api/client'
import { analysisApi, type Analysis } from '@/api/analysis'
import { MANUAL_TRANSITIONS, plansApi, type ManualStatus, type Plan, type PlanStatus } from '@/api/plans'
import { playbookApi, type Setup, type SetupSummary } from '@/api/playbook'
import { riskApi, type RiskCalcResult } from '@/api/risk'
import { useDesktop } from '@/composables/useDesktop'
import type { Locale } from '@/i18n'
import { formatNumber } from '@/lib/format'
import { useAccountsStore } from '@/stores/accounts'
import { useReferenceStore } from '@/stores/reference'
import {
  calcInput,
  defaultManagement,
  emotionFromPlan,
  emotionInput,
  emptyModel,
  formatRiskPct,
  fromPlan,
  isValid,
  missingRequired,
  nextScenario,
  parseNum,
  scenarioOptions,
  toCreate,
  toUpdate,
  validatePlan,
  type EmotionModel,
  type PlanFormModel,
} from './form'
import { dayMonth } from './display'
import { missingFromError, planErrorKey } from './errors'
import { PLAN_STATUS_BADGE, isTerminalPlan } from './status'
import PlanChecklistCard from './PlanChecklistCard.vue'
import PlanForm, { type CalcView } from './PlanForm.vue'
import PlanLockBar from './PlanLockBar.vue'
import PlanRevisionsCard from './PlanRevisionsCard.vue'
import PlanSummaryCard from './PlanSummaryCard.vue'
import PreEmotionCard from './PreEmotionCard.vue'
import RevisionDialog from './RevisionDialog.vue'
import StatusDialog from './StatusDialog.vue'

// /plans/new?analysis= and /plans/:id — screens/web/05-WPlan.png, screens/mobile/07-PlanForm.png, 08-PlanLocked.png.
// F-06 AC1–AC7 (+ F-11 AC1): draft → (checklist) → lock (hash, rev 1) → revisions with a reason; status changes.
const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()
const desktop = useDesktop()
const accounts = useAccountsStore()
const reference = useReferenceStore()

const isNew = computed(() => route.name === 'plan-new')
const routeId = computed(() => (isNew.value ? null : String(route.params.id)))

type Load = 'loading' | 'ready' | 'notFound' | 'error'
const state = ref<Load>('loading')
const plan = ref<Plan | null>(null)
const analysis = ref<Analysis | null>(null)
const setups = ref<SetupSummary[]>([])
const setup = ref<Setup | null>(null)
const model = ref<PlanFormModel>(emptyModel())
const emotion = ref<EmotionModel>({ mood: null, confidence: null, tags: [] })
const accountId = ref<string | null>(null)
const symbolId = ref<string | null>(null)
const planDate = ref<string | null>(null)
const baseline = ref('')
let emotionBaseline = ''

const showErrors = ref(false)
const triedLock = ref(false)
const serverMissing = ref<string[]>([])
const saving = ref(false)
const locking = ref(false)
const notice = ref<string | null>(null)
const actionError = ref<string | null>(null)
const emotionError = ref<string | null>(null)
const revisionOpen = ref(false)
const statusOpen = ref(false)
const statusTarget = ref<ManualStatus | null>(null)
const deleteOpen = ref(false)
const deleting = ref(false)
const menuOpen = ref(false)
const menuRef = ref<HTMLElement | null>(null)
onClickOutside(menuRef, () => (menuOpen.value = false))

/* ── Derived ─────────────────────────────────────────────── */

const status = computed<PlanStatus>(() => plan.value?.status ?? 'draft')
const editable = computed(() => isNew.value || status.value === 'draft')
const revisable = computed(() => status.value === 'locked' || status.value === 'triggered')
const emotionEditable = computed(() => isNew.value || status.value === 'draft' || status.value === 'locked')
const terminal = computed(() => !!plan.value && isTerminalPlan(plan.value.status))
const symbol = computed(() => (symbolId.value ? reference.symbolById.get(symbolId.value) : undefined))
const digits = computed(() => symbol.value?.digits ?? 2)
const symbolCode = computed(() => plan.value?.symbol_code ?? symbol.value?.code ?? analysis.value?.symbol_code ?? '')
const l = computed(() => locale.value as Locale)

const title = computed(() => t('trading.planTitle', { label: model.value.scenario || '?', symbol: symbolCode.value }))
const crumb = computed<{ to: RouteLocationRaw; label: string }>(() => {
  const a = analysis.value
  const aId = plan.value?.analysis_id ?? a?.id
  if (aId && a) return { to: { name: 'analysis', params: { id: aId } }, label: t('plans.crumbAnalysis', { symbol: a.symbol_code, date: dayMonth(a.analysis_date, l.value) }) }
  return { to: { name: 'today' }, label: t('plans.crumbToday') }
})

const setupOptions = computed(() => {
  const opts = setups.value.map((s) => ({ value: s.id, label: s.name }))
  const p = plan.value
  if (p && !opts.some((o) => o.value === p.setup_id)) opts.unshift({ value: p.setup_id, label: p.setup_name })
  if (!model.value.setupId) opts.unshift({ value: '', label: t('plans.fields.setupPlaceholder') })
  return opts
})
const setupName = computed(() => setup.value?.name ?? plan.value?.setup_name ?? '')

const siblingScenarios = computed(() => (analysis.value?.plans ?? []).filter((p) => p.id !== plan.value?.id).map((p) => p.scenario_label))
const scenarios = computed(() => scenarioOptions(siblingScenarios.value, model.value.scenario, desktop.value ? 2 : 3))

const context = computed(() =>
  isNew.value && !analysis.value
    ? {
        accounts: accounts.active.map((a) => ({ value: a.id, label: a.name })),
        symbols: reference.symbols.map((s) => ({ value: s.id, label: s.code })),
      }
    : null,
)
const accountName = computed(() => accounts.accounts.find((a) => a.id === accountId.value)?.name ?? '')

/** Checklist shown: frozen answers once locked, else the setup's items with the form's answers. */
const checklistItems = computed(() => {
  const p = plan.value
  if (p && p.status !== 'draft') return p.checklist_items
  const s = setup.value
  if (s && s.id === model.value.setupId) {
    return s.checklist.map((c) => ({ id: c.id, text: c.text, is_required: c.is_required, checked: !!model.value.checklist[c.id], note: '' }))
  }
  return (p?.checklist_items ?? []).map((c) => ({ ...c, checked: !!model.value.checklist[c.id] }))
})
const checkedCount = computed(() => checklistItems.value.filter((c) => c.checked).length)
const missing = computed(() => missingRequired(checklistItems.value, model.value.checklist))
const flagged = computed(() => (triedLock.value ? [...new Set([...missing.value, ...serverMissing.value])] : []))
const showCantLock = computed(() => editable.value && triedLock.value && flagged.value.length > 0)

const errors = computed(() => (showErrors.value && editable.value ? validatePlan(model.value) : {}))
const dirty = computed(() => isNew.value || JSON.stringify(toUpdate(model.value)) !== baseline.value)

const chartPlan = computed<PlanLines | null>(() => {
  const entry = parseNum(model.value.entry)
  const sl = parseNum(model.value.stopLoss)
  if (entry === null || sl === null || entry <= 0 || sl <= 0) return null
  const tps = model.value.tps.map((tp) => parseNum(tp.price)).filter((x): x is number => x !== null && x > 0)
  return { entry, stopLoss: sl, takeProfits: tps }
})

const menuItems = computed(() => {
  const p = plan.value
  if (!p) return []
  const items: { id: ManualStatus | 'delete'; label: string }[] = (['skipped', 'missed', 'invalidated'] as ManualStatus[])
    .filter((s) => MANUAL_TRANSITIONS[s].includes(p.status))
    .map((s) => ({ id: s, label: t(`plans.status.${s}`) }))
  if (p.status === 'draft') items.push({ id: 'delete', label: t('plans.status.delete') })
  return items
})

const terminalText = computed(() => {
  const p = plan.value
  if (!p || !terminal.value) return null
  const statusLabel = t(`trading.planStatus.${p.status}`)
  const body = p.status_reason
    ? t('plans.terminal.reason', { reason: p.status_reason })
    : p.status === 'expired'
      ? t('plans.terminal.expired')
      : p.status === 'closed'
        ? t('plans.terminal.closed')
        : ''
  return { title: t('plans.terminal.title', { status: statusLabel }), body }
})

/* ── Calc box (F-06 AC2) ─────────────────────────────────── */

const calcResult = ref<RiskCalcResult | null>(null)
const calcError = ref<string | null>(null)
let calcSeq = 0
watchDebounced(
  () => (editable.value && state.value === 'ready' ? calcInput(model.value, accountId.value, symbolId.value) : null),
  async (input) => {
    const mine = ++calcSeq
    if (!input) {
      calcResult.value = null
      calcError.value = null
      return
    }
    try {
      const r = await riskApi.calc(input)
      if (mine !== calcSeq) return
      calcResult.value = r
      calcError.value = null
    } catch (e) {
      if (mine !== calcSeq) return
      calcResult.value = null
      calcError.value = t(planErrorKey(e))
    }
  },
  { debounce: 250, deep: true, immediate: true },
)

const calcView = computed<CalcView | null>(() => {
  const p = plan.value
  if (!editable.value && p) {
    return {
      riskAmount: p.planned_risk_amount,
      lot: p.planned_lot,
      rr: p.planned_rr,
      currency: p.currency,
      balance: p.calc?.balance ?? null,
      contract: p.calc?.contract_size ?? null,
      tick: p.calc?.value_per_point ?? null,
    }
  }
  const r = calcResult.value
  if (!r) return null
  return { riskAmount: r.risk_amount, lot: r.lot, rr: r.rr_avg, currency: r.currency, balance: r.balance, contract: r.contract_size, tick: r.value_per_point }
})

/* ── Loading ─────────────────────────────────────────────── */

const snapshot = () => JSON.stringify(toUpdate(model.value))

function applyPlan(p: Plan) {
  plan.value = p
  accountId.value = p.account_id
  symbolId.value = p.symbol_id
  planDate.value = p.plan_date
  model.value = fromPlan(p, reference.symbolById.get(p.symbol_id)?.digits ?? 2)
  emotion.value = emotionFromPlan(p)
  emotionBaseline = JSON.stringify(emotionInput(emotion.value))
  baseline.value = snapshot()
}

async function loadSetup(id: string) {
  setup.value = await playbookApi.get(id)
  return setup.value
}

/** User picked another setup: its checklist, management rules and default risk % (F-06, F-04). */
async function chooseSetup(id: string) {
  model.value.setupId = id
  if (!id) return
  try {
    const s = await loadSetup(id)
    if (model.value.setupId !== id) return
    model.value.checklist = Object.fromEntries(s.checklist.map((c) => [c.id, false]))
    model.value.riskPct = formatRiskPct(s.default_risk_pct)
    model.value.management = defaultManagement(s.management_rules)
    triedLock.value = false
    serverMissing.value = []
  } catch (e) {
    actionError.value = t(planErrorKey(e))
  }
}

async function load() {
  state.value = 'loading'
  notice.value = null
  actionError.value = null
  showErrors.value = false
  triedLock.value = false
  serverMissing.value = []
  plan.value = null
  analysis.value = null
  setup.value = null
  try {
    await Promise.all([reference.ensureLoaded(), accounts.ensureLoaded()])
    const list = await playbookApi.list()
    setups.value = list.items.filter((s) => !s.is_archived)
    if (isNew.value) {
      const aId = typeof route.query.analysis === 'string' ? route.query.analysis : null
      if (aId) analysis.value = await analysisApi.get(aId)
      const a = analysis.value
      accountId.value = a?.account_id ?? accounts.selected?.id ?? accounts.active[0]?.id ?? null
      symbolId.value = a?.symbol_id ?? reference.symbolByCode.get('XAUUSD')?.id ?? reference.symbols[0]?.id ?? null
      planDate.value = a?.analysis_date ?? null
      model.value = emptyModel({ scenario: nextScenario((a?.plans ?? []).map((p) => p.scenario_label)) })
      emotion.value = { mood: null, confidence: null, tags: [] }
      emotionBaseline = ''
      baseline.value = ''
      const first = setups.value[0]
      state.value = 'ready'
      if (first) await chooseSetup(first.id)
      return
    }
    const p = await plansApi.get(routeId.value!)
    applyPlan(p)
    const [a] = await Promise.all([
      p.analysis_id ? analysisApi.get(p.analysis_id).catch(() => null) : Promise.resolve(null),
      loadSetup(p.setup_id).catch(() => null),
    ])
    analysis.value = a
    state.value = 'ready'
  } catch (e) {
    state.value = e instanceof ApiError && e.status === 404 ? 'notFound' : 'error'
  }
}

watch(
  [isNew, routeId, () => route.query.analysis],
  () => {
    if (!isNew.value && plan.value && plan.value.id === routeId.value) return // just created → URL replaced
    void load()
  },
  { immediate: true },
)

/* ── Actions ─────────────────────────────────────────────── */

function toggleCheck(id: string) {
  if (!editable.value) return
  model.value.checklist = { ...model.value.checklist, [id]: !model.value.checklist[id] }
  serverMissing.value = serverMissing.value.filter((x) => x !== id)
}

async function save(): Promise<boolean> {
  showErrors.value = true
  actionError.value = null
  notice.value = null
  if (!isValid(validatePlan(model.value))) {
    actionError.value = t('plans.errors.form')
    return false
  }
  if (!isNew.value && !dirty.value) return true
  if (!accountId.value || !symbolId.value) {
    actionError.value = t('plans.noAccount')
    return false
  }
  saving.value = true
  try {
    if (isNew.value) {
      const p = await plansApi.create(
        toCreate(model.value, { analysisId: analysis.value?.id ?? null, accountId: accountId.value, symbolId: symbolId.value, planDate: planDate.value }, emotion.value),
      )
      applyPlan(p)
      await router.replace({ name: 'plan', params: { id: p.id } })
    } else {
      applyPlan(await plansApi.update(plan.value!.id, toUpdate(model.value)))
    }
    showErrors.value = false
    return true
  } catch (e) {
    actionError.value = t(planErrorKey(e))
    if (e instanceof ApiError && e.code === 'plan_not_draft') void load()
    return false
  } finally {
    saving.value = false
  }
}

async function saveDraft() {
  if (await save()) notice.value = t('plans.savedDraft')
}

async function lock() {
  triedLock.value = true
  notice.value = null
  if (missing.value.length) return
  if (!(await save())) return
  locking.value = true
  try {
    applyPlan(await plansApi.lock(plan.value!.id))
    triedLock.value = false
    serverMissing.value = []
    notice.value = t('plans.lockedNotice')
  } catch (e) {
    const miss = missingFromError(e)
    if (miss) serverMissing.value = miss
    else actionError.value = t(planErrorKey(e))
  } finally {
    locking.value = false
  }
}

async function onRevised(rev: { revision_no: number }) {
  try {
    applyPlan(await plansApi.get(plan.value!.id))
    notice.value = t('plans.revisionSheet.saved', { n: rev.revision_no })
  } catch (e) {
    actionError.value = t(planErrorKey(e))
  }
}

function onStatusChanged(p: Plan) {
  applyPlan(p)
  notice.value = t('plans.status.changed', { status: t(`trading.planStatus.${p.status}`) })
}

function pickMenu(id: ManualStatus | 'delete') {
  menuOpen.value = false
  if (id === 'delete') {
    deleteOpen.value = true
    return
  }
  statusTarget.value = id
  statusOpen.value = true
}

async function deletePlan() {
  const p = plan.value
  if (!p) return
  deleting.value = true
  try {
    await plansApi.remove(p.id)
    deleteOpen.value = false
    await router.replace(p.analysis_id ? { name: 'analysis', params: { id: p.analysis_id } } : { name: 'today' })
  } catch (e) {
    deleteOpen.value = false
    actionError.value = t(planErrorKey(e))
  } finally {
    deleting.value = false
  }
}

// Pre-trade emotion (F-06 AC7) saves itself on existing plans until the entry; a new plan sends it with the create.
watchDebounced(
  emotion,
  async (e) => {
    const p = plan.value
    if (!p || !emotionEditable.value) return
    const body = emotionInput(e)
    const json = JSON.stringify(body)
    if (json === emotionBaseline) return
    try {
      const updated = await plansApi.setPreEmotion(p.id, body)
      emotionBaseline = json
      emotionError.value = null
      if (plan.value?.id === updated.id) plan.value = { ...plan.value, pre_emotion: updated.pre_emotion }
    } catch (err) {
      emotionError.value = t(planErrorKey(err))
    }
  },
  { debounce: 500, deep: true },
)

const keyLevelsText = computed(() =>
  (analysis.value?.key_levels ?? [])
    .slice(0, 3)
    .map((k) => `${k.label} ${formatNumber(k.price, digits.value)}${k.price_to ? `–${formatNumber(k.price_to, digits.value)}` : ''}`)
    .join(' · '),
)
</script>

<template>
  <!-- Header: crumb back to the analysis, "แผน A · XAUUSD" + status, actions (screens.css .topbar) -->
  <header class="flex flex-wrap items-center gap-3 px-4 pt-4 md:px-6 lg:tt-topbar lg:sticky lg:top-0 lg:z-nav lg:px-8 lg:py-4">
    <div class="min-w-[200px] flex-1">
      <RouterLink :to="crumb.to" class="tt-crumb"><AppIcon name="back" :size="16" />{{ crumb.label }}</RouterLink>
      <h1 class="m-0 flex flex-wrap items-center gap-2 text-h2 lg:text-h1">
        <span>{{ state === 'ready' ? title : t('pages.plan') }}</span>
        <TtBadge v-if="state === 'ready'" :variant="PLAN_STATUS_BADGE[status]" data-testid="plan-status">{{ t(`trading.planStatus.${status}`) }}</TtBadge>
      </h1>
    </div>
    <template v-if="state === 'ready'">
      <template v-if="desktop && editable">
        <TtButton :loading="saving && !locking" :disabled="locking" @click="saveDraft">{{ t('plans.saveDraft') }}</TtButton>
        <TtButton
          variant="primary"
          icon="planLocked"
          :class="{ 'tt-btn--disabled': missing.length > 0 }"
          :loading="locking"
          data-testid="plan-lock-btn"
          @click="lock"
        >
          {{ t('plans.lock', { done: checkedCount, total: checklistItems.length }) }}
        </TtButton>
      </template>
      <TtButton v-if="desktop && revisable" icon="edit" data-testid="plan-revise-btn" @click="revisionOpen = true">{{ t('plans.revise') }}</TtButton>
      <div v-if="menuItems.length" ref="menuRef" class="relative">
        <TtIconButton icon="options" :label="t('plans.options')" :aria-expanded="menuOpen" aria-haspopup="menu" @click="menuOpen = !menuOpen" />
        <ul v-if="menuOpen" class="tt-menu right-0 top-11 w-max min-w-[220px]" role="menu">
          <li v-for="m in menuItems" :key="m.id" role="none">
            <button type="button" role="menuitem" class="tt-menu__item" :class="{ 'text-loss-ink': m.id === 'delete' }" @click="pickMenu(m.id)">
              {{ m.label }}
            </button>
          </li>
        </ul>
      </div>
    </template>
  </header>

  <PageContent>
    <!-- Loading / not found / error -->
    <div v-if="state === 'loading'" class="flex flex-col gap-6" aria-busy="true" :aria-label="t('ui.loading')">
      <div class="grid gap-6 lg:grid-cols-[1fr_360px]">
        <div class="flex flex-col gap-6">
          <div class="tt-card"><TtSkeleton :lines="5" height="20px" /></div>
          <div class="tt-card"><TtSkeleton :lines="4" height="20px" /></div>
        </div>
        <div class="tt-card"><TtSkeleton :lines="4" height="20px" /></div>
      </div>
    </div>
    <div v-else-if="state === 'notFound'" class="tt-card flex flex-col items-center gap-3 py-10 text-center" data-testid="plan-not-found">
      <TtEmpty icon="plan" :message="t('plans.notFound.title')" />
      <p class="m-0 text-body-sm text-ink-muted">{{ t('plans.notFound.body') }}</p>
      <TtButton variant="primary" :to="{ name: 'today' }">{{ t('plans.notFound.back') }}</TtButton>
    </div>
    <TtAlert v-else-if="state === 'error'" variant="loss" :title="t('plans.errors.load')">
      <template #action>
        <TtButton size="sm" @click="load">{{ t('plans.retry') }}</TtButton>
      </template>
    </TtAlert>

    <template v-else>
      <!-- Notices -->
      <PlanLockBar v-if="plan?.locked_at" :locked-at="plan.locked_at" :hash="plan.current_hash ?? plan.lock_hash" :revision="plan.current_revision" :short="!desktop" />
      <TtAlert v-if="terminalText" variant="info" :title="terminalText.title" :body="terminalText.body || undefined" data-testid="plan-terminal" />
      <TtAlert v-if="showCantLock" variant="loss" :title="t('plans.cantLock.title')" :body="t('plans.cantLock.body')" data-testid="plan-cant-lock" />
      <TtAlert v-if="actionError" variant="loss" :title="actionError" dismissible @dismiss="actionError = null" />
      <TtAlert v-if="notice" variant="profit" :title="notice" dismissible @dismiss="notice = null" />
      <TtAlert v-if="isNew && !accountId" variant="warning" :title="t('plans.noAccount')">
        <template #action><TtButton size="sm" :to="{ name: 'accounts' }">{{ t('plans.goAccounts') }}</TtButton></template>
      </TtAlert>
      <TtAlert v-if="isNew && !setups.length" variant="warning" :title="t('plans.noSetup')">
        <template #action><TtButton size="sm" :to="{ name: 'playbook' }">{{ t('plans.goPlaybook') }}</TtButton></template>
      </TtAlert>

      <!-- ≥1024px: form column + checklist / emotion / revisions -->
      <div v-if="desktop" class="flex flex-wrap items-start gap-6">
        <div class="flex min-w-0 flex-[999_1_520px] flex-col gap-6">
          <PlanForm
            v-model="model"
            v-model:account-id="accountId"
            v-model:symbol-id-model="symbolId"
            layout="desktop"
            :readonly="!editable"
            :errors="errors"
            :setup-options="setupOptions"
            :scenarios="scenarios"
            :rules="setup?.management_rules ?? null"
            :calc="calcView"
            :calc-error="editable ? calcError : null"
            :account-name="accountName"
            :symbol-id="symbolId"
            :symbol-code="symbolCode"
            :digits="digits"
            :chart-plan="chartPlan"
            :context="context"
            @setup="chooseSetup"
          />
        </div>
        <aside class="flex min-w-0 max-w-[400px] flex-[1_1_320px] flex-col gap-6">
          <PlanChecklistCard :setup-name="setupName" :items="checklistItems" :missing="flagged" :highlight="showCantLock" :readonly="!editable" @toggle="toggleCheck" />
          <PreEmotionCard v-model="emotion" :readonly="!emotionEditable" :error="emotionError" />
          <PlanRevisionsCard :revisions="plan?.revisions ?? []" :digits="digits" />
        </aside>
      </div>

      <!-- <1024px: screens/mobile/07-PlanForm.png (editable) · 08-PlanLocked.png (locked) -->
      <template v-else>
        <div v-if="analysis && editable" class="tt-alert text-[13px] leading-5" data-testid="plan-from-analysis">
          <AppIcon name="analysis" class="mt-0.5" />
          <div class="min-w-0 flex-1">
            <span class="tt-alert__title">
              {{ t('plans.fromAnalysis', { date: dayMonth(analysis.analysis_date, l), bias: t(`trading.bias.${analysis.htf_bias}`) }) }}
            </span>
            <span v-if="keyLevelsText" class="tt-alert__body">{{ keyLevelsText }}</span>
          </div>
        </div>
        <template v-if="editable">
          <PlanForm
            v-model="model"
            v-model:account-id="accountId"
            v-model:symbol-id-model="symbolId"
            layout="mobile"
            :readonly="false"
            :errors="errors"
            :setup-options="setupOptions"
            :scenarios="scenarios"
            :rules="setup?.management_rules ?? null"
            :calc="calcView"
            :calc-error="calcError"
            :account-name="accountName"
            :symbol-id="symbolId"
            :symbol-code="symbolCode"
            :digits="digits"
            :chart-plan="chartPlan"
            :context="context"
            @setup="chooseSetup"
          />
        </template>
        <template v-else-if="plan">
          <PlanSummaryCard :plan="plan" :digits="digits" />
          <TtButton v-if="revisable" block icon="edit" data-testid="plan-revise-btn" @click="revisionOpen = true">{{ t('plans.revise') }}</TtButton>
        </template>
        <PlanChecklistCard :setup-name="setupName" :items="checklistItems" :missing="flagged" :highlight="showCantLock" :readonly="!editable" @toggle="toggleCheck" />
        <PreEmotionCard v-model="emotion" :readonly="!emotionEditable" :error="emotionError" />
        <PlanRevisionsCard v-if="plan?.revisions.length" :revisions="plan.revisions" :digits="digits" />

        <!-- Sticky action bar above the bottom nav -->
        <div
          v-if="editable"
          class="sticky bottom-[calc(64px+env(safe-area-inset-bottom))] z-20 -mx-4 -mb-4 flex flex-col gap-1.5 border-t border-border bg-surface px-4 pb-3 pt-2 md:-mx-6"
        >
          <span v-if="missing.length" class="tt-help tt-help--error text-center">{{ t('plans.cantLock.hint') }}</span>
          <div class="flex gap-2">
            <TtButton size="lg" class="flex-1" :loading="saving && !locking" :disabled="locking" @click="saveDraft">{{ t('plans.saveDraft') }}</TtButton>
            <TtButton
              variant="primary"
              size="lg"
              icon="planLocked"
              class="flex-[1.5]"
              :class="{ 'tt-btn--disabled': missing.length > 0 }"
              :loading="locking"
              data-testid="plan-lock-btn"
              @click="lock"
            >
              {{ t('plans.lock', { done: checkedCount, total: checklistItems.length }) }}
            </TtButton>
          </div>
        </div>
      </template>
    </template>
  </PageContent>

  <RevisionDialog v-if="plan && revisable" v-model:open="revisionOpen" :plan="plan" :digits="digits" @saved="onRevised" />
  <StatusDialog v-if="plan" v-model:open="statusOpen" :plan-id="plan.id" :status="statusTarget" @changed="onStatusChanged" />
  <TtModal v-model:open="deleteOpen" :title="t('plans.status.deleteTitle')" :subtitle="t('plans.status.deleteBody')" size="sm">
    <template #footer>
      <TtButton class="flex-1" @click="deleteOpen = false">{{ t('plans.revisionSheet.cancel') }}</TtButton>
      <TtButton variant="danger" class="flex-1" :loading="deleting" @click="deletePlan">{{ t('plans.status.deleteConfirm') }}</TtButton>
    </template>
  </TtModal>
</template>
