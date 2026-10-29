<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AppIcon from '@/components/AppIcon.vue'
import TtButton from '@/components/ui/TtButton.vue'
import TtField from '@/components/ui/TtField.vue'
import TtInput from '@/components/ui/TtInput.vue'
import TtResponsiveDialog from '@/components/ui/TtResponsiveDialog.vue'
import TtSelect from '@/components/ui/TtSelect.vue'
import { LEVEL_KINDS, type KeyLevel } from '@/api/analysis'
import { LEVEL_MARKER, MAX_LEVELS, addLevel, emptyLevelForm, formatLevelPrice, levelFromForm, validateLevel, type LevelErrors } from './model'

// Key levels (F-05 AC1): desktop = card with "เพิ่ม" in the header; mobile = field with a list + "เพิ่ม level" below.
const props = defineProps<{ digits: number; layout: 'card' | 'field' }>()
const levels = defineModel<KeyLevel[]>({ required: true })
const { t } = useI18n()

const open = ref(false)
const form = ref(emptyLevelForm())
const errors = ref<LevelErrors>({})
const full = computed(() => levels.value.length >= MAX_LEVELS)
const kindOptions = computed(() => LEVEL_KINDS.map((k) => ({ value: k, label: t(`analysis.levels.kinds.${k}`) })))

function openForm() {
  form.value = emptyLevelForm()
  errors.value = {}
  open.value = true
}
function submit() {
  errors.value = validateLevel(form.value)
  if (Object.keys(errors.value).length || full.value) return
  levels.value = addLevel(levels.value, levelFromForm(form.value))
  open.value = false
}
function remove(i: number) {
  levels.value = levels.value.filter((_, j) => j !== i)
}

const priceText = (l: KeyLevel) => formatLevelPrice(l, props.digits)
const subText = (l: KeyLevel) => [t(`analysis.levels.kinds.${l.kind}`), l.label].filter(Boolean).join(' · ')
const err = (k: keyof LevelErrors) => (errors.value[k] ? t(`analysis.levels.errors.${errors.value[k]}`) : undefined)
</script>

<template>
  <section :class="layout === 'card' ? 'tt-card tt-card--flush overflow-hidden' : 'flex flex-col gap-2'" :aria-labelledby="`kl-${layout}`">
    <header v-if="layout === 'card'" class="tt-card__head px-4 pt-4">
      <h2 :id="`kl-${layout}`" class="tt-card__title">{{ t('analysis.levels.title') }}</h2>
      <TtButton variant="ghost" size="sm" icon="add" :disabled="full" @click="openForm">{{ t('analysis.levels.add') }}</TtButton>
    </header>
    <span v-else :id="`kl-${layout}`" class="tt-label">{{ t('analysis.levels.title') }}</span>

    <ul v-if="levels.length" class="m-0 list-none p-0" :class="layout === 'field' ? 'tt-list' : 'mt-1'">
      <li
        v-for="(l, i) in levels"
        :key="`${l.price}-${l.price_to}-${l.kind}-${i}`"
        class="flex items-center gap-3 border-b border-border py-2.5 last:border-b-0"
        :class="layout === 'card' ? 'px-4' : 'px-3'"
      >
        <i class="block w-3 flex-none rounded-[2px]" :class="LEVEL_MARKER[l.kind]" aria-hidden="true" />
        <div class="flex min-w-0 flex-1 flex-col">
          <span class="tt-num text-sm font-semibold leading-5">{{ priceText(l) }}</span>
          <span class="truncate text-caption font-normal text-ink-muted">{{ subText(l) }}</span>
        </div>
        <button
          type="button"
          class="tt-iconbtn tt-iconbtn--bare size-8"
          :aria-label="t('analysis.levels.remove', { price: priceText(l) })"
          :title="t('analysis.levels.remove', { price: priceText(l) })"
          @click="remove(i)"
        >
          <AppIcon name="close" :size="16" />
        </button>
      </li>
    </ul>
    <p v-else class="m-0 text-body-sm text-ink-muted" :class="layout === 'card' ? 'px-4 pb-4 pt-2' : ''">{{ t('analysis.levels.empty') }}</p>

    <TtButton v-if="layout === 'field'" class="self-start" variant="ghost" size="sm" icon="add" :disabled="full" @click="openForm">
      {{ t('analysis.levels.addLevel') }}
    </TtButton>

    <TtResponsiveDialog v-model:open="open" :title="t('analysis.levels.dialogTitle')" size="sm">
      <form id="level-form" class="flex flex-col gap-4" novalidate @submit.prevent="submit">
        <TtField :label="t('analysis.levels.kind')">
          <TtSelect v-model="form.kind" :options="kindOptions" />
        </TtField>
        <div class="grid gap-3" :class="form.kind === 'zone' ? 'grid-cols-2' : 'grid-cols-1'">
          <TtField :label="form.kind === 'zone' ? t('analysis.levels.priceFrom') : t('analysis.levels.price')" :error="err('price')" required>
            <TtInput v-model="form.price" numeric autocomplete="off" />
          </TtField>
          <TtField v-if="form.kind === 'zone'" :label="t('analysis.levels.priceTo')" :error="err('priceTo')" required>
            <TtInput v-model="form.priceTo" numeric autocomplete="off" />
          </TtField>
        </div>
        <TtField :label="t('analysis.levels.label')">
          <TtInput v-model="form.label" maxlength="100" :placeholder="t('analysis.levels.labelPlaceholder')" />
        </TtField>
      </form>
      <template #footer>
        <TtButton variant="secondary" @click="open = false">{{ t('analysis.levels.cancel') }}</TtButton>
        <TtButton variant="primary" type="submit" form="level-form">{{ t('analysis.levels.submit') }}</TtButton>
      </template>
    </TtResponsiveDialog>
  </section>
</template>
