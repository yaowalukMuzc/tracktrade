<script setup lang="ts">
import { computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import TtAlert from '@/components/ui/TtAlert.vue'
import TtButton from '@/components/ui/TtButton.vue'
import TtEmpty from '@/components/ui/TtEmpty.vue'
import TtModal from '@/components/ui/TtModal.vue'
import TtSkeleton from '@/components/ui/TtSkeleton.vue'
import MatchPicker from './MatchPicker.vue'
import { useMatchQueue } from './useMatchQueue'

// Desktop match modal over /trades (screens/web/06-WTrades.png). Walks the queue starting at `startId`.
const props = defineProps<{ startId: string | null; accountId?: string; tz: string }>()
const open = defineModel<boolean>('open', { default: false })
const emit = defineEmits<{ matched: [id: string] }>()
const { t } = useI18n()

const q = useMatchQueue({ accountId: () => props.accountId, onMatched: (id) => emit('matched', id) })

watch(
  open,
  (isOpen) => {
    if (isOpen) void q.load(props.startId)
  },
  { immediate: true },
)
// Close once the last trade is handled.
watch(q.done, (finished) => {
  if (finished && q.items.value.length) open.value = false
})

const subtitle = computed(() => {
  const item = q.current.value
  if (!item) return undefined
  const counter = t('trades.match.counter', { i: q.index.value + 1, n: q.items.value.length })
  const eligible = item.candidates.filter((c) => c.eligible).length
  return `${counter} · ${eligible ? t('trades.match.several') : t('trades.match.none')}`
})
</script>

<template>
  <TtModal v-model:open="open" :title="t('trades.match.title')" :subtitle="subtitle" size="md">
    <TtSkeleton v-if="q.state.value === 'loading'" :lines="3" height="64px" />
    <TtAlert v-else-if="q.state.value === 'error'" variant="loss" :title="t('trades.match.loadFailed')">
      <template #action>
        <TtButton size="sm" @click="q.load(startId)">{{ t('trades.error.retry') }}</TtButton>
      </template>
    </TtAlert>
    <TtEmpty v-else-if="!q.current.value" icon="success" :message="t('trades.match.empty')" />
    <template v-else>
      <MatchPicker
        :key="q.current.value.position.id"
        v-model="q.choice.value"
        :position="q.current.value.position"
        :first-entry="q.current.value.first_entry"
        :candidates="q.current.value.candidates"
        :tz="tz"
      />
      <TtAlert v-if="q.saveError.value" variant="loss" :title="t('trades.match.failed')" />
    </template>
    <template v-if="q.current.value" #footer>
      <TtButton variant="ghost" :disabled="q.saving.value" @click="q.skip">{{ t('trades.match.skip') }}</TtButton>
      <TtButton variant="primary" :loading="q.saving.value" data-testid="match-confirm" @click="q.confirm">{{ t('trades.match.confirm') }}</TtButton>
    </template>
  </TtModal>
</template>
