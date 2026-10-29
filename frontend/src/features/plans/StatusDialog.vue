<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import TtAlert from '@/components/ui/TtAlert.vue'
import TtButton from '@/components/ui/TtButton.vue'
import TtField from '@/components/ui/TtField.vue'
import TtResponsiveDialog from '@/components/ui/TtResponsiveDialog.vue'
import TtTextarea from '@/components/ui/TtTextarea.vue'
import { plansApi, type ManualStatus, type Plan } from '@/api/plans'
import { planErrorKey } from './errors'

// F-06 AC6 — skipped / missed / invalidated, always with a reason.
const props = defineProps<{ planId: string; status: ManualStatus | null }>()
const open = defineModel<boolean>('open', { default: false })
const emit = defineEmits<{ changed: [Plan] }>()
const { t } = useI18n()

const reason = ref('')
const error = ref<string | null>(null)
const saving = ref(false)
const title = computed(() => (props.status ? t(`plans.status.dialog.${props.status}`) : ''))

watch(open, (o) => {
  if (o) {
    reason.value = ''
    error.value = null
  }
})

async function submit() {
  if (!props.status || !reason.value.trim()) return
  saving.value = true
  error.value = null
  try {
    const plan = await plansApi.setStatus(props.planId, props.status, reason.value.trim())
    open.value = false
    emit('changed', plan)
  } catch (e) {
    error.value = t(planErrorKey(e))
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <TtResponsiveDialog v-model:open="open" :title="title" :subtitle="t('plans.status.dialogBody')" size="sm">
    <form id="plan-status-form" class="tt-stack pt-1" novalidate @submit.prevent="submit">
      <TtAlert v-if="error" variant="loss" :title="error" />
      <TtField :label="t('plans.status.reason')" required>
        <TtTextarea v-model="reason" :maxlength="500" :placeholder="t('plans.status.reasonPlaceholder')" />
      </TtField>
    </form>
    <template #footer>
      <TtButton class="flex-1" @click="open = false">{{ t('plans.revisionSheet.cancel') }}</TtButton>
      <TtButton type="submit" form="plan-status-form" variant="primary" class="flex-1" :disabled="!reason.trim()" :loading="saving">
        {{ t('plans.status.confirm') }}
      </TtButton>
    </template>
  </TtResponsiveDialog>
</template>
