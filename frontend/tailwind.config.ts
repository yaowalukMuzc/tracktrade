import type { Config } from 'tailwindcss'
// Design source of truth — every token comes from here; never invent values.
import design from '../design-system/tailwind.config.js'

const v = (n: string) => `var(--${n})`
// JS inference widens the font-size tuples, so re-type the design config.
const base = (design as unknown as Pick<Config, 'theme'>).theme ?? {}
const ext = (base.extend ?? {}) as Record<string, Record<string, unknown>>

export default {
  darkMode: ['selector', '[data-theme="dark"]'],
  content: ['./index.html', './src/**/*.{vue,ts}'],
  theme: {
    ...base,
    extend: {
      ...ext,
      // Tokens that exist in tokens.css but are not mapped by design-system/tailwind.config.js (PLAN M3).
      colors: {
        ...ext.colors,
        chart: { ...(ext.colors?.chart as object), grid: v('chart-grid'), actual: v('chart-actual') },
        overlay: v('overlay'),
        'focus-ring': v('focus-ring'),
      },
      zIndex: { nav: v('z-nav'), sheet: v('z-sheet'), toast: v('z-toast') },
      // Layout sizes fixed by the design (screens.css): sidebar 240px, content max 1240px (PLAN M2).
      width: { sidebar: '240px' },
      maxWidth: { content: '1240px' },
    },
  },
} satisfies Config
