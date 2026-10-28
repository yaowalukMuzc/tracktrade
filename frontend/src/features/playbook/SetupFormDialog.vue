<script setup lang="ts">
import { computed, nextTick, reactive, ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useMediaQuery } from '@vueuse/core'
import { ApiError } from '@/api/client'
import { SESSIONS, TIMEFRAMES, playbookApi, type SessionName, type Setup, type Timeframe } from '@/api/playbook'
import TtAlert from '@/components/ui/TtAlert.vue'
import TtButton from '@/components/ui/TtButton.vue'
import TtChip from '@/components/ui/TtChip.vue'
import TtField from '@/components/ui/TtField.vue'
import TtInput from '@/components/ui/TtInput.vue'
import TtModal from '@/components/ui/TtModal.vue'
import TtSheet from '@/components/ui/TtSheet.vue'
import TtTextarea from '@/components/ui/TtTextarea.vue'
import TtToggle from '@/components/ui/TtToggle.vue'
import ChecklistEditor from './ChecklistEditor.vue'
import {
  DESCRIPTION_MAX,
  ERROR_PARAMS,
  NAME_MAX,
  apiFieldErrors,
  emptyForm,
  errorKey,
  formFromSetup,
  formToInput,
  sessionLabel,
  validateForm,
  type FormErrors,
  type FormField,
  type SetupFormModel,
} from './model'

// Create / edit a setup (F-04 AC1). Modal ≥1024px, bottom sheet below. On create the checklist is part of the form;
// on edit it is edited in place on the detail. Delete is offered here; a used setup → 409 setup_in_use → Archive (AC2).
const props = defineProps<{ setup?: Setup | null }>()
const open = defineModel<boolean>('open', { default: false })
const emit = defineEmits<{ saved: [Setup, 'created' | 'updated']; deleted: [string]; archived: [Setup] }>()
const { t } = useI18n()
const isDesktop = useMediaQuery('(min-width: 1024px)')
const formId = `setup-form-${useId()}`

const editing = computed(() => !!props.setup)
const model = reactive<SetupFormModel>(emptyForm())
const errors = ref<FormErrors>({})
const formError = ref<[string, Record<string, unknown>?] | null>(null)
const saving = ref(false)
const addingItem = ref(false)
const confirmDelete = ref(false)
const deleting = ref(false)
const inUse = ref(false)
const archiving = ref(false)
const tried = ref(false)

watch(
  open,
  (on) => {
    if (!on) return
    Object.assign(model, props.setup ? formFromSetup(props.setup) : emptyForm())
    errors.value = {}
    formError.value = null
    inUse.value = false
    tried.value = false
    confirmDelete.value = false
    addingItem.value = !props.setup
  },
  { immediate: true },
)

// After a failed submit, errors update as the user types so fixed fields clear right away.
watch(model, () => {
  if (tried.value) errors.value = validateForm(model, !editing.value)
  if (tried.value && !Object.keys(errors.value).length) formError.value = null
}, { deep: true })

const err = (f: FormField) => (errors.value[f] ? t(errors.value[f]!, ERROR_PARAMS[f]) : undefined)

function toggle<T>(list: T[], v: T) {
  const i = list.indexOf(v)
  if (i >= 0) list.splice(i, 1)
  else list.push(v)
}

async function submit() {
  tried.value = true
  errors.value = validateForm(model, !editing.value)
  formError.value = null
  if (Object.keys(errors.value).length) {
    formError.value = ['playbook.form.fixErrors']
    return
  }
  saving.value = true
  try {
    if (props.setup) {
      const { checklist: _c, ...body } = formToInput(model, false)
      emit('saved', await playbookApi.update(props.setup.id, body), 'updated')
    } else {
      emit('saved', await playbookApi.create(formToInput(model, true)), 'created')
    }
    open.value = false
  } catch (e) {
    errors.value = apiFieldErrors(e)
    formError.value = errorKey(e)
  } finally {
    saving.value = false
  }
}

async function askDelete() {
  inUse.value = false
  confirmDelete.value = true
  await nextTick()
  document.getElementById(formId)?.querySelector<HTMLElement>('.tt-btn--danger')?.focus()
}

async function doDelete() {
  if (!props.setup) return
  deleting.value = true
  try {
    await playbookApi.remove(props.setup.id)
    confirmDelete.value = false
    open.value = false
    emit('deleted', props.setup.id)
  } catch (e) {
    confirmDelete.value = false
    if (e instanceof ApiError && e.code === 'setup_in_use') inUse.value = true
    else formError.value = errorKey(e)
  } finally {
    deleting.value = false
  }
}

async function archiveInstead() {
  if (!props.setup) return
  archiving.value = true
  try {
    const res = await playbookApi.archive(props.setup.id)
    open.value = false
    emit('archived', res)
  } catch (e) {
    formError.value = errorKey(e)
  } finally {
    archiving.value = false
  }
}

const title = computed(() => (editing.value ? t('playbook.form.editTitle') : t('playbook.form.createTitle')))
const tfChips = TIMEFRAMES
const sessionChips = SESSIONS
const pickTf = (v: Timeframe) => toggle(model.timeframes, v)
const pickSession = (v: SessionName) => toggle(model.sessions, v)
</script>

<template>
  <component
    :is="isDesktop ? TtModal : TtSheet"
    v-model:open="open"
    v-bind="isDesktop ? { size: 'lg' } : {}"
    :title="title"
    :subtitle="editing ? undefined : t('playbook.form.subtitle')"
  >
    <form :id="formId" class="flex flex-col gap-5" novalidate @submit.prevent="submit">
      <TtAlert v-if="formError" variant="loss" :title="t(formError[0], formError[1] ?? {})" />

      <TtAlert v-if="inUse" variant="warning" :title="t('playbook.form.inUseTitle')" :body="t('playbook.form.inUseBody')">
        <template #action>
          <TtButton size="sm" icon="archive" :loading="archiving" @click="archiveInstead">{{ t('playbook.form.archiveInstead') }}</TtButton>
        </template>
      </TtAlert>

      <TtField :label="t('playbook.form.name')" required :error="err('name')">
        <TtInput v-model="model.name" :maxlength="NAME_MAX" :placeholder="t('playbook.form.namePlaceholder')" autocomplete="off" />
      </TtField>
      <TtField :label="t('playbook.form.description')" :error="err('description')">
        <TtTextarea v-model="model.description" rows="3" :maxlength="DESCRIPTION_MAX" :placeholder="t('playbook.form.descriptionPlaceholder')" />
      </TtField>

      <fieldset class="m-0 flex flex-col gap-2 border-0 p-0">
        <legend class="tt-label mb-2 p-0">{{ t('playbook.form.timeframes') }}</legend>
        <div class="flex flex-wrap gap-2">
          <TtChip v-for="tf in tfChips" :key="tf" size="sm" :selected="model.timeframes.includes(tf)" @click="pickTf(tf)">{{ tf }}</TtChip>
        </div>
      </fieldset>
      <fieldset class="m-0 flex flex-col gap-2 border-0 p-0">
        <legend class="tt-label mb-2 p-0">{{ t('playbook.form.sessions') }}</legend>
        <div class="flex flex-wrap gap-2">
          <TtChip v-for="s in sessionChips" :key="s" size="sm" :selected="model.sessions.includes(s)" @click="pickSession(s)">{{ sessionLabel(t, s) }}</TtChip>
        </div>
      </fieldset>

      <TtField :label="t('playbook.form.defaultRisk')" required :error="err('risk')" class="sm:max-w-[220px]">
        <TtInput v-model="model.risk" numeric suffix="%" />
      </TtField>

      <fieldset class="m-0 flex flex-col gap-3 border-0 p-0">
        <legend class="mb-1 p-0 text-h3">{{ t('playbook.form.rules') }}</legend>
        <p class="m-0 -mt-1 text-body-sm text-ink-muted">{{ t('playbook.form.rulesHelp') }}</p>

        <div class="flex flex-col gap-3 rounded-md border border-border p-3">
          <div class="flex items-center justify-between gap-3">
            <span class="text-body font-medium">{{ t('playbook.form.partial') }}</span>
            <TtToggle v-model="model.partialOn" :label="t('playbook.form.partial')" />
          </div>
          <div v-if="model.partialOn" class="grid grid-cols-2 gap-3">
            <TtField :label="t('playbook.form.partialPct')" :error="err('partialPct')">
              <TtInput v-model="model.partialPct" numeric suffix="%" />
            </TtField>
            <TtField :label="t('playbook.form.partialAt')" :error="err('partialAt')">
              <TtInput v-model="model.partialAt" numeric suffix="R" />
            </TtField>
          </div>
        </div>

        <div class="flex flex-col gap-3 rounded-md border border-border p-3">
          <div class="flex items-center justify-between gap-3">
            <span class="text-body font-medium">{{ t('playbook.form.breakEven') }}</span>
            <TtToggle v-model="model.beOn" :label="t('playbook.form.breakEven')" />
          </div>
          <TtField v-if="model.beOn" :label="t('playbook.form.breakEvenAt')" :error="err('beAt')" class="sm:max-w-[220px]">
            <TtInput v-model="model.beAt" numeric suffix="R" />
          </TtField>
        </div>

        <div class="flex flex-col gap-3 rounded-md border border-border p-3">
          <div class="flex items-center justify-between gap-3">
            <span class="text-body font-medium">{{ t('playbook.form.trailing') }}</span>
            <TtToggle v-model="model.trailOn" :label="t('playbook.form.trailing')" />
          </div>
          <TtField v-if="model.trailOn" :label="t('playbook.form.trailingMethod')" :error="err('trailMethod')">
            <TtInput v-model="model.trailMethod" :maxlength="100" :placeholder="t('playbook.form.trailingPlaceholder')" />
          </TtField>
        </div>
      </fieldset>

      <fieldset v-if="!editing" class="m-0 flex flex-col gap-1 border-0 p-0">
        <legend class="mb-1 p-0 text-h3">{{ t('playbook.form.checklist') }}</legend>
        <p class="m-0 text-body-sm text-ink-muted">{{ t('playbook.form.checklistHelp') }}</p>
        <ChecklistEditor v-model="model.checklist" v-model:adding="addingItem" />
        <TtButton v-if="!addingItem" variant="ghost" size="sm" icon="add" class="self-start" @click="addingItem = true">{{ t('playbook.checklist.add') }}</TtButton>
        <p v-if="err('checklist')" class="tt-help tt-help--error m-0" role="alert">{{ err('checklist') }}</p>
      </fieldset>

      <TtAlert v-if="confirmDelete" variant="loss" :title="t('playbook.form.deleteTitle')" :body="t('playbook.form.deleteBody')">
        <div class="mt-3 flex flex-wrap gap-2">
          <TtButton variant="danger" size="sm" icon="delete" :loading="deleting" @click="doDelete">{{ t('playbook.form.deleteConfirm') }}</TtButton>
          <TtButton variant="ghost" size="sm" @click="confirmDelete = false">{{ t('playbook.form.cancel') }}</TtButton>
        </div>
      </TtAlert>
    </form>

    <template #footer>
      <TtButton v-if="editing" variant="ghost" icon="delete" class="mr-auto !text-loss-ink" @click="askDelete">{{ t('playbook.form.delete') }}</TtButton>
      <span v-else class="flex-1" />
      <TtButton variant="ghost" @click="open = false">{{ t('playbook.form.cancel') }}</TtButton>
      <TtButton variant="primary" type="submit" :form="formId" :loading="saving">
        {{ editing ? t('playbook.form.submitEdit') : t('playbook.form.submitCreate') }}
      </TtButton>
    </template>
  </component>
</template>
