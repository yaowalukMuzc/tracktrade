import type { Config } from 'tailwindcss'
// Design source of truth — every token comes from here; never invent values.
import design from '../design-system/tailwind.config.js'

export default {
  // JS inference widens the font-size tuples, so re-type the design config.
  theme: (design as unknown as Pick<Config, 'theme'>).theme,
  darkMode: ['selector', '[data-theme="dark"]'],
  content: ['./index.html', './src/**/*.{vue,ts}'],
} satisfies Config
