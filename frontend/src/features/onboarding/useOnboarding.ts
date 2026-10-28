import { inject, provide, reactive, type InjectionKey } from 'vue'
import { useI18n } from 'vue-i18n'
import { emptyForm, type FieldErrors, type FieldKey, type OnboardingForm } from './form'

export type ImportMethod = 'mt5' | 'ctrader' | 'manual'

interface OnboardingState {
  form: OnboardingForm
  errors: FieldErrors
  /** Import method chosen on step "connect broker" — UI only until broker sync ships (F-08, Phase 4). */
  method: ImportMethod
}

const key: InjectionKey<OnboardingState> = Symbol('onboarding')

/** Created once by OnboardingView; the section components read/write the same draft. */
export function provideOnboarding() {
  const state: OnboardingState = reactive({ form: emptyForm(), errors: {}, method: 'manual' as ImportMethod })
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
