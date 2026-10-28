<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import TtAlert from '@/components/ui/TtAlert.vue'
import TtButton from '@/components/ui/TtButton.vue'
import TtChip from '@/components/ui/TtChip.vue'
import TtField from '@/components/ui/TtField.vue'
import TtInput from '@/components/ui/TtInput.vue'
import TtResponsiveDialog from '@/components/ui/TtResponsiveDialog.vue'
import TtSegmented from '@/components/ui/TtSegmented.vue'
import TtSelect from '@/components/ui/TtSelect.vue'
import type { RuleCode, RuleParams, Severity } from '@/api/accounts'

// Add an extra rule to the account (spec §2.2 trading_rules). Params per rule type mirror the backend schemas.
const open = defineModel<boolean>('open', { default: false })
const props = defineProps<{ create: (body: { code: RuleCode; params: RuleParams; severity: Severity }) => Promise<void> }>()
const { t, tm, rt } = useI18n()

const form = reactive({ code: 'no_trading_window' as RuleCode, days: [4] as number[], after: '20:00', ratio: '1.2', n: '3', text: '', severity: 'medium' as Severity })
const errors = ref<Record<string, string>>({})
const formError = ref('')
const saving = ref(false)

watch(open, (o) => {
  if (o) {
    Object.assign(form, { code: 'no_trading_window', days: [4], after: '20:00', ratio: '1.2', n: '3', text: '', severity: 'medium' })
    errors.value = {}
    formError.value = ''
  }
})

const codes: RuleCode[] = ['no_trading_window', 'max_lot_vs_plan', 'max_consecutive_losses', 'custom']
const codeOptions = computed(() => codes.map((c) => ({ value: c, label: t(`accounts.rules.code.${c}`) })))
const severityOptions = computed(() => (['low', 'medium', 'high'] as Severity[]).map((s) => ({ value: s, label: t(`accounts.rules.severity.${s}`) })))
const weekdays = computed(() => (tm('accounts.rules.weekday') as unknown[]).map((w) => rt(w as Parameters<typeof rt>[0])))

function toggleDay(d: number) {
  form.days = form.days.includes(d) ? form.days.filter((x) => x !== d) : [...form.days, d].sort()
}

function params(): RuleParams | null {
  const e: Record<string, string> = {}
  let p: RuleParams
  if (form.code === 'no_trading_window') {
    if (!form.days.length) e.days = t('accounts.errors.days')
    if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(form.after)) e.after = t('accounts.errors.time')
    p = { days: form.days, after: form.after }
  } else if (form.code === 'max_lot_vs_plan') {
    const r = Number(form.ratio)
    if (!(r > 1 && r <= 10)) e.ratio = t('accounts.errors.range', { min: 1, max: 10 })
    p = { ratio: String(r) }
  } else if (form.code === 'max_consecutive_losses') {
    const n = Number(form.n)
    if (!Number.isInteger(n) || n < 1 || n > 20) e.n = t('accounts.errors.range', { min: 1, max: 20 })
    p = { n }
  } else {
    if (!form.text.trim()) e.text = t('accounts.errors.required')
    p = { text: form.text.trim() }
  }
  errors.value = e
  return Object.keys(e).length ? null : p
}

async function submit() {
  formError.value = ''
  const p = params()
  if (!p) return
  saving.value = true
  try {
    await props.create({ code: form.code, params: p, severity: form.severity })
    open.value = false
  } catch {
    formError.value = t('accounts.errors.generic')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <TtResponsiveDialog v-model:open="open" :title="t('accounts.rules.dialogTitle')">
    <form id="rule-form" class="tt-stack pt-2" novalidate @submit.prevent="submit">
      <TtAlert v-if="formError" variant="loss" :title="formError" />
      <TtField :label="t('accounts.rules.kind')">
        <TtSelect v-model="form.code" :options="codeOptions" />
      </TtField>

      <template v-if="form.code === 'no_trading_window'">
        <TtField :label="t('accounts.rules.days')" :error="errors.days">
          <div class="tt-row" role="group" :aria-label="t('accounts.rules.days')">
            <TtChip v-for="(w, i) in weekdays" :key="i" :selected="form.days.includes(i)" @click="toggleDay(i)">{{ w }}</TtChip>
          </div>
        </TtField>
        <TtField :label="t('accounts.rules.after')" :error="errors.after">
          <TtInput v-model="form.after" type="text" inputmode="numeric" placeholder="20:00" class="max-w-[160px]" />
        </TtField>
      </template>
      <TtField v-else-if="form.code === 'max_lot_vs_plan'" :label="t('accounts.rules.ratio')" :error="errors.ratio">
        <TtInput v-model="form.ratio" numeric suffix="×" />
      </TtField>
      <TtField v-else-if="form.code === 'max_consecutive_losses'" :label="t('accounts.rules.losses')" :error="errors.n">
        <TtInput v-model="form.n" numeric :suffix="t('accounts.risk.trades')" />
      </TtField>
      <template v-else>
        <TtField :label="t('accounts.rules.text')" :error="errors.text">
          <TtInput v-model="form.text" maxlength="200" :placeholder="t('accounts.rules.textPlaceholder')" />
        </TtField>
        <p class="m-0 text-caption text-ink-muted">{{ t('accounts.rules.customNote') }}</p>
      </template>

      <TtField :label="t('accounts.rules.severityField')">
        <TtSegmented v-model="form.severity" :options="severityOptions" :label="t('accounts.rules.severityField')" block />
      </TtField>
    </form>
    <template #footer>
      <TtButton variant="secondary" class="flex-1 lg:flex-none" @click="open = false">{{ t('accounts.cancel') }}</TtButton>
      <TtButton type="submit" form="rule-form" variant="primary" class="flex-1 lg:flex-none" :loading="saving">{{ t('accounts.rules.save') }}</TtButton>
    </template>
  </TtResponsiveDialog>
</template>
