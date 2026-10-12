TrackTrade is a Trading Journal & Trade Lifecycle app that measures the gap between **Analysis → Plan → Execution → Outcome** across six dimensions: Analysis · Planning · Execution · Risk Management · Discipline · Emotion. The interface is soft and minimal: a pastel palette — Beige white `#F6F7F0` / `#ECE9DF`, Petal pink `#E0DADE`, Lavender `#D5B6B9` — with warm dark type, deep-rose accents for text and hairline borders instead of shadows. Strong color appears only where it carries meaning (profit, loss, warning) and in charts. It is mobile-first (375px), bilingual (ไทย / English), built with Vue 3 + Tailwind CSS, and ships light and dark themes.

## Principles

1. **Process before P/L.** Adherence and quality are shown as prominently as money, never colored by it. A Good-Loss is shown in `q-good-loss` (blue), not red.
2. **Pastel by default.** UI chrome uses the pastel set: Lavender `brand-600` fills primary actions (with dark `on-brand` text — never white), Petal pink `brand-100` marks selection, Beige whites are the grounds, and deep rose `brand-700` carries any brand-colored text, outline or thin mark (pastels are too light for text). Strong color is reserved for meaning: `profit` = up, `loss` = down or destructive, `warning` = attention/luck/pending, and for charts.
3. **Numbers are the content.** All prices, P/L, R, %, lots use tabular numerals (`tabular-nums`) and the `num*` styles; right-align them in columns.
4. **Plan-first flow.** The primary action on Today is always "สร้างแผน" (new plan); locking is a deliberate, visible moment (`PlanLock`).
5. **Never color alone.** Every P/L carries a sign (`+` / `−`), every direction says LONG/SHORT, every status has a word.

## Content fundamentals

- **Voice:** a calm coach, not a hype app. Short, factual, second person implied. "แผนนี้ยังไม่ครบ checklist 1 ข้อ" — not "อุ๊ปส์! ลืมอะไรไปหรือเปล่า? 😅".
- **Language:** Thai UI copy keeps trading terms in English where traders use them: Entry, SL, TP, Lot, R, Win rate, Profit factor, Setup, Session, Adherence. Do not transliterate (ไม่ใช้ "สต็อปลอส").
- **Casing:** English labels in sentence case ("New plan", "Avg adherence"). ALL CAPS only for `overline` labels and LONG/SHORT. Never uppercase Thai.
- **Numbers:** `4,387.52` (price digits from `symbols.digits`), `+$1,669.98`, `−1.0R` (U+2212 minus), `62.5%`, `0.13 lot`. Dates in TH locale: `9 ก.ย. 2026 · 15:00`; EN: `Sep 9, 2026 · 15:00`. Show the account timezone in tooltips.
- **No emoji** in UI copy or as decoration. Mood uses the 1–10 scale with Hugeicons `sad-01` / `neutral` / `smile`.
- **Buttons:** verb first — "ล็อกแผน", "บันทึกรีวิว", "เชื่อมต่อ MT5", "Generate report".
- **Empty states:** one sentence of what's missing + one primary action. "ยังไม่มีแผนวันนี้ — เริ่มจากวิเคราะห์ตลาด" → [สร้าง Analysis].

## Color

The palette is pastel and warm. `bg` (Beige white) is the page, `surface` (white) the cards; `ink`, `ink-muted`, `ink-subtle` are the only text colors on them (all ≥ 4.5:1 in both themes). Cards are separated by `border` alone — `shadow-sm` is `none`.

| Role | Tokens | Rule |
| --- | --- | --- |
| Pastel brand | `brand-600` Lavender `#D5B6B9` (primary fill) + `on-brand` dark text, `brand-hover`, `brand-100` Petal pink `#E0DADE` (selected ground), `brand-50` (wash), `brand-200` (outline), `surface-sunken` Beige white `#ECE9DF`, `bg` Beige white `#F6F7F0` | Primary buttons, FAB, locked badge, selected chips, active nav ground. One primary button per screen. |
| Deep rose | `brand-700` `#7A4A52` (dark theme `#E3C7CA`), `on-accent` | All brand-colored TEXT and thin marks: links, ghost buttons, active tab/nav, toggles, checkboxes, meters, focus ring, wordmark. |
| Accent | `gold-500`, `gold-100`, `gold-ink` | Only for PRO / upgrade. Use sparingly. |
| Profit | `profit`, `profit-100`, `profit-ink` | Positive P/L, win, Good-Win, bullish bias, LONG badge. |
| Loss | `loss`, `loss-100`, `loss-ink` | Negative P/L, Bad-Loss, bearish bias, SHORT badge, rule breach, destructive. |
| Warning | `warning`, `warning-100`, `warning-ink` | Bad-Win (luck), skipped/missed, pending match, unplanned, news, OCR low confidence. |
| Quadrants | `q-good-win`, `q-good-loss`, `q-bad-win`, `q-bad-loss` | Aliases of profit/chart-cobalt/warning/loss — use the `q-*` names so meaning survives a palette change. |
| Dimensions | `dim-analysis`, `dim-planning`, `dim-execution`, `dim-risk`, `dim-discipline`, `dim-emotion` | Marks only (bars, dots, swatches) in that fixed order; labels stay `ink`. |
| Chart | `chart-up`, `chart-down`, `chart-grid`, `chart-plan` (dashed), `chart-actual`, `chart-area`, `brand-500` | TradingView Lightweight Charts theme. Plan lines dashed `chart-plan`, actual fills solid `chart-actual`, equity curve `brand-500` over `chart-area`. `brand-500` (cobalt) lives in charts only. |

Profit and loss sit at similar lightness, so they are never told apart by hue alone: sign, arrow icon or word is mandatory. In charts LONG/SHORT markers carry the word.

## Typography

One stack, two scripts: `--font-sans` is `Inter, Anuphan, …`. Latin and digits render in **Inter**, Thai glyphs fall through to **Anuphan** automatically — never set Thai text in a different stack by hand. Load both from Google Fonts:

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Anuphan:wght@300;400;500;600;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
```

- Body copy is `body` (15/24). The 1.6 line-height is deliberate: Thai upper vowels and tone marks need it. Don't go below 1.5 for any Thai text.
- Page titles: `h2` on mobile, `h1` on desktop. Card titles `h3`. Stat labels `caption`. English section labels `overline`.
- Numbers: `display` (hero P/L), `num-lg` (stat tiles), `num` (lists, inputs), `num-sm` (calendar, badges). Always `tabular-nums`.
- Weights: 400 body, 500 labels, 600 titles and numbers, 700 display/wordmark only.

## Spacing, layout, radius, elevation

- 4px grid via `space-*` (Tailwind's default scale). Page gutter `space-4` on mobile, `space-6` ≥ 768px. Card padding `space-4` (mobile) / `space-5` (desktop). Gap between cards `space-3` mobile, `space-6` desktop.
- Breakpoints (Tailwind defaults): mobile < 768 single column + BottomNav; `md` 768 two columns; `lg` 1024 left sidebar (240px) replaces BottomNav, content max 1200px.
- Touch targets ≥ 44px (`tt-btn` default height). Sticky bottom CTA on forms (`tt-btn--lg --block`) above the BottomNav.
- Radius: `radius-sm` badges & calendar cells, `radius-md` controls, `radius-lg` cards, `radius-xl` sheets/modals, `radius-full` chips.
- Elevation: cards sit on `bg` with a `border` hairline and no shadow; sheets/modals use `shadow-lg` over `overlay`; floating buttons `shadow-md`. No other shadows, no gradients.
- Focus: 2px solid `focus-ring`, 2px offset, on every interactive element.
- Motion: 150ms ease for color/background; 250ms ease-out for sheets sliding up. Respect `prefers-reduced-motion`.

## Iconography

- **Hugeicons — Stroke Rounded, free set** (`@hugeicons/core-free-icons` + `@hugeicons/vue`). 24×24 grid, 1.5px stroke, round caps/joins, `currentColor`.
- Sizes: 16px inside badges/chips/small buttons, 20px in buttons, fields and lists, 24px in BottomNav and empty states. Never mix filled or other icon families.
- Icons inherit text color; a lone icon button needs an `aria-label`.
- Canonical mapping (the `Icons` asset group holds these as SVG references):

| Concept | Icon | Concept | Icon |
| --- | --- | --- | --- |
| Today | `home-01` | Calendar | `calendar-03` |
| Trades | `chart-candlestick` | Performance | `analytics-01` |
| Journal / Review | `note-edit` | Playbook | `book-02` |
| Analysis | `chart-line-data-01` | Plan | `target-02` |
| Plan locked / unlock | `square-lock-02` / `square-unlock-02` | Checklist | `check-list` |
| AI Coach | `ai-magic` / `ai-brain-01` | Screenshot scan | `ai-scan` |
| Alerts | `notification-01` | News | `news-01` |
| Accounts | `wallet-01` | Connection | `plug-01` / `link-01` |
| Risk | `shield-01` | Mentor | `teacher` / `user-group` |
| Rule breach | `alert-02` | Execution / fill | `exchange-01` |
| Mood | `sad-01` · `neutral` · `smile` | Settings | `settings-02` |

```vue
<script setup>
import { HugeiconsIcon } from '@hugeicons/vue'
import { SquareLock02Icon } from '@hugeicons/core-free-icons'
</script>
<template>
  <button class="tt-btn tt-btn--primary">
    <HugeiconsIcon :icon="SquareLock02Icon" :size="20" :stroke-width="1.5" />ล็อกแผน
  </button>
</template>
```

## Logo

There is no logo file yet. Set the name as the type wordmark `tt-wordmark`: "Track**Trade**", Inter 700, −2% tracking, "Track" in `ink` and "Trade" in `brand-700` (deep rose). Don't draw a mark until one is supplied.

## Tailwind setup

Tokens are CSS custom properties (light on `:root`, dark on `[data-theme="dark"]`); Tailwind reads them so utilities switch with the theme. Use `darkMode: ['selector', '[data-theme="dark"]']`.

```js
// tailwind.config.js
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
```

Component classes (`tt-btn`, `tt-card`, `tt-pnl`…) live in `components/bundle.css`; port them to `@layer components` with `@apply`, or use the Tailwind recipe in each component's guideline. Example: a stat tile is `rounded-lg border border-border bg-surface px-4 py-3` + `text-caption text-ink-muted` + `text-num-lg tabular-nums`.

## Screen patterns

- **Root screens** (วันนี้, ปฏิทิน, เทรด, สถิติ, เพิ่มเติม): AppBar with wordmark + account switcher + alerts; BottomNav.
- **Forms** (Analysis, Plan, Manual trade, Review, OCR confirm): AppBar with back + title; sections as cards; sticky bottom primary CTA.
- **Detail** (Trade, Plan, Setup): hero summary card (symbol, direction, P/L, scores) → Tabs → content.
- **Sheets** for quick logging (in-trade emotion prompt, daily mood, revision reason, day detail) slide up with `radius-xl` top corners.
- **Mentor view** is read-only: hide edit actions, show a "Mentor view · R only" `tt-badge--brand` in the AppBar when `pnl_visibility = r_only`.
