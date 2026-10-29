<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { EditorContent, VueNodeViewRenderer, useEditor, type JSONContent } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import Image from '@tiptap/extension-image'
import AppIcon from '@/components/AppIcon.vue'
import TtAlert from '@/components/ui/TtAlert.vue'
import type { RichDoc } from '@/api/analysis'
import { UPLOAD_TYPES, uploadAttachment } from '@/api/playbook'
import { errorKey, imageFileError, normalizeDoc } from './model'
import NarrativeImage from './NarrativeImage.vue'

// Narrative rich text (F-05 AC1): Tiptap with B / I / H2 / image (screens/source/WAnalysis.dc.html).
// `card` = desktop card with the toolbar in its header; `field` = mobile field with the toolbar inside the box.
defineProps<{ layout: 'card' | 'field' }>()
const model = defineModel<RichDoc>({ required: true })
const { t } = useI18n()

const AuthedImage = Image.extend({
  addNodeView() {
    return VueNodeViewRenderer(NarrativeImage)
  },
})

const editor = useEditor({
  content: normalizeDoc(model.value) as JSONContent,
  extensions: [
    StarterKit.configure({ heading: { levels: [2] }, link: false, codeBlock: false, code: false, horizontalRule: false }),
    AuthedImage.configure({ inline: false, allowBase64: false }),
  ],
  editorProps: {
    attributes: {
      class: 'narrative-content',
      role: 'textbox',
      'aria-multiline': 'true',
      'aria-label': t('analysis.narrative.editor'),
    },
  },
  onUpdate: ({ editor: e }) => {
    const doc = e.getJSON() as RichDoc
    last = JSON.stringify(doc)
    model.value = doc
  },
})
let last = JSON.stringify(normalizeDoc(model.value))

// Value replaced from outside (load / reload) → reset the editor content.
watch(model, (doc) => {
  const json = JSON.stringify(normalizeDoc(doc))
  if (json === last || !editor.value) return
  last = json
  editor.value.commands.setContent(normalizeDoc(doc) as JSONContent, { emitUpdate: false })
})
onBeforeUnmount(() => editor.value?.destroy())

const fileInput = ref<HTMLInputElement | null>(null)
const uploading = ref(false)
const error = ref<[string, Record<string, unknown>?] | null>(null)

async function onFile(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file || !editor.value) return
  error.value = imageFileError(file)
  if (error.value) return
  uploading.value = true
  try {
    const att = await uploadAttachment(file)
    editor.value.chain().focus().setImage({ src: att.url, alt: file.name }).run()
  } catch (err) {
    const key = errorKey(err)
    error.value = key[0] === 'analysis.errors.generic' ? ['analysis.errors.upload'] : key
  } finally {
    uploading.value = false
  }
}

type Action = { id: 'bold' | 'italic' | 'heading'; glyph: string; cls?: string; active: () => boolean; run: () => void }
const actions: Action[] = [
  { id: 'bold', glyph: 'B', active: () => !!editor.value?.isActive('bold'), run: () => editor.value?.chain().focus().toggleBold().run() },
  { id: 'italic', glyph: 'I', cls: 'italic', active: () => !!editor.value?.isActive('italic'), run: () => editor.value?.chain().focus().toggleItalic().run() },
  {
    id: 'heading',
    glyph: 'H2',
    active: () => !!editor.value?.isActive('heading', { level: 2 }),
    run: () => editor.value?.chain().focus().toggleHeading({ level: 2 }).run(),
  },
]
const btn =
  'grid size-8 place-items-center rounded-[8px] border-0 bg-transparent text-[13px] font-bold text-ink-muted transition-colors hover:bg-surface-sunken focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-700'
</script>

<template>
  <div class="flex flex-col gap-3">
    <div :class="layout === 'card' ? 'flex items-center justify-between gap-3' : ''">
      <h2 v-if="layout === 'card'" class="m-0 text-h3">{{ t('analysis.narrative.title') }}</h2>
      <span v-else class="tt-label">{{ t('analysis.narrative.title') }}</span>
      <div v-if="layout === 'card'" class="flex gap-0.5" role="toolbar" :aria-label="t('analysis.narrative.toolbar')">
        <template v-for="a in actions" :key="a.id">
          <button
            type="button"
            :class="[btn, a.cls, { 'bg-brand-100 text-brand-700': a.active() }]"
            :aria-label="t(`analysis.narrative.${a.id}`)"
            :title="t(`analysis.narrative.${a.id}`)"
            :aria-pressed="a.active()"
            @click="a.run()"
          >
            {{ a.glyph }}
          </button>
        </template>
        <button type="button" :class="btn" :aria-label="t('analysis.narrative.image')" :title="t('analysis.narrative.image')" :disabled="uploading" @click="fileInput?.click()">
          <AppIcon :name="uploading ? 'loading' : 'image'" :size="16" :class="{ 'tt-spin': uploading }" />
        </button>
      </div>
    </div>

    <div class="narrative-box overflow-hidden rounded-md border border-border-strong bg-surface">
      <div v-if="layout === 'field'" class="flex gap-0.5 border-b border-border p-1.5" role="toolbar" :aria-label="t('analysis.narrative.toolbar')">
        <template v-for="a in actions" :key="a.id">
          <button
            type="button"
            :class="[btn, a.cls, { 'bg-brand-100 text-brand-700': a.active() }]"
            :aria-label="t(`analysis.narrative.${a.id}`)"
            :aria-pressed="a.active()"
            @click="a.run()"
          >
            {{ a.glyph }}
          </button>
        </template>
        <button type="button" :class="btn" :aria-label="t('analysis.narrative.image')" :disabled="uploading" @click="fileInput?.click()">
          <AppIcon :name="uploading ? 'loading' : 'image'" :size="16" :class="{ 'tt-spin': uploading }" />
        </button>
      </div>
      <EditorContent :editor="editor" />
    </div>
    <input ref="fileInput" type="file" class="sr-only" tabindex="-1" aria-hidden="true" :accept="UPLOAD_TYPES.join(',')" @change="onFile" />
    <p v-if="uploading" class="m-0 text-caption text-ink-muted" role="status">{{ t('analysis.narrative.uploading') }}</p>
    <TtAlert v-if="error" variant="loss" :title="t(error[0], error[1] ?? {})" dismissible @dismiss="error = null" />
  </div>
</template>

<style scoped>
.narrative-box :deep(.narrative-content) {
  min-height: 120px;
  padding: var(--space-3);
  font: 400 15px/1.6 var(--font-sans);
  color: var(--ink);
  outline: none;
}
.narrative-box:focus-within { border-color: var(--brand-700); box-shadow: 0 0 0 3px var(--focus-ring); }
.narrative-box :deep(.narrative-content p) { margin: 0 0 var(--space-2); }
.narrative-box :deep(.narrative-content p:last-child) { margin-bottom: 0; }
.narrative-box :deep(.narrative-content h2) { margin: var(--space-2) 0; font: 600 18px/28px var(--font-sans); }
.narrative-box :deep(.narrative-content ul),
.narrative-box :deep(.narrative-content ol) { margin: 0 0 var(--space-2); padding-left: 20px; }
.narrative-box :deep(.narrative-content strong) { font-weight: 700; }
</style>
