<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import PageContent from '@/components/shell/PageContent.vue'
import PageHeader from '@/components/shell/PageHeader.vue'
import TtAlert from '@/components/ui/TtAlert.vue'
import TtBadge from '@/components/ui/TtBadge.vue'
import TtButton from '@/components/ui/TtButton.vue'
import TtChip from '@/components/ui/TtChip.vue'
import TtEmpty from '@/components/ui/TtEmpty.vue'
import TtField from '@/components/ui/TtField.vue'
import TtMoodScale from '@/components/ui/TtMoodScale.vue'
import TtSegmented from '@/components/ui/TtSegmented.vue'
import TtSelect from '@/components/ui/TtSelect.vue'
import TtSkeleton from '@/components/ui/TtSkeleton.vue'
import TradeChart, { type ChartTool } from '@/components/chart/TradeChart.vue'
import ChartToolbar from '@/components/chart/ChartToolbar.vue'
import { useOhlc } from '@/components/chart/useOhlc'
import { BIASES, analysisApi, drawingsApi, type Analysis, type Drawing } from '@/api/analysis'
import { SESSIONS, type SessionName, type Timeframe } from '@/api/playbook'
import type { PlanBrief } from '@/api/plans'
import { useDesktop } from '@/composables/useDesktop'
import type { Locale } from '@/i18n'
import { intlLocale } from '@/lib/format'
import { useAccountsStore } from '@/stores/accounts'
import { useReferenceStore } from '@/stores/reference'
import { PLAN_STATUS_BADGE, directionBadge } from '@/features/plans/status'
import DateInput from './DateInput.vue'
import KeyLevelsCard from './KeyLevelsCard.vue'
import NarrativeEditor from './NarrativeEditor.vue'
import {
  ANALYSIS_TFS,
  errorKey,
  formToBody,
  isIsoDate,
  isNotFound,
  localToday,
  normalizeDoc,
  toDrawingInputs,
  toggleTimeframe,
  type AnalysisForm,
} from './model'

// screens/web/04-WAnalysis.png + screens/mobile/06-Analysis.png — F-05 AC1–AC2 (analysis + narrative + key levels),
// F-19 AC3–AC4 (chart drawings saved with the analysis).
// /analysis/new?symbol=XAUUSD&date=YYYY-MM-DD&account=<id> → first save creates it, then /analysis/:id autosaves.
const AUTOSAVE_MS = 1500

const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()
const desktop = useDesktop()
const refs = useReferenceStore()
const accounts = useAccountsStore()

const routeId = computed(() => (route.name === 'analysis' ? String(route.params.id) : null))

const status = ref<'loading' | 'ready' | 'notFound' | 'error'>('loading')
const analysis = ref<Analysis | null>(null)
const form = ref<AnalysisForm>(blankForm())
const drawings = ref<Drawing[]>([])
const saving = ref(false)
const savedAt = ref<Date | null>(null)
const saveError = ref<[string, Record<string, unknown>?] | null>(null)
const drawingsError = ref(false)

const chartTf = ref<Timeframe>('H1')
const tool = ref<ChartTool>('cursor')
const selectedDrawing = ref<string | null>(null)
const chart = ref<InstanceType<typeof TradeChart> | null>(null)

// ---------------------------------------------------------------- load

function blankForm(): AnalysisForm {
  return {
    account_id: null,
    symbol_id: '',
    analysis_date: localToday(),
    htf_bias: 'range',
    timeframes: [],
    session: null,
    confidence: 5,
    key_levels: [],
    narrative: { type: 'doc', content: [] },
  }
}

function newForm(): AnalysisForm {
  const q = route.query
  const code = typeof q.symbol === 'string' ? q.symbol.toUpperCase() : 'XAUUSD'
  const symbol = refs.symbolByCode.get(code) ?? refs.symbolByCode.get('XAUUSD') ?? refs.symbols[0]
  const account = typeof q.account === 'string' && accounts.active.some((a) => a.id === q.account) ? q.account : (accounts.selected?.id ?? null)
  return { ...blankForm(), symbol_id: symbol?.id ?? '', account_id: account, analysis_date: isIsoDate(q.date) ? q.date : localToday() }
}

function formOf(a: Analysis): AnalysisForm {
  return {
    account_id: a.account_id,
    symbol_id: a.symbol_id,
    analysis_date: a.analysis_date,
    htf_bias: a.htf_bias,
    timeframes: [...a.timeframes],
    session: a.session,
    confidence: a.confidence,
    key_levels: a.key_levels.map((l) => ({ ...l })),
    narrative: normalizeDoc(a.narrative),
  }
}

/** JSON of what the server has — autosave only sends real changes. */
let savedForm = ''
let savedDrawings = '[]'

async function load(id: string | null) {
  if (id && id === analysis.value?.id) return // we just created it and replaced the URL
  clearTimers()
  status.value = 'loading'
  saveError.value = null
  drawingsError.value = false
  selectedDrawing.value = null
  tool.value = 'cursor'
  try {
    await Promise.all([refs.ensureLoaded(), accounts.ensureLoaded()])
    if (!id) {
      analysis.value = null
      form.value = newForm()
      drawings.value = []
      savedForm = ''
      savedDrawings = '[]'
      savedAt.value = null
    } else {
      const [a, ds] = await Promise.all([analysisApi.get(id), drawingsApi.list('analysis', id)])
      if (id !== routeId.value) return
      analysis.value = a
      form.value = formOf(a)
      drawings.value = ds
      savedForm = JSON.stringify(formToBody(form.value))
      savedDrawings = JSON.stringify(toDrawingInputs(ds))
      savedAt.value = new Date(a.updated_at)
    }
    status.value = 'ready'
  } catch (e) {
    status.value = isNotFound(e) ? 'notFound' : 'error'
  }
}

// ---------------------------------------------------------------- save / autosave

let formTimer: ReturnType<typeof setTimeout> | undefined
let drawingsTimer: ReturnType<typeof setTimeout> | undefined
let inflight: Promise<void> | null = null
let drawingsInflight: Promise<void> | null = null

function clearTimers() {
  clearTimeout(formTimer)
  clearTimeout(drawingsTimer)
  formTimer = drawingsTimer = undefined
}

/** Create (first save) or patch the analysis. Serialized: a save during a save runs after it. */
function save(): Promise<void> {
  clearTimeout(formTimer)
  formTimer = undefined
  const run = async () => {
    const body = formToBody(form.value)
    const json = JSON.stringify(body)
    if (analysis.value && json === savedForm) return
    saving.value = true
    try {
      if (!analysis.value) {
        const created = await analysisApi.create(body)
        analysis.value = created
        savedForm = json
        void router.replace({ name: 'analysis', params: { id: created.id } })
        await saveDrawings()
      } else {
        analysis.value = await analysisApi.update(analysis.value.id, body)
        savedForm = json
      }
      savedAt.value = new Date()
      saveError.value = null
    } catch (e) {
      saveError.value = errorKey(e)
    } finally {
      saving.value = false
    }
  }
  inflight = (inflight ?? Promise.resolve()).then(run).finally(() => (inflight = null))
  return inflight
}

function saveDrawings(): Promise<void> {
  clearTimeout(drawingsTimer)
  drawingsTimer = undefined
  const run = async () => {
    const id = analysis.value?.id
    const inputs = toDrawingInputs(drawings.value)
    const json = JSON.stringify(inputs)
    if (!id || json === savedDrawings) return
    try {
      await drawingsApi.save('analysis', id, inputs)
      savedDrawings = json
      savedAt.value = new Date()
      drawingsError.value = false
    } catch {
      drawingsError.value = true
    }
  }
  drawingsInflight = (drawingsInflight ?? Promise.resolve()).then(run).finally(() => (drawingsInflight = null))
  return drawingsInflight
}

async function saveAll() {
  await save()
  if (analysis.value) await saveDrawings()
}

watch(
  form,
  () => {
    if (status.value !== 'ready' || !analysis.value) return
    clearTimeout(formTimer)
    formTimer = setTimeout(() => void save(), AUTOSAVE_MS)
  },
  { deep: true },
)
watch(
  drawings,
  () => {
    if (status.value !== 'ready' || !analysis.value) return
    clearTimeout(drawingsTimer)
    drawingsTimer = setTimeout(() => void saveDrawings(), AUTOSAVE_MS)
  },
  { deep: true },
)

/** Leaving with a pending autosave: flush it first (never blocks navigation). */
onBeforeRouteLeave(async (to) => {
  if (to.name === 'analysis' && to.params.id === analysis.value?.id) return
  if (analysis.value && (formTimer || drawingsTimer || inflight || drawingsInflight)) await saveAll().catch(() => undefined)
})
onBeforeUnmount(() => {
  if (analysis.value && (formTimer || drawingsTimer)) void saveAll()
  clearTimers()
})

watch(routeId, (id) => void load(id), { immediate: true })

async function createPlan() {
  await saveAll()
  if (analysis.value) void router.push({ name: 'plan-new', query: { analysis: analysis.value.id } })
}

// ---------------------------------------------------------------- view model

const symbol = computed(() => refs.symbolById.get(form.value.symbol_id) ?? null)
const symbolCode = computed(() => symbol.value?.code ?? analysis.value?.symbol_code ?? '')
const plans = computed<PlanBrief[]>(() => analysis.value?.plans ?? [])
const symbolLocked = computed(() => plans.value.length > 0)
// Plans pin the symbol (409 analysis_has_plans): offer only the current one instead of a greyed-out control.
const symbolOptions = computed(() =>
  refs.symbols.filter((s) => !symbolLocked.value || s.id === form.value.symbol_id).map((s) => ({ value: s.id, label: s.code })),
)

const ohlc = useOhlc(
  computed(() => (status.value === 'ready' ? form.value.symbol_id || null : null)),
  chartTf,
)
const digits = computed(() => ohlc.data.value?.digits ?? symbol.value?.digits ?? 2)
const sourceNote = computed(() => {
  const src = ohlc.data.value?.source
  if (!src) return ''
  return src === 'mock' ? t('chart.sourceMock') : t('chart.sourceBroker', { source: src === 'mt5' ? 'MT5' : 'cTrader' })
})
const chartLabel = computed(() => t('analysis.chart.label', { symbol: symbolCode.value, tf: chartTf.value }))

const accountOptions = computed(() => {
  const list = accounts.active.map((a) => ({ value: a.id, label: a.name }))
  const current = form.value.account_id
  if (current && !list.some((o) => o.value === current)) {
    const archived = accounts.accounts.find((a) => a.id === current)
    if (archived) list.push({ value: archived.id, label: archived.name })
  }
  return [{ value: '', label: t('analysis.noAccount') }, ...list]
})
const accountModel = computed({
  get: () => form.value.account_id ?? '',
  set: (v: string) => (form.value.account_id = v || null),
})

const biasOptions = computed(() => BIASES.map((b) => ({ value: b, label: t(`trading.bias.${b}`) })))
const confidenceModel = computed({
  get: () => form.value.confidence,
  set: (v: number | null) => {
    if (v) form.value.confidence = v
  },
})

function toggleSession(s: SessionName) {
  form.value.session = form.value.session === s ? null : s
}
function toggleTf(tf: Timeframe) {
  form.value.timeframes = toggleTimeframe(form.value.timeframes, tf)
}

const timeFmt = computed(() => new Intl.DateTimeFormat(intlLocale(locale.value as Locale), { hour: '2-digit', minute: '2-digit', hour12: false }))
const saveStatus = computed(() => {
  if (saving.value) return t('analysis.saving')
  if (savedAt.value) return t('analysis.autosaved', { time: timeFmt.value.format(savedAt.value) })
  return analysis.value ? '' : t('analysis.unsaved')
})
const title = computed(() => (desktop.value && symbolCode.value ? t('analysis.titleWithSymbol', { symbol: symbolCode.value }) : t('analysis.title')))

const planPrice = (p: PlanBrief) =>
  new Intl.NumberFormat('en-US', { minimumFractionDigits: digits.value, maximumFractionDigits: digits.value }).format(Number(p.entry_price))
const planOrder = (p: PlanBrief) => `${t(`trading.entryOrder.${p.direction}.${p.entry_type}`)} ${planPrice(p)}`

function deleteDrawing() {
  chart.value?.deleteSelected()
}
</script>

<template>
  <div class="flex min-h-full flex-col">
    <PageHeader :title="title" :crumb="{ to: { name: 'today' }, label: t('analysis.back') }">
      <template v-if="status === 'ready'" #actions>
        <span class="text-caption text-ink-muted" role="status" aria-live="polite">{{ saveStatus }}</span>
        <template v-if="desktop">
          <TtButton variant="secondary" :loading="saving" @click="saveAll">{{ t('analysis.save') }}</TtButton>
          <TtButton variant="primary" icon="plan" :disabled="!analysis" :title="analysis ? undefined : t('analysis.createPlanHint')" @click="createPlan">
            {{ t('analysis.createPlan') }}
          </TtButton>
        </template>
      </template>
    </PageHeader>

    <PageContent class="lg:!max-w-none">
      <!-- ================= loading / not found / error ================= -->
      <div v-if="status === 'loading'" class="flex flex-col gap-6 lg:grid lg:grid-cols-[minmax(0,1fr)_320px]" aria-busy="true" :aria-label="t('analysis.loading')">
        <div class="flex flex-col gap-6">
          <div class="tt-card"><TtSkeleton :lines="1" height="36px" /><div class="mt-3"><TtSkeleton :lines="1" :height="desktop ? '520px' : '260px'" /></div></div>
          <div class="tt-card"><TtSkeleton :lines="4" /></div>
        </div>
        <div class="flex flex-col gap-6">
          <div class="tt-card"><TtSkeleton :lines="5" height="32px" /></div>
          <div class="tt-card"><TtSkeleton :lines="3" height="40px" /></div>
        </div>
      </div>

      <section v-else-if="status === 'notFound'" class="tt-card">
        <TtEmpty icon="analysis" :message="t('analysis.notFound')">
          <TtButton variant="primary" icon="back" :to="{ name: 'today' }">{{ t('analysis.backToday') }}</TtButton>
        </TtEmpty>
      </section>

      <TtAlert v-else-if="status === 'error'" variant="loss" :title="t('analysis.errors.load')">
        <template #action>
          <TtButton size="sm" variant="secondary" @click="load(routeId)">{{ t('analysis.retry') }}</TtButton>
        </template>
      </TtAlert>

      <template v-else>
        <TtAlert v-if="saveError" variant="loss" :title="t('analysis.errors.save')" :body="t(saveError[0], saveError[1] ?? {})" dismissible @dismiss="saveError = null">
          <template #action>
            <TtButton size="sm" variant="secondary" @click="saveAll">{{ t('analysis.retry') }}</TtButton>
          </template>
        </TtAlert>
        <TtAlert v-if="drawingsError" variant="loss" :title="t('analysis.errors.drawings')" dismissible @dismiss="drawingsError = false">
          <template #action>
            <TtButton size="sm" variant="secondary" @click="saveDrawings">{{ t('analysis.retry') }}</TtButton>
          </template>
        </TtAlert>

        <!-- ================= Desktop ================= -->
        <div v-if="desktop" class="grid grid-cols-[minmax(0,1fr)_320px] items-start gap-6">
          <div class="flex min-w-0 flex-col gap-6">
            <section class="overflow-hidden rounded-lg border border-border bg-surface" :aria-label="chartLabel">
              <div class="flex flex-wrap items-center gap-1.5 border-b border-border px-3 py-2.5">
                <TtSelect
                  v-model="form.symbol_id"
                  class="!h-9 !w-[140px]"
                  :options="symbolOptions"
                  :aria-label="t('analysis.symbol')"
                  :title="symbolLocked ? t('analysis.symbolLocked') : undefined"
                />
                <div class="flex gap-1.5" role="group" :aria-label="t('analysis.chart.timeframe')">
                  <TtChip v-for="tf in ANALYSIS_TFS" :key="tf" size="sm" :selected="chartTf === tf" @click="chartTf = tf">{{ tf }}</TtChip>
                </div>
                <span class="flex-1" />
                <span class="text-caption text-ink-muted">{{ sourceNote }}</span>
              </div>
              <div class="flex">
                <div class="flex-none border-r border-border p-2">
                  <ChartToolbar v-model="tool" vertical bare :can-delete="!!selectedDrawing" @delete="deleteDrawing" />
                </div>
                <div class="min-w-0 flex-1 p-2">
                  <TradeChart
                    v-if="ohlc.data.value"
                    ref="chart"
                    v-model:drawings="drawings"
                    v-model:tool="tool"
                    :bars="ohlc.data.value.bars"
                    :digits="digits"
                    :timeframe="chartTf"
                    :label="chartLabel"
                    :key-levels="form.key_levels"
                    editable
                    height="560px"
                    @select="selectedDrawing = $event"
                  />
                  <div v-else-if="ohlc.error.value" class="grid h-[560px] place-items-center">
                    <div class="flex flex-col items-center gap-3">
                      <span class="text-body-sm text-ink-muted">{{ t('chart.loadError') }}</span>
                      <TtButton size="sm" @click="ohlc.reload">{{ t('chart.retry') }}</TtButton>
                    </div>
                  </div>
                  <TtSkeleton v-else :lines="1" height="560px" />
                </div>
              </div>
            </section>

            <section class="tt-card">
              <NarrativeEditor v-model="form.narrative" layout="card" />
            </section>
          </div>

          <aside class="flex min-w-0 flex-col gap-6">
            <section class="tt-card tt-stack">
              <div class="grid grid-cols-2 gap-3">
                <TtField :label="t('analysis.date')" id="an-date">
                  <DateInput id="an-date" v-model="form.analysis_date" />
                </TtField>
                <TtField :label="t('analysis.account')">
                  <TtSelect v-model="accountModel" :options="accountOptions" />
                </TtField>
              </div>
              <div class="tt-field">
                <span class="tt-label" aria-hidden="true">{{ t('analysis.bias') }}</span>
                <TtSegmented v-model="form.htf_bias" :class="`bias-${form.htf_bias}`" :options="biasOptions" :label="t('analysis.bias')" block />
              </div>
              <div class="tt-field">
                <span id="an-tfs" class="tt-label">{{ t('analysis.timeframes') }}</span>
                <div class="tt-row" role="group" aria-labelledby="an-tfs">
                  <TtChip v-for="tf in ANALYSIS_TFS" :key="tf" :selected="form.timeframes.includes(tf)" @click="toggleTf(tf)">{{ tf }}</TtChip>
                </div>
              </div>
              <div class="tt-field">
                <span id="an-session" class="tt-label">{{ t('analysis.session') }}</span>
                <div class="tt-row" role="group" aria-labelledby="an-session">
                  <TtChip v-for="s in SESSIONS" :key="s" :selected="form.session === s" :dot="form.session === s" @click="toggleSession(s)">
                    {{ t(`trading.session.${s}`) }}
                  </TtChip>
                </div>
              </div>
              <TtMoodScale v-model="confidenceModel" :label="t('analysis.confidence')" :clearable="false" />
            </section>

            <KeyLevelsCard v-model="form.key_levels" :digits="digits" layout="card" />

            <section class="tt-card tt-stack" aria-labelledby="an-plans">
              <div class="flex items-center justify-between gap-3">
                <h2 id="an-plans" class="m-0 text-h3">{{ t('analysis.plans.title') }}</h2>
                <TtBadge>{{ plans.length }}</TtBadge>
              </div>
              <ul v-if="plans.length" class="m-0 list-none p-0">
                <li v-for="p in plans" :key="p.id" class="border-b border-border last:border-b-0">
                  <RouterLink
                    :to="{ name: 'plan', params: { id: p.id } }"
                    class="flex items-center gap-3 py-2 text-ink no-underline hover:text-brand-700"
                    :aria-label="t('analysis.plans.open', { label: p.scenario_label, direction: t(`trading.direction.${p.direction}`), order: planOrder(p) })"
                  >
                    <TtBadge :variant="directionBadge(p.direction)">{{ p.scenario_label }}</TtBadge>
                    <span class="tt-num min-w-0 flex-1 truncate text-sm font-semibold">{{ planOrder(p) }}</span>
                    <TtBadge :variant="PLAN_STATUS_BADGE[p.status]">{{ t(`trading.planStatus.${p.status}`) }}</TtBadge>
                  </RouterLink>
                </li>
              </ul>
              <p v-else class="m-0 text-body-sm text-ink-muted">{{ analysis ? t('analysis.plans.empty') : t('analysis.createPlanHint') }}</p>
            </section>
          </aside>
        </div>

        <!-- ================= Mobile ================= -->
        <template v-else>
          <div class="grid grid-cols-2 gap-3">
            <TtField :label="t('analysis.symbol')">
              <TtSelect v-model="form.symbol_id" :options="symbolOptions" :title="symbolLocked ? t('analysis.symbolLocked') : undefined" />
            </TtField>
            <TtField :label="t('analysis.date')" id="an-date-m">
              <DateInput id="an-date-m" v-model="form.analysis_date" />
            </TtField>
          </div>

          <section class="overflow-hidden rounded-lg border border-border bg-surface" :aria-label="chartLabel">
            <div class="flex flex-wrap items-center gap-1.5 border-b border-border px-2.5 py-2" role="group" :aria-label="t('analysis.chart.timeframe')">
              <TtChip v-for="tf in ANALYSIS_TFS" :key="tf" size="sm" :selected="chartTf === tf" @click="chartTf = tf">{{ tf }}</TtChip>
            </div>
            <div class="border-b border-border px-1 py-1">
              <ChartToolbar v-model="tool" bare :can-delete="!!selectedDrawing" @delete="deleteDrawing" />
            </div>
            <TradeChart
              v-if="ohlc.data.value"
              ref="chart"
              v-model:drawings="drawings"
              v-model:tool="tool"
              :bars="ohlc.data.value.bars"
              :digits="digits"
              :timeframe="chartTf"
              :label="chartLabel"
              :key-levels="form.key_levels"
              editable
              height="260px"
              @select="selectedDrawing = $event"
            />
            <div v-else-if="ohlc.error.value" class="grid h-[260px] place-items-center">
              <TtButton size="sm" @click="ohlc.reload">{{ t('chart.retry') }}</TtButton>
            </div>
            <div v-else class="p-2"><TtSkeleton :lines="1" height="244px" /></div>
            <p v-if="sourceNote" class="m-0 border-t border-border px-3 py-2 text-caption text-ink-muted">{{ sourceNote }}</p>
          </section>

          <div class="tt-field">
            <span class="tt-label" aria-hidden="true">{{ t('analysis.bias') }}</span>
            <TtSegmented v-model="form.htf_bias" :class="`bias-${form.htf_bias}`" :options="biasOptions" :label="t('analysis.bias')" block />
          </div>

          <KeyLevelsCard v-model="form.key_levels" :digits="digits" layout="field" />

          <div class="tt-field">
            <span id="an-tfs-m" class="tt-label">{{ t('analysis.timeframesUsed') }}</span>
            <div class="tt-row" role="group" aria-labelledby="an-tfs-m">
              <TtChip v-for="tf in ANALYSIS_TFS" :key="tf" :selected="form.timeframes.includes(tf)" @click="toggleTf(tf)">{{ tf }}</TtChip>
            </div>
          </div>
          <div class="tt-field">
            <span id="an-session-m" class="tt-label">{{ t('analysis.session') }}</span>
            <div class="tt-row" role="group" aria-labelledby="an-session-m">
              <TtChip v-for="s in SESSIONS" :key="s" :selected="form.session === s" :dot="form.session === s" @click="toggleSession(s)">
                {{ t(`trading.session.${s}`) }}
              </TtChip>
            </div>
          </div>

          <NarrativeEditor v-model="form.narrative" layout="field" />

          <TtMoodScale v-model="confidenceModel" :label="t('analysis.confidence')" :clearable="false" />

          <TtField :label="t('analysis.account')">
            <TtSelect v-model="accountModel" :options="accountOptions" />
          </TtField>

          <section v-if="analysis" class="flex flex-col gap-2" aria-labelledby="an-plans-m">
            <span id="an-plans-m" class="tt-label">{{ t('analysis.plans.title') }}</span>
            <ul v-if="plans.length" class="tt-list">
              <li v-for="p in plans" :key="p.id">
                <RouterLink
                  :to="{ name: 'plan', params: { id: p.id } }"
                  class="tt-list__row"
                  :aria-label="t('analysis.plans.open', { label: p.scenario_label, direction: t(`trading.direction.${p.direction}`), order: planOrder(p) })"
                >
                  <TtBadge :variant="directionBadge(p.direction)">{{ p.scenario_label }}</TtBadge>
                  <span class="tt-num min-w-0 flex-1 truncate text-sm font-semibold">{{ planOrder(p) }}</span>
                  <TtBadge :variant="PLAN_STATUS_BADGE[p.status]">{{ t(`trading.planStatus.${p.status}`) }}</TtBadge>
                </RouterLink>
              </li>
            </ul>
            <p v-else class="m-0 text-body-sm text-ink-muted">{{ t('analysis.plans.empty') }}</p>
          </section>
        </template>
      </template>
    </PageContent>

    <!-- Mobile action bar (06-Analysis.png .scr__foot), above the bottom nav. -->
    <div
      v-if="!desktop && status === 'ready'"
      class="sticky bottom-[calc(64px+env(safe-area-inset-bottom))] z-20 mt-auto flex gap-3 border-t border-border bg-surface px-4 py-3"
    >
      <TtButton class="flex-1" variant="secondary" size="lg" :loading="saving" @click="saveAll">{{ t('analysis.save') }}</TtButton>
      <TtButton class="flex-[1.4]" variant="primary" size="lg" icon="plan" :disabled="!analysis" @click="createPlan">{{ t('analysis.createPlanShort') }}</TtButton>
    </div>
  </div>
</template>

<style scoped>
/* HTF bias: the chosen side reads in its meaning colour (WAnalysis.dc.html: Bull = profit-ink). */
.bias-bull :deep(.tt-seg__item--on) { color: var(--profit-ink); }
.bias-bear :deep(.tt-seg__item--on) { color: var(--loss-ink); }
</style>
