<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { useMediaQuery } from '@vueuse/core'
import PageContent from '@/components/shell/PageContent.vue'
import PageHeader from '@/components/shell/PageHeader.vue'
import TtAlert from '@/components/ui/TtAlert.vue'
import TtButton from '@/components/ui/TtButton.vue'
import TtIconButton from '@/components/ui/TtIconButton.vue'
import TtSkeleton from '@/components/ui/TtSkeleton.vue'
import { playbookApi, type Setup } from '@/api/playbook'
import PlaybookView from './PlaybookView.vue'
import SetupDetail from './SetupDetail.vue'
import SetupFormDialog from './SetupFormDialog.vue'
import { errorKey } from './model'

// /playbook/:id — mobile setup detail (screens/mobile/22-SetupDetail.png). ≥1024px renders the Playbook split view
// with this setup selected, so a shared link works at any width.
const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const isDesktop = useMediaQuery('(min-width: 1024px)')
const id = computed(() => String(route.params.id))

const setup = ref<Setup | null>(null)
const loading = ref(false)
const err = ref<[string, Record<string, unknown>?] | null>(null)
const formOpen = ref(false)
const notice = ref<string | null>(null)

async function load() {
  loading.value = true
  err.value = null
  try {
    setup.value = await playbookApi.get(id.value)
  } catch (e) {
    setup.value = null
    err.value = errorKey(e)
  } finally {
    loading.value = false
  }
}
watch(
  [id, isDesktop],
  () => {
    if (!isDesktop.value && setup.value?.id !== id.value) void load()
  },
  { immediate: true },
)

function onSaved(s: Setup) {
  setup.value = s
  notice.value = t('playbook.saved')
}
function onDeleted() {
  void router.replace({ name: 'playbook' })
}
</script>

<template>
  <PlaybookView v-if="isDesktop" :focus-id="id" />
  <template v-else>
    <PageHeader :title="setup?.name ?? t('pages.playbook')" :crumb="{ to: { name: 'playbook' }, label: t('playbook.back') }">
      <template #actions>
        <TtIconButton v-if="setup" icon="edit" bare :label="t('playbook.editSetup', { name: setup.name })" @click="formOpen = true" />
      </template>
    </PageHeader>
    <PageContent>
      <TtAlert v-if="notice" variant="profit" :title="notice" dismissible @dismiss="notice = null" />
      <TtAlert v-if="err" variant="loss" :title="t(err[0], err[1] ?? {})">
        <template #action>
          <TtButton size="sm" @click="load">{{ t('playbook.retry') }}</TtButton>
        </template>
      </TtAlert>
      <SetupDetail v-else-if="setup" :setup="setup" layout="page" @update="setup = $event" @edit="formOpen = true" />
      <div v-else-if="loading" class="flex flex-col gap-3" aria-busy="true" :aria-label="t('ui.loading')">
        <TtSkeleton :lines="2" />
        <div class="grid grid-cols-2 gap-3">
          <div v-for="n in 4" :key="n" class="tt-card"><TtSkeleton :lines="2" /></div>
        </div>
        <div class="tt-card"><TtSkeleton :lines="4" /></div>
      </div>
    </PageContent>
    <SetupFormDialog v-model:open="formOpen" :setup="setup" @saved="onSaved" @deleted="onDeleted" @archived="setup = $event" />
  </template>
</template>
