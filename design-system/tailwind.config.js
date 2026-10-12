// TrackTrade — Tailwind config (reads CSS variables from tokens.css)
const v = (n) => `var(--${n})`
export default {
  darkMode: ['selector', '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        bg: v('bg'), surface: { DEFAULT: v('surface'), raised: v('surface-raised'), sunken: v('surface-sunken') },
        border: { DEFAULT: v('border'), strong: v('border-strong') },
        ink: { DEFAULT: v('ink'), muted: v('ink-muted'), subtle: v('ink-subtle'), inverse: v('ink-inverse') },
        brand: { 50: v('brand-50'), 100: v('brand-100'), 200: v('brand-200'), 500: v('brand-500'), 600: v('brand-600'), 700: v('brand-700'), hover: v('brand-hover') },
        'on-brand': v('on-brand'), 'on-accent': v('on-accent'),
        gold: { 100: v('gold-100'), 500: v('gold-500'), ink: v('gold-ink') },
        profit: { DEFAULT: v('profit'), 100: v('profit-100'), ink: v('profit-ink') },
        loss: { DEFAULT: v('loss'), 100: v('loss-100'), ink: v('loss-ink') },
        warning: { DEFAULT: v('warning'), 100: v('warning-100'), ink: v('warning-ink') },
        chart: { area: v('chart-area'), plan: v('chart-plan'), up: v('chart-up'), down: v('chart-down') },
        q: { 'good-win': v('q-good-win'), 'good-loss': v('q-good-loss'), 'bad-win': v('q-bad-win'), 'bad-loss': v('q-bad-loss') },
        dim: { analysis: v('dim-analysis'), planning: v('dim-planning'), execution: v('dim-execution'), risk: v('dim-risk'), discipline: v('dim-discipline'), emotion: v('dim-emotion') },
      },
      fontFamily: { sans: ['Inter', 'Anuphan', 'system-ui', 'sans-serif'] },
      fontSize: {
        display: ['32px', { lineHeight: '40px', fontWeight: '700', letterSpacing: '-0.02em' }],
        h1: ['24px', { lineHeight: '32px', fontWeight: '700' }],
        h2: ['20px', { lineHeight: '30px', fontWeight: '600' }],
        h3: ['16px', { lineHeight: '24px', fontWeight: '600' }],
        body: ['15px', '24px'], 'body-sm': ['13px', '20px'],
        caption: ['12px', { lineHeight: '18px', fontWeight: '500' }],
        overline: ['11px', { lineHeight: '16px', fontWeight: '600', letterSpacing: '0.06em' }],
        'num-lg': ['24px', { lineHeight: '32px', fontWeight: '600' }], num: ['15px', { lineHeight: '22px', fontWeight: '600' }], 'num-sm': ['12px', { lineHeight: '16px', fontWeight: '600' }],
      },
      borderRadius: { sm: '6px', md: '10px', lg: '14px', xl: '20px' },
      boxShadow: { sm: v('shadow-sm'), md: v('shadow-md'), lg: v('shadow-lg') },
    },
  },
}
