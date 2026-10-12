import { describe, expect, it } from 'vitest'
import { h } from 'vue'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import th from '@/i18n/locales/th.json'
import TtButton from './TtButton.vue'
import TtField from './TtField.vue'
import TtInput from './TtInput.vue'
import TtPnl from './TtPnl.vue'
import TtSegmented from './TtSegmented.vue'
import TtToggle from './TtToggle.vue'
import { MINUS } from '@/lib/format'

const i18n = createI18n({ legacy: false, locale: 'th', messages: { th } })
const global = { plugins: [i18n], stubs: { RouterLink: true } }

describe('TtPnl', () => {
  it('shows sign and direction class', () => {
    const up = mount(TtPnl, { props: { money: 420 }, global })
    expect(up.text()).toBe('+$420.00')
    expect(up.classes()).toContain('tt-pnl--up')
    const down = mount(TtPnl, { props: { money: -486, r: -1 }, global })
    expect(down.text()).toContain(`${MINUS}$486.00`)
    expect(down.text()).toContain(`${MINUS}1.0R`)
    expect(down.classes()).toContain('tt-pnl--down')
  })

  it('never renders money in r_only view (F-22 AC2)', () => {
    const w = mount(TtPnl, { props: { money: 1669.98, r: 2.4, visibility: 'r_only' }, global })
    expect(w.text()).toBe('+2.4R')
    expect(w.text()).not.toContain('$')
  })
})

describe('TtButton', () => {
  it('maps variant/size classes and disables while loading', () => {
    const w = mount(TtButton, { props: { variant: 'primary', size: 'lg', loading: true }, slots: { default: 'ล็อกแผน' }, global })
    expect(w.classes()).toEqual(expect.arrayContaining(['tt-btn', 'tt-btn--primary', 'tt-btn--lg']))
    expect(w.attributes('disabled')).toBeDefined()
  })
})

describe('TtField + TtInput', () => {
  it('links label and error to the control', () => {
    const w = mount(TtField, {
      props: { label: 'อีเมล', error: 'ไม่ถูกต้อง' },
      slots: { default: () => [TtInputH()] },
      global,
    })
    const input = w.get('input')
    expect(w.get('label').attributes('for')).toBe(input.attributes('id'))
    expect(input.attributes('aria-invalid')).toBe('true')
    expect(input.classes()).toContain('tt-input--error')
    expect(input.attributes('aria-describedby')).toBe(w.get('.tt-help').attributes('id'))
  })

  it('highlights low-confidence OCR fields (F-09 AC3)', () => {
    const w = mount(TtField, { props: { label: 'SL', lowConfidence: 'ตรวจอีกครั้ง' }, slots: { default: () => [TtInputH()] }, global })
    expect(w.get('input').classes()).toContain('tt-input--lowconf')
    expect(w.get('.tt-help').classes()).toContain('tt-help--warn')
  })
})

describe('TtSegmented', () => {
  const options = [
    { value: '$', label: '$' },
    { value: 'R', label: 'R' },
  ]
  it('selects with click and arrow keys', async () => {
    const w = mount(TtSegmented, { props: { label: 'unit', modelValue: '$', options }, global })
    const [first, second] = w.findAll('button')
    expect(first.attributes('aria-checked')).toBe('true')
    await second.trigger('click')
    await second.trigger('keydown', { key: 'ArrowRight' })
    expect(w.emitted('update:modelValue')).toEqual([['R'], ['$']])
  })
})

describe('TtToggle', () => {
  it('is a switch with aria-checked', async () => {
    const w = mount(TtToggle, { props: { label: 'Push', modelValue: false }, global })
    expect(w.attributes('role')).toBe('switch')
    expect(w.attributes('aria-checked')).toBe('false')
    await w.trigger('click')
    expect(w.emitted('update:modelValue')).toEqual([[true]])
  })
})

const TtInputH = () => h(TtInput, { modelValue: '' })
