<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { watchDebounced } from '@vueuse/core'
import TtAlert from '@/components/ui/TtAlert.vue'
import TtButton from '@/components/ui/TtButton.vue'
import TtField from '@/components/ui/TtField.vue'
import TtInput from '@/components/ui/TtInput.vue'
import TtResponsiveDialog from '@/components/ui/TtResponsiveDialog.vue'
import TtTextarea from '@/components/ui/TtTextarea.vue'
import { plansApi, type Plan, type Revision } from '@/api/plans'
import { formatR } from '@/lib/format'
import { formatPct, formatPrice, formatRiskPct, isValid, revisionChanges, revisionDraft, validateRevision, type RevisionDraft } from './form'
import { moneyDelta } from './display'
import { planErrorKey } from './errors'

// screens/mobile/08-PlanLocked.png sheet — the only way to change a locked plan (F-06 AC4): new values,
// live risk delta ("Risk เพิ่มขึ้น +0.33R (+$335)"), a required reason; after the entry it is flagged (AC5).
const props = defineProps<{ plan: Plan; digits: number }>()
const open = defineModel<boolean>('open', { default: false })
const emit = defineEmits<{ saved: [Revision] }>()
const { t } = useI18n()

const draft = ref<RevisionDraft>(revisionDraft(props.plan, props.digits))
const reason = ref('')
const preview = ref<Revision | null>(null)
const previewError = ref<string | null>(null)
const saveError = ref<string | null>(null)
const saving = ref(false)
let seq = 0

const triggered = computed(() => props.plan.status === 'triggered')
const errors = computed(() => validateRevision(props.plan, draft.value))
const changes = computed(() => revisionChanges(props.plan, draft.value, { triggered: triggered.value }))
const hasChanges = computed(() => Object.keys(changes.value).length > 0)
const canSave = computed(() => hasChanges.value && isValid(errors.value) && reason.value.trim() !== '' && !previewError.value)
const err = (k: string) => (errors.value[k] ? t(`plans.errors.${errors.value[k]}`) : undefined)

watch(open, (o) => {
  if (!o) return
  draft.value = revisionDraft(props.plan, props.digits)
  reason.value = ''
  preview.value = null
  previewError.value = null
  saveError.value = null
})

watchDebounced(
  changes,
  async (c) => {
    const mine = ++seq
    if (!open.value || !Object.keys(c).length || !isValid(errors.value)) {
      preview.value = null
      previewError.value = null
      return
    }
    try {
      const p = await plansApi.previewRevision(props.plan.id, c)
      if (mine === seq) {
        preview.value = p
        previewError.value = null
      }
    } catch (e) {
      if (mine === seq) {
        preview.value = null
        previewError.value = t(planErrorKey(e))
      }
    }
  },
  { debounce: 300, deep: true },
)

const delta = computed(() => {
  const p = preview.value
  if (!p || p.risk_delta_amount === null) return null
  const amount = Number(p.risk_delta_amount)
  const r = p.risk_delta_r === null ? null : Number(p.risk_delta_r)
  // Before the entry the lot follows the risk %, so only lot rounding moves the amount: "unchanged".
  if (Math.abs(amount) < 0.005 || (r !== null && Math.abs(r) < 0.005)) return { tone: 'same' as const, text: t('plans.revisionSheet.riskSame') }
  const vars = { r: r === null ? '' : formatR(r, 2), money: moneyDelta(amount, props.plan.currency) }
  return amount > 0 ? { tone: 'up' as const, text: t('plans.revisionSheet.riskUp', vars) } : { tone: 'down' as const, text: t('plans.revisionSheet.riskDown', vars) }
})

async function save() {
  if (!canSave.value) return
  saving.value = true
  saveError.value = null
  try {
    const rev = await plansApi.revise(props.plan.id, changes.value, reason.value.trim())
    open.value = false
    emit('saved', rev)
  } catch (e) {
    saveError.value = t(planErrorKey(e))
  } finally {
    saving.value = false
  }
}

const oldPrice = (v: string) => formatPrice(v, props.digits)
const oldClass = '!bg-surface-sunken !text-ink-subtle'
</script>

<template>
  <TtResponsiveDialog v-model:open="open" :title="t('plans.revisionSheet.title', { n: plan.current_revision + 1 })">
    <form id="plan-revision-form" class="tt-stack pt-1" novalidate data-testid="revision-form" @submit.prevent="save">
      <TtAlert
        v-if="triggered"
        variant="warning"
        :title="t('plans.revisionSheet.afterEntryTitle')"
        :body="t('plans.revisionSheet.afterEntryBody')"
      />
      <TtAlert v-if="saveError" variant="loss" :title="saveError" />

      <div class="grid grid-cols-2 gap-3">
        <TtField :label="t('plans.revisionSheet.old', { field: 'SL' })">
          <TtInput :model-value="oldPrice(plan.stop_loss)" numeric disabled :class="oldClass" />
        </TtField>
        <TtField :label="t('plans.revisionSheet.new', { field: 'SL' })" :error="err('stopLoss')">
          <TtInput v-model="draft.stopLoss" numeric />
        </TtField>
        <TtField :label="t('plans.revisionSheet.old', { field: 'Entry' })">
          <TtInput :model-value="oldPrice(plan.entry_price)" numeric disabled :class="oldClass" />
        </TtField>
        <TtField :label="t('plans.revisionSheet.new', { field: 'Entry' })" :error="err('entry')">
          <TtInput v-model="draft.entry" numeric />
        </TtField>
        <template v-for="(tp, i) in draft.tps" :key="i">
          <TtField :label="t('plans.revisionSheet.old', { field: t('plans.fields.tpLabel', { n: i + 1, pct: formatPct(plan.take_profits[i]?.pct ?? tp.pct) }) })">
            <TtInput :model-value="plan.take_profits[i] ? oldPrice(plan.take_profits[i].price) : ''" numeric disabled :class="oldClass" />
          </TtField>
          <TtField :label="t('plans.revisionSheet.new', { field: t('plans.fields.tpN', { n: i + 1 }) })" :error="err(`tp.${i}`)">
            <TtInput v-model="tp.price" numeric />
          </TtField>
        </template>
        <template v-if="!triggered">
          <TtField :label="t('plans.revisionSheet.old', { field: 'Risk %' })">
            <TtInput :model-value="formatRiskPct(plan.planned_risk_pct)" numeric suffix="%" disabled :class="oldClass" />
          </TtField>
          <TtField :label="t('plans.revisionSheet.new', { field: 'Risk %' })" :error="err('riskPct')">
            <TtInput v-model="draft.riskPct" numeric suffix="%" />
          </TtField>
        </template>
      </div>
      <p v-if="triggered" class="tt-help m-0">{{ t('plans.revisionSheet.riskFixed') }}</p>

      <div aria-live="polite">
        <p v-if="previewError" class="tt-help tt-help--error m-0">{{ previewError }}</p>
        <p v-else-if="delta" class="tt-help m-0 text-[13px] font-medium" :class="{ 'tt-help--error': delta.tone === 'up' }" data-testid="revision-delta">
          {{ delta.text }}
        </p>
        <p v-else-if="!hasChanges" class="tt-help m-0">{{ t('plans.revisionSheet.noChanges') }}</p>
      </div>

      <TtField :label="t('plans.revisionSheet.reason')" required>
        <TtTextarea v-model="reason" class="!min-h-[80px]" :maxlength="500" :placeholder="t('plans.revisionSheet.reasonPlaceholder')" />
      </TtField>
    </form>
    <template #footer>
      <TtButton size="lg" class="flex-1" @click="open = false">{{ t('plans.revisionSheet.cancel') }}</TtButton>
      <TtButton type="submit" form="plan-revision-form" variant="primary" size="lg" class="flex-[1.4]" :disabled="!canSave" :loading="saving">
        {{ t('plans.revisionSheet.save') }}
      </TtButton>
    </template>
  </TtResponsiveDialog>
</template>
