<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppIcon from '@/components/AppIcon.vue'
import PageContent from '@/components/shell/PageContent.vue'
import PageHeader from '@/components/shell/PageHeader.vue'
import TtAlert from '@/components/ui/TtAlert.vue'
import TtBadge from '@/components/ui/TtBadge.vue'
import TtButton from '@/components/ui/TtButton.vue'
import TtCheckbox from '@/components/ui/TtCheckbox.vue'
import TtEmpty from '@/components/ui/TtEmpty.vue'
import TtModal from '@/components/ui/TtModal.vue'
import TtSkeleton from '@/components/ui/TtSkeleton.vue'
import TtTabs from '@/components/ui/TtTabs.vue'
import {
  accountsApi,
  type Account,
  type AccountInput,
  type AuditEntry,
  type RiskProfile,
  type RiskProfileInput,
  type RiskStatus,
  type Rule,
  type RuleCode,
  type RuleParams,
  type Severity,
  type SymbolOverride,
  type SymbolSpec,
} from '@/api/accounts'
import { useDesktop } from '@/composables/useDesktop'
import { formatAmount, formatNumber, intlLocale } from '@/lib/format'
import type { Locale } from '@/i18n'
import { useAccountsStore } from '@/stores/accounts'
import AccountFormDialog from './AccountFormDialog.vue'
import AuditLogCard from './AuditLogCard.vue'
import type { Connection, IngestionJob } from '@/api/connections'
import ConnectionCard from './ConnectionCard.vue'
import IngestionHistory from './IngestionHistory.vue'
import { connectionBadge } from './model'
import RiskProfileCard from './RiskProfileCard.vue'
import RulesCard from './RulesCard.vue'
import SymbolMappingCard from './SymbolMappingCard.vue'
import TodayCard from './TodayCard.vue'
import { useConnections, useNow } from './useConnections'

// screens/web/14-WAccounts.png + screens/mobile/23-Accounts.png — F-02 (accounts, risk profile, audit), F-03 AC2 (symbol mapping).
// URL keeps the selection: /accounts?account=<id>&tab=risk|rules|symbols|connections|audit
type Tab = 'risk' | 'rules' | 'symbols' | 'connections' | 'audit'
const TABS: Tab[] = ['risk', 'rules', 'symbols', 'connections', 'audit']

const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()
const store = useAccountsStore()
const desktop = useDesktop()

const loadError = ref(false)
const showArchived = ref(false)
const statuses = ref<Record<string, RiskStatus>>({})
const profile = ref<RiskProfile | null>(null)
const rules = ref<Rule[] | null>(null)
const overrides = ref<SymbolOverride[] | null>(null)
const audit = ref<AuditEntry[] | null>(null)
const symbols = ref<SymbolSpec[]>([])

const formOpen = ref(false)
const editing = ref<Account | null>(null)
const menuFor = ref<string | null>(null)
const confirmArchive = ref<Account | null>(null)
const archiving = ref(false)
const rulesCard = ref<InstanceType<typeof RulesCard>>()
const symbolsCard = ref<InstanceType<typeof SymbolMappingCard>>()

const listed = computed(() => (showArchived.value ? store.accounts : store.active))
const selectedId = computed(() => {
  const q = route.query.account
  if (typeof q === 'string' && store.accounts.some((a) => a.id === q)) return q
  return store.selected?.id ?? store.active[0]?.id ?? store.accounts[0]?.id ?? null
})
const selected = computed(() => store.accounts.find((a) => a.id === selectedId.value) ?? null)
const tab = computed<Tab>({
  get: () => (TABS.includes(route.query.tab as Tab) ? (route.query.tab as Tab) : 'risk'),
  set: (v) => void router.replace({ query: { ...route.query, tab: v } }),
})
const tabItems = computed(() =>
  TABS.map((v) => ({
    value: v,
    label: v === 'risk' ? t('accounts.tabs.risk', { name: selected.value?.name ?? '' }) : t(`accounts.tabs.${v}`),
    count: v === 'rules' && rules.value?.length ? rules.value.length : undefined,
  })),
)
// Running balance from the risk status (broker-reported or initial + closed P/L), initial balance until it loads.
const balance = computed(() => Number((selected.value && statuses.value[selected.value.id]?.balance) ?? selected.value?.initial_balance ?? 0))
const editedAt = computed(() =>
  profile.value ? new Intl.DateTimeFormat(intlLocale(locale.value as Locale), { day: 'numeric', month: 'short' }).format(new Date(profile.value.updated_at)) : '',
)

function select(id: string) {
  menuFor.value = null
  void router.replace({ query: { ...route.query, account: id } })
}

async function loadAll() {
  loadError.value = false
  try {
    await store.load()
    if (!symbols.value.length) symbols.value = await accountsApi.symbols()
    await loadStatuses()
  } catch {
    loadError.value = true
  }
}

async function loadStatuses() {
  const entries = await Promise.all(store.accounts.map(async (a) => [a.id, await accountsApi.riskStatus(a.id)] as const))
  statuses.value = Object.fromEntries(entries)
}

async function loadSelected(id: string | null) {
  profile.value = null
  rules.value = null
  overrides.value = null
  audit.value = null
  if (!id) return
  const [p, r, o, a] = await Promise.all([accountsApi.riskProfile(id), accountsApi.rules(id), accountsApi.overrides(id), accountsApi.auditLog(id)])
  if (id !== selectedId.value) return // selection changed meanwhile
  profile.value = p
  rules.value = r
  overrides.value = o
  audit.value = a
}

const refreshAudit = async () => {
  if (selectedId.value) audit.value = await accountsApi.auditLog(selectedId.value)
}

// ---------------------------------------------------------------- broker connections (F-08)

const now = useNow()
const linkedIds = computed(() => store.accounts.filter((a) => a.platform !== 'manual').map((a) => a.id))
const conns = useConnections(linkedIds, { jobs: true })
function connOf(a: Account): Connection | null {
  const kind = a.platform === 'mt5' ? 'mt5_ea' : 'ctrader_oauth'
  return (conns.connections.value[a.id] ?? []).find((c) => c.kind === kind) ?? null
}
const connBadge = (a: Account) => connectionBadge(a.platform, connOf(a) ?? undefined, now.value, locale.value)
const selectedJobs = computed<IngestionJob[] | null>(() => (selected.value && conns.loaded.value ? (conns.jobs.value[selected.value.id] ?? []) : null))
const selectedHistoryDays = () => (selected.value ? (connOf(selected.value)?.stats.history_days ?? null) : null)
async function onConnectionChanged(c: Connection) {
  conns.replace(c)
  await Promise.all([conns.load(), refreshAudit()])
}

/** Back from cTrader's consent page: `?ctrader=connected|error&reason=` → a message, then a clean URL. */
const ctraderReturn = ref<{ ok: boolean; reason: string } | null>(null)
onMounted(() => {
  const q = route.query
  if (q.ctrader !== 'connected' && q.ctrader !== 'error') return
  ctraderReturn.value = { ok: q.ctrader === 'connected', reason: typeof q.reason === 'string' ? q.reason : '' }
  const rest = { ...q }
  delete rest.ctrader
  delete rest.reason
  void router.replace({ query: rest })
})

onMounted(loadAll)
watch(selectedId, (id) => void loadSelected(id).catch(() => (loadError.value = true)), { immediate: true })

// ---------------------------------------------------------------- actions

async function submitAccount(body: AccountInput) {
  if (editing.value) {
    store.upsert(await accountsApi.update(editing.value.id, body))
  } else {
    const created = await store.create(body)
    select(created.id)
  }
  await Promise.all([loadStatuses(), refreshAudit()])
}

function openCreate() {
  editing.value = null
  formOpen.value = true
}
function openEdit(a: Account) {
  menuFor.value = null
  editing.value = a
  formOpen.value = true
}

async function setArchived(a: Account, archived: boolean) {
  archiving.value = true
  try {
    store.upsert(archived ? await accountsApi.archive(a.id) : await accountsApi.unarchive(a.id))
    confirmArchive.value = null
    menuFor.value = null
    if (archived && !showArchived.value && a.id === selectedId.value) {
      const next = store.active[0]
      if (next) select(next.id)
    }
    await refreshAudit()
  } finally {
    archiving.value = false
  }
}

async function saveProfile(body: RiskProfileInput) {
  const id = selectedId.value!
  profile.value = await accountsApi.saveRiskProfile(id, body)
  statuses.value = { ...statuses.value, [id]: await accountsApi.riskStatus(id) }
  await refreshAudit()
}

async function createRule(body: { code: RuleCode; params: RuleParams; severity: Severity }) {
  const rule = await accountsApi.createRule(selectedId.value!, body)
  rules.value = [...(rules.value ?? []), rule]
  await refreshAudit()
}
async function toggleRule(rule: Rule, on: boolean) {
  const updated = await accountsApi.updateRule(selectedId.value!, rule.id, { is_active: on })
  rules.value = (rules.value ?? []).map((r) => (r.id === rule.id ? updated : r))
  await refreshAudit()
}
async function removeRule(rule: Rule) {
  await accountsApi.deleteRule(selectedId.value!, rule.id)
  rules.value = (rules.value ?? []).filter((r) => r.id !== rule.id)
  await refreshAudit()
}

async function saveOverride(body: { broker_symbol: string; symbol_id: string; contract_size: string | null; tick_value: string | null }) {
  const saved = await accountsApi.saveOverride(selectedId.value!, body)
  const rest = (overrides.value ?? []).filter((o) => o.id !== saved.id)
  overrides.value = [...rest, saved].sort((a, b) => a.broker_symbol.localeCompare(b.broker_symbol))
  await refreshAudit()
}
async function removeOverride(o: SymbolOverride) {
  await accountsApi.deleteOverride(selectedId.value!, o.id)
  overrides.value = (overrides.value ?? []).filter((x) => x.id !== o.id)
  await refreshAudit()
}

// ---------------------------------------------------------------- display helpers

const TYPE_BADGE = { prop: 'gold', live: 'brand', demo: 'neutral' } as const
const TYPE_TILE = { prop: 'bg-gold-100 text-gold-ink', live: 'bg-brand-100 text-brand-700', demo: 'bg-surface-sunken text-ink-muted' } as const

function sub(a: Account) {
  return a.account_number ? `#${a.account_number}` : t('accounts.manualSource')
}
function usage(a: Account) {
  const s = statuses.value[a.id]
  if (!s) return { daily: '—', dd: '—' }
  return {
    daily: `${formatAmount(s.daily_loss.used, s.currency, 0)} / ${formatAmount(s.daily_loss.limit, s.currency, 0)}`,
    dd: `${formatNumber(s.drawdown_pct.used, 1)}% / ${formatNumber(s.drawdown_pct.limit, 1)}%`,
  }
}
const money = (a: Account, v?: string) => formatAmount(v ?? a.initial_balance, a.currency, 0)
</script>

<template>
  <div>
    <PageHeader :title="desktop ? t('accounts.title') : t('accounts.titleShort')">
      <template #actions>
        <TtButton variant="primary" :size="desktop ? 'md' : 'sm'" icon="add" @click="openCreate">
          {{ desktop ? t('accounts.add') : t('accounts.addShort') }}
        </TtButton>
      </template>
    </PageHeader>

    <PageContent>
      <TtAlert v-if="loadError" variant="loss" :title="t('accounts.loadError')">
        <template #action>
          <TtButton size="sm" variant="secondary" @click="loadAll">{{ t('accounts.retry') }}</TtButton>
        </template>
      </TtAlert>

      <TtAlert
        v-if="ctraderReturn"
        :variant="ctraderReturn.ok ? 'profit' : 'loss'"
        :title="ctraderReturn.ok ? t('connections.ctrader.returnConnected') : t('connections.ctrader.returnError')"
        :body="!ctraderReturn.ok && ctraderReturn.reason ? t('connections.ctrader.returnReason', { reason: ctraderReturn.reason }) : undefined"
        dismissible
        @dismiss="ctraderReturn = null"
      />

      <div v-if="!store.loaded && !loadError" class="tt-card"><TtSkeleton :lines="3" height="40px" /></div>

      <section v-else-if="store.loaded && !store.accounts.length" class="tt-card">
        <TtEmpty icon="accounts" :message="t('accounts.empty')">
          <TtButton variant="primary" icon="add" @click="openCreate">{{ t('accounts.add') }}</TtButton>
        </TtEmpty>
      </section>

      <template v-else-if="store.loaded">
        <!-- ================= Desktop ================= -->
        <template v-if="desktop">
          <div class="tt-card tt-card--flush overflow-visible">
            <div class="tt-tblwrap overflow-visible">
              <table class="tt-tbl">
                <caption class="sr-only">{{ t('accounts.title') }}</caption>
                <thead>
                  <tr>
                    <th scope="col">{{ t('accounts.col.account') }}</th>
                    <th scope="col">{{ t('accounts.col.type') }}</th>
                    <th scope="col">{{ t('accounts.col.platform') }}</th>
                    <th scope="col" class="tt-tbl__r">{{ t('accounts.col.balance') }}</th>
                    <th scope="col" class="tt-tbl__r">{{ t('accounts.col.equity') }}</th>
                    <th scope="col">{{ t('accounts.col.dailyLoss') }}</th>
                    <th scope="col">{{ t('accounts.col.drawdown') }}</th>
                    <th scope="col">{{ t('accounts.col.connection') }}</th>
                    <th scope="col"><span class="sr-only">{{ t('accounts.col.actions') }}</span></th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="a in listed"
                    :key="a.id"
                    class="tt-tbl__link"
                    :class="{ 'bg-brand-50': a.id === selectedId, 'text-ink-muted': !a.is_active }"
                    tabindex="0"
                    :aria-selected="a.id === selectedId"
                    @click="select(a.id)"
                    @keydown.enter.prevent="select(a.id)"
                  >
                    <td>
                      <b class="font-semibold">{{ a.name }}</b>
                      <TtBadge v-if="!a.is_active" class="ml-2" variant="outline">{{ t('accounts.archivedBadge') }}</TtBadge>
                      <div class="text-caption text-ink-muted">{{ sub(a) }}</div>
                    </td>
                    <td><TtBadge :variant="TYPE_BADGE[a.account_type]">{{ t(`accounts.type.${a.account_type}`) }}</TtBadge></td>
                    <td>{{ t(`accounts.platform.${a.platform}`) }}</td>
                    <td class="tt-tbl__r tt-num">{{ money(a, statuses[a.id]?.balance) }}</td>
                    <td class="tt-tbl__r tt-num">{{ money(a, statuses[a.id]?.equity) }}</td>
                    <td class="tt-num">{{ usage(a).daily }}</td>
                    <td class="tt-num">{{ usage(a).dd }}</td>
                    <td><TtBadge :variant="connBadge(a).variant">{{ t(connBadge(a).key, connBadge(a).params ?? {}) }}</TtBadge></td>
                    <td class="tt-tbl__r relative">
                      <button
                        type="button"
                        class="tt-iconbtn tt-iconbtn--bare"
                        :aria-label="t('accounts.menu', { name: a.name })"
                        aria-haspopup="menu"
                        :aria-expanded="menuFor === a.id"
                        @click.stop="menuFor = menuFor === a.id ? null : a.id"
                      >
                        <AppIcon name="options" />
                      </button>
                      <ul v-if="menuFor === a.id" class="tt-menu right-2 top-12 z-sheet min-w-[200px] text-left" role="menu" @click.stop>
                        <li role="none">
                          <button type="button" role="menuitem" class="tt-menu__item" @click="openEdit(a)">
                            <AppIcon name="edit" :size="16" />{{ t('accounts.edit') }}
                          </button>
                        </li>
                        <li role="none">
                          <button
                            v-if="a.is_active"
                            type="button"
                            role="menuitem"
                            class="tt-menu__item"
                            @click="((confirmArchive = a), (menuFor = null))"
                          >
                            <AppIcon name="delete" :size="16" />{{ t('accounts.archive') }}
                          </button>
                          <button v-else type="button" role="menuitem" class="tt-menu__item" @click="setArchived(a, false)">
                            <AppIcon name="back" :size="16" />{{ t('accounts.unarchive') }}
                          </button>
                        </li>
                      </ul>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
          <TtCheckbox v-if="store.accounts.length !== store.active.length" v-model="showArchived" class="self-end">
            {{ t('accounts.showArchived') }}
          </TtCheckbox>

          <template v-if="selected">
            <TtTabs v-model="tab" :items="tabItems" :label="t('accounts.tabs.label')" />
            <div class="grid grid-cols-[minmax(0,1fr)_minmax(320px,400px)] items-start gap-6">
              <div class="flex min-w-0 flex-col gap-6">
                <RiskProfileCard
                  v-if="tab === 'risk'"
                  :profile="profile"
                  :balance="balance"
                  :currency="selected.currency"
                  :save="saveProfile"
                />
                <RulesCard v-if="tab === 'risk' || tab === 'rules'" ref="rulesCard" :rules="rules" :create="createRule" :toggle="toggleRule" :remove="removeRule" />
                <SymbolMappingCard v-if="tab === 'symbols'" :overrides="overrides" :symbols="symbols" :save="saveOverride" :remove="removeOverride" />
                <template v-if="tab === 'connections'">
                  <ConnectionCard
                    :account="selected"
                    :connection="connOf(selected)"
                    :now="now"
                    :loading="!conns.loaded.value"
                    layout="full"
                    @changed="onConnectionChanged"
                  />
                  <IngestionHistory v-if="selected.platform !== 'manual'" :jobs="selectedJobs" :history-days="selectedHistoryDays" />
                </template>
                <AuditLogCard v-if="tab === 'audit'" :entries="audit" />
              </div>
              <aside class="flex flex-col gap-6">
                <TodayCard :status="statuses[selected.id] ?? null" />
                <ConnectionCard
                  v-if="tab !== 'connections'"
                  :account="selected"
                  :connection="connOf(selected)"
                  :now="now"
                  :loading="!conns.loaded.value"
                  @changed="onConnectionChanged"
                />
              </aside>
            </div>
          </template>
        </template>

        <!-- ================= Mobile ================= -->
        <template v-else>
          <ul class="tt-list" :aria-label="t('accounts.titleShort')">
            <li v-for="a in listed" :key="a.id">
              <button
                type="button"
                class="tt-list__row w-full border-0 text-left"
                :class="a.id === selectedId ? 'bg-brand-50' : 'bg-transparent'"
                :aria-pressed="a.id === selectedId"
                @click="select(a.id)"
              >
                <span class="grid h-9 w-9 flex-none place-items-center rounded-md" :class="TYPE_TILE[a.account_type]">
                  <AppIcon name="accounts" />
                </span>
                <span class="flex min-w-0 flex-1 flex-col">
                  <span class="truncate text-[15px] font-semibold">{{ a.name }}</span>
                  <span class="truncate text-caption text-ink-muted">
                    {{ [t(`accounts.type.${a.account_type}`), t(`accounts.platform.${a.platform}`), a.account_number && `#${a.account_number}`].filter(Boolean).join(' · ') }}
                  </span>
                </span>
                <span class="flex flex-none flex-col items-end gap-1">
                  <span class="tt-num text-[17px] font-bold">{{ money(a, statuses[a.id]?.balance) }}</span>
                  <TtBadge v-if="!a.is_active" variant="neutral">{{ t('accounts.archivedBadge') }}</TtBadge>
                  <TtBadge v-else-if="a.platform === 'manual'" variant="outline">{{ t('accounts.platform.manual') }}</TtBadge>
                  <TtBadge v-else :variant="connBadge(a).variant">{{ t(connBadge(a).key, connBadge(a).params ?? {}) }}</TtBadge>
                </span>
              </button>
            </li>
          </ul>
          <TtCheckbox v-if="store.accounts.length !== store.active.length" v-model="showArchived">{{ t('accounts.showArchived') }}</TtCheckbox>

          <template v-if="selected">
            <div class="flex items-baseline justify-between gap-2 pt-2">
              <h2 class="m-0 truncate text-h3">{{ t('accounts.risk.sectionTitle', { name: selected.name }) }}</h2>
              <span v-if="profile" class="flex-none text-caption text-ink-muted">{{ t('accounts.risk.editedShort', { date: editedAt }) }}</span>
            </div>
            <TodayCard :status="statuses[selected.id] ?? null" compact />
            <RiskProfileCard :profile="profile" :balance="balance" :currency="selected.currency" :save="saveProfile" />

            <div class="flex items-center justify-between gap-2 pt-2">
              <h2 class="m-0 text-h3">{{ t('accounts.rules.title') }}</h2>
              <TtButton variant="ghost" size="sm" icon="add" @click="rulesCard?.openDialog()">{{ t('accounts.rules.addShort') }}</TtButton>
            </div>
            <RulesCard ref="rulesCard" bare :rules="rules" :create="createRule" :toggle="toggleRule" :remove="removeRule" />

            <div class="flex items-center justify-between gap-2 pt-2">
              <h2 class="m-0 text-h3">{{ t('accounts.symbols.title') }}</h2>
              <TtButton variant="ghost" size="sm" icon="add" @click="symbolsCard?.openDialog()">{{ t('accounts.symbols.add') }}</TtButton>
            </div>
            <SymbolMappingCard ref="symbolsCard" bare :overrides="overrides" :symbols="symbols" :save="saveOverride" :remove="removeOverride" />

            <ConnectionCard :account="selected" :connection="connOf(selected)" :now="now" :loading="!conns.loaded.value" @changed="onConnectionChanged" />
            <TtButton
              v-if="selected.platform !== 'manual'"
              variant="secondary"
              block
              icon="connection"
              :to="{ name: 'account-connections', query: { account: selected.id } }"
            >
              {{ t('connections.openPage') }}
            </TtButton>
            <AuditLogCard :entries="audit" :limit="5" />
            <TtButton v-if="selected.is_active" variant="ghost" block @click="confirmArchive = selected">{{ t('accounts.archive') }}</TtButton>
            <TtButton v-else variant="ghost" block @click="setArchived(selected, false)">{{ t('accounts.unarchive') }}</TtButton>
          </template>
        </template>
      </template>
    </PageContent>

    <AccountFormDialog v-model:open="formOpen" :account="editing" :submit="submitAccount" />

    <TtModal
      :open="!!confirmArchive"
      size="sm"
      :title="t('accounts.archiveConfirmTitle', { name: confirmArchive?.name ?? '' })"
      @update:open="(v: boolean) => !v && (confirmArchive = null)"
    >
      <p class="m-0 text-body text-ink-muted">{{ t('accounts.archiveConfirmBody') }}</p>
      <template #footer>
        <TtButton variant="secondary" @click="confirmArchive = null">{{ t('accounts.cancel') }}</TtButton>
        <TtButton variant="danger" :loading="archiving" @click="confirmArchive && setArchived(confirmArchive, true)">{{ t('accounts.archive') }}</TtButton>
      </template>
    </TtModal>
  </div>
</template>
