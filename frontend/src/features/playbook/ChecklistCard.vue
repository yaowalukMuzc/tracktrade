<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import TtAlert from '@/components/ui/TtAlert.vue'
import TtButton from '@/components/ui/TtButton.vue'
import TtCard from '@/components/ui/TtCard.vue'
import { playbookApi, type Setup } from '@/api/playbook'
import ChecklistEditor from './ChecklistEditor.vue'
import { MAX_CHECKLIST, errorKey, toChecklistInput, toEditItems, type EditItem } from './model'

// Checklist card of the setup detail: every edit is saved right away (PUT keeps item ids). Saves are serialised;
// new items get their server id without changing their row key, so focus and drag state survive a save.
const props = defineProps<{ setup: Setup }>()
const emit = defineEmits<{ update: [Setup] }>()
const { t } = useI18n()

const items = ref<EditItem[]>(toEditItems(props.setup.checklist))
const adding = ref(false)
const error = ref<[string, Record<string, unknown>?] | null>(null)
let lastSaved = props.setup
let saving = false
let dirty = false

watch(
  () => props.setup.id,
  () => {
    items.value = toEditItems(props.setup.checklist)
    lastSaved = props.setup
    adding.value = false
    error.value = null
  },
)

function onChange(next: EditItem[]) {
  items.value = next
  dirty = true
  void flush()
}

async function flush() {
  if (saving) return
  saving = true
  error.value = null
  try {
    while (dirty) {
      dirty = false
      const snapshot = items.value
      const res = await playbookApi.saveChecklist(props.setup.id, toChecklistInput(snapshot))
      // Same order and length as the snapshot → hand out the new ids by position.
      const ids = new Map(snapshot.map((it, i) => [it.key, res.checklist[i]?.id]))
      items.value = items.value.map((it) => (it.id ? it : { ...it, id: ids.get(it.key) }))
      lastSaved = res
      emit('update', res)
    }
  } catch (e) {
    dirty = false
    error.value = errorKey(e)
    items.value = toEditItems(lastSaved.checklist)
  } finally {
    saving = false
  }
}

const full = computed(() => items.value.length >= MAX_CHECKLIST)
</script>

<template>
  <TtCard class="!pb-1">
    <header class="tt-card__head !mb-0">
      <h2 class="tt-card__title">{{ t('playbook.checklist.title') }}</h2>
      <TtButton variant="ghost" size="sm" icon="add" :disabled="full || adding" @click="adding = true">{{ t('playbook.checklist.add') }}</TtButton>
    </header>
    <TtAlert v-if="error" variant="loss" :title="t('playbook.checklist.saveError')" :body="t(error[0], error[1] ?? {})" dismissible class="my-2" @dismiss="error = null" />
    <ChecklistEditor v-model:adding="adding" :model-value="items" @update:model-value="onChange" />
  </TtCard>
</template>
