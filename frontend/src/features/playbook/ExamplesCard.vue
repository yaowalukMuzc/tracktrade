<script setup lang="ts">
import { computed, onBeforeUnmount, ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import AppIcon from '@/components/AppIcon.vue'
import TtAlert from '@/components/ui/TtAlert.vue'
import TtAuthedImage from '@/components/ui/TtAuthedImage.vue'
import TtButton from '@/components/ui/TtButton.vue'
import TtField from '@/components/ui/TtField.vue'
import TtInput from '@/components/ui/TtInput.vue'
import { MAX_UPLOAD_MB, UPLOAD_TYPES, playbookApi, uploadAttachment, type Setup, type SetupExample } from '@/api/playbook'
import ConfirmModal from './ConfirmModal.vue'
import { MAX_EXAMPLES, errorKey, fileError } from './model'

// Example images (F-04 AC1): pick a file → caption → upload (attachment, then link to the setup). Owner-only URLs
// are loaded with the bearer token via TtAuthedImage. `page` = mobile section (no card, 2 columns, 4:3 tiles).
const props = defineProps<{ setup: Setup; layout: 'split' | 'page' }>()
const emit = defineEmits<{ update: [Setup] }>()
const { t } = useI18n()

const fileInput = ref<HTMLInputElement>()
const noteId = `ex-note-${useId()}`
const pending = ref<{ file: File; preview: string; note: string } | null>(null)
const busy = ref(false)
const error = ref<[string, Record<string, unknown>?] | null>(null)
const removing = ref<SetupExample | null>(null)
const full = computed(() => props.setup.examples.length >= MAX_EXAMPLES)

function clearPending() {
  if (pending.value) URL.revokeObjectURL(pending.value.preview)
  pending.value = null
}
watch(() => props.setup.id, () => {
  clearPending()
  error.value = null
})
onBeforeUnmount(clearPending)

function pick() {
  error.value = null
  fileInput.value?.click()
}

function onFile(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  const bad = fileError(file)
  if (bad) {
    error.value = bad
    return
  }
  clearPending()
  pending.value = { file, preview: URL.createObjectURL(file), note: '' }
  setTimeout(() => document.getElementById(noteId)?.focus())
}

async function save() {
  const p = pending.value
  if (!p) return
  busy.value = true
  error.value = null
  try {
    const att = await uploadAttachment(p.file)
    emit('update', await playbookApi.addExample(props.setup.id, att.id, p.note.trim()))
    clearPending()
  } catch (e) {
    error.value = errorKey(e)
  } finally {
    busy.value = false
  }
}

async function confirmRemove() {
  const ex = removing.value
  if (!ex) return
  busy.value = true
  error.value = null
  try {
    emit('update', await playbookApi.removeExample(props.setup.id, ex.id))
    removing.value = null
  } catch (e) {
    removing.value = null
    error.value = errorKey(e)
  } finally {
    busy.value = false
  }
}

const removeOpen = computed({
  get: () => !!removing.value,
  set: (v: boolean) => {
    if (!v) removing.value = null
  },
})
</script>

<template>
  <section :class="layout === 'split' ? 'tt-card flex flex-col gap-4' : 'flex flex-col gap-3'">
    <header class="flex items-center justify-between gap-2">
      <h2 class="m-0 text-h3">{{ t('playbook.examples.title') }}</h2>
      <TtButton variant="ghost" size="sm" icon="upload" :disabled="full || busy || !!pending" @click="pick">{{ t('playbook.examples.upload') }}</TtButton>
      <input ref="fileInput" type="file" class="sr-only" tabindex="-1" aria-hidden="true" :accept="UPLOAD_TYPES.join(',')" @change="onFile" />
    </header>

    <TtAlert v-if="error" variant="loss" :title="t(error[0], error[1] ?? {})" dismissible @dismiss="error = null" />

    <form v-if="pending" class="flex flex-col gap-3 rounded-md border border-border bg-surface-sunken p-3 sm:flex-row sm:items-end" @submit.prevent="save">
      <img :src="pending.preview" :alt="t('playbook.examples.preview')" class="aspect-[16/10] w-full rounded-md border border-border object-cover sm:w-40" />
      <TtField :id="noteId" :label="t('playbook.examples.note')" class="min-w-0 flex-1" :help="t('playbook.examples.hint', { mb: MAX_UPLOAD_MB, max: MAX_EXAMPLES })">
        <TtInput v-model="pending.note" :maxlength="200" :placeholder="t('playbook.examples.notePlaceholder')" />
      </TtField>
      <div class="flex gap-2 sm:pb-7">
        <TtButton variant="ghost" size="sm" :disabled="busy" @click="clearPending">{{ t('playbook.examples.cancel') }}</TtButton>
        <TtButton type="submit" size="sm" icon="upload" :loading="busy">{{ t('playbook.examples.save') }}</TtButton>
      </div>
    </form>

    <ul v-if="setup.examples.length" class="m-0 grid list-none gap-2 p-0" :class="layout === 'split' ? 'grid-cols-2 xl:grid-cols-3' : 'grid-cols-2'">
      <li v-for="ex in setup.examples" :key="ex.id" class="flex min-w-0 flex-col gap-1">
        <div class="relative overflow-hidden rounded-md border border-border bg-surface-sunken" :class="layout === 'split' ? 'aspect-[16/10]' : 'aspect-[4/3]'">
          <TtAuthedImage :src="ex.url" :alt="ex.note || t('playbook.examples.alt', { name: setup.name })" />
          <button
            type="button"
            class="absolute right-1.5 top-1.5 grid h-8 w-8 place-items-center rounded-md border border-border bg-surface text-ink-muted hover:text-loss-ink"
            :aria-label="t('playbook.examples.remove', { note: ex.note })"
            :title="t('playbook.examples.remove', { note: ex.note })"
            :disabled="busy"
            @click="removing = ex"
          >
            <AppIcon name="delete" :size="16" />
          </button>
        </div>
        <span v-if="ex.note" class="truncate text-caption text-ink-muted">{{ ex.note }}</span>
      </li>
    </ul>
    <button
      v-else-if="!pending"
      type="button"
      class="flex flex-col items-center gap-2 rounded-md border border-dashed border-border-strong bg-surface-sunken px-4 py-6 text-center text-body-sm text-ink-muted"
      @click="pick"
    >
      <AppIcon name="upload" :size="24" class="text-ink-subtle" />
      <span>{{ t('playbook.examples.empty') }}</span>
      <span class="text-caption text-ink-subtle">{{ t('playbook.examples.hint', { mb: MAX_UPLOAD_MB, max: MAX_EXAMPLES }) }}</span>
    </button>
    <p v-if="full" class="m-0 text-caption text-ink-subtle">{{ t('playbook.examples.full', { max: MAX_EXAMPLES }) }}</p>

    <ConfirmModal
      v-model:open="removeOpen"
      :title="t('playbook.examples.removeTitle')"
      :body="t('playbook.examples.removeBody')"
      :confirm="t('playbook.examples.removeConfirm')"
      :loading="busy"
      @confirm="confirmRemove"
    />
  </section>
</template>
