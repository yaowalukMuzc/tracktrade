<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AuthLayout from './AuthLayout.vue'
import LocaleSwitch from '@/components/shell/LocaleSwitch.vue'
import TtAlert from '@/components/ui/TtAlert.vue'
import TtButton from '@/components/ui/TtButton.vue'
import TtCheckbox from '@/components/ui/TtCheckbox.vue'
import TtField from '@/components/ui/TtField.vue'
import TtInput from '@/components/ui/TtInput.vue'
import { useSessionStore } from '@/stores/session'
import { safeRedirect } from '@/router/guards'
import { authErrorKey, isEmail } from './errors'

// screens/web/01-WLogin.png + screens/mobile/01-Main.png (F-01 AC2).
const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const session = useSessionStore()

const form = reactive({ email: '', password: '', remember: true })
const errors = reactive<{ email?: string; password?: string }>({})
const formError = ref('')
const notice = ref('')
const busy = ref(false)

function validate() {
  errors.email = !form.email ? t('auth.errors.required') : !isEmail(form.email) ? t('auth.errors.email') : undefined
  errors.password = !form.password ? t('auth.errors.required') : undefined
  return !errors.email && !errors.password
}

async function submit() {
  formError.value = ''
  if (!validate()) return
  busy.value = true
  try {
    await session.login(form.email.trim(), form.password, form.remember)
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
    <!-- Mobile header: wordmark + language -->
    <div class="flex items-center justify-between px-6 py-5 lg:hidden">
      <span class="tt-wordmark text-[22px]">Track<b>Trade</b></span>
      <LocaleSwitch />
    </div>

    <div class="flex w-full flex-1 flex-col gap-6 px-6 pb-6 pt-8 lg:max-w-[400px] lg:flex-none lg:p-0">
      <div class="flex flex-col gap-2">
        <div class="flex items-center justify-between gap-3">
          <h1 class="m-0 text-h1">{{ t('auth.login') }}</h1>
          <LocaleSwitch class="hidden lg:inline-flex" />
        </div>
        <p class="m-0 text-body text-ink-muted lg:hidden">{{ t('auth.pitchShort') }}</p>
      </div>

      <form class="flex flex-col gap-4" novalidate @submit.prevent="submit">
        <TtAlert v-if="formError" variant="loss" :title="formError" />
        <TtAlert v-if="notice" variant="info" :body="notice" dismissible @dismiss="notice = ''" />
        <TtField :label="t('auth.email')" :error="errors.email">
          <TtInput v-model="form.email" type="email" autocomplete="email" :placeholder="t('auth.emailPlaceholder')" />
        </TtField>
        <TtField :label="t('auth.password')" :error="errors.password">
          <TtInput v-model="form.password" type="password" autocomplete="current-password" revealable />
        </TtField>
        <div class="flex items-center justify-between gap-3">
          <TtCheckbox v-model="form.remember">{{ t('auth.remember') }}</TtCheckbox>
          <button type="button" class="tt-link border-0 bg-transparent p-0 text-[14px]" @click="notice = t('auth.forgotSoon')">
            {{ t('auth.forgot') }}
          </button>
        </div>
        <TtButton type="submit" variant="primary" size="lg" block :loading="busy">{{ t('auth.login') }}</TtButton>
      </form>

      <div class="flex items-center gap-3 text-[13px] text-ink-subtle">
        <span class="tt-divider flex-1" />
        <span class="lg:hidden">{{ t('auth.or') }}</span>
        <span class="hidden lg:inline">{{ t('auth.noAccount') }}</span>
        <span class="tt-divider flex-1" />
      </div>
      <TtButton :to="{ name: 'register', query: route.query }" variant="secondary" size="lg" block>
        <span class="lg:hidden">{{ t('auth.createAccount') }}</span>
        <span class="hidden lg:inline">{{ t('auth.createAccountFree') }}</span>
      </TtButton>

      <p class="m-0 hidden text-center text-caption text-ink-subtle lg:block">{{ t('auth.privacyLine') }}</p>
      <TtAlert class="mt-auto text-[13px] leading-5 lg:hidden" icon="risk" :title="t('auth.privacyTitle')" :body="t('auth.privacyBody')" />
    </div>
  </AuthLayout>
</template>
