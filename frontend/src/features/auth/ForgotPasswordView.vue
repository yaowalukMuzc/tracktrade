<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AuthLayout from './AuthLayout.vue'
import AuthMobileBar from './AuthMobileBar.vue'
import TtAlert from '@/components/ui/TtAlert.vue'
import TtButton from '@/components/ui/TtButton.vue'
import TtField from '@/components/ui/TtField.vue'
import TtInput from '@/components/ui/TtInput.vue'
import { useSessionStore } from '@/stores/session'
import { authErrorKey, isEmail } from './errors'

// F-01 AC5. No mock in screens/ (PLAN §8.2): Login's split layout + one field.
// The confirmation is identical whether or not the email has an account.
const { t } = useI18n()
const route = useRoute()
const session = useSessionStore()

const form = reactive({ email: typeof route.query.email === 'string' ? route.query.email : '' })
const error = ref<string>()
const formError = ref('')
const sentTo = ref('')
const busy = ref(false)

async function submit() {
  formError.value = ''
  error.value = !form.email ? t('auth.errors.required') : !isEmail(form.email) ? t('auth.errors.email') : undefined
  if (error.value) return
  busy.value = true
  try {
    await session.requestPasswordReset(form.email.trim())
    sentTo.value = form.email.trim()
  } catch (e) {
    formError.value = t(authErrorKey(e))
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <AuthLayout>
    <AuthMobileBar />
    <div class="flex w-full flex-1 flex-col gap-6 px-6 pb-6 pt-4 lg:max-w-[400px] lg:flex-none lg:p-0">
      <div class="flex flex-col gap-1.5">
        <h1 class="m-0 text-h1">{{ t('auth.forgotTitle') }}</h1>
        <p class="m-0 text-body text-ink-muted">{{ t('auth.forgotSub') }}</p>
      </div>

      <TtAlert v-if="sentTo" variant="info" :title="t('auth.resetSentTitle')" :body="t('auth.resetSentBody', { email: sentTo })" />

      <form v-else class="flex flex-col gap-4" novalidate @submit.prevent="submit">
        <TtAlert v-if="formError" variant="loss" :title="formError" />
        <TtField :label="t('auth.email')" :error="error">
          <TtInput v-model="form.email" type="email" autocomplete="email" :placeholder="t('auth.emailPlaceholder')" />
        </TtField>
        <TtButton type="submit" variant="primary" size="lg" block :loading="busy">{{ t('auth.sendResetLink') }}</TtButton>
      </form>

      <TtButton :to="{ name: 'login' }" variant="ghost" size="lg" block>{{ t('auth.backToLogin') }}</TtButton>
    </div>
  </AuthLayout>
</template>
