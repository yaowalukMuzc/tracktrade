<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import TtButton from '@/components/ui/TtButton.vue'
import TtField from '@/components/ui/TtField.vue'
import TtInput from '@/components/ui/TtInput.vue'
import TtResponsiveDialog from '@/components/ui/TtResponsiveDialog.vue'
import TtSegmented from '@/components/ui/TtSegmented.vue'
import type { Side } from '@/api/positions'
import { utcOffset } from '@/lib/timezones'
import { validateExecution, type ExecRow } from './model'

// Add / edit one fill (scale-in, partial close). Modal on desktop, bottom sheet on mobile.
const props = defineProps<{ row: ExecRow | null; isNew: boolean; tz: string }>()
const open = defineModel<boolean>('open', { default: false })
const emit = defineEmits<{ save: [row: ExecRow]; remove: [key: string] }>()
const { t } = useI18n()

const draft = ref<ExecRow | null>(null)
const tried = ref(false)
watch(
  () => [open.value, props.row] as const,
  ([isOpen, row]) => {
    if (isOpen && row) {
      draft.value = { ...row }
      tried.value = false
    }
  },
  { immediate: true },
)

const side = computed<Side>({
  get: () => draft.value?.side ?? 'in',
  set: (v) => {
    if (draft.value) draft.value.side = v
  },
})
const sides = computed(() => (['in', 'out'] as Side[]).map((v) => ({ value: v, label: t(`tradeNew.executions.side.${v}`) })))
const errors = computed(() => (tried.value && draft.value ? validateExecution(draft.value) : {}))
const err = (k: keyof typeof errors.value) => (errors.value[k] ? t(`tradeNew.errors.${errors.value[k]}`) : undefined)
const title = computed(() => (props.isNew ? t(side.value === 'in' ? 'tradeNew.dialog.addIn' : 'tradeNew.dialog.addOut') : t('tradeNew.dialog.edit')))

function save() {
  tried.value = true
  if (!draft.value || Object.keys(validateExecution(draft.value)).length) return
  emit('save', { ...draft.value })
  open.value = false
}
function remove() {
  if (draft.value) emit('remove', draft.value.key)
  open.value = false
}
</script>

<template>
  <TtResponsiveDialog v-model:open="open" :title="title" size="sm">
    <form v-if="draft" class="tt-stack" data-testid="exec-dialog" @submit.prevent="save">
      <TtField :label="t('tradeNew.dialog.side')">
        <TtSegmented v-model="side" :options="sides" :label="t('tradeNew.dialog.side')" block />
      </TtField>
      <div class="grid grid-cols-2 gap-3">
        <TtField :label="t('tradeNew.dialog.lot')" required :error="err('lot')">
          <TtInput v-model="draft.lot" numeric inputmode="decimal" data-testid="exec-lot" />
        </TtField>
        <TtField :label="t('tradeNew.dialog.price')" required :error="err('price')">
          <TtInput v-model="draft.price" numeric inputmode="decimal" data-testid="exec-price" />
        </TtField>
      </div>
      <TtField :label="t('tradeNew.dialog.time', { tz: utcOffset(tz) })" required :error="err('local')">
        <input v-model="draft.local" type="datetime-local" class="tt-input" data-testid="exec-time" />
      </TtField>
      <div class="grid grid-cols-2 gap-3">
        <TtField :label="t('tradeNew.dialog.commission')" :help="t('tradeNew.dialog.commissionHelp')" :error="err('commission')">
          <TtInput v-model="draft.commission" numeric inputmode="decimal" placeholder="0.00" data-testid="exec-commission" />
        </TtField>
        <TtField :label="t('tradeNew.dialog.swap')" :help="t('tradeNew.dialog.swapHelp')" :error="err('swap')">
          <TtInput v-model="draft.swap" numeric inputmode="decimal" placeholder="0.00" />
        </TtField>
      </div>
      <button type="submit" class="hidden" aria-hidden="true" tabindex="-1" />
    </form>
    <template #footer>
      <TtButton v-if="!isNew" variant="danger" icon="delete" class="mr-auto" data-testid="exec-delete" @click="remove">{{ t('tradeNew.dialog.delete') }}</TtButton>
      <TtButton @click="open = false">{{ t('tradeNew.dialog.cancel') }}</TtButton>
      <TtButton variant="primary" data-testid="exec-save" @click="save">{{ t('tradeNew.dialog.save') }}</TtButton>
    </template>
  </TtResponsiveDialog>
</template>
