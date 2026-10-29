<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import AppIcon from '@/components/AppIcon.vue'
import PageHeader from '@/components/shell/PageHeader.vue'
import PageContent from '@/components/shell/PageContent.vue'
import TtAlert from '@/components/ui/TtAlert.vue'
import TtButton from '@/components/ui/TtButton.vue'
import TtEmpty from '@/components/ui/TtEmpty.vue'
import TtSkeleton from '@/components/ui/TtSkeleton.vue'
import { todayApi, type Today } from '@/api/analysis'
import { useDesktop } from '@/composables/useDesktop'
import { formatLongDate, greetingKey } from '@/lib/format'
import { useAccountsStore } from '@/stores/accounts'
import { useInboxStore } from '@/stores/inbox'
import { useReferenceStore } from '@/stores/reference'
import { useSessionStore } from '@/stores/session'
import { useUiStore } from '@/stores/ui'
import AnalysisCard from './AnalysisCard.vue'
import AnalysisList from './AnalysisList.vue'
import DailyMoodCard from './DailyMoodCard.vue'
import NewsCard from './NewsCard.vue'
import PlanCards from './PlanCards.vue'
import PlansTable from './PlansTable.vue'
import TodayKpis from './TodayKpis.vue'
import TodoCard from './TodoCard.vue'
import { rankAnalyses, sortPlans, todayKpis } from './model'
import { sessionHint, splitMinutes } from './sessionHint'

// screens/web/03-WToday.png + screens/mobile/05-Today.png — F-05/F-06 of the day, F-02 AC3 account
// filter, F-11 AC5 daily mood. The news banner of the design waits for an economic calendar (Phase 6).
const { t } = useI18n()
const session = useSessionStore()
const ui = useUiStore()
const inbox = useInboxStore()
const accounts = useAccountsStore()
const reference = useReferenceStore()
const desktop = useDesktop()

// ------------------------------------------------------------------ header (greeting, date, session hint)

const now = ref(new Date())
let clock: ReturnType<typeof setInterval> | null = null
onMounted(() => (clock = setInterval(() => (now.value = new Date()), 30_000)))
onBeforeUnmount(() => clock && clearInterval(clock))

function duration(minutes: number) {
  const { h, m } = splitMinutes(minutes)
  return h && m ? t('today.duration.hm', { h, m }) : h ? t('today.duration.h', { h }) : t('today.duration.m', { m })
}
const hintText = computed(() => {
  const h = sessionHint(now.value)
  if (!h) return ''
  const name = t(`today.session.${h.session}`)
  return h.kind === 'open' ? t('today.sessionHint.open', { session: name }) : t('today.sessionHint.opensIn', { session: name, time: duration(h.minutes) })
})
const dateLine = computed(() => [formatLongDate(now.value, ui.locale), hintText.value].filter(Boolean).join(' · '))
const greeting = computed(() => t(greetingKey(now.value), { name: session.firstName }))

// ------------------------------------------------------------------ data

const today = shallowRef<Today | null>(null)
const loadError = ref(false)
const selectedAnalysis = ref<string | null>(null)
let seq = 0

async function load() {
  const mine = ++seq
  loadError.value = false
  try {
    const res = await todayApi.get({ ...accounts.accountParam })
    if (mine === seq) today.value = res
  } catch {
    if (mine === seq) loadError.value = true
  }
}

// F-02 AC3: the account switcher filters analyses, plans and limits.
watch(() => accounts.accountParam.account_id, load, { immediate: true })
onMounted(() => void reference.ensureLoaded().catch(() => undefined))

const analyses = computed(() => (today.value ? rankAnalyses(today.value.analyses, today.value.plans) : []))
const plans = computed(() => (today.value ? sortPlans(today.value.plans, analyses.value.map((a) => a.symbol_code)) : []))
const kpis = computed(() => (today.value ? todayKpis(today.value) : null))
/** "+ แผนใหม่" starts from the analysis on screen: the desktop card's, or the only one on mobile. */
const newPlanTo = computed(() => {
  const list = analyses.value
  const id = desktop.value ? (selectedAnalysis.value ?? list[0]?.id) : list.length === 1 ? list[0].id : null
  return id ? { path: '/plans/new', query: { analysis: id } } : '/plans/new'
})
watch(analyses, (list) => {
  if (!list.some((a) => a.id === selectedAnalysis.value)) selectedAnalysis.value = list[0]?.id ?? null
})
</script>

<template>
  <PageHeader :title="greeting" :overline="dateLine">
    <template #actions>
      <div class="relative hidden w-[260px] items-center xl:flex">
        <span class="pointer-events-none absolute left-3 text-ink-subtle"><AppIcon name="search" /></span>
        <input
          type="search"
          :aria-label="t('shell.search')"
          :placeholder="t('shell.searchPlaceholder')"
          class="h-11 w-full rounded-md border border-border-strong bg-surface pl-10 pr-3 text-body text-ink placeholder:text-ink-subtle"
        />
      </div>
      <RouterLink to="/alerts" class="tt-iconbtn hidden lg:inline-grid" :aria-label="t('shell.notifications')">
        <AppIcon name="alerts" />
        <i v-if="inbox.unreadAlerts > 0" class="tt-nav__dot !right-1.5 !top-1.5 !m-0" />
      </RouterLink>
      <RouterLink to="/trades/new" class="tt-btn tt-btn--secondary hidden md:inline-flex">
        <AppIcon name="add" />{{ t('shell.addTrade') }}
      </RouterLink>
      <RouterLink to="/plans/new" class="tt-btn tt-btn--primary hidden md:inline-flex">
        <AppIcon name="plan" />{{ t('shell.newPlan') }}
      </RouterLink>
    </template>
  </PageHeader>

  <PageContent>
    <TtAlert v-if="loadError" variant="loss" :title="t('today.loadError')">
      <template #action>
        <TtButton size="sm" @click="load">{{ t('today.retry') }}</TtButton>
      </template>
    </TtAlert>

    <template v-else-if="!today || !kpis">
      <TtSkeleton :lines="1" height="96px" />
      <div class="flex flex-wrap items-start gap-6">
        <div class="flex min-w-0 flex-[999_1_520px] flex-col gap-6">
          <div class="tt-card"><TtSkeleton :lines="4" height="24px" /></div>
          <div class="tt-card"><TtSkeleton :lines="3" height="24px" /></div>
        </div>
        <div class="hidden min-w-0 flex-[1_1_320px] flex-col gap-6 lg:flex">
          <div class="tt-card"><TtSkeleton :lines="2" height="24px" /></div>
          <div class="tt-card"><TtSkeleton :lines="2" height="24px" /></div>
        </div>
      </div>
    </template>

    <!-- ≥1024px: KPIs, then analysis + plans | to-do, mood, news (screens/web/03-WToday.png). -->
    <template v-else-if="desktop">
      <TodayKpis :kpis="kpis" />
      <div class="flex flex-wrap items-start gap-6">
        <div class="flex min-w-0 flex-[999_1_520px] flex-col gap-6">
          <AnalysisCard v-if="analyses.length" v-model:selected="selectedAnalysis" :analyses="analyses" :timezone="today.timezone" />
          <section v-else class="tt-card" data-testid="today-analysis-empty">
            <TtEmpty icon="analysis" :message="t('today.analysis.empty')">
              <TtButton variant="primary" icon="analysis" to="/analysis/new">{{ t('today.analysis.write') }}</TtButton>
            </TtEmpty>
          </section>

          <section class="tt-card tt-card--flush" data-testid="today-plans">
            <div class="tt-card__head !mb-0 px-5 pt-4">
              <h2 class="tt-card__title">{{ t('today.plans.title') }}</h2>
              <RouterLink :to="newPlanTo" class="tt-link text-body-sm">{{ t('today.plans.new') }}</RouterLink>
            </div>
            <div v-if="plans.length" class="mt-3"><PlansTable :plans="plans" /></div>
            <TtEmpty v-else icon="plan" :message="t('today.plans.empty')">
              <TtButton icon="plan" :to="newPlanTo">{{ t('today.plans.create') }}</TtButton>
            </TtEmpty>
          </section>
        </div>
        <aside class="flex min-w-0 flex-[1_1_320px] flex-col gap-6">
          <TodoCard :todo="today.todo" />
          <DailyMoodCard :date="today.date" :daily="today.daily" />
          <NewsCard />
        </aside>
      </div>
    </template>

    <!-- < 1024px (screens/mobile/05-Today.png): mood first, KPIs, to-do, analyses, plan cards, FAB. -->
    <template v-else>
      <DailyMoodCard :date="today.date" :daily="today.daily" compact />
      <TodayKpis :kpis="kpis" compact />
      <TodoCard :todo="today.todo" />

      <section class="flex flex-col gap-2.5">
        <div class="flex items-center justify-between gap-2">
          <h2 class="m-0 text-h3">{{ t('today.analysis.section') }}</h2>
          <RouterLink to="/analysis/new" class="tt-link text-body-sm">{{ t('today.analysis.add') }}</RouterLink>
        </div>
        <AnalysisList v-if="analyses.length" :analyses="analyses" />
        <div v-else class="tt-card" data-testid="today-analysis-empty">
          <TtEmpty icon="analysis" :message="t('today.analysis.empty')">
            <TtButton variant="primary" icon="analysis" to="/analysis/new">{{ t('today.analysis.write') }}</TtButton>
          </TtEmpty>
        </div>
      </section>

      <section class="flex flex-col gap-2.5" data-testid="today-plans">
        <div class="flex items-center justify-between gap-2">
          <h2 class="m-0 text-h3">{{ t('today.plans.section') }}</h2>
          <RouterLink :to="newPlanTo" class="tt-link text-body-sm">{{ t('today.plans.new') }}</RouterLink>
        </div>
        <PlanCards v-if="plans.length" :plans="plans" :timezone="today.timezone" />
        <div v-else class="tt-card"><TtEmpty icon="plan" :message="t('today.plans.empty')" /></div>
      </section>

      <!-- Room for the FAB above the bottom nav. -->
      <div class="h-14" aria-hidden="true" />
      <RouterLink
        :to="newPlanTo"
        class="tt-fab fixed bottom-[calc(80px+env(safe-area-inset-bottom))] right-4 z-30"
        :aria-label="t('today.fab')"
      >
        <AppIcon name="add" :size="24" />
      </RouterLink>
    </template>
  </PageContent>
</template>
