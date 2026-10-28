<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AuthLayout from './AuthLayout.vue'
import AuthMobileBar from './AuthMobileBar.vue'
import TtAlert from '@/components/ui/TtAlert.vue'
import TtButton from '@/components/ui/TtButton.vue'
import TtField from '@/components/ui/TtField.vue'
import TtInput from '@/components/ui/TtInput.vue'
import { useSessionStore } from '@/stores/session'
import { authErrorKey, MIN_PASSWORD } from './errors'

// F-01 AC6: link from the reset email (`/reset-password?token=…`, 1 hour, single use).
// Success signs out every device, so the user logs in again with the new password.
const { t } = useI18n()
const route = useRoute()
const session = useSessionStore()

const token = computed(() => (typeof route.query.token === 'string' ? route.query.token : ''))
const form = reactive({ password: '', confirm: '' })
const errors = reactive<{ password?: string; confirm?: string }>({})
const formError = ref('')
const linkInvalid = ref(false)
const done = ref(false)
const busy = ref(false)

function validate() {
  errors.password = form.password.length < MIN_PASSWORD ? t('auth.passwordMin', { n: form.password.length }) : undefined
  errors.confirm = form.confirm !== form.password ? t('auth.errors.password_mismatch') : undefined
  return !errors.password && !errors.confirm
}

async function submit() {
  formError.value = ''
  if (!validate()) return
  busy.value = true
  try {
    await session.resetPassword(token.value, form.password)
    done.value = true
  } catch (e) {
    const key = authErrorKey(e)
    if (key === 'auth.errors.reset_link_invalid') linkInvalid.value = true
    else formError.value = t(key)
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
        <h1 class="m-0 text-h1">{{ t('auth.resetTitle') }}</h1>
        <p v-if="!done && token && !linkInvalid" class="m-0 text-body text-ink-muted">{{ t('auth.resetSub') }}</p>
      </div>

      <template v-if="done">
        <TtAlert variant="profit" :title="t('auth.resetDoneTitle')" :body="t('auth.resetDoneBody')" />
        <TtButton :to="{ name: 'login' }" variant="primary" size="lg" block>{{ t('auth.login') }}</TtButton>
      </template>

      <template v-else-if="!token || linkInvalid">
        <TtAlert variant="loss" :title="t('auth.errors.reset_link_invalid')" :body="t('auth.resetLinkInvalidBody')" />
        <TtButton :to="{ name: 'forgot-password' }" variant="primary" size="lg" block>{{ t('auth.requestNewLink') }}</TtButton>
      </template>

      <form v-else class="flex flex-col gap-4" novalidate @submit.prevent="submit">
        <TtAlert v-if="formError" variant="loss" :title="formError" />
        <TtField :label="t('auth.newPassword')" :error="errors.password">
          <TtInput v-model="form.password" type="password" autocomplete="new-password" revealable />
        </TtField>
        <TtField :label="t('auth.confirmPassword')" :error="errors.confirm">
          <TtInput v-model="form.confirm" type="password" autocomplete="new-password" revealable />
        </TtField>
        <TtButton type="submit" variant="primary" size="lg" block :loading="busy">{{ t('auth.setNewPassword') }}</TtButton>
      </form>

      <TtButton v-if="!done" :to="{ name: 'login' }" variant="ghost" size="lg" block>{{ t('auth.backToLogin') }}</TtButton>
    </div>
  </AuthLayout>
</template>
