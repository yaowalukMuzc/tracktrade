<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { useMediaQuery } from '@vueuse/core'
import PageContent from '@/components/shell/PageContent.vue'
import PageHeader from '@/components/shell/PageHeader.vue'
import TtAlert from '@/components/ui/TtAlert.vue'
import TtButton from '@/components/ui/TtButton.vue'
import TtEmpty from '@/components/ui/TtEmpty.vue'
import TtSegmented from '@/components/ui/TtSegmented.vue'
import TtSkeleton from '@/components/ui/TtSkeleton.vue'
import { playbookApi, type Setup, type SetupSummary } from '@/api/playbook'
import SetupCard from './SetupCard.vue'
import SetupDetail from './SetupDetail.vue'
import SetupFormDialog from './SetupFormDialog.vue'
import { errorKey } from './model'

// Playbook (F-04): screens/web/13-WPlaybook.png — ≥1024px list + detail of the selected setup (`?setup=<id>`,
// or `/playbook/:id` via SetupDetailView → `focusId`); below 1024px the list of screens/mobile/21 linking to
// /playbook/:id. Active/Archived is `?tab=archived`.
const props = defineProps<{ focusId?: string }>()
const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const isDesktop = useMediaQuery('(min-width: 1024px)')

type Tab = 'active' | 'archived'
type Err = [string, Record<string, unknown>?]
const tab = ref<Tab>(route.query.tab === 'archived' ? 'archived' : 'active')
const items = ref<SetupSummary[]>([])
const counts = ref({ active: 0, archived: 0 })
const loading = ref(true)
const loadErr = ref<Err | null>(null)

const detail = ref<Setup | null>(null)
const detailLoading = ref(false)
const detailErr = ref<Err | null>(null)
const notice = ref<string | null>(null)

const formOpen = ref(false)
const formSetup = ref<Setup | null>(null)

const selectedId = computed(() => props.focusId ?? (typeof route.query.setup === 'string' ? route.query.setup : null))

const tabOptions = computed(() => [
  { value: 'active' as const, label: t('playbook.tabActive', { n: counts.value.active }) },
  { value: 'archived' as const, label: t('playbook.tabArchived', { n: counts.value.archived }) },
])
const tabModel = computed({ get: () => tab.value, set: (v: Tab) => void setTab(v) })

/* ── Data ── */
async function loadList() {
  loading.value = true
  loadErr.value = null
  try {
    const res = await playbookApi.list(tab.value === 'archived')
    items.value = res.items
    counts.value = res.counts
  } catch (e) {
    loadErr.value = errorKey(e)
  } finally {
    loading.value = false
  }
}

let detailReq = 0
async function loadDetail(id: string) {
  const req = ++detailReq
  detailLoading.value = true
  detailErr.value = null
  try {
    const res = await playbookApi.get(id)
    if (req === detailReq) detail.value = res
  } catch (e) {
    if (req === detailReq) {
      detail.value = null
      detailErr.value = errorKey(e)
    }
  } finally {
    if (req === detailReq) detailLoading.value = false
  }
}

/* ── Selection (URL is the source of truth) ── */
function select(id: string) {
  if (id === selectedId.value) return
  if (props.focusId) void router.replace({ name: 'setup-detail', params: { id }, query: route.query })
  else void router.replace({ query: { ...route.query, setup: id } })
}
function clearSelection() {
  detail.value = null
  const { setup: _s, ...query } = route.query
  if (props.focusId) void router.replace({ name: 'playbook', query })
  else if (selectedId.value) void router.replace({ query })
}

/** Desktop always shows a detail: keep the current one if it belongs to this tab, else the first setup. */
function ensureSelection() {
  if (!isDesktop.value || loading.value || loadErr.value) return
  const id = selectedId.value
  const inTab = !!id && (items.value.some((i) => i.id === id) || (detail.value?.id === id && detail.value.is_archived === (tab.value === 'archived')))
  if (inTab) return
  if (items.value.length) select(items.value[0].id)
  else clearSelection()
}

async function setTab(v: Tab) {
  if (v === tab.value) return
  tab.value = v
  const { tab: _t, ...query } = route.query
  await router.replace({ ...(props.focusId ? { name: 'setup-detail', params: { id: props.focusId } } : {}), query: v === 'archived' ? { ...query, tab: v } : query })
  await loadList()
  ensureSelection()
}

async function init() {
  const id = selectedId.value
  if (isDesktop.value && id) {
    await loadDetail(id)
    // Opened on an archived setup (or vice versa) → show the tab it lives in.
    if (detail.value && detail.value.is_archived !== (tab.value === 'archived')) tab.value = detail.value.is_archived ? 'archived' : 'active'
  }
  await loadList()
  ensureSelection()
}
onMounted(init)

watch(selectedId, (id) => {
  if (isDesktop.value && id && id !== detail.value?.id) void loadDetail(id)
})
watch(isDesktop, (d) => {
  if (!d) return
  ensureSelection()
  if (selectedId.value && selectedId.value !== detail.value?.id) void loadDetail(selectedId.value)
})

/* ── Mutations ── */
function patchSummary(s: Setup) {
  items.value = items.value.map((i) =>
    i.id === s.id
      ? { ...i, name: s.name, timeframes: s.timeframes, sessions: s.sessions, default_risk_pct: s.default_risk_pct, checklist_count: s.checklist_count }
      : i,
  )
}
function onUpdate(s: Setup) {
  if (detail.value?.id === s.id) detail.value = s
  patchSummary(s)
}
async function onArchived(s: Setup) {
  detail.value = s
  tab.value = s.is_archived ? 'archived' : 'active'
  const { tab: _t, ...query } = route.query
  await router.replace({ ...(props.focusId ? { name: 'setup-detail', params: { id: props.focusId } } : {}), query: s.is_archived ? { ...query, tab: 'archived' } : query })
  await loadList()
}

function openCreate() {
  formSetup.value = null
  formOpen.value = true
}
function openEdit() {
  formSetup.value = detail.value
  formOpen.value = true
}
async function onSaved(s: Setup, kind: 'created' | 'updated') {
  notice.value = kind === 'created' ? t('playbook.created') : t('playbook.saved')
  if (kind === 'updated') return onUpdate(s)
  if (!isDesktop.value) return void router.push({ name: 'setup-detail', params: { id: s.id } })
  detail.value = s
  if (tab.value !== 'active') await setTab('active')
  else await loadList()
  select(s.id)
}
async function onDeleted() {
  notice.value = t('playbook.deleted')
  detail.value = null
  await loadList()
  if (props.focusId) await router.replace({ name: 'playbook', query: tab.value === 'archived' ? { tab: 'archived' } : {} })
  else if (items.value.length) select(items.value[0].id)
  else clearSelection()
}
</script>

<template>
  <PageHeader :title="t('pages.playbook')">
    <template #actions>
      <TtSegmented v-model="tabModel" :options="tabOptions" :label="t('playbook.tabsLabel')" class="hidden lg:inline-flex" />
      <TtButton variant="primary" icon="add" class="hidden lg:inline-flex" @click="openCreate">{{ t('playbook.create') }}</TtButton>
      <TtButton variant="primary" size="sm" icon="add" class="lg:hidden" :aria-label="t('playbook.create')" @click="openCreate">{{ t('playbook.createShort') }}</TtButton>
    </template>
  </PageHeader>

  <PageContent>
    <TtSegmented v-model="tabModel" :options="tabOptions" :label="t('playbook.tabsLabel')" block class="lg:!hidden" />
    <TtAlert v-if="notice" variant="profit" :title="notice" dismissible @dismiss="notice = null" />

    <TtAlert v-if="loadErr" variant="loss" :title="t('playbook.loadError')" :body="t(loadErr[0], loadErr[1] ?? {})">
      <template #action>
        <TtButton size="sm" @click="init">{{ t('playbook.retry') }}</TtButton>
      </template>
    </TtAlert>

    <!-- Loading -->
    <div v-else-if="loading && !items.length" class="flex items-start gap-6" :aria-label="t('ui.loading')" aria-busy="true">
      <div class="flex w-full flex-col gap-3 lg:w-[320px] lg:flex-none">
        <div v-for="n in 3" :key="n" class="tt-card"><TtSkeleton :lines="3" /></div>
      </div>
      <div class="hidden min-w-0 flex-1 flex-col gap-6 lg:flex">
        <div class="tt-card"><TtSkeleton :lines="3" height="20px" /></div>
        <div class="tt-card"><TtSkeleton :lines="5" /></div>
      </div>
    </div>

    <!-- Empty -->
    <section v-else-if="!items.length && !(isDesktop && detail)" class="tt-card">
      <TtEmpty icon="playbook" :message="tab === 'archived' ? t('playbook.emptyArchived') : t('playbook.empty')">
        <TtButton v-if="tab === 'active'" variant="primary" icon="add" @click="openCreate">{{ t('playbook.create') }}</TtButton>
      </TtEmpty>
    </section>

    <!-- Desktop: list + detail -->
    <div v-else-if="isDesktop" class="flex items-start gap-6">
      <ul class="m-0 flex w-[320px] flex-none list-none flex-col gap-3 p-0" :aria-label="t('playbook.listLabel')">
        <li v-for="s in items" :key="s.id">
          <SetupCard :setup="s" :selected="s.id === selectedId" @select="select(s.id)" />
        </li>
      </ul>
      <div class="min-w-0 flex-1">
        <TtAlert v-if="detailErr" variant="loss" :title="t(detailErr[0], detailErr[1] ?? {})">
          <template #action>
            <TtButton v-if="selectedId" size="sm" @click="loadDetail(selectedId)">{{ t('playbook.retry') }}</TtButton>
          </template>
        </TtAlert>
        <SetupDetail
          v-else-if="detail && detail.id === selectedId"
          :setup="detail"
          layout="split"
          @update="onUpdate"
          @edit="openEdit"
          @archived="onArchived"
        />
        <div v-else-if="detailLoading || selectedId" class="flex flex-col gap-6" aria-busy="true">
          <div class="tt-card"><TtSkeleton :lines="3" height="20px" /></div>
          <div class="tt-card"><TtSkeleton :lines="5" /></div>
        </div>
      </div>
    </div>

    <!-- Mobile: list → /playbook/:id -->
    <ul v-else class="m-0 flex list-none flex-col gap-3 p-0" :aria-label="t('playbook.listLabel')">
      <li v-for="s in items" :key="s.id">
        <SetupCard :setup="s" :to="{ name: 'setup-detail', params: { id: s.id } }" />
      </li>
    </ul>
  </PageContent>

  <SetupFormDialog v-model:open="formOpen" :setup="formSetup" @saved="onSaved" @deleted="onDeleted" @archived="onArchived" />
</template>
