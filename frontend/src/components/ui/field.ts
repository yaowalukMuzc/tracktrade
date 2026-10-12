import { computed, inject, type ComputedRef, type InjectionKey } from 'vue'

/** Shared by TtField and its control (TtInput/TtSelect/TtTextarea) so label, help and state stay linked. */
export interface FieldContext {
  id: string
  helpId: string
  invalid: ComputedRef<boolean>
  lowConfidence: ComputedRef<boolean>
  hasHelp: ComputedRef<boolean>
  required: ComputedRef<boolean>
}

export const fieldKey: InjectionKey<FieldContext> = Symbol('tt-field')

/** Control-side helper: merges the surrounding field's state with the control's own props. */
export function useFieldControl(props: { id?: string; error?: boolean; lowConfidence?: boolean }) {
  const field = inject(fieldKey, null)
  const id = computed(() => props.id ?? field?.id)
  const invalid = computed(() => !!props.error || !!field?.invalid.value)
  const lowConf = computed(() => !!props.lowConfidence || !!field?.lowConfidence.value)
  const stateClass = computed(() => ({ 'tt-input--error': invalid.value, 'tt-input--lowconf': lowConf.value && !invalid.value }))
  const aria = computed(() => ({
    id: id.value,
    'aria-invalid': invalid.value || undefined,
    'aria-describedby': field?.hasHelp.value ? field.helpId : undefined,
    'aria-required': field?.required.value || undefined,
  }))
  return { stateClass, aria }
}
