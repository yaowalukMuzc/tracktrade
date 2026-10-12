<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import PageHeader from '@/components/shell/PageHeader.vue'
import PageContent from '@/components/shell/PageContent.vue'
import TtAlert from '@/components/ui/TtAlert.vue'
import TtButton from '@/components/ui/TtButton.vue'
import TtCard from '@/components/ui/TtCard.vue'
import TtField from '@/components/ui/TtField.vue'
import TtInput from '@/components/ui/TtInput.vue'
import TtSegmented from '@/components/ui/TtSegmented.vue'
import TtSelect from '@/components/ui/TtSelect.vue'
import { useSessionStore } from '@/stores/session'
import { useUiStore, type ThemePref } from '@/stores/ui'
import { timezoneOptions } from '@/lib/timezones'
import { authErrorKey } from '@/features/auth/errors'
import type { Locale } from '@/i18n'

// Phase 1 slice of screens/web/16-WSettings.png: profile (name, locale, timezone) + theme. F-01 AC3.
const { t } = useI18n()
const session = useSessionStore()
const ui = useUiStore()

const profile = reactive({ display_name: '', timezone: 'UTC' })
watch(
  () => session.user,
  (u) => {
    if (!u) return
    profile.display_name = u.display_name
    profile.timezone = u.timezone
  },
  { immediate: true },
)

const saving = ref(false)
const status = ref<{ ok: boolean; text: string } | null>(null)
const tzOptions = computed(() => timezoneOptions(profile.timezone))
const localeOptions = [
  { value: 'th' as const, label: 'ไทย' },
  { value: 'en' as const, label: 'English' },
]
const themeOptions = computed(() => [
  { value: 'light' as const, label: t('shell.themeLight') },
  { value: 'dark' as const, label: t('shell.themeDark') },
  { value: 'system' as const, label: t('shell.themeSystem') },
])

// Language and theme apply instantly (no reload) and save in the background.
const locale = computed({
  get: () => ui.locale,
  set: (l: Locale) => void save({ locale: l }),
})
const theme = computed({
  get: () => ui.theme,
  set: (th: ThemePref) => void save({ theme: th }),
})

async function save(patch: Parameters<typeof session.updateProfile>[0]) {
  status.value = null
  try {
    await session.updateProfile(patch)
    return true
  } catch (e) {
    status.value = { ok: false, text: t(authErrorKey(e)) }
    return false
  }
}

async function saveProfile() {
  saving.value = true
  if (await save({ display_name: profile.display_name.trim(), timezone: profile.timezone })) status.value = { ok: true, text: t('ui.saved') }
  saving.value = false
}
</script>

<template>
  <PageHeader :title="t('pages.settings')" />
  <PageContent>
    <TtAlert v-if="status" :variant="status.ok ? 'profit' : 'loss'" :title="status.text" dismissible @dismiss="status = null" />

    <TtCard :title="t('settings.profile')">
      <p class="-mt-2 mb-4 text-body-sm text-ink-muted">{{ t('settings.profileSub') }}</p>
      <form class="grid gap-4 md:grid-cols-2" @submit.prevent="saveProfile">
        <TtField :label="t('auth.displayName')">
          <TtInput v-model="profile.display_name" autocomplete="nickname" />
        </TtField>
        <TtField :label="t('auth.email')">
          <TtInput :model-value="session.user?.email" type="email" disabled />
        </TtField>
        <TtField :label="t('auth.language')">
          <TtSelect v-model="locale" :options="localeOptions" />
        </TtField>
        <TtField :label="t('auth.timezone')">
          <TtSelect v-model="profile.timezone" :options="tzOptions" />
        </TtField>
        <div class="md:col-span-2">
          <TtButton type="submit" variant="primary" :loading="saving" :disabled="!profile.display_name.trim()">{{ t('settings.saveProfile') }}</TtButton>
        </div>
      </form>
    </TtCard>

    <TtCard :title="t('settings.appearance')">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <span class="text-body">{{ t('settings.theme') }}</span>
        <TtSegmented v-model="theme" :options="themeOptions" :label="t('settings.theme')" />
      </div>
    </TtCard>

    <p class="m-0 text-body-sm text-ink-subtle">{{ t('settings.comingLater') }}</p>
  </PageContent>
</template>
