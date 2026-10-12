import { nextTick, onBeforeUnmount, watch, type Ref } from 'vue'

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

/** Modal/Sheet behaviour: Esc closes, Tab is trapped inside, body scroll locked, focus restored on close. */
export function useDialog(open: Ref<boolean>, panel: Ref<HTMLElement | undefined>, close: () => void) {
  let restoreTo: HTMLElement | null = null

  function onKey(e: KeyboardEvent) {
    if (e.key === 'Escape') {
      e.stopPropagation()
      close()
      return
    }
    if (e.key !== 'Tab' || !panel.value) return
    const items = [...panel.value.querySelectorAll<HTMLElement>(FOCUSABLE)]
    if (!items.length) return
    const first = items[0]
    const last = items[items.length - 1]
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault()
      last.focus()
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault()
      first.focus()
    }
  }

  function teardown() {
    document.removeEventListener('keydown', onKey)
    document.body.style.overflow = ''
    restoreTo?.focus?.()
    restoreTo = null
  }

  watch(
    open,
    async (isOpen) => {
      if (!isOpen) return teardown()
      restoreTo = document.activeElement as HTMLElement | null
      document.addEventListener('keydown', onKey)
      document.body.style.overflow = 'hidden'
      await nextTick()
      const target = panel.value?.querySelector<HTMLElement>('[autofocus]') ?? panel.value
      target?.focus()
    },
    { immediate: true },
  )
  onBeforeUnmount(teardown)
}
