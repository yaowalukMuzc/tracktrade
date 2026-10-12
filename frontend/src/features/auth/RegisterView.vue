<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AuthLayout from './AuthLayout.vue'
import AppIcon from '@/components/AppIcon.vue'
import TtAlert from '@/components/ui/TtAlert.vue'
import TtButton from '@/components/ui/TtButton.vue'
import TtCheckbox from '@/components/ui/TtCheckbox.vue'
import TtField from '@/components/ui/TtField.vue'
import TtInput from '@/components/ui/TtInput.vue'
import TtSelect from '@/components/ui/TtSelect.vue'
import { useSessionStore } from '@/stores/session'
import { useUiStore } from '@/stores/ui'
import { safeRedirect } from '@/router/guards'
import { timezoneOptions, browserTimezone } from '@/lib/timezones'
import type { Locale } from '@/i18n'
import { authErrorKey, isEmail, passwordStrength } from './errors'

// screens/mobile/02-Register.png; desktop reuses the Login split layout (PLAN §8.2). F-01 AC1, AC3.
const MIN_PASSWORD = 8
const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const session = useSessionStore()
const ui = useUiStore()

const form = reactive({
  display_name: '',
  email: '',
  password: '',
  locale: ui.locale as Locale,
  timezone: browserTimezone(),
  accept_terms: false,
})
const touched = reactive({ password: false })
const errors = reactive<{ display_name?: string; email?: string; password?: string; terms?: string }>({})
const formError = ref('')
const busy = ref(false)

const localeOptions = [
  { value: 'th' as const, label: 'ไทย' },
  { value: 'en' as const, label: 'English' },
]
const tzOptions = computed(() => timezoneOptions(form.timezone))

// Choosing a language switches the UI right away (F-01 AC3).
watch(() => form.locale, (l) => ui.setLocale(l))

const strength = computed(() => passwordStrength(form.password))
const strengthKey = computed(() => (['weak', 'weak', 'fair', 'good', 'strong'] as const)[strength.value])
const barClass = computed(() => (strength.value <= 2 ? 'bg-warning' : 'bg-brand-700'))
const passwordHint = computed(() =>
  form.password.length > 0 && form.password.length < MIN_PASSWORD ? t('auth.passwordMin', { n: form.password.length }) : undefined,
)

function validate() {
  errors.display_name = form.display_name.trim() ? undefined : t('auth.errors.required')
  errors.email = !form.email ? t('auth.errors.required') : !isEmail(form.email) ? t('auth.errors.email') : undefined
  errors.password = form.password.length < MIN_PASSWORD ? t('auth.passwordMin', { n: form.password.length }) : undefined
  errors.terms = form.accept_terms ? undefined : t('auth.errors.terms')
  return !errors.display_name && !errors.email && !errors.password && !errors.terms
}

async function submit() {
  formError.value = ''
  touched.password = true
  if (!validate()) return
  busy.value = true
  try {
    await session.register({ ...form, email: form.email.trim(), display_name: form.display_name.trim() })
    await router.replace(safeRedirect(route.query.redirect))
  } catch (e) {
    formError.value = t(authErrorKey(e))
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <AuthLayout>
    <!-- Mobile app bar: back + centered wordmark -->
    <div class="tt-appbar border-0 lg:hidden">
      <RouterLink :to="{ name: 'login', query: route.query }" class="tt-iconbtn tt-iconbtn--bare" :aria-label="t('shell.back')">
        <AppIcon name="back" />
      </RouterLink>
      <span class="flex-1" />
      <span class="tt-wordmark">Track<b>Trade</b></span>
      <span class="flex-1" />
      <span class="w-10" />
    </div>

    <form class="flex w-full flex-1 flex-col gap-5 px-6 pb-6 pt-4 lg:max-w-[400px] lg:flex-none lg:p-0" novalidate @submit.prevent="submit">
      <div class="flex flex-col gap-1.5">
        <h1 class="m-0 text-h1">{{ t('auth.registerTitle') }}</h1>
        <p class="m-0 text-body text-ink-muted">{{ t('auth.registerSub') }}</p>
      </div>

      <TtAlert v-if="formError" variant="loss" :title="formError" />

      <TtField :label="t('auth.displayName')" :error="errors.display_name">
        <TtInput v-model="form.display_name" autocomplete="nickname" />
      </TtField>
      <TtField :label="t('auth.email')" :error="errors.email">
        <TtInput v-model="form.email" type="email" autocomplete="email" :placeholder="t('auth.emailPlaceholder')" />
      </TtField>
      <TtField :label="t('auth.password')" :error="errors.password ?? (touched.password ? passwordHint : undefined)">
        <TtInput v-model="form.password" type="password" autocomplete="new-password" revealable @blur="touched.password = true" />
        <template #after>
          <div
            class="mt-1 grid grid-cols-4 gap-1"
            role="meter"
            :aria-label="t('auth.strength.label')"
            aria-valuemin="0"
            aria-valuemax="4"
            :aria-valuenow="strength"
            :aria-valuetext="t(`auth.strength.${strengthKey}`)"
          >
            <i v-for="n in 4" :key="n" class="h-1 rounded-sm" :class="n <= strength ? barClass : 'bg-surface-sunken'" />
          </div>
          <span v-if="!errors.password && !(touched.password && passwordHint) && form.password" class="tt-help">
            {{ t(`auth.strength.${strengthKey}`) }}
          </span>
        </template>
      </TtField>

      <div class="grid grid-cols-2 gap-3">
        <TtField :label="t('auth.language')">
          <TtSelect v-model="form.locale" :options="localeOptions" />
        </TtField>
        <TtField :label="t('auth.timezone')">
          <TtSelect v-model="form.timezone" :options="tzOptions" />
        </TtField>
      </div>

      <div class="flex flex-col gap-1">
        <TtCheckbox v-model="form.accept_terms" :aria-invalid="!!errors.terms || undefined">
          <i18n-t keypath="auth.acceptTerms" tag="span" scope="global">
            <template #terms><a href="#" class="tt-link font-normal underline" @click.prevent>{{ t('auth.terms') }}</a></template>
            <template #privacy><a href="#" class="tt-link font-normal underline" @click.prevent>{{ t('auth.privacy') }}</a></template>
          </i18n-t>
        </TtCheckbox>
        <span v-if="errors.terms" class="tt-help tt-help--error" role="alert">{{ errors.terms }}</span>
      </div>

      <div class="mt-auto flex flex-col items-center gap-3 pt-4 lg:mt-2 lg:pt-0">
        <TtButton type="submit" variant="primary" size="lg" block :loading="busy">{{ t('auth.register') }}</TtButton>
        <span class="text-[14px] text-ink-muted">
          {{ t('auth.haveAccount') }}
          <RouterLink :to="{ name: 'login', query: route.query }" class="tt-link">{{ t('auth.login') }}</RouterLink>
        </span>
      </div>
    </form>
  </AuthLayout>
</template>
