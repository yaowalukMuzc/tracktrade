# TrackTrade — Design handoff for implementation

TrackTrade is a Trading Journal & Trade Lifecycle web app (Analysis → Plan → Execution → Outcome, measured across 6 dimensions). The full product spec is `docs/spec.md` — read it before building any feature. This folder is the **design source of truth**: tokens, component styles, and a rendered image of every screen.

## Stack (from spec)
Vue 3 + TypeScript, Vite, Tailwind CSS, Pinia, vue-i18n (TH/EN), Vite PWA, TradingView Lightweight Charts. Backend FastAPI (see spec §1.5).

## Design system — use these, never invent values
| File | Use |
|---|---|
| `design-system/README.md` | Brand book: principles, color roles, typography, spacing, iconography, screen patterns. **Read first.** |
| `design-system/tokens.css` | CSS custom properties. Light on `:root`, dark on `[data-theme="dark"]`. Import once in `src/main.ts`. |
| `design-system/tailwind.config.js` | Maps every token to Tailwind utilities (`bg-surface`, `text-ink-muted`, `bg-brand-600`, `text-profit` …). Merge into the project's config; `darkMode: ['selector','[data-theme="dark"]']`. |
| `design-system/components.css` | Reference implementation of every component as plain classes (`tt-btn`, `tt-card`, `tt-pnl` …). Port to Vue components / `@layer components`. |
| `design-system/components/*.md` | Per-component usage rules (variants, states, do/don't). |
| `design-system/tokens.json` | Same tokens as data (for scripts / Lightweight Charts theme). |
| `design-system/hugeicons-used.json` | The Hugeicons used in the designs (name → SVG paths). |

### Non-negotiable rules
- **Palette is pastel.** Lavender `brand-600 #D5B6B9` is a FILL with dark `on-brand` text — never white text on it. Any brand-colored text, outline, toggle, checkbox, meter or link uses deep rose `brand-700 #7A4A52`. Page `bg #F6F7F0`, wells `surface-sunken #ECE9DF`, borders/selection `brand-100 #E0DADE`.
- **Strong color only for meaning:** `profit` / `loss` / `warning`, plus chart tokens (`chart-*`, `brand-500`, `dim-*`, `q-*`). Never color quality/adherence by P/L.
- **Every P/L shows a sign** (`+` / `−` U+2212); directions always say LONG/SHORT.
- **Fonts:** one stack `Inter, Anuphan` (Inter for Latin/digits, Anuphan auto-fallback for Thai). Load both from Google Fonts. Body line-height 1.6 for Thai. Numbers use `tabular-nums`.
- **Icons:** Hugeicons Stroke Rounded (free): `@hugeicons/vue` + `@hugeicons/core-free-icons`, 1.5px stroke, 16/20/24px. Concept→icon map is in `design-system/README.md` › Iconography.
- **Cards:** border only, no shadow. Radius: controls 10px, cards 14px, sheets 20px, chips full.
- **Both themes** must work (`data-theme` on `<html>`), WCAG AA contrast.
- All UI strings go through vue-i18n — no hard-coded text.

## Screens
Rendered images (light theme) are in `screens/web` (1440px, primary) and `screens/mobile` (390px, PWA). Fonts in the PNGs fell back to system fonts because Google Fonts was not reachable during export — use Inter/Anuphan as specified. `screens/source/*.dc.html` is the exact markup of each screen (uses the `tt-*` classes + `screens.css` layout helpers); treat it as reference for structure and copy, not as code to ship (`{{…}}`, `<sc-for>`, `<sc-if>`, `<dc-import>` are design-tool template syntax).

| # | Web screen | Suggested route | Spec features |
|---|---|---|---|
| 01 | Login | `/login` | F-01 |
| 02 | Onboarding (account, risk, broker) | `/onboarding` | F-01, F-02, F-08 |
| 03 | Today | `/` | F-05, F-06, F-11 AC5, F-21 |
| 04 | Market Analysis | `/analysis/:id` | F-05, F-19 AC3 |
| 05 | Trade Plan + Lock + revisions | `/plans/:id` | F-06 |
| 06 | Trades list + match-queue modal | `/trades` | F-07, F-10 |
| 07 | Add trade (Screenshot scan / Manual) | `/trades/new` | F-07, F-09 |
| 08 | Trade detail (Plan vs Actual, deviations, quality, timeline) | `/trades/:id` | F-12 AC4, F-13, F-14, F-19 |
| 09 | Trade review | `/trades/:id/review` | F-11 AC3, F-12 |
| 10 | Trading Calendar | `/calendar` | F-17 |
| 11 | Performance (P/L + Behavior) | `/stats` | F-18 |
| 12 | Diagnosis & AI Coach | `/diagnosis` | F-15, F-16 |
| 13 | Playbook + setup detail | `/playbook` | F-04 |
| 14 | Accounts, Risk & Connections | `/accounts` | F-02, F-03, F-08 |
| 15 | Alerts & Economic calendar | `/alerts` | F-20, F-21 |
| 16 | Settings & Mentorship | `/settings` | F-01, F-22, privacy NFR |
| 17 | Mentor dashboard | `/mentor` | F-22 AC7 |
| 18 | Mentor trade review (R only) | `/mentor/trades/:id` | F-22 AC2–AC4 |

Layout: ≥1024px = 240px left sidebar (`screens/source/WSide.dc.html`) + content (max 1240px); below that, the mobile screens show the same features with a 5-item bottom nav.

## Suggested build order
Follow spec §4 phases. For UI: 1) tokens + Tailwind + fonts + icons + app shell (sidebar / bottom nav, theme toggle, i18n); 2) base components from `components.css` (Button, Field, SegmentedControl, Tabs, Chip, Badge, PnL, StatTile, Card, Alert); 3) screens in the order of the table above.
