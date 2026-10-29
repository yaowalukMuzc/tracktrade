<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppIcon from '@/components/AppIcon.vue'
import TtAlert from '@/components/ui/TtAlert.vue'
import TtButton from '@/components/ui/TtButton.vue'
import TtStepper from '@/components/ui/TtStepper.vue'
import { useDesktop } from '@/composables/useDesktop'
import { safeRedirect, skipOnboarding } from '@/router/guards'
import { accountsApi } from '@/api/accounts'
import { useAccountsStore } from '@/stores/accounts'
import { useSessionStore } from '@/stores/session'
import AccountSection from './AccountSection.vue'
import BrokerStep from './BrokerStep.vue'
import ImportSection from './ImportSection.vue'
import RiskSection from './RiskSection.vue'
import { apiErrors, toPayload, validate, type FieldError, type FieldErrors } from './form'
import { provideOnboarding } from './useOnboarding'

// screens/web/02-WOnboarding.png (account + risk + import method, then the broker step) and
// screens/mobile/03-Onboarding.png → 04-ConnectBroker.png (two steps). F-02 AC1–AC2, F-08 AC1.
// The account is saved before the broker step: the EA key / cTrader link belong to it. Going back and saving
// again updates that account instead of creating a second one.
// Full-screen flow outside AppLayout: no sidebar / bottom nav.
const state = provideOnboarding()
const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const accounts = useAccountsStore()
const session = useSessionStore()
const desktop = useDesktop()

/** 1 = account & risk (+ import method on desktop), 2 = broker step. */
const step = ref<1 | 2>(1)
const busy = ref(false)
const attempted = ref(false)
const formError = ref<FieldError | null>(null)
const target = computed(() => safeRedirect(route.query.redirect))

const desktopSteps = computed(() => [
  { title: t('onboarding.steps.user'), subtitle: session.user?.email },
  { title: t('onboarding.steps.account'), subtitle: t('onboarding.steps.accountSub') },
  { title: t('onboarding.steps.broker'), subtitle: t('onboarding.steps.brokerSub') },
])
const mobileSteps = computed(() => [{ title: t('onboarding.steps.account') }, { title: t('onboarding.steps.broker') }])

function setErrors(e: FieldErrors) {
  for (const k of Object.keys(state.errors)) delete state.errors[k as keyof FieldErrors]
  Object.assign(state.errors, e)
}

// After the first attempt, messages follow the input live.
watch(
  () => state.form,
  (f) => attempted.value && setErrors(validate(f)),
  { deep: true },
)

async function focusFirstInvalid() {
  await nextTick()
  document.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus()
}

async function goTo(n: 1 | 2) {
  step.value = n
  await nextTick()
  window.scrollTo({ top: 0 })
  document.getElementById('ob-heading')?.focus()
}

/** Validates the draft; on failure shows the messages (on step 1) and focuses the first invalid field. */
function check() {
  attempted.value = true
  const e = validate(state.form)
  setErrors(e)
  if (Object.keys(e).length === 0) return true
  if (step.value !== 1) void goTo(1).then(focusFirstInvalid)
  else void focusFirstInvalid()
  return false
}

/** First save: one call creates the account with its risk profile. Later: update account + profile. */
async function saveAccount() {
  const body = toPayload(state.form)
  if (!state.account) {
    state.account = await accounts.create(body)
    return
  }
  const { risk_profile, ...fields } = body
  const updated = await accountsApi.update(state.account.id, fields)
  if (risk_profile) await accountsApi.saveRiskProfile(updated.id, risk_profile)
  if (updated.platform !== state.account.platform) state.apiKey = null
  accounts.upsert(updated)
  state.account = updated
}

async function submit() {
  formError.value = null
  if (step.value === 2) {
    await router.replace(target.value)
    return
  }
  if (!check()) return
  busy.value = true
  try {
    await saveAccount()
    // Desktop with "Screenshot / manual" has nothing to connect: done.
    if (desktop.value && state.method === 'manual') await router.replace(target.value)
    else await goTo(2)
  } catch (e) {
    const { fields, form } = apiErrors(e)
    setErrors(fields)
    formError.value = form ?? null
    if (Object.keys(fields).length && !desktop.value) await goTo(1)
    await focusFirstInvalid()
  } finally {
    busy.value = false
  }
}

async function skip() {
  skipOnboarding()
  await router.replace(target.value)
}

const errorText = computed(() => (formError.value ? t(`onboarding.errors.${formError.value.key}`) : ''))
const desktopSave = computed(() => (state.method === 'manual' ? t('onboarding.save') : t('onboarding.saveConnect')))
</script>

<template>
  <div class="flex min-h-dvh flex-col bg-bg text-ink">
    <!-- ≥1024px: wordmark bar with progress + skip -->
    <header v-if="desktop" class="sticky top-0 z-30 flex items-center gap-3 border-b border-border bg-surface px-8 py-4">
      <span class="tt-wordmark text-[20px]">Track<b>Trade</b></span>
      <span class="flex-1" />
      <span class="text-caption text-ink-muted">{{ t('onboarding.stepOf', { n: step + 1, total: 3 }) }}</span>
      <TtButton variant="ghost" size="sm" @click="skip">{{ t('onboarding.skip') }}</TtButton>
    </header>
    <!-- <1024px: app bar + progress bar -->
    <div v-else class="sticky top-0 z-30">
      <header class="tt-appbar !border-b-0">
        <button v-if="step === 2" type="button" class="tt-iconbtn tt-iconbtn--bare -ml-2" :aria-label="t('shell.back')" @click="goTo(1)">
          <AppIcon name="back" />
        </button>
        <h1 class="tt-appbar__title">{{ step === 1 ? t('onboarding.mobileTitle') : t('onboarding.broker.mobileTitle') }}</h1>
        <span class="text-caption text-ink-muted tabular-nums">{{ t('onboarding.stepCount', { n: step, total: 2 }) }}</span>
        <TtButton v-if="step === 1" variant="ghost" size="sm" class="-mr-2" @click="skip">{{ t('onboarding.skip') }}</TtButton>
      </header>
      <TtStepper variant="bar" :steps="mobileSteps" :current="step - 1" :label="t('onboarding.progress')" />
    </div>

    <form class="flex flex-1 flex-col" novalidate @submit.prevent="submit">
      <div v-if="desktop" class="mx-auto flex w-full max-w-content items-start gap-6 px-8 pb-10 pt-6">
        <aside class="w-60 flex-none">
          <TtStepper :steps="desktopSteps" :current="step" :label="t('onboarding.progress')" :done-label="t('onboarding.done')" />
        </aside>
        <div v-if="step === 1" class="flex min-w-0 flex-1 flex-col gap-6">
          <div>
            <h1 id="ob-heading" tabindex="-1" class="m-0 text-h1 outline-none">{{ t('onboarding.title') }}</h1>
            <p class="m-0 text-body text-ink-muted">{{ t('onboarding.sub') }}</p>
          </div>
          <TtAlert v-if="errorText" variant="loss" :title="errorText" />
          <div class="grid items-start gap-6 [grid-template-columns:repeat(auto-fit,minmax(min(100%,340px),1fr))]">
            <AccountSection />
            <RiskSection />
          </div>
          <ImportSection />
          <div class="flex justify-end gap-3">
            <TtButton type="submit" variant="primary" size="lg" :loading="busy">{{ desktopSave }}</TtButton>
          </div>
        </div>
        <div v-else class="flex min-w-0 max-w-[720px] flex-1 flex-col gap-6">
          <div>
            <h1 id="ob-heading" tabindex="-1" class="m-0 text-h1 outline-none">{{ t('onboarding.broker.heading') }}</h1>
            <p class="m-0 text-body text-ink-muted">{{ t('onboarding.broker.sub') }}</p>
          </div>
          <BrokerStep />
          <div class="flex justify-end gap-3">
            <TtButton variant="secondary" size="lg" @click="goTo(1)">{{ t('onboarding.back') }}</TtButton>
            <TtButton type="submit" variant="primary" size="lg">{{ t('onboarding.start') }}</TtButton>
          </div>
        </div>
      </div>

      <template v-else>
        <div class="flex flex-1 flex-col gap-4 p-4">
          <div class="flex flex-col gap-2.5">
            <h2 id="ob-heading" tabindex="-1" class="m-0 text-h2 outline-none">
              {{ step === 1 ? t('onboarding.mobileHeading') : t('onboarding.broker.heading') }}
            </h2>
            <p class="m-0 text-body-sm text-ink-muted">{{ step === 1 ? t('onboarding.sub') : t('onboarding.broker.sub') }}</p>
          </div>
          <TtAlert v-if="errorText" variant="loss" :title="errorText" />
          <template v-if="step === 1">
            <AccountSection />
            <RiskSection />
          </template>
          <BrokerStep v-else />
        </div>
        <div class="sticky bottom-0 flex flex-col gap-2 border-t border-border bg-surface px-4 pb-4 pt-3">
          <TtButton type="submit" variant="primary" size="lg" block :loading="busy">
            {{ step === 1 ? t('onboarding.next') : t('onboarding.start') }}
          </TtButton>
          <TtButton v-if="step === 2" variant="ghost" block @click="skip">{{ t('onboarding.skip') }}</TtButton>
        </div>
      </template>
    </form>
  </div>
</template>
