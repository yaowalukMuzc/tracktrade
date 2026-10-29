<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { watchDebounced } from '@vueuse/core'
import AppIcon from '@/components/AppIcon.vue'
import PageContent from '@/components/shell/PageContent.vue'
import PageHeader from '@/components/shell/PageHeader.vue'
import TtAlert from '@/components/ui/TtAlert.vue'
import TtButton from '@/components/ui/TtButton.vue'
import TtEmpty from '@/components/ui/TtEmpty.vue'
import TtIconButton from '@/components/ui/TtIconButton.vue'
import TtSegmented from '@/components/ui/TtSegmented.vue'
import TtSkeleton from '@/components/ui/TtSkeleton.vue'
import TtTabs from '@/components/ui/TtTabs.vue'
import { playbookApi, type SetupSummary } from '@/api/playbook'
import { TRADE_TABS, positionsApi, type PositionSummary, type TabCounts, type TradeTab } from '@/api/positions'
import { realtime } from '@/api/ws'
import { useDesktop } from '@/composables/useDesktop'
import type { Locale } from '@/i18n'
import { formatMoney, formatR } from '@/lib/format'
import { useAccountsStore } from '@/stores/accounts'
import { useInboxStore } from '@/stores/inbox'
import { useReferenceStore } from '@/stores/reference'
import { useSessionStore } from '@/stores/session'
import MatchDialog from './MatchDialog.vue'
import TradeCard from './TradeCard.vue'
import TradeFilters from './TradeFilters.vue'
import TradesTable from './TradesTable.vue'
import {
  dayLabelKind,
  dayMonth,
  groupByDay,
  loadPnlMode,
  queryToState,
  savePnlMode,
  stateToQuery,
  toFilters,
  type PnlMode,
  type TradeQuery,
} from './model'

// /trades — screens/web/06-WTrades.png (table + match modal), screens/mobile/09-Trades.png (cards by day).
// F-07 (list of positions), F-10 AC2–AC3 (match queue). Filters live in the URL; the account is the global switcher.
const PAGE = 20
const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()
const desktop = useDesktop()
const accounts = useAccountsStore()
const reference = useReferenceStore()
const session = useSessionStore()
const inbox = useInboxStore()

const tz = computed(() => session.user?.timezone ?? Intl.DateTimeFormat().resolvedOptions().timeZone)
const l = computed(() => locale.value as Locale)
const state = computed<TradeQuery>(() => queryToState(route.query))
const accountId = computed(() => accounts.selected?.id)

const items = ref<PositionSummary[]>([])
const total = ref(0)
const counts = ref<TabCounts | null>(null)
const load = ref<'loading' | 'ready' | 'error'>('loading')
const loadingMore = ref(false)
const setups = ref<SetupSummary[]>([])
const search = ref(state.value.q)
const searchOpen = ref(!!state.value.q)
const exportError = ref(false)
const mode = ref<PnlMode>(loadPnlMode(session.user?.id))
watch(mode, (m) => savePnlMode(session.user?.id, m))

const anyFilter = computed(() => !!(state.value.q || state.value.from || state.value.to || state.value.symbol_id || state.value.setup_id))

function update(patch: Partial<TradeQuery>, resetPage = true) {
  const next = { ...state.value, ...patch, ...(resetPage ? { page: 1 } : {}) }
  void router.replace({ query: stateToQuery(next, route.query) })
}

let request = 0
async function fetchPage(append = false) {
  const id = ++request
  const page = append ? Math.floor(items.value.length / PAGE) + 1 : desktop.value ? state.value.page : 1
  if (append) loadingMore.value = true
  else load.value = 'loading'
  try {
    const res = await positionsApi.list(toFilters(state.value, accountId.value), (page - 1) * PAGE, PAGE)
    if (id !== request) return
    items.value = append ? [...items.value, ...res.items] : res.items
    total.value = res.total
    counts.value = res.counts
    load.value = 'ready'
  } catch {
    if (id === request && !append) load.value = 'error'
  } finally {
    loadingMore.value = false
  }
}

watch([() => route.query, accountId, desktop], () => {
  if (route.name === 'trades') void fetchPage()
})
watchDebounced(search, (q) => update({ q }), { debounce: 350 })

// ------------------------------------------------------------------ match dialog (desktop) / page (mobile)
const matchOpen = ref(false)
const matchStart = ref<string | null>(null)

function openMatch(positionId: string | null) {
  if (!desktop.value) {
    void router.push({ name: 'trade-match', query: positionId ? { id: positionId } : {} })
    return
  }
  matchStart.value = positionId
  matchOpen.value = true
}
// `/trades?match=<id>` (from Add trade, Today, notifications) opens the picker for that trade.
watch(
  () => route.query.match,
  (m) => {
    if (typeof m !== 'string' || !m) return
    const rest = { ...route.query }
    delete rest.match
    void router.replace({ query: rest })
    openMatch(m === '1' ? null : m)
  },
  { immediate: true },
)
function onMatched() {
  void fetchPage()
  void inbox.refreshTrades()
}

// ------------------------------------------------------------------ realtime
let refetchTimer: ReturnType<typeof setTimeout> | undefined
const stopRealtime = realtime.on((msg) => {
  if (!msg.type.startsWith('position.') && msg.type !== 'match.pending') return
  clearTimeout(refetchTimer)
  refetchTimer = setTimeout(() => fetchPage(), 400)
})
onBeforeUnmount(() => {
  stopRealtime()
  clearTimeout(refetchTimer)
})

onMounted(async () => {
  void fetchPage()
  try {
    await reference.ensureLoaded()
    setups.value = (await playbookApi.list()).items
  } catch {
    /* filters fall back to "all"; the list still works */
  }
})

// ------------------------------------------------------------------ view helpers
const tabItems = computed(() =>
  TRADE_TABS.map((v) => ({ value: v, label: t(`trades.tabs.${v}`), count: counts.value?.[v] })),
)
const tab = computed<TradeTab>({ get: () => state.value.tab, set: (v) => update({ tab: v }) })
const groups = computed(() => groupByDay(items.value, tz.value))
const pendingCount = computed(() => counts.value?.pending ?? 0)
const page = computed(() => state.value.page)
const lastPage = computed(() => Math.max(1, Math.ceil(total.value / PAGE)))
const range = computed(() => ({
  from: total.value ? (page.value - 1) * PAGE + 1 : 0,
  to: Math.min(page.value * PAGE, total.value),
  total: total.value,
}))
const emptyMessage = computed(() => (anyFilter.value || state.value.tab !== 'all' ? t('trades.empty.filtered') : t('trades.empty.none')))

function dayHeading(day: string, iso: string) {
  const kind = dayLabelKind(day, tz.value)
  return t(`trades.day.${kind}`, { date: dayMonth(iso, tz.value, l.value) })
}
function dayTotal(totals: { currency: string; money: number; r: number }[]) {
  return totals.map((x) => `${formatMoney(x.money, x.currency)} · ${formatR(x.r)}`).join('  ')
}
const totalClass = (totals: { money: number }[]) => {
  const sum = totals.reduce((s, x) => s + x.money, 0)
  return sum > 0 ? 'tt-pnl--up' : sum < 0 ? 'tt-pnl--down' : 'tt-pnl--flat'
}

async function exportCsv() {
  exportError.value = false
  try {
    await positionsApi.exportCsv({ ...toFilters(state.value, accountId.value) })
  } catch {
    exportError.value = true
  }
}
const pnlOptions = computed(() => [
  { value: 'money' as PnlMode, label: t('trades.pnlMode.money') },
  { value: 'r' as PnlMode, label: t('trades.pnlMode.r') },
])
</script>

<template>
  <div>
    <PageHeader :title="t('pages.trades')">
      <template #actions>
        <template v-if="desktop">
          <div class="relative flex w-[240px] items-center">
            <span class="pointer-events-none absolute left-3 text-ink-subtle"><AppIcon name="search" /></span>
            <input
              v-model="search"
              type="search"
              :aria-label="t('trades.search.label')"
              :placeholder="t('trades.search.placeholder')"
              class="h-11 w-full rounded-md border border-border-strong bg-surface pl-10 pr-3 text-body text-ink placeholder:text-ink-subtle"
              data-testid="trades-search"
            />
          </div>
          <TtButton icon="download" @click="exportCsv">{{ t('trades.export') }}</TtButton>
          <TtButton variant="primary" icon="add" to="/trades/new?mode=manual">{{ t('trades.add') }}</TtButton>
        </template>
        <template v-else>
          <TtIconButton icon="search" :label="t('trades.search.label')" :active="searchOpen" @click="searchOpen = !searchOpen" />
        </template>
      </template>
    </PageHeader>

    <PageContent>
      <input
        v-if="!desktop && searchOpen"
        v-model="search"
        type="search"
        class="tt-input"
        :aria-label="t('trades.search.label')"
        :placeholder="t('trades.search.placeholder')"
      />

      <TtTabs v-model="tab" :items="tabItems" :label="t('trades.tabs.label')" />

      <div class="flex items-center gap-3">
        <div class="min-w-0 flex-1">
          <TradeFilters :state="state" :symbols="reference.symbols" :setups="setups" :tz="tz" @change="update" />
        </div>
        <TtSegmented v-if="desktop" v-model="mode" :options="pnlOptions" :label="t('trades.pnlMode.label')" />
      </div>

      <TtAlert v-if="exportError" variant="loss" :title="t('trades.exportFailed')" dismissible @dismiss="exportError = false" />

      <template v-if="pendingCount > 0 && tab !== 'pending'">
        <TtAlert v-if="desktop" variant="warning" icon="link" :title="t('trades.pending.title', { n: pendingCount })" :body="t('trades.pending.body')" data-testid="pending-alert">
          <template #action>
            <TtButton size="sm" @click="openMatch(null)">{{ t('trades.pending.action') }}</TtButton>
          </template>
        </TtAlert>
        <RouterLink v-else :to="{ name: 'trade-match' }" class="no-underline" data-testid="pending-alert">
          <TtAlert variant="warning" icon="link" :title="t('trades.pending.title', { n: pendingCount })" :body="t('trades.pending.bodyShort')">
            <template #action><AppIcon name="forward" /></template>
          </TtAlert>
        </RouterLink>
      </template>

      <!-- Loading / error / empty -->
      <div v-if="load === 'loading' && !items.length" class="tt-card">
        <TtSkeleton :lines="6" height="40px" />
      </div>
      <TtAlert v-else-if="load === 'error'" variant="loss" :title="t('trades.error.load')">
        <template #action>
          <TtButton size="sm" @click="fetchPage()">{{ t('trades.error.retry') }}</TtButton>
        </template>
      </TtAlert>
      <div v-else-if="!items.length && !desktop" class="tt-card">
        <TtEmpty icon="trades" :message="emptyMessage">
          <TtButton v-if="anyFilter" @click="update({ q: '', from: null, to: null, symbol_id: null, setup_id: null })">
            {{ t('trades.filters.clear') }}
          </TtButton>
          <TtButton v-else variant="primary" icon="add" to="/trades/new?mode=manual">{{ t('trades.add') }}</TtButton>
        </TtEmpty>
      </div>

      <!-- Desktop: table -->
      <div v-else-if="desktop" class="tt-card overflow-hidden !p-0" :aria-busy="load === 'loading'">
        <TradesTable :trades="items" :mode="mode" :tz="tz" :empty="emptyMessage" />
        <div class="flex items-center justify-between border-t border-border px-4 py-3">
          <span class="text-caption text-ink-muted">{{ t('trades.paging.range', range) }}</span>
          <div class="tt-row">
            <TtIconButton icon="back" :label="t('trades.paging.prev')" :disabled="page <= 1" @click="update({ page: page - 1 }, false)" />
            <TtIconButton icon="forward" :label="t('trades.paging.next')" :disabled="page >= lastPage" @click="update({ page: page + 1 }, false)" />
          </div>
        </div>
      </div>

      <!-- Mobile: cards grouped by day -->
      <template v-else>
        <section v-for="g in groups" :key="g.day" class="flex flex-col gap-3">
          <div class="flex items-center justify-between">
            <span class="text-overline uppercase text-ink-muted">{{ dayHeading(g.day, g.items[0].opened_at) }}</span>
            <span v-if="g.totals.length" class="tt-pnl text-num-sm" :class="totalClass(g.totals)">{{ dayTotal(g.totals) }}</span>
          </div>
          <TradeCard v-for="p in g.items" :key="p.id" :trade="p" :mode="mode" :tz="tz" />
        </section>
        <TtButton v-if="items.length < total" block :loading="loadingMore" @click="fetchPage(true)">{{ t('trades.paging.more') }}</TtButton>
      </template>
    </PageContent>

    <RouterLink v-if="!desktop" to="/trades/new?mode=manual" class="tt-fab fixed bottom-[calc(80px+env(safe-area-inset-bottom))] right-4 z-20" :aria-label="t('trades.add')">
      <AppIcon name="add" :size="24" />
    </RouterLink>

    <MatchDialog v-if="desktop" v-model:open="matchOpen" :start-id="matchStart" :account-id="accountId" :tz="tz" @matched="onMatched" />
  </div>
</template>
