<script setup lang="ts">
import { computed, nextTick, ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import AppIcon from '@/components/AppIcon.vue'
import TtButton from '@/components/ui/TtButton.vue'
import TtCheckbox from '@/components/ui/TtCheckbox.vue'
import TtInput from '@/components/ui/TtInput.vue'
import { ITEM_MAX, MAX_CHECKLIST, moveItem, newKey, type EditItem } from './model'

// Setup checklist editor (F-04 AC1): reorder by dragging the handle (pointer events → mouse + touch) or with
// ↑/↓ on the focused handle; tap an item to edit its text / "จำเป็น" / delete it; add inline. Emits the whole list.
const props = defineProps<{ disabled?: boolean }>()
const items = defineModel<EditItem[]>({ required: true })
const adding = defineModel<boolean>('adding', { default: false })
const { t } = useI18n()
const hintId = `cl-hint-${useId()}`

const announce = ref('')
const handles = new Map<string, HTMLElement>()
const listEl = ref<HTMLElement>()

/* ── Reorder ── */
const drag = ref<{ key: string; from: number; list: EditItem[] } | null>(null)
const view = computed(() => drag.value?.list ?? items.value)

function announceMove(list: EditItem[], key: string) {
  const pos = list.findIndex((i) => i.key === key)
  announce.value = t('playbook.checklist.moved', { text: list[pos].text, pos: pos + 1, total: list.length })
}

function onPointerDown(e: PointerEvent, i: number) {
  if (props.disabled || e.button !== 0) return
  e.preventDefault()
  ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
  drag.value = { key: items.value[i].key, from: i, list: [...items.value] }
}

function onPointerMove(e: PointerEvent) {
  const d = drag.value
  if (!d || !listEl.value) return
  const rows = [...listEl.value.querySelectorAll<HTMLElement>('[data-row]')]
  const cur = d.list.findIndex((x) => x.key === d.key)
  let target = 0
  rows.forEach((row, j) => {
    if (j === cur) return
    const r = row.getBoundingClientRect()
    if (e.clientY > r.top + r.height / 2) target++
  })
  if (target !== cur) d.list = moveItem(d.list, cur, target)
}

function onPointerUp() {
  const d = drag.value
  if (!d) return
  drag.value = null
  const to = d.list.findIndex((x) => x.key === d.key)
  if (to !== d.from) {
    items.value = d.list
    announceMove(d.list, d.key)
  }
}

async function onHandleKey(e: KeyboardEvent, i: number) {
  const step = e.key === 'ArrowUp' ? -1 : e.key === 'ArrowDown' ? 1 : 0
  if (!step || props.disabled) return
  e.preventDefault()
  const next = moveItem(items.value, i, i + step)
  if (next === items.value) return
  const key = items.value[i].key
  items.value = next
  announceMove(next, key)
  await nextTick()
  handles.get(key)?.focus()
}

/* ── Edit / toggle / delete ── */
const editing = ref<{ key: string; text: string; required: boolean } | null>(null)

async function startEdit(it: EditItem) {
  if (props.disabled) return
  editing.value = { key: it.key, text: it.text, required: it.is_required }
  await nextTick()
  ;(document.getElementById(`cl-edit-${it.key}`) as HTMLInputElement | null)?.focus()
}
function commitEdit() {
  const e = editing.value
  if (!e) return
  editing.value = null
  const text = e.text.trim().slice(0, ITEM_MAX)
  if (!text) return
  const cur = items.value.find((i) => i.key === e.key)
  if (!cur || (cur.text === text && cur.is_required === e.required)) return
  items.value = items.value.map((i) => (i.key === e.key ? { ...i, text, is_required: e.required } : i))
}
/** Leaving the edit row (click or Tab elsewhere) saves it. */
function onEditFocusOut(ev: FocusEvent) {
  const box = ev.currentTarget as HTMLElement
  if (!box.contains(ev.relatedTarget as Node | null)) commitEdit()
}
function remove(key: string) {
  editing.value = null
  items.value = items.value.filter((i) => i.key !== key)
}

/* ── Add ── */
const draft = ref({ text: '', required: false })
const draftId = `cl-new-${useId()}`
const full = computed(() => items.value.length >= MAX_CHECKLIST)

watch(adding, async (on) => {
  if (!on) return
  draft.value = { text: '', required: false }
  await nextTick()
  ;(document.getElementById(draftId) as HTMLInputElement | null)?.focus()
})

function add() {
  const text = draft.value.text.trim().slice(0, ITEM_MAX)
  if (!text || full.value) return
  items.value = [...items.value, { key: newKey(), text, is_required: draft.value.required }]
  draft.value = { text: '', required: false }
  if (full.value) adding.value = false
}

const setHandle = (key: string) => (el: unknown) => {
  if (el instanceof HTMLElement) handles.set(key, el)
  else handles.delete(key)
}
</script>

<template>
  <div>
    <p :id="hintId" class="sr-only">{{ t('playbook.checklist.moveHint') }}</p>
    <p class="sr-only" aria-live="polite">{{ announce }}</p>

    <ol v-if="view.length" ref="listEl" class="m-0 list-none p-0">
      <li
        v-for="(it, i) in view"
        :key="it.key"
        data-row
        class="group flex items-center gap-2 border-b border-border py-2 last:border-b-0"
        :class="{ 'rounded-md bg-surface-sunken': drag?.key === it.key }"
      >
        <button
          :ref="setHandle(it.key)"
          type="button"
          class="-ml-1 grid h-8 w-7 flex-none touch-none place-items-center rounded-sm text-ink-subtle"
          :class="disabled ? 'cursor-not-allowed' : drag?.key === it.key ? 'cursor-grabbing' : 'cursor-grab'"
          :aria-label="t('playbook.checklist.move', { text: it.text })"
          :aria-describedby="hintId"
          :disabled="disabled"
          @pointerdown="onPointerDown($event, i)"
          @pointermove="onPointerMove"
          @pointerup="onPointerUp"
          @pointercancel="onPointerUp"
          @keydown="onHandleKey($event, i)"
        >
          <AppIcon name="dragHandle" />
        </button>

        <div v-if="editing?.key === it.key" class="flex min-w-0 flex-1 flex-col gap-2 py-1" @focusout="onEditFocusOut">
          <TtInput
            :id="`cl-edit-${it.key}`"
            v-model="editing.text"
            :maxlength="ITEM_MAX"
            :aria-label="t('playbook.checklist.textLabel')"
            @keydown.enter.prevent="commitEdit"
            @keydown.esc.stop.prevent="editing = null"
          />
          <div class="flex flex-wrap items-center gap-2">
            <TtCheckbox v-model="editing.required" @keydown.esc.stop.prevent="editing = null">{{ t('playbook.checklist.newRequired') }}</TtCheckbox>
            <span class="flex-1" />
            <TtButton variant="ghost" size="sm" icon="delete" class="!text-loss-ink" :aria-label="t('playbook.checklist.delete', { text: it.text })" @click="remove(it.key)">
              {{ t('playbook.checklist.remove') }}
            </TtButton>
            <TtButton size="sm" icon="check" @click="commitEdit">{{ t('playbook.checklist.done') }}</TtButton>
          </div>
        </div>
        <template v-else>
          <button
            type="button"
            class="min-w-0 flex-1 cursor-pointer break-words bg-transparent p-0 text-left text-body text-ink"
            :aria-label="t('playbook.checklist.editText', { text: it.text })"
            :disabled="disabled"
            @click="startEdit(it)"
          >
            {{ it.text }}
          </button>
          <span v-if="it.is_required" class="tt-badge flex-none">{{ t('playbook.checklist.required') }}</span>
        </template>
      </li>
    </ol>
    <p v-else-if="!adding" class="m-0 py-3 text-body-sm text-ink-muted">{{ t('playbook.checklist.empty') }}</p>

    <form v-if="adding" class="flex flex-col gap-2 border-t border-border py-3" :class="{ 'border-t-0': !view.length }" @submit.prevent="add">
      <TtInput
        :id="draftId"
        v-model="draft.text"
        :maxlength="ITEM_MAX"
        :placeholder="t('playbook.checklist.newPlaceholder')"
        :aria-label="t('playbook.checklist.newLabel')"
        :disabled="disabled || full"
        @keydown.esc.stop.prevent="adding = false"
      />
      <div class="flex flex-wrap items-center gap-2">
        <TtCheckbox v-model="draft.required" :disabled="disabled">{{ t('playbook.checklist.newRequired') }}</TtCheckbox>
        <span class="flex-1" />
        <TtButton size="sm" variant="ghost" @click="adding = false">{{ t('playbook.checklist.cancel') }}</TtButton>
        <TtButton size="sm" type="submit" icon="add" :disabled="disabled || full || !draft.text.trim()">{{ t('playbook.checklist.confirmAdd') }}</TtButton>
      </div>
      <p v-if="full" class="m-0 text-body-sm text-ink-muted">{{ t('playbook.checklist.max', { n: MAX_CHECKLIST }) }}</p>
    </form>
  </div>
</template>
