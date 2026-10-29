import { inject, provide, reactive, type InjectionKey } from 'vue'
import { useI18n } from 'vue-i18n'
import type { Account } from '@/api/accounts'
import { emptyForm, type FieldErrors, type FieldKey, type OnboardingForm } from './form'

export type ImportMethod = 'mt5' | 'ctrader' | 'manual'

interface OnboardingState {
  form: OnboardingForm
  errors: FieldErrors
  /** How trades will arrive; follows the account's platform (MT5 → EA, cTrader → OAuth, manual → screenshot). */
  method: ImportMethod
  /** The account once saved — the broker step needs it for the API key / cTrader link (F-08 AC1). */
  account: Account | null
  /** The EA key, shown in full only here, right after it was created. */
  apiKey: string | null
  /** The EA delivered its first deal (WS `sync.first_deal`). */
  firstDeal: boolean
}

const key: InjectionKey<OnboardingState> = Symbol('onboarding')

/** Created once by OnboardingView; the section components read/write the same draft. */
export function provideOnboarding() {
  const state: OnboardingState = reactive({
    form: emptyForm(),
    errors: {},
    method: 'mt5' as ImportMethod,
    account: null,
    apiKey: null,
    firstDeal: false,
  })
  provide(key, state)
  return state
}

export function useOnboarding() {
  const state = inject(key)
  if (!state) throw new Error('useOnboarding() outside OnboardingView')
  const { t } = useI18n()
  /** Localized validation message for one field (undefined = valid). */
  const errorOf = (f: FieldKey) => {
    const e = state.errors[f]
    return e ? t(`onboarding.errors.${e.key}`, e.params ?? {}) : undefined
  }
  return { state, errorOf, t }
}
