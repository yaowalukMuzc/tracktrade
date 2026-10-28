<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AppIcon from '@/components/AppIcon.vue'
import TtButton from '@/components/ui/TtButton.vue'
import TtEmpty from '@/components/ui/TtEmpty.vue'
import TtIconButton from '@/components/ui/TtIconButton.vue'
import TtSkeleton from '@/components/ui/TtSkeleton.vue'
import TtToggle from '@/components/ui/TtToggle.vue'
import type { Rule, RuleCode, RuleParams, Severity } from '@/api/accounts'
import { describeRule, SEVERITY_TONE } from './model'
import RuleDialog from './RuleDialog.vue'

// "กฎเพิ่มเติม": icon tone = severity (high → loss, medium → warning, low → brand), on/off switch, delete.
const props = defineProps<{
  rules: Rule[] | null
  create: (body: { code: RuleCode; params: RuleParams; severity: Severity }) => Promise<void>
  toggle: (rule: Rule, on: boolean) => Promise<void>
  remove: (rule: Rule) => Promise<void>
  /** Mobile: the section heading sits outside the card (screens/mobile/23-Accounts.png). */
  bare?: boolean
}>()
const { t, locale } = useI18n()
const dialog = ref(false)
const busy = ref<string | null>(null)

const TONE_CLASS = { loss: 'bg-loss-100 text-loss-ink', warn: 'bg-warning-100 text-warning-ink', brand: 'bg-brand-100 text-brand-700' }

function title(rule: Rule) {
  if (rule.code === 'custom') return String(rule.params.text ?? '')
  const d = describeRule(rule, (i) => t(`accounts.rules.weekday[${i}]`), locale.value)
  return t(d.key, d.params ?? {})
}
function subtitle(rule: Rule) {
  const by = rule.created_by === 'mentor' ? t('accounts.rules.byMentor') : t('accounts.rules.byYou')
  return `${by} · ${t('accounts.rules.severityLabel', { level: t(`accounts.rules.severity.${rule.severity}`) })}`
}

async function run(rule: Rule, fn: () => Promise<void>) {
  busy.value = rule.id
  try {
    await fn()
  } finally {
    busy.value = null
  }
}
defineExpose({ openDialog: () => (dialog.value = true) })
</script>

<template>
  <section class="tt-card tt-card--flush overflow-hidden">
    <header v-if="!bare" class="tt-card__head px-4 pt-4 md:px-5 md:pt-5">
      <h2 class="tt-card__title">{{ t('accounts.rules.title') }}</h2>
      <TtButton variant="ghost" size="sm" icon="add" @click="dialog = true">{{ t('accounts.rules.add') }}</TtButton>
    </header>
    <div v-if="!props.rules" class="p-4 md:p-5"><TtSkeleton :lines="2" height="36px" /></div>
    <TtEmpty v-else-if="!props.rules.length" icon="risk" :message="t('accounts.rules.empty')" />
    <ul v-else class="m-0 list-none p-0">
      <li v-for="(rule, i) in props.rules" :key="rule.id" class="flex items-center gap-3 px-4 py-3 md:px-5" :class="{ 'border-t border-border': i > 0 || !bare }">
        <span class="grid h-9 w-9 flex-none place-items-center rounded-md" :class="TONE_CLASS[SEVERITY_TONE[rule.severity]]">
          <AppIcon name="risk" />
        </span>
        <div class="flex min-w-0 flex-1 flex-col">
          <span class="text-[14px] font-semibold leading-5" :class="{ 'text-ink-muted': !rule.is_active }">{{ title(rule) }}</span>
          <span class="text-[12px] leading-[18px] text-ink-muted">{{ subtitle(rule) }}</span>
        </div>
        <TtIconButton
          v-if="rule.created_by === 'trader'"
          icon="delete"
          bare
          :label="t('accounts.rules.delete', { rule: title(rule) })"
          :disabled="busy === rule.id"
          @click="run(rule, () => remove(rule))"
        />
        <TtToggle
          :model-value="rule.is_active"
          :label="t('accounts.rules.toggle', { rule: title(rule) })"
          :disabled="busy === rule.id"
          @update:model-value="run(rule, () => toggle(rule, $event))"
        />
      </li>
    </ul>
    <RuleDialog v-model:open="dialog" :create="create" />
  </section>
</template>
