# TrackTrade — Implementation Plan

> เขียนจาก kickoff (2026-10-12) หลังอ่าน `CLAUDE.md`, `docs/spec.md` ทั้งไฟล์, `design-system/*`, ภาพใน `screens/web` (18) + `screens/mobile` (31) และ `screens/source/WSide|WToday|WPlan.dc.html`
> อัปเดต 2026-10-28: เปลี่ยน auth เป็น **Better Auth** ตาม spec (2026-10-22) — ดู §5.3, §6 auth, §8.1 S6–S7
> เอกสารนี้คือแผนอ้างอิงของทุก phase — prompt ใน `docs/prompts/phase-N.md` สั่งให้อ่านก่อนเริ่มงาน ถ้าตัดสินใจอะไรเปลี่ยนไป ให้แก้ที่นี่ก่อนแล้วค่อยแก้โค้ด

## 0. สถานะตอนเริ่ม

| ส่วน | สถานะ |
|---|---|
| `frontend/` | มี skeleton แล้ว (spec §4 Phase 1 ติ๊ก Frontend skeleton ไว้): Vue 3.5 + TS 5.9 + Vite 8 + Tailwind 3.4 + Pinia + vue-router 5 + vue-i18n 11 + vite-plugin-pwa + `@hugeicons/vue` มี app shell (`SideNav`, `AppBar`, `BottomNav`, `AccountSwitcher`, `ThemeToggle`, `LocaleSwitch`), route ครบทุกหน้าแบบ placeholder, `TodayView`/`MoreView` ตัวอย่าง, `th.json`/`en.json` |
| ที่ยังขาดใน frontend | ยังไม่ port `components/ui/*`, ไม่มี API client/auth, ธีมมีแค่ light/dark (แบบต้องการ Light/Dark/**ตามระบบ**), PWA ยังไม่มี icon, ไม่มี eslint/vitest |
| `backend/`, `connectors/`, `docker-compose.yml`, CI | ยังไม่มี |
| git | โฟลเดอร์นี้**ยังไม่เป็น git repo** (phase prompt สั่ง commit และใช้ GitHub Actions) |
| เครื่อง dev | ไดรฟ์ **C: เต็ม (เหลือ 0 GB)** — คำสั่งที่เขียน temp/cache ลง C: ล้มเหลว (npm cache, Docker Desktop, pip cache, Playwright browsers) ต้องเคลียร์ก่อนเริ่ม Phase 1 |

---

## 1. Monorepo layout

```
tracktrade/
├─ CLAUDE.md
├─ design-system/          ← คงไว้ที่ root (source of truth; frontend import ตรงจากที่นี่)
├─ screens/                ← คงไว้ที่ root (web/, mobile/, source/)
├─ sources/                ← ภาพอ้างอิงดิบ (ไม่ใช้ใน build)
├─ docs/
│  ├─ spec.md · PLAN.md · PROGRESS.md
│  ├─ prompts/
│  ├─ adr/                 ← บันทึกการตัดสินใจ (0001-news-provider.md …)
│  └─ qa/phase-N/          ← screenshot Playwright เทียบแบบ
├─ frontend/               ← Vue PWA (มีอยู่แล้ว)
├─ backend/                ← FastAPI + arq worker (image เดียว รันได้ 2 command)
├─ auth/                   ← Better Auth (Node/TypeScript) — `/api/auth/*`, JWKS, email reset password
├─ connectors/
│  └─ mt5-ea/              ← TrackTrade.mq5 + include/*.mqh + README ติดตั้ง
├─ infra/
│  ├─ nginx/               ← config web (prod) + reverse proxy /api, /ws
│  └─ backup/              ← script pg_dump รายวัน + restore drill
├─ docker-compose.yml      ← dev: postgres:17, redis:7, auth, api, worker, web, mailpit, minio
├─ docker-compose.prod.yml ← override prod (nginx build, ไม่มี mailpit, HTTPS ผ่าน Caddy/Traefik)
├─ .env.example
└─ .github/workflows/ci.yml
```

- Build context ของ service `web` ต้องเป็น root (เพราะ `tailwind.config.ts` และ `main.ts` import `../design-system/*`) — ห้ามก๊อป token ไปไว้ใน `frontend/` เพื่อไม่ให้ค่าสองชุดเพี้ยนกัน (ต่างจาก phase-1 prompt ข้อ D2 ที่บอกให้ copy — ดูคำถามข้อ Q2)
- `backend` ใช้ `uv` + `pyproject.toml`; `frontend` ใช้ `npm` (มี `package-lock.json` อยู่แล้ว)

---

## 2. Frontend architecture

### 2.1 โครง `src/`

```
src/
├─ main.ts                 ← import '@ds/tokens.css' + styles/main.css, ติดตั้ง pinia/router/i18n/vue-query
├─ App.vue
├─ router/
│  ├─ index.ts             ← routes (มีแล้ว) + meta: titleKey, nav, auth, role('trader'|'mentor'), layout
│  ├─ guards.ts            ← auth guard, onboarding guard (ยังไม่มีบัญชี → /onboarding), mentor guard
│  └─ nav.ts               ← เมนู sidebar/bottom nav (มีแล้ว)
├─ layouts/
│  ├─ AppLayout.vue        ← ≥1024: Sidebar 240 + Topbar + content (max-w 1240); <1024: AppBar + BottomNav
│  └─ AuthLayout.vue       ← login/register (split brand panel บน desktop)
├─ components/
│  ├─ shell/               ← SideNav, AppBar, BottomNav, Topbar, AccountSwitcher, ThemeToggle, LocaleSwitch, PageHeader (มีแล้วบางส่วน)
│  ├─ ui/                  ← คอมโพเนนต์พื้นฐาน port จาก components.css (ตาราง §3) — prefix `Tt` เช่น TtButton.vue
│  ├─ chart/               ← TtChart (Lightweight Charts wrapper), ChartToolbar, drawing primitives, PlanOverlay, EquityChart
│  └─ TtIcon.vue           ← (มีแล้ว) wrapper Hugeicons
├─ features/
│  ├─ auth/                ← LoginView, RegisterView, api.ts
│  ├─ onboarding/
│  ├─ today/
│  ├─ analysis/            ← AnalysisView, KeyLevelList, NarrativeEditor
│  ├─ plans/               ← PlanView, PlanForm, ChecklistCard, RevisionSheet, PlanLockBanner
│  ├─ trades/              ← TradesView, TradeTable, TradeCard, MatchModal, AddTradeView (manual/ocr), TradeDetailView, DeviationTable
│  ├─ review/              ← ReviewView, RubricRow, InTradePromptSheet
│  ├─ calendar/            ← CalendarView, DaySheet, WeekView
│  ├─ stats/               ← PerformanceView (P/L + Behavior + Breakdown), DiagnosisView, CoachReport
│  ├─ playbook/
│  ├─ accounts/            ← AccountsView, RiskProfileForm, RulesList, SymbolMapping, Connections, AuditLog
│  ├─ alerts/              ← AlertsView, NewsCalendar, ToastHost
│  ├─ settings/            ← SettingsView, MentorSettings, PrivacySection
│  └─ mentor/              ← MentorDashboardView, ReviewQueue, MentorTradeView
│     (แต่ละ feature: views/, components/, api.ts, queries.ts, types.ts)
├─ api/
│  ├─ authClient.ts        ← Better Auth client (`better-auth/vue` + jwtClient) — signIn/signUp/signOut/requestPasswordReset/resetPassword
│  ├─ client.ts            ← fetch wrapper FastAPI: JWT ของ Better Auth ใน memory (ขอจาก `/api/auth/token`), ขอใหม่เมื่อ 401 ครั้งเดียว, error `{code,message,details}`
│  ├─ schema.d.ts          ← generate จาก OpenAPI ของ backend (`openapi-typescript`) — ห้ามเขียน type ซ้ำมือ
│  └─ ws.ts                ← WebSocket client: reconnect + backoff, dispatch event → query invalidation / toast
├─ stores/                 ← state ข้ามหน้าเท่านั้น: session, ui (theme/locale/unit $/R), accounts (บัญชีที่เลือก), inbox (badge counts)
├─ composables/            ← useBreakpoint, useFormat, useAccountFilter, usePnlVisibility, useConfirm, useToast
├─ lib/
│  ├─ format.ts            ← (มีแล้ว) money/R/%/price(digits)/lot/date ตาม locale + timezone, เครื่องหมาย U+2212
│  ├─ risk.ts              ← preview คำนวณ lot/risk/RR ฝั่ง client (ผลจริงมาจาก API)
│  └─ chartTheme.ts        ← อ่าน CSS var จาก tokens → theme ของ Lightweight Charts, re-apply เมื่อสลับธีม
├─ i18n/locales/{th,en}.json  ← key ซ้อนตาม feature: `trades.table.adherence`
└─ styles/
   ├─ main.css             ← tailwind base/components/utilities + base (font, line-height 1.6, tabular-nums)
   └─ components.css       ← port จาก design-system/components.css เข้า `@layer components` (class tt-*)
```

### 2.2 Library ที่จะเพิ่ม (นอกเหนือจาก stack ใน spec)

| Library | ใช้ทำอะไร | เหตุผล |
|---|---|---|
| `@tanstack/vue-query` + persister (IndexedDB) | server state, cache, retry, invalidation จาก WS | F-23 AC1 "อ่านข้อมูลล่าสุดที่ cache ไว้ได้" ตอน offline; ไม่ต้องเขียน cache ใน Pinia |
| `lightweight-charts` v5 | กราฟ | ตาม spec; drawing tools ต้องเขียนเองเป็น series primitives (ดู Risk R3) |
| `@tiptap/vue-3` (StarterKit + Image) | narrative rich text (F-05) | toolbar ในแบบ: B / I / H2 / รูป |
| `zod` | validate ฟอร์ม + parse response สำคัญ | ข้อความ error ผ่าน i18n |
| `@vueuse/core` | breakpoint, media query (ธีมตามระบบ), storage | |
| `openapi-typescript` (dev) | gen type จาก backend | contract เดียว |
| `vitest`, `@vue/test-utils`, `@playwright/test`, `eslint` + `typescript-eslint` + `eslint-plugin-vue`, `@intlify/eslint-plugin-vue-i18n` | test/lint | rule `no-raw-text` บังคับ F-23 AC2 |

### 2.3 Naming

- Component ใน `components/ui` และ `components/chart`: `Tt` + PascalCase (`TtButton`, `TtPnl`) — กันชนกับ HTML element และแยกจาก component ของ feature
- View: `XxxView.vue` ใน `features/<domain>/views/`; route name kebab-case (`trade-detail`)
- Store: `useXxxStore` (setup store); query key: `['positions', filters]`
- i18n key: `feature.section.item` camelCase; ข้อความระบบจาก DB (emotion tag, mistake category) ใช้ `label_th/label_en` จาก API ไม่ใส่ใน json
- CSS: ใช้ class `tt-*` ที่ port มา หรือ Tailwind utility ที่ผูก token เท่านั้น — ห้าม hex/rgb, ห้าม `px` arbitrary ที่ไม่มีใน token (ยกเว้น layout ที่แบบกำหนด เช่น sidebar 240, content 1240 — ประกาศเป็นค่าใน `tailwind.config.ts` `extend.spacing/maxWidth` ครั้งเดียว)

### 2.4 Token → Tailwind

- `main.ts` import `@ds/tokens.css` (มีแล้ว) — light บน `:root`, dark บน `[data-theme="dark"]`
- `frontend/tailwind.config.ts` ใช้ `theme` จาก `../design-system/tailwind.config.js` ตรงๆ (มีแล้ว) แล้ว **extend เพิ่มเฉพาะ token ที่มีใน tokens.css แต่ config ยังไม่ map**: `chart-grid`, `chart-actual`, `focus-ring` (ring color), `overlay` (backdrop), `z-nav/sheet/toast` (zIndex), `maxWidth.content = 1240px`, `width.sidebar = 240px`
- `darkMode: ['selector','[data-theme="dark"]']` (มีแล้ว)
- กราฟอ่านค่าจาก `getComputedStyle(document.documentElement)` (`--chart-up`, `--chart-plan`, …) ผ่าน `lib/chartTheme.ts` เพราะ canvas ใช้ CSS var ไม่ได้ — `tokens.json` ใช้สำหรับ script/test เท่านั้น

### 2.5 ธีม

- ค่า: `light | dark | system` (แบบ Settings มี 3 ตัวเลือก) — ปัจจุบัน store มี 2 ค่า ต้องเพิ่ม `system` ที่ฟัง `prefers-color-scheme` แบบ live
- ใส่ `data-theme` บน `<html>` เสมอ (resolved เป็น light/dark) — script ใน `index.html` ทำก่อน first paint (มีแล้ว)
- บันทึก: localStorage `tt.theme` (ทันที) + `users.theme` ผ่าน `PATCH /me` เมื่อ login (sync ข้ามอุปกรณ์) — ต้องเพิ่มคอลัมน์ `users.theme` (§8.3)
- อัปเดต `<meta name="theme-color">` ตามธีม (มีแล้ว) — ค่าสีอ่านจาก token `--bg` แทน hard-code

### 2.6 Icons

- `@hugeicons/vue` `HugeiconsIcon` + `@hugeicons/core-free-icons` ผ่าน `TtIcon` (มีแล้ว: `:icon`, `size 16|20|24`, `stroke-width 1.5`, `aria-hidden`)
- เพิ่ม `src/lib/icons.ts` = concept map ตามตาราง Iconography ใน `design-system/README.md` (`today → Home01Icon`, `planLocked → SquareLock02Icon`, …) — feature ใช้ชื่อ concept ไม่ import icon ตรง เพื่อให้แผนที่ไอคอนอยู่ที่เดียว และ tree-shake ได้เพราะเป็น named import
- `TtIconButton` บังคับ prop `label` (เป็น `aria-label`)

### 2.7 ข้อมูล/สถานะข้ามหน้า

- **Account filter** (F-02 AC3): `useAccountsStore().selected` = `'all' | accountId` → ทุก query ใส่ `account_id` ใน key และ query param; เก็บใน localStorage
- **Unit $/R**: `ui.unit` ต่อ viewer (SegmentedControl.md) — ถ้า `pnl_visibility=r_only` บังคับ `R` และซ่อน toggle
- **Mentor mode**: user ที่ `is_mentor` สลับ workspace ได้จาก AccountSwitcher ("Mentor workspace") → layout ใช้ `mentorSideNav` (มีใน `nav.ts` แล้ว) และ route `/mentor/*`
- **Realtime**: `api/ws.ts` เชื่อมหลัง login; event → `queryClient.invalidateQueries` + toast (`alert.created`) + badge (`inbox.counts`)

### 2.8 Responsive

- `<1024px`: AppBar (root = wordmark + account chip + bell; inner = back + title + overflow), BottomNav 5 รายการ, form มี sticky CTA ด้านล่าง, ตารางเปลี่ยนเป็น card list (`TradeCard`)
- `≥1024px`: Sidebar 240 + Topbar (crumb + h1 + actions) + content `max-w-content` padding 24/32, layout `split--main` (main 1fr + aside 320–400)
- ทุกหน้าต้องใช้ได้ที่ 375px (F-23 AC3); ตารางกว้างใน desktop แคบ → `overflow-x-auto` ในกล่อง
- ตัวเลขยาวในเซลล์แคบ (ปฏิทินมือถือ `−$1,025` ตัดบรรทัดในแบบ) → `<md` ใช้ compact format (`−$1.0k`) + `title` ค่าเต็ม

---

## 3. Component inventory

### 3.1 จาก `design-system/components/*.md` (มี CSS ใน `components.css` แล้ว)

| Component | ไฟล์ | Props หลัก | ใช้ที่หน้า |
|---|---|---|---|
| Button | `TtButton` | `variant: primary\|secondary\|ghost\|danger`, `size: sm\|md\|lg`, `block`, `icon`, `loading`, `disabled`, `to` (render เป็น RouterLink) | ทุกหน้า |
| IconButton | `TtIconButton` | `icon`, `label` (required), `active`, `badge` | Topbar, AppBar, chart toolbar |
| Field + Input/Select/Textarea | `TtField`, `TtInput`, `TtSelect`, `TtTextarea`, `TtNumberInput` | `label`, `required`, `help`, `error`, `lowConfidence` (+ข้อความ % มั่นใจ), `suffix`, `numeric`, `digits`, `v-model` | Onboarding, Analysis, Plan, AddTrade, Review, Accounts, Settings, Login |
| SegmentedControl | `TtSegmented` | `options[{value,label}]`, `v-model`, `block`, `size` | Period, $/R, ประเภทบัญชี, ภาษา, ธีม, HTF bias, Entry type, Scenario, ใช่/ไม่, rubric 25/50/75/100 |
| Tabs | `TtTabs` | `items[{value,label,count?}]`, `v-model` หรือ route-based | Trades, Accounts, Trade detail (mobile), Stats (mobile) |
| Chip | `TtChip` | `selected`, `valence: pos\|neg\|neutral`, `add`, `dot`, `size` | TF/session, emotion/mistake tags, filters |
| Badge | `TtBadge` | `variant: neutral\|solid\|brand\|outline\|warning\|loss\|profit\|long\|short\|gold`, `icon` | สถานะแผน, LONG/SHORT, source, "จำเป็น", counts |
| Grade | `TtGrade` | `grade: A\|B\|C\|D`, `score?` | Trades, Detail, Calendar, Mentor |
| PnL | `TtPnl` | `money?`, `r?`, `currency`, `size: display\|lg\|md\|sm`, `arrow`, `visibility: currency\|r_only`, `compact` | ทุกที่ที่มีผลลัพธ์ (บังคับเครื่องหมาย + / −) |
| StatTile | `TtStat` | `label`, `icon?`, `value` (slot), `delta?`, `meter?` | Today, Performance, Playbook, Trade detail, Mentor |
| Card | `TtCard` | `title?`, `action?` (slot), `padding`, `flush` | ทุกหน้า |
| Alert | `TtAlert` | `variant: info\|loss\|warning\|profit\|gold`, `icon`, `title`, `body`, `action` slot, `dismissible` | Today (ข่าว), Plan lock warn, OCR, Trades (รอจับคู่), Connections error, AI privacy note |
| AppBar | `AppBar` (shell, มีแล้ว) | `mode: root\|inner`, `title`, `back`, `actions` slot | mobile ทุกหน้า |
| BottomNav | `BottomNav` (มีแล้ว) | items จาก `nav.ts`, `dot` | mobile root screens |
| CalendarDay | `TtCalendarDay` + `TtCalendarGrid` | `date`, `pnl`, `r`, `unit`, `trades`, `mood`, `adherence`, `grade`, `today`, `outside`, `weekStart` | Calendar |
| Checklist | `TtChecklist` | `items[{id,text,required}]`, `v-model:answers`, `showMissing`, `readonly`, `reorderable` (Playbook ลากเรียง) | Plan, Playbook |
| DeviationRow | `TtDeviationRow` (mobile) / `DeviationTable` (desktop) | `deviation{type,expected,actual,costAmount,costR,dimension}`, `visibility` | Trade detail, Mentor trade |
| DimensionBars | `TtDimensionBars` | `values{dim:number}`, `unit: R\|$\|%\|score`, `primary` | Performance, Diagnosis, Mentor |
| MoodScale | `TtMoodScale` | `v-model 1–10`, `label`, `phase`, `ends` (icon sad/smile) | Today (daily), Plan, In-trade sheet, Review, Analysis (confidence) |
| PlanLock | `TtPlanLock` | `lockedAt`, `hash`, `revision`, `canRevise` | Plan |
| QuadrantMatrix | `TtQuadrant` | `counts{gw,gl,bw,bl}`, `mode: count\|pct`, `@select` | Performance, Behavior |
| ScoreMeter | `TtRing`, `TtMeter` | `value 0–100`, `label`, สีตามคะแนน (≥80 `brand-700`, 60–79 `warning`, <60 `loss`) — ไม่เคยใช้ P/L | Trade detail, Today, Accounts "วันนี้" |
| Timeline | `TtTimeline` | `events[{type,time,title,body,tone}]` | Trade detail |
| TradeCard | `TtTradeCard` | `position` summary, `visibility`, `to` | Trades (mobile), DaySheet, Playbook detail, Mentor queue |
| Wordmark | `TtWordmark` | `size` | Sidebar, AppBar, Login |
| FAB | `TtFab` | `icon`, `label`, `to` | Today / Trades (mobile) |

### 3.2 เห็นในภาพแต่ยังไม่มีใน DS (ต้องออกแบบ CSS จาก `screens.css` + token)

| Component | Props หลัก | ใช้ที่หน้า | ที่มาในแบบ |
|---|---|---|---|
| Sidebar (`SideNav`) | `mode: trader\|mentor`, badges | ทุกหน้า desktop | `WSide.dc.html`, `.side*` (มีแล้วบางส่วน) |
| Topbar | `crumb{to,label}`, `title`, `badge`, `actions` slot | ทุกหน้า desktop | `.topbar`, `.crumb` |
| AccountSwitcher | `accounts`, `v-model`, `allowAll`, `mentorWorkspace` | Sidebar, AppBar, filters | มีแล้ว |
| Modal | `open`, `title`, `subtitle`, `size`, footer slot, focus trap, `Esc` | Match queue (desktop), confirm dialogs | `06-WTrades` |
| Sheet (bottom sheet) | `open`, `title`, `grab`, footer slot | Revision, In-trade prompt, Day sheet, Daily mood — desktop แสดงเป็น Modal/side panel | `.sheet`, `08-PlanLocked`, `13-InTradePrompt`, `17-DaySheet` |
| Table | `columns[{key,label,align,width}]`, `rows`, `loading`, `empty`, `rowLink`, sticky header, `overflow-x-auto` | Today plans, Trades, Deviations, Diagnosis mistakes, Accounts, Mentor | `.tbl`, `.tblwrap` |
| Pagination | `page`, `pageSize`, `total` | Trades | `06-WTrades` |
| Toggle (switch) | `v-model`, `label` (aria), `disabled` | Management plan, Rules, Settings, Mentor perms, Push | `.toggle` |
| Checkbox | `v-model`, `label` | Login remember, Register terms, Checklist box | `01-WLogin`, `.tt-check__box` |
| Radio card | `v-model`, `value`, `title`, `subtitle`, `badge` | Match modal, Onboarding broker choice | `06-WTrades`, `02-WOnboarding` |
| Toast + ToastHost | `variant`, `title`, `body`, `action`, auto-dismiss; ใช้สไตล์ Alert บน `surface-raised` + `shadow-lg`, `z-toast` | ทั้งแอป (WS alerts) | `Alert.md` |
| Stepper | `steps[{title,subtitle,state}]`, `current`, `orientation` (desktop vertical card, mobile progress bar + "1/2") | Onboarding | `02-WOnboarding`, `03-Onboarding` |
| ListRow | `icon`, `tone: brand\|loss\|warn\|profit\|gold`, `title`, `subtitle`, `end` slot, `to` | Today "ต้องจัดการ", Alerts, More, Settings privacy, Connections history | `.row`, `.row__ic*` |
| KeyValue list | `items[{label,value}]` | Plan locked, Calendar summary, Review side panel, Playbook management rules | `.kv` |
| Avatar | `initials`, `size`, `src?` | Sidebar user, Mentor, Comments | `.avatar` |
| SearchInput | `v-model`, `placeholder`, debounce | Today topbar, Trades | `03-WToday`, `06-WTrades` |
| DirectionToggle | `v-model: long\|short` | Plan, Manual trade | `.dirbtn` |
| CalcStrip | `items[{label,value}]` | Plan (risk amount/lot/RR), AddTrade (net P/L, R) | `.calc` |
| Dropzone / FileUpload | `accept`, `maxSize`, `@file`, progress | AddTrade OCR, Playbook examples, Review attachments | `.dropzone` |
| AttachmentGrid | `items`, `add`, `draw` | Review, Playbook | `09-WReview`, `13-WPlaybook` |
| ExecutionList | `executions[{side,lot,price,time}]`, `@add`, `@edit` | Manual trade | `10-ManualTrade` |
| CommentThread | `comments`, `@send`, author role | Trade detail, Mentor trade | `08-WTradeDetail`, `18-WMentorTrade` |
| RubricRow | `dimension`, `hint`, `v-model 25\|50\|75\|100`, `source` | Review (self), Mentor trade | `09-WReview` |
| ImpactBars | `impact: low\|med\|high` (3 แท่ง + ข้อความ — ห้ามสีอย่างเดียว) | Alerts/News | `15-WAlerts`, `26-News` |
| KeyLevelList | `levels[{price,label,kind}]`, editable | Analysis | `04-WAnalysis` |
| CodeBox (API key) | `value`, `masked`, `copy` | Connections, Onboarding | `.code` |
| Skeleton / EmptyState / ErrorState | `lines`, `icon`, `message`, `action` | ทุกหน้า (ไม่มีในแบบ — §8.2) | — |
| Legend | `items[{style: dashed\|solid\|swatch, label}]` | Charts, Calendar | `.legend` |
| Chart components | `TtChart` (`candles`, `tf`, `theme`), `ChartToolbar` (TF chips + tools), `DrawingLayer` (trendline/ray/horizontal/rect/text/measure), `PlanOverlay` (entry/SL/TP dashed + labels), `ActualOverlay` (fills, exit, SL changes over time), `EquityChart` (area + DD band) | Today, Analysis, Plan, Trade detail, Review, Mentor, Performance | `screens/source/Chart.dc.html` |

---

## 4. Screen → Phase mapping

API อ้างอิง §6 (prefix `/api/v1` ละไว้)

### 4.1 Web (`screens/web`, 1440px)

| # | ภาพ | Route | Phase | API หลัก |
|---|---|---|---|---|
| 01 | `01-WLogin` | `/login` (+ `/register` ใช้ split layout เดียวกัน) | 1 | `POST /auth/login`, `POST /auth/register` |
| 02 | `02-WOnboarding` | `/onboarding` | 2 (step Broker เติมจริงใน 4) | `POST /accounts`, `PUT /accounts/{id}/risk-profile`, `POST /accounts/{id}/connections/mt5` |
| 03 | `03-WToday` | `/` | shell 1 · เนื้อหา 3 · badge/ต้องจัดการ 4–6 · mood 5 · ข่าว 6 | `GET /today`, `GET /analyses?date=`, `GET /plans?date=`, `GET /news?date=`, `PUT /daily/{date}` |
| 04 | `04-WAnalysis` | `/analysis/new`, `/analysis/:id` | 3 | `GET/POST/PATCH /analyses`, `GET /market-data/ohlc`, `GET/PUT /chart-drawings` |
| 05 | `05-WPlan` | `/plans/new?analysis=`, `/plans/:id` | 3 | `GET/POST/PATCH /plans`, `POST /plans/{id}/lock`, `POST /plans/{id}/revisions`, `POST /risk/calc`, `GET /setups/{id}` |
| 06 | `06-WTrades` (+ modal) | `/trades`, modal `?match=:positionId` | 4 (คอลัมน์ score เติมใน 6) | `GET /positions`, `GET /positions/{id}/match-candidates`, `PUT /positions/{id}/match`, `GET /positions/export.csv` |
| 07 | `07-WAddTrade` | `/trades/new?mode=manual\|scan` | manual 4 · scan 5 | `POST /positions`, `POST /ocr/uploads`, `GET /ocr/uploads/{id}`, `POST /ocr/uploads/{id}/confirm` |
| 08 | `08-WTradeDetail` | `/trades/:id` | โครง+timeline 5 · engine 6 · chart overlay 7 · comments 8 | `GET /positions/{id}` (รวม adherence/deviations/quality), `GET /positions/{id}/timeline`, `GET /positions/{id}/chart`, `GET/POST /comments` |
| 09 | `09-WReview` | `/trades/:id/review` | 5 | `GET/PUT /positions/{id}/review`, `POST /positions/{id}/review/submit`, `POST /attachments` |
| 10 | `10-WCalendar` | `/calendar?view=month\|week&m=2026-10` | 7 | `GET /calendar`, `GET /calendar/days/{date}` |
| 11 | `11-DesktopDashboard` | `/stats` | 7 | `GET /stats/summary`, `/stats/equity`, `/stats/quadrants`, `/stats/breakdown`, `GET /positions?limit=5` |
| 12 | `12-WDiagnosis` | `/diagnosis` | 7 (rule engine data จาก 6) | `GET /diagnosis`, `GET/POST /coach/reports` |
| 13 | `13-WPlaybook` | `/playbook`, `/playbook/:id` | 2 (stats เติมใน 7) | `GET/POST/PATCH /setups`, `PUT /setups/{id}/checklist`, `POST /setups/{id}/examples`, `GET /setups/{id}/stats` |
| 14 | `14-WAccounts` | `/accounts?account=&tab=risk\|rules\|symbols\|connections\|audit` | 2 (แท็บการเชื่อมต่อ 4) | `GET /accounts`, `/accounts/{id}/risk-profile`, `/rules`, `/symbol-overrides`, `/risk-status`, `/audit-log`, `/connections` |
| 15 | `15-WAlerts` | `/alerts` | 6 | `GET /alerts`, `POST /alerts/{id}/read`, `POST /alerts/read-all`, `GET /news`, `PUT /me/notification-preferences` |
| 16 | `16-WSettings` | `/settings?section=profile\|notifications\|mentor\|privacy` | profile/theme/locale 1 · notifications 6 · mentor+privacy 8 | `GET/PATCH /me`, `GET /me/sessions`, `POST /me/export`, `DELETE /me`, `/mentor-links` |
| 17 | `17-WMentor` | `/mentor` | 8 | `GET /mentor/traders`, `GET /mentor/review-queue`, `GET /mentor/alerts` |
| 18 | `18-WMentorTrade` | `/mentor/trades/:id` | 8 | `GET /mentor/positions/{id}`, `PUT /mentor/positions/{id}/scores`, `POST /mentor/assignments`, `/comments` |

### 4.2 Mobile (`screens/mobile`, 390px) — route เดียวกับ web, layout ต่างตาม breakpoint

| # | ภาพ | Route | Phase | หมายเหตุ |
|---|---|---|---|---|
| 01 | `01-Main` | `/login` | 1 | |
| 02 | `02-Register` | `/register` | 1 | strength bar, ภาษา+timezone, ยอมรับเงื่อนไข |
| 03 | `03-Onboarding` | `/onboarding` (step บัญชี) | 2 | progress "1/2" |
| 04 | `04-ConnectBroker` | `/onboarding` (step broker) | 2 · ทำงานจริง 4 | API key แสดงเต็มครั้งเดียว + "รอสัญญาณจาก EA…" (WS event `sync.first_deal`) |
| 05 | `05-Today` | `/` | 1/3/5/6 | daily mood อยู่บนสุด, FAB |
| 06 | `06-Analysis` | `/analysis/:id` | 3 | |
| 07 | `07-PlanForm` | `/plans/:id` | 3 | scenario A/B/C, entry type แบบ segmented |
| 08 | `08-PlanLocked` | `/plans/:id` + Sheet revision | 3 | |
| 09 | `09-Trades` | `/trades` | 4 | TradeCard แทนตาราง, group ตามวัน |
| 10 | `10-ManualTrade` | `/trades/new?mode=manual` | 4 | |
| 11 | `11-ScanConfirm` | `/trades/new?mode=scan` | 5 | |
| 12 | `12-MatchQueue` | `/trades/match` (full screen, "1/2") | 4 | desktop = modal |
| 13 | `13-InTradePrompt` | Sheet ทับหน้าใดก็ได้ (จาก inbox/WS/Push deep link `/inbox/:id`) | 5 | |
| 14 | `14-TradeDetail` | `/trades/:id` (tabs: Plan vs Actual · Review · Timeline · Comments) | 5/6/7/8 | |
| 15 | `15-Review` | `/trades/:id/review` | 5 | |
| 16 | `16-Calendar` | `/calendar` | 7 | |
| 17 | `17-DaySheet` | Sheet บน `/calendar?day=2026-10-08` | 7 | desktop = panel ขวา |
| 18 | `18-Performance` | `/stats?tab=pnl` | 7 | |
| 19 | `19-Behavior` | `/stats?tab=behavior` | 7 | |
| 20 | `20-AICoach` | `/stats?tab=coach` | 7 | แท็บ Diagnosis = `/stats?tab=diagnosis` (เนื้อหาเดียวกับ `/diagnosis` desktop) |
| 21 | `21-Playbook` | `/playbook` | 2 | |
| 22 | `22-SetupDetail` | `/playbook/:id` | 2 (stats/เทรดล่าสุด 7) | |
| 23 | `23-Accounts` | `/accounts` | 2 | |
| 24 | `24-Connections` | `/accounts/connections` | 4 | |
| 25 | `25-Alerts` | `/alerts` | 6 | |
| 26 | `26-News` | `/alerts/news` | 6 | desktop = คอลัมน์ขวาของ `/alerts` |
| 27 | `27-More` | `/more` | 1 (มีแล้ว) | |
| 28 | `28-Settings` | `/settings` | 1/6/8 | |
| 29 | `29-MentorInvite` | `/settings/mentor` | 8 | desktop = section ใน `/settings` |
| 30 | `30-MentorDashboard` | `/mentor` | 8 | |
| 31 | `31-MentorTradeView` | `/mentor/trades/:id` | 8 | |

Route ที่ต้องเพิ่มจาก router ปัจจุบัน: `/register`, `/analysis/new`, `/plans/new`, `/trades/match`, `/playbook/:id`, `/accounts/connections`, `/alerts/news`, `/settings/mentor`, `/mentor/alerts`, `/inbox/:id`, `/dev/ui` (dev only)

---

## 5. Backend architecture

### 5.1 โครงโฟลเดอร์

```
backend/
├─ pyproject.toml            ← fastapi, pydantic-settings, sqlalchemy[asyncio], asyncpg, alembic, arq, redis, argon2-cffi, pyjwt, structlog, httpx, anthropic, pywebpush, cryptography, boto3/aioboto3, slowapi
├─ alembic.ini · alembic/versions/
├─ app/
│  ├─ main.py                ← create_app(settings) → FastAPI; include routers; middleware; lifespan (db engine, redis, ws hub)
│  ├─ core/
│  │  ├─ config.py           ← Settings(BaseSettings): DATABASE_URL, REDIS_URL, JWT_SECRET, FERNET_KEY, ANTHROPIC_API_KEY, S3_*, SMTP_*, VAPID_*, CORS_ORIGINS, MATCH_TOLERANCE_SL=0.3, QUALITY_WEIGHTS …
│  │  ├─ db.py               ← async engine, async_sessionmaker, get_session dependency (unit of work ต่อ request)
│  │  ├─ models_base.py      ← Base: id uuid7, created_at, updated_at; type Money=Numeric(18,2), Price=Numeric(18,6)
│  │  ├─ security.py         ← ตรวจ JWT ของ Better Auth ด้วย JWKS (cache ตาม `kid`) — FastAPI ไม่ออก token / ไม่ hash password แล้ว
│  │  ├─ access.py           ← AccessContext(user, trader_id, link) + policy: owner / active mentor (read-only, r_only) → 404 / 403
│  │  ├─ errors.py           ← AppError(code, message, details) + handlers → `{code,message,details}`
│  │  ├─ logging.py          ← structlog JSON, request_id, user_id
│  │  ├─ ratelimit.py        ← Redis token bucket (auth, ingest, ocr, coach)
│  │  ├─ audit.py            ← บันทึก audit_logs (before/after) ผ่าน service hook (ไม่ใช่ HTTP middleware ล้วน เพราะต้องได้ before/after ระดับ entity)
│  │  ├─ crypto.py           ← Fernet encrypt/decrypt สำหรับ OAuth tokens
│  │  ├─ storage.py          ← S3-compatible client (MinIO ใน dev) + presigned URL
│  │  └─ pubsub.py           ← Redis publish helpers (`user:{id}` channel)
│  ├─ modules/
│  │  ├─ auth/ users/ accounts/ symbols/ playbooks/ analysis/ plans/ executions/ ingestion/
│  │  ├─ market_data/ emotions/ reviews/ metrics/ diagnosis/ alerts/ news/ mentorship/ ai_coach/ realtime/
│  │  │   └─ แต่ละ module: models.py · schemas.py · repo.py · service.py · router.py · tasks.py (ถ้ามี job)
│  │  └─ metrics/engine/     ← **pure functions ไม่แตะ DB**: adherence.py, deviations.py, quality.py, quadrant.py, cost.py, VERSION
│  ├─ worker/
│  │  ├─ settings.py         ← arq WorkerSettings: functions, cron_jobs, retry/backoff
│  │  └─ jobs.py             ← recompute_position, expire_plans, sync_ctrader, fetch_ohlc, run_ocr, fetch_news, pre_news_alerts, weekly_coach, send_push
│  ├─ realtime/hub.py        ← WebSocket connection registry ต่อ process + Redis pub/sub subscriber → fan-out
│  └─ seeds/                 ← symbols.yaml, emotion_tags.yaml, mistake_categories.yaml, deviation_map.yaml, demo/ (ข้อมูลตามภาพแบบ "Nook Knight")
└─ tests/
   ├─ unit/                  ← engine, risk calc, matching, formatting
   ├─ integration/           ← API + Postgres จริง (docker) ด้วย httpx.AsyncClient
   └─ fixtures/trades/*.yaml ← scenario fixture (§7.1)
```

### 5.2 หลักการ

- **Layering**: router (HTTP, schema) → service (business rule, transaction, audit, publish event) → repo (query) ; module อื่นเรียกผ่าน service เท่านั้น
- **Ownership**: repo ทุกตัวรับ `AccessContext` แล้วกรอง `user_id`/`account.user_id` ใน query เอง — ไม่พบ = 404 (F-01 AC4); mentor ผ่าน `mentor_links.status='active'` อ่านได้, เขียน = 403 (F-22 AC6) ยกเว้น endpoint mentor โดยเฉพาะ (scores, mistakes, comments, assignments)
- **R-only serializer**: response schema ของ mentor มี `PnlView` ที่ตัด field เงินทิ้งระดับ schema (ไม่ใช่ซ่อนใน UI) เมื่อ `pnl_visibility='r_only'` — test ครอบทุก endpoint mentor (F-22 AC2)
- **Money/price**: `Decimal` ทั้งระบบ, JSON serialize เป็น **string** (`"4387.52"`) เพื่อไม่เสีย precision; frontend format ตาม `symbols.digits`
- **Time**: เก็บ UTC; "วันเทรด" คำนวณตาม timezone ที่กำหนด (ดู Q6)
- **Engine reproducible**: input snapshot (plan revision ที่ใช้, risk profile snapshot, executions, modifications, news ในช่วง) เก็บใน `adherence_results.inputs_hash` + `engine_version` (F-13 AC6)
- **Recompute pipeline**: event `position.closed | position.matched | plan.revised | score.changed` → arq `recompute_position(position_id)` (dedupe ด้วย job id) → adherence → deviations → quality auto → summary/quadrant → mistakes → publish `metrics.updated`
- **Ingest path** (≤5s ถึง alert): `/ingest` validate + upsert idempotent (unique `broker_deal_id`) ใน transaction → enqueue `process_ingest` → matching + rule check → `rule_breaches` + `alerts` → Redis publish → WS + Web Push
- **arq cron**: `expire_plans` ทุก 5 นาที, `fetch_news` ทุก 1 ชม., `pre_news_alerts` ทุก 1 นาที, `weekly_coach` จันทร์ 06:00 (ตาม timezone ผู้ใช้ — รันทุกชั่วโมงแล้วเลือกผู้ใช้ที่ถึงเวลา), `balance_snapshot` รายวัน
- **WebSocket** `/ws?token=<access>`: auth ตอน connect, ping/pong 25s, subscribe channel `user:{id}` (+ `mentor:{id}` สำหรับ alert ที่ forward); message `{type, data, ts}`
- **AI**: Claude API — OCR ใช้ vision model, Coach ใช้ text model (ตั้งชื่อ model ใน settings); input ผ่าน `ai_coach/anonymize.py` ที่ whitelist field (ไม่มี email/account number/ชื่อ) + test (F-16 AC2); retry 3 ครั้ง backoff แล้ว `status=error` (AC4)

---

### 5.3 Authentication — Better Auth (Phase 2)

ตัดสิน open question spec §5 (2026-10-28):

| เรื่อง | ตัดสิน | เหตุผล |
|---|---|---|
| ที่รัน | **Node service แยก** `auth/` (Better Auth + `better-auth/node` handler บน `node:http`) container `auth` port 3000 | web เป็น static nginx ไม่มี Node runtime; แยก deploy/scale ได้ |
| Routing | browser เรียก `/api/auth/*` (same-origin ผ่าน nginx / Vite proxy) → `auth`; `/api/v1/*` → FastAPI | session cookie httpOnly + SameSite=Lax ไม่ต้องทำ CORS |
| FastAPI ตรวจ session | **JWT (jwt plugin, EdDSA) + JWKS** จาก `AUTH_JWKS_URL` cache ตาม `kid`; payload มี `sub=user.id`, `sid=session.id`; FastAPI เช็กแถว `auth_sessions` (ยังไม่หมดอายุ) ทุก request | ตรวจลายเซ็นได้โดยไม่เรียก auth service ทุกครั้ง แต่ revoke/reset password มีผลทันที (F-01 AC6) — เป็น PK lookup ในฐานข้อมูลเดียวกัน |
| JWT ฝั่ง browser | frontend ขอ `GET /api/auth/token` (อายุ 15 นาที) เก็บใน memory; 401 → ขอใหม่ 1 ครั้ง → ไม่ได้ = session หลุด → `/login?redirect=` | เหมือน access token เดิม แต่ต่ออายุด้วย session cookie ของ Better Auth |
| WebSocket | `/api/v1/ws?token=<jwt>` ตรวจแบบเดียวกัน | |
| Schema | Alembic เป็นเจ้าของ schema ทั้งหมด; Better Auth map ด้วย `modelName` + `fields` เป็น snake_case: `users` (name→`display_name`, + `email_verified`, `image`, additionalFields `locale`, `timezone`, `theme`, `plan_tier`, `is_mentor`), `auth_sessions`, `auth_accounts`, `auth_verifications`, `auth_jwks`; id = uuid | schema เดียว ไม่ต้องรัน migration 2 ระบบ; FastAPI ใช้ `users` ต่อได้ทันที |
| Password | argon2id (`@node-rs/argon2`, พารามิเตอร์เท่า argon2-cffi default) ผ่าน `emailAndPassword.password.hash/verify`; min 8 ตัวอักษร | hash เดิมจาก Phase 1 (PHC string) verify ได้เลย → AC8 ไม่ต้องสมัครใหม่ |
| Migration | Alembic ย้าย `users.password_hash` → `auth_accounts(provider_id='credential')` แล้ว drop `password_hash`, `refresh_tokens` | AC8 |
| Forgot/Reset | `requestPasswordReset` → email ลิงก์ `/reset-password?token=` (อายุ 1 ชม., ใช้ครั้งเดียว, ตอบเหมือนกันทุกกรณี), `resetPassword` + `revokeSessionsOnPasswordReset` | AC5–AC6 |
| Email | nodemailer SMTP; dev = **Mailpit** (UI :8025) | |
| Rate limit | Better Auth `rateLimit` (window/max ตาม env, sign-in/sign-up/reset เข้มกว่า) | NFR |
| Sessions/อุปกรณ์ | `authClient.listSessions()/revokeSession()` (Settings) | แทน `/me/sessions` เดิม |
| Guard | frontend: ทุก route ยกเว้น `/login`, `/register`, `/forgot-password`, `/reset-password` (meta `public`); backend: ทุก router ยกเว้น health ต้องมี session + test ที่ไล่ทุก route ใน OpenAPI ว่าได้ 401 | AC7 |

---

## 6. API contract draft (`/api/v1`)

รูปแบบทั่วไป: list ใช้ cursor pagination `?cursor=&limit=` → `{items, next_cursor}`; ทุก list รับ `account_id` (ไม่ส่ง = ทุกบัญชี); error `{code, message, details}`; เวลาเป็น ISO-8601 UTC; เงิน/ราคาเป็น string

### auth (Better Auth service — `/api/auth/*`, ไม่อยู่ใต้ `/api/v1`)
| Method | Path | Request → Response |
|---|---|---|
| POST | `/api/auth/sign-up/email` | `{email, password(≥8), name, locale, timezone}` → `{user, token}` + session cookie |
| POST | `/api/auth/sign-in/email` | `{email, password, rememberMe}` → `{user}` + session cookie (rememberMe=false → cookie หมดเมื่อปิด browser) |
| POST | `/api/auth/sign-out` | → ลบ session |
| GET | `/api/auth/get-session` | → `{session, user}` |
| GET | `/api/auth/token` | → `{token}` JWT 15 นาที สำหรับเรียก FastAPI |
| GET | `/api/auth/jwks` | public keys (FastAPI ใช้ตรวจ JWT) |
| POST | `/api/auth/request-password-reset` | `{email, redirectTo}` → `{status:true}` เสมอ |
| POST | `/api/auth/reset-password` | `{newPassword, token}` → revoke ทุก session |
| POST | `/api/auth/change-password` | `{currentPassword, newPassword, revokeOtherSessions}` |
| GET / POST | `/api/auth/list-sessions`, `/api/auth/revoke-session` | อุปกรณ์ที่ login |

### users (`/api/v1`)
| Method | Path | Request → Response |
|---|---|---|
| GET / PATCH | `/me` | `{display_name, locale, timezone, theme}` |
| GET / PUT | `/me/notification-preferences` | `{rule_breach, news_high, news_lead_min, in_trade_prompt, coach_weekly, mentor_comment}` |
| POST / DELETE | `/me/push-subscriptions` | `{endpoint, keys}` |
| POST | `/me/export` | → 202 `{job_id}` (zip CSV+JSON, ลิงก์ทางอีเมล) |
| DELETE | `/me` | `{password}` → 202 (ลบถาวร) |

### accounts / risk / symbols
| Method | Path | Request → Response |
|---|---|---|
| GET / POST | `/accounts` | `{name, broker, platform, account_type, account_number?, currency, initial_balance}` → Account (+ risk_profile default) |
| GET / PATCH | `/accounts/{id}` | |
| POST | `/accounts/{id}/archive` | |
| GET / PUT | `/accounts/{id}/risk-profile` | `{risk_per_trade_pct, max_daily_loss_pct, max_drawdown_pct, max_trades_per_day, revenge_cooldown_min, news_blackout_min}` |
| GET | `/accounts/{id}/risk-status` | `{balance, equity, daily_loss:{used,limit}, drawdown:{pct,limit}, trades_today:{n,max}}` |
| GET / POST / PATCH | `/accounts/{id}/rules[/{rule_id}]` | `{code, params, severity, is_active}` |
| GET / POST / DELETE | `/accounts/{id}/symbol-overrides` | `{broker_symbol, symbol_id, contract_size?, tick_value?}` |
| GET | `/accounts/{id}/audit-log` | `[{actor, action, entity, before, after, at}]` |
| GET | `/symbols` | `[{id, code, asset_class, digits, pip_size, contract_size, quote_currency}]` |
| POST | `/risk/calc` | `{account_id, symbol_id, direction, entry, stop_loss, take_profits[{price,pct}], risk_pct? \| lot?}` → `{risk_amount, lot, rr_per_tp[], rr_avg, tick_value, contract_size, balance}` |

### connections / ingest
| Method | Path | Request → Response |
|---|---|---|
| GET | `/accounts/{id}/connections` | `[{kind, status, last_sync_at, last_error, key_hint:"tt_live_9f2c…a71b", stats:{deals_today, mods_today}}]` |
| POST | `/accounts/{id}/connections/mt5` | → `{api_key}` **แสดงครั้งเดียว** (เก็บ hash + prefix/last4) — เรียกซ้ำ = rotate |
| POST | `/accounts/{id}/connections/ctrader/authorize` | → `{authorize_url}`; callback `GET /connections/ctrader/callback` |
| POST | `/connections/{id}/sync` | → 202 (cTrader: ดึงทันที; MT5: วางคำสั่งให้ EA poll — ดู M14) |
| GET | `/accounts/{id}/ingestion-jobs` | ประวัติการนำเข้า |
| GET | `/downloads/mt5-ea` | ไฟล์ `.ex5` |
| POST | `/ingest/events` | header `X-Api-Key`; `{account:{balance,equity,server_time}, deals[], positions[], modifications[], ohlc[]}` → `{accepted, duplicates}` (idempotent) |
| GET | `/ingest/commands` | EA poll ทุก 10s → `[{id, kind:"resync"\|"ohlc", params}]` |

### playbook / attachments
| Method | Path | Request → Response |
|---|---|---|
| GET / POST | `/setups?archived=` | `{name, description, timeframes[], sessions[], default_risk_pct, management_rules{partial,be,trailing}}` |
| GET / PATCH / DELETE | `/setups/{id}` | DELETE เมื่อถูกใช้แล้ว → 409 `setup_in_use` (F-04 AC2) |
| POST | `/setups/{id}/archive` · `/unarchive` | |
| PUT | `/setups/{id}/checklist` | `[{id?, text, is_required}]` (ลำดับ = order) |
| POST / DELETE | `/setups/{id}/examples[/{eid}]` | `{attachment_id, note}` |
| GET | `/setups/{id}/stats?from&to` | `{trades, win_rate, expectancy_r, avg_adherence, avg_quality}` |
| POST | `/attachments` | multipart (≤10MB, png/jpg/webp) → `{id, url}` |

### analysis / plans
| Method | Path | Request → Response |
|---|---|---|
| GET / POST | `/analyses?date=&symbol=` | `{account_id?, symbol_id, analysis_date, htf_bias, key_levels[{price,price_to?,kind,label}], timeframes[], session, narrative(json), confidence}` |
| GET / PATCH | `/analyses/{id}` | (+ `plans[]` ย่อ) |
| GET / PUT | `/chart-drawings?owner_type&owner_id&timeframe` | `[{tool, points, style, text?}]` |
| GET / POST | `/plans?date=&status=&analysis_id=` | `{analysis_id, setup_id, account_id, symbol_id, direction, scenario_label, entry_type, entry_price, stop_loss, take_profits[], planned_risk_pct, management_plan, invalidation, valid_until, checklist_answers[], pre_emotion{mood,confidence,tags[]}}` → Plan (+ calc) |
| GET / PATCH | `/plans/{id}` | PATCH ได้เฉพาะ `draft` |
| POST | `/plans/{id}/lock` | → `{locked_at, lock_hash, revision_no:1}`; required ขาด → 422 `checklist_incomplete {missing[]}` |
| POST | `/plans/{id}/revisions` | `{changes{...}, reason}` (reason บังคับ) → revision (+ `changed_after_entry`) |
| GET | `/plans/{id}/revisions` | |
| POST | `/plans/{id}/status` | `{status: skipped\|missed\|invalidated, reason}` |

### positions / matching / OCR
| Method | Path | Request → Response |
|---|---|---|
| GET | `/positions?tab=all\|review\|pending\|unplanned\|open&symbol&setup_id&quadrant&from&to&q&cursor` | `{items[PositionSummary], counts{all,review,pending,unplanned,open}, next_cursor}` |
| POST | `/positions` | manual `{account_id, symbol_id, direction, initial_sl, initial_tp, plan_id?, executions[{side,lot,price,executed_at,commission}], swap?}` → Position (+ calc) |
| GET / PATCH / DELETE | `/positions/{id}` | detail: position + executions + plan snapshot + adherence + deviations + quality(by source) + summary + review state; DELETE เฉพาะ manual/ocr |
| GET | `/positions/{id}/timeline` | `[{type, at, title_key, data}]` |
| GET | `/positions/{id}/chart?tf=` | `{bars[], plan_lines, fills[], sl_tp_changes[], drawings[]}` |
| GET | `/positions/match-queue` | pending positions + candidates |
| GET | `/positions/{id}/match-candidates` | `[{plan, entry_distance, distance_pct_of_sl, within_valid, recommended}]` |
| PUT | `/positions/{id}/match` | `{plan_id \| null}` (null = unplanned) → recompute |
| GET | `/positions/export.csv?…filters` | |
| GET | `/market-data/ohlc?symbol_id&tf&from&to&account_id` | `[{ts,o,h,l,c,v}]` |
| POST | `/ocr/uploads` | multipart → 202 `{id}`; WS `ocr.completed` |
| GET | `/ocr/uploads/{id}` | `{status, fields{name:{value, confidence}}, read_count, total}` |
| POST | `/ocr/uploads/{id}/confirm` | position payload ที่ user แก้แล้ว → Position (`source=ocr`, แนบภาพ) |

### emotions / review
| Method | Path | Request → Response |
|---|---|---|
| GET / POST | `/emotion-tags` | `{label_th, label_en, valence}` (user tag) |
| POST | `/emotion-logs` | `{owner_type, owner_id, phase, mood, confidence?, tags[], trigger_event?, reason_code?, note?}` |
| GET | `/inbox` | in-trade prompts ที่ยังไม่ตอบ `[{id, position_id, trigger_event, detail}]` |
| POST | `/inbox/{id}/answer` · `/dismiss` | emotion log payload |
| GET / PUT | `/daily/{date}` | `{mood?, tags[], journal?}` |
| GET / PUT | `/positions/{id}/review` | draft `{what_went_well, what_went_wrong, lesson, would_take_again, self_scores{analysis,planning,emotion}, mistake_category_ids[], post_emotion{...}, attachment_ids[]}` |
| POST | `/positions/{id}/review/submit` | → recompute quality |
| GET | `/mistake-categories` | |

### metrics / stats / calendar / diagnosis / coach
| Method | Path | Request → Response |
|---|---|---|
| GET | `/today` | `{pnl_today, r_today, trades_today, daily_loss, adherence_week, goal?, todo{pending_match, pending_review, inbox}}` |
| GET | `/stats/summary?from&to&setup_id` | `{pnl{net, win_rate, wins, losses, profit_factor, gross_win, gross_loss, expectancy_r, avg_win_r, avg_loss_r, max_dd_pct}, behavior{avg_adherence, avg_quality, grade, unplanned_pct, mistake_cost_r, mistake_cost_amount, deltas}}` |
| GET | `/stats/equity?from&to&unit` | `{points[], max_dd{from,to,pct}}` |
| GET | `/stats/quadrants` | `{good_win, good_loss, bad_win, bad_loss}` |
| GET | `/stats/breakdown?by=setup\|session\|dow\|symbol\|emotion_tag` | `[{key, label, trades, net_r, net_amount, expectancy_r, win_rate}]` |
| GET | `/calendar?month=&unit=` | `{days[{date, pnl, r, trades, mood, avg_adherence, grade}], weeks[], month_summary}` |
| GET | `/calendar/days/{date}` | `{summary, positions[], journal, verdict}` |
| GET | `/diagnosis?from&to&unit=R\|$\|%` | `{dimensions{...}, primary{dimension, cost_r, share, explanation_key}, top_mistakes[], by_emotion_tag[]}` |
| GET | `/coach/reports?cursor` · `/coach/reports/{id}` | `{period, period_start, status, primary_dimension, summary_md, evidence[{position_ref, quadrant, note, r}], recommendations[3]}` |
| POST | `/coach/reports` | `{period:"week", period_start?}` → 202 |

### alerts / news
| Method | Path | Request → Response |
|---|---|---|
| GET | `/alerts?type=rule_breach\|news\|mentor\|system&account_id&unread&cursor` | `{items, unread_count}` |
| POST | `/alerts/{id}/read` · `/alerts/read-all` | |
| GET | `/news?from&to&impact[]&currencies[]` | `[{id, currency, title, impact, scheduled_at, forecast, previous, actual, blackout{from,to}?}]` |

### mentorship / comments
| Method | Path | Request → Response |
|---|---|---|
| GET / POST | `/mentor-links` | trader เชิญ `{email}` (ส่งอีเมล invite) |
| PATCH | `/mentor-links/{id}` | `{pnl_visibility, can_assign_rules, forward_alerts}` |
| DELETE | `/mentor-links/{id}` | revoke |
| POST | `/mentor-links/{id}/resend` | |
| GET | `/assignments` · POST `/assignments/{id}/accept` · `/reject` | rule ที่ accept → `trading_rules` (F-22 AC5) |
| GET | `/mentor/invites` · POST `/mentor/invites/{id}/accept` | ฝั่ง mentor |
| GET | `/mentor/traders?period=` | `[{trader, accounts, trades, avg_adherence, grade, unplanned_pct, good_pct, primary_dimension, net_r, net_amount?, pending_reviews, visibility}]` |
| GET | `/mentor/review-queue` | |
| GET | `/mentor/alerts` | alert ที่ forward มา |
| GET | `/mentor/positions/{id}` | detail แบบ read-only (R-only serializer) |
| PUT | `/mentor/positions/{id}/scores` | `{scores{dim:25..100}, mistake_category_ids[], note?}` (source=mentor) |
| POST | `/mentor/assignments` | `{trader_id, kind: rule\|goal, payload, due_at?}` |
| GET / POST | `/comments?target_type&target_id` | `{body, parent_id?}` |

### realtime
`WS /ws?token=` → event types: `alert.created`, `position.created`, `position.updated`, `match.pending`, `metrics.updated`, `ocr.completed`, `inbox.prompt`, `sync.status`, `coach.report.ready`, `comment.created`, `inbox.counts`

---

## 7. Testing strategy

### 7.1 Backend — pytest
- **Unit (ไม่มี DB)**
  - Risk calculator: XAUUSD (contract 100), EURUSD, USDJPY, GBPJPY, cross ที่ต้องแปลง quote currency → เทียบค่าที่ได้จาก MT5 จริง (ตาราง golden ใน `tests/fixtures/risk_mt5.csv`) คลาดเคลื่อน ≤1% (F-03 AC3)
  - Position math: scale-in/partial avg entry/exit, net P/L รวม commission/swap, R จาก initial risk, MAE/MFE
  - Matching: tolerance 0.3×SL, valid_until, หลาย candidate → pending, plan lock หลัง entry → unplanned
  - Plan state machine ครบทุก transition + expire
  - Adherence/Quality engine จาก **scenario fixture YAML** (`tests/fixtures/trades/*.yaml` = plan + risk snapshot + executions + modifications + news + expected deviations/scores):
    - `follow_plan_hit_sl` → adherence = 100 (F-13 AC7) และเป็น Good-Loss
    - `good_loss`, `bad_win` (ขยับ SL แล้วชนะ), `unplanned`, `sl_widened`, `revenge_trade` (เปิดภายใน cooldown หลังโดน SL) — ตาม Phase 6
    - `oversize_11pct`, `early_exit`, `missed_partial`, `missed_be`, `news_blackout`, `max_trades_exceeded`, `max_daily_loss`
  - **Quality ไม่ใช้ P/L** (F-14 AC5): property test — สุ่ม scenario, เปลี่ยน exit price/pnl แต่คง deviations → quality score และ grade เท่าเดิม; และ static test ว่า signature ของ `quality.compute()` ไม่มี field P/L
  - Final score priority mentor > self > auto + weights, grade boundary, quadrant
  - Anonymizer ของ AI Coach ไม่มี email/account_number/display_name (F-16 AC2)
- **Integration (Postgres + Redis จริงใน docker)**
  - Auth (FastAPI): JWT ผิด/หมดอายุ/ไม่มี/kid ไม่รู้จัก/session ถูก revoke → 401; ทุก route ยกเว้น health → 401 เมื่อไม่มี token (F-01 AC7)
  - Auth (Better Auth, `auth/` vitest + Postgres): sign-up (<8 → error), sign-in ด้วย hash argon2 เดิมจาก Phase 1 (AC8), reset password ใช้ซ้ำไม่ได้/revoke session (AC5–AC6), forgot ตอบเหมือนกันทั้งมี/ไม่มี email
  - **Ownership matrix**: ทุก endpoint ที่มี `{id}` — user B เรียกของ user A ได้ 404 (generate test จาก route table อัตโนมัติ) (F-01 AC4)
  - Mentor: write endpoints → 403, `r_only` → ไม่มี key เงินใน JSON ทุก response (walk JSON หา field ต้องห้าม) (F-22 AC2, AC6), audit log ถูกเขียน
  - Ingest idempotent: deal เดิม 2 ครั้ง = 1 record (F-08 AC3); latency ingest → alert ใน WS < 5s (F-20 AC1)
  - Risk profile เปลี่ยน → adherence เทรดเก่าไม่เปลี่ยน (F-02 AC4)
  - AI Coach ล้มเหลว (mock 500) → retry 3 → `status=error`, endpoint อื่นปกติ (F-16 AC4)
- เครื่องมือ: `pytest-asyncio`, `httpx.AsyncClient`, `factory-boy`/builder ของเราเอง, `freezegun`/`time-machine`, `respx` (mock HTTP provider), coverage ≥ 85% สำหรับ `metrics/engine` และ `plans`

### 7.2 Frontend — vitest + @vue/test-utils
- `lib/format`: เครื่องหมาย `+`/`−` (U+2212) ทุกกรณี, digits ตาม symbol, compact, locale th/en, timezone
- Component: TtPnl (r_only ไม่ render `$`), TtButton variants/disabled, TtField (error/lowconf), TtSegmented keyboard, TtChecklist (required block), TtMoodScale, TtRing สีตามคะแนน, TtCalendarDay
- Store: accounts filter, ui theme (system + media query mock), session refresh
- API client: 401 → refresh 1 ครั้ง → retry; refresh ล้ม → logout
- i18n: test ว่า key ใน `th.json` และ `en.json` ตรงกันครบ; eslint `@intlify/vue-i18n/no-raw-text` ใน CI (F-23 AC2)

### 7.3 E2E + visual — Playwright
- Seed ข้อมูล demo ที่ตรงกับภาพแบบ (`backend/app/seeds/demo` — Nook Knight, FTMO 100K, เทรด 9 ต.ค. ฯลฯ) และ freeze เวลา `2026-10-09 08:00 +07:00` → screenshot จะเทียบกับ `screens/*` ได้ตรงที่สุด
- Projects: `desktop-light` (1440×900), `desktop-dark`, `mobile-light` (390×844), `mobile-dark`
- **Visual check 2 ชั้น**: (1) เก็บ screenshot ลง `docs/qa/phase-N/` แล้วเปิดคู่กับภาพแบบไล่ตรวจด้วยตา (ภาพแบบใช้ system font จึง pixel-diff ตรงๆ ไม่ได้) (2) เมื่อหน้าผ่านการตรวจแล้ว เก็บเป็น baseline `toHaveScreenshot` เพื่อจับ regression
- Accessibility: `@axe-core/playwright` ทุกหน้า (contrast AA ทั้งสองธีม, label, focus)
- Flow หลัก (Phase 8): register → onboarding → analysis → plan lock → manual trade → match → review → dashboard; mentor invite → accept → r_only view
- PWA: offline shell + อ่านหน้าที่ cache ไว้ (F-23 AC1)

### 7.4 CI (GitHub Actions)
- `backend`: ruff (lint+format), mypy (strict ใน `core`, `metrics/engine`), pytest (services postgres:17, redis:7)
- `frontend`: eslint, vue-tsc, vitest, build
- `e2e` (main branch / nightly): docker compose up → Playwright
- Script ตรวจ design rules: grep hex/rgb นอก `design-system/` + `tokens`, `text-white`/`text-ink-inverse` บน `bg-brand-600`, import icon นอก Hugeicons

---

## 8. Risks & open questions

### 8.1 จาก spec §5 + ข้อเสนอ default

| # | คำถาม | Default ที่เสนอ | ตัดสินภายใน |
|---|---|---|---|
| S1 | News provider | ทำ adapter interface; เริ่มด้วย **Finnhub** economic calendar (มี API ทางการ) แล้วเทียบ FMP; ไม่ scrape ForexFactory (ToS เปราะ) | Phase 6 |
| S2 | Quality weights + rubric | weight เท่ากัน 6 มิติ (1/6) ใน config; rubric 4 ระดับ 25/50/75/100 ตามแบบ; grade A ≥ 85, B ≥ 70, C ≥ 55, D < 55 (สอดคล้องกับภาพ: 58 = C, 71/74 = B) | Phase 6 |
| S3 | Matching tolerance | ราคา ≤ 0.3×ระยะ SL, เวลา: entry อยู่ระหว่าง `locked_at` – `valid_until`; เก็บค่าใน config ต่อ user ปรับได้ภายหลัง; log distance จริงไว้ validate | Phase 4 |
| S4 | MT5 bridge | **EA (MQL5)** — แบบ (`04-ConnectBroker`, `14-WAccounts`) ออกแบบรอบ EA + API key; Python package ต้องมี Windows VPS ต่อ user | Phase 4 |
| S5 | Attachment storage | **S3-compatible** ตั้งแต่แรก (MinIO ใน docker compose, prod ใช้ R2/S3) — โค้ดเส้นเดียว · **Phase 2 (2026-10-28):** เริ่มด้วย `LocalStorage` (disk, volume `media`) หลัง interface `core/storage.py` เพราะ pull image MinIO ไม่ได้; ไฟล์ส่งผ่าน API ที่ตรวจ owner (`GET /attachments/{id}/content`) ไม่ใช้ public URL — เพิ่ม S3 adapter ก่อน production | Phase 2 / 8 |
| S6 | Better Auth: แยก Node service หรือรวมกับ web; FastAPI ตรวจแบบ JWT/JWKS หรือถาม Better Auth ทุก request | **ตัดสินแล้ว:** Node service แยก + JWT/JWKS + เช็ก `auth_sessions` (§5.3) | Phase 2 ✅ |
| S7 | Email provider production | dev = Mailpit; prod = SMTP ผ่าน env (Resend/SES ใช้ SMTP ได้ทั้งคู่) | Phase 8 |

### 8.2 สิ่งที่ภาพออกแบบไม่ครอบคลุม — default

| เรื่อง | Default |
|---|---|
| Loading | Skeleton รูปทรงเดียวกับเนื้อหา (card/ตาราง/กราฟ) บน `surface-sunken`, ไม่ใช้ spinner เต็มหน้า; ปุ่มแสดง loading ในตัว |
| Empty | 1 ประโยค + 1 ปุ่ม primary ตาม README (เช่น "ยังไม่มีแผนวันนี้ — เริ่มจากวิเคราะห์ตลาด" → [สร้าง Analysis]); ไอคอน 24px `ink-subtle` |
| Error | `TtAlert --loss` ในตำแหน่งของ section ที่ล้ม + ปุ่ม "ลองใหม่"; ส่วนอื่นของหน้ายังใช้ได้ (สำคัญกับ AI Coach F-16 AC4); 404 → หน้า not-found ใน shell |
| Offline | แถบ `TtAlert --warning` ด้านบน "ออฟไลน์ — แสดงข้อมูลล่าสุดที่บันทึกไว้", ปิดปุ่มที่ต้องเขียนข้อมูล |
| Form validation | inline ใต้ช่อง (`tt-help--error`) + สรุปบนสุดเมื่อ submit ล้ม; ปุ่ม primary disabled พร้อมเหตุผลใน label/helper |
| ยืนยันการลบ/revoke | Modal + ปุ่ม `danger`; ลบบัญชีผู้ใช้ต้องพิมพ์รหัสผ่าน |
| Plan สถานะอื่น (missed/invalidated/expired/closed) | หน้าเดียวกับ locked แต่ read-only + badge ตาม Badge.md + เหตุผล |
| Trade เปิดอยู่ (open) | Detail แสดง unrealized ไม่ได้ (ไม่มี price feed) → แสดง "เปิดอยู่" + SL/TP ปัจจุบัน, ไม่มี adherence/quality |
| Dark theme | ไม่มีภาพ dark — ใช้ token dark; ตรวจ contrast ด้วย axe ทุกหน้า |
| Register บน desktop | ใช้ split layout ของ Login + ฟอร์มจาก `02-Register` |
| Forgot password, terms/privacy pages | ไม่มีแบบ — ดู Q3 |
| ภาพ PWA icon / splash | ยังไม่มี logo → icon ชั่วคราวเป็น wordmark "TT" บน `brand-600` (ต้องได้รับอนุมัติ) |

### 8.3 Spec ↔ Design ไม่ตรงกัน / data model ที่ต้องเพิ่ม

| # | จุด | ข้อเสนอ |
|---|---|---|
| M1 | `components/AppBar.md`, `BottomNav.md`, `Tabs.md`, `CalendarDay.md` บอกให้ใช้ `brand-600` กับ wordmark / nav active / tab active / today outline แต่ `components.css`, README และ CLAUDE.md ใช้ `brand-700` (pastel อ่านไม่ออกเป็นตัวอักษร) | ยึด `components.css` = `brand-700`; แก้ไฟล์ .md 4 ไฟล์ให้ตรง (ขออนุญาตแก้ design-system docs) |
| M2 | ความกว้าง content: README 1200px vs CLAUDE.md/`screens.css` 1240px | ใช้ 1240px |
| M3 | `design-system/tailwind.config.js` ไม่ map `chart-grid`, `chart-actual`, `focus-ring`, `overlay`, z-index | extend ใน `frontend/tailwind.config.ts` (ไม่สร้างค่าใหม่ แค่ map token ที่มี) |
| M4 | `.toggle::after` ใน `screens.css` ใช้ `#FFFFFF` hard-code (ขัดกฎ no hex) | ใช้ `var(--surface-raised)` สำหรับปุ่มกลม หรือเพิ่ม token `--toggle-knob` ใน tokens.json — ต้องการคำตัดสิน design |
| M5 | Scenario: web A/B, mobile A/B/C | ใช้ label อิสระ A–Z; segmented แสดง scenario ที่มีใน analysis + ตัวถัดไป |
| M6 | ปุ่ม "ล็อกแผน (2/3)" นับ checklist ทุกข้อ แต่ AC3 บล็อกเฉพาะข้อ required | ปุ่มแสดง done/total ตาม Checklist.md แต่ disabled เฉพาะเมื่อ required ขาด และ helper ระบุชื่อข้อที่ขาด |
| M7 | `05-WPlan` สถานะ Draft แต่มี "rev 2 แก้หลังเข้าเทรด" (draft ไม่มี revision) | ถือเป็น mock; ทำสถานะ locked ตาม `WPlan.dc.html` (`locked` variant) + `08-PlanLocked` |
| M8 | Mentor ให้คะแนน: web ครบ 6 มิติ, mobile แค่ Planning + Emotion | ให้ครบ 6 มิติทั้งสองขนาด (F-14 AC3 mentor override ได้ทุกมิติ) mobile ใช้ accordion |
| M9 | Settings web มี toggle "คอมเมนต์จาก Mentor" / Alerts web มี filter "ระบบ" — mobile ไม่มี | ทำให้เหมือนกันทั้งสองขนาด |
| M10 | Web Performance (`11`) ไม่มี breakdown ตาม setup/session/day-of-week/symbol (F-18 AC3) แต่ mobile `18` มี (ยกเว้น symbol) | เพิ่ม section Breakdown บน web ใต้ Behavior ใช้การ์ดแบบ mobile + เพิ่ม symbol; emotion tag อยู่ใน Diagnosis/Behavior ตามแบบ |
| M11 | Tabs.md: Performance = ภาพรวม·Behavior·Breakdown·Diagnosis; mobile = P/L·Behavior·Diagnosis·AI Coach; web แยก `/stats` กับ `/diagnosis` | web ตามภาพ (2 route), mobile ตามภาพ (4 แท็บใน `/stats`) ใช้ component เดียวกัน; แก้ Tabs.md |
| M12 | AI Coach อ้าง "#T-1042" แต่ data model ใช้ uuid | เพิ่ม `positions.ref_no` (running number ต่อ user) |
| M13 | API key แสดง masked + ปุ่ม copy ในหน้า Accounts แต่ spec เก็บแบบ hash | เก็บ `key_prefix` + `key_last4`; copy key เต็มได้เฉพาะตอนสร้าง/rotate (onboarding, "สร้าง key ใหม่") |
| M14 | ปุ่ม "Sync ตอนนี้" ของ MT5 EA แต่ EA เป็นฝั่ง push | EA poll `GET /ingest/commands` ทุก 10s รับคำสั่ง resync; หรือซ่อนปุ่มสำหรับ MT5 |
| M15 | "Journal ของวัน" (Calendar, DaySheet) ไม่มี entity | ใช้ `emotion_logs` (`owner_type=day`, `phase=daily`) + `note` เป็น journal — ไม่สร้างตารางใหม่ |
| M16 | In-trade prompt มีตัวเลือกเหตุผล ("กลัวโดน SL ก่อนกลับตัว" …) | เพิ่ม `emotion_logs.reason_code` (+ ตาราง reason ตาม trigger_event) |
| M17 | Alerts ในแบบมี mentor comment, sync ล้มเหลว, รายงาน AI พร้อม, งานมอบหมาย — spec มีแค่ `rule_breach/news` | ขยาย `alerts.type` = `rule_breach \| news \| mentor \| system` + `subtype` |
| M18 | สิทธิ์ "ส่ง alert ผิดกฎให้ Mentor" ต่อ mentor (F-20 AC4 "ตั้งค่าได้") ไม่มีฟิลด์ | เพิ่ม `mentor_links.forward_alerts` |
| M19 | Settings การแจ้งเตือน 5 toggle + นาทีก่อนข่าว, ธีม, รูปโปรไฟล์ | เพิ่ม `users.theme`, `users.notification_prefs (jsonb)`, avatar ผ่าน `attachments(owner_type=user)` |
| M20 | "รหัสผ่าน & อุปกรณ์ที่เข้าสู่ระบบ (2 อุปกรณ์)" | ~~refresh_tokens family~~ → ใช้ `auth_sessions` ของ Better Auth (`user_agent`, `ip_address`) + `listSessions/revokeSession` |
| M21 | Login มี "จดจำฉันไว้" + "ลืมรหัสผ่าน?", Register มี "ยอมรับเงื่อนไข/นโยบาย" | remember = Better Auth `rememberMe` (ไม่ติ๊ก = session cookie); forgot password = F-01 AC5 (Phase 2) |
| M22 | ช่องค้นหา (Today topbar, Trades) ไม่มีใน spec | ค้นหาใน `/trades` (symbol/setup/tag) ใน Phase 4; ช่องค้นหาบน Today เปิดหน้า Trades พร้อม query |
| M23 | ปุ่ม "แชร์ให้ Mentor" ใน Trade detail แต่ spec ให้ mentor เห็นข้อมูลทั้งหมดผ่าน link | เสนอให้ปุ่มนี้ = "ขอรีวิว" → ใส่ `positions.review_requested_at` และคิวรีวิว mentor = เทรดที่ขอ + เทรดที่ trader รีวิวแล้วแต่ mentor ยังไม่ให้คะแนน → Q7 |
| M24 | Goal จาก mentor ("Adherence ≥ 85% ในเดือน ต.ค.", แสดงบน Today) — spec มี `mentor_assignments.kind=goal` แต่ไม่กำหนดรูปแบบ | `payload = {metric: adherence\|quality\|unplanned_pct\|max_trades, op, target, period}`; progress คำนวณจาก stats |
| M25 | User ที่เป็นทั้ง trader และ mentor ("Mentor workspace" ใน account switcher) | สลับ workspace จาก AccountSwitcher เมื่อ `is_mentor=true`; `is_mentor` เปิดเองได้ใน Settings หรือเปิดอัตโนมัติเมื่อ accept invite |
| M26 | ตาราง Accounts มี Equity แต่ spec มีแค่ snapshot รายวัน | EA/cTrader ส่ง balance/equity ใน heartbeat (`account` ใน `/ingest/events`) เก็บล่าสุดใน `trading_accounts.last_equity`; manual = balance |
| M27 | Plan revision หลัง entry (SL 4,366.78 → 4,360) และ `order_modifications` (SL widened) เป็นเหตุการณ์เดียวกันแต่จะเกิด deviation 2 ตัว | dedupe: ถ้า revision หลัง entry ตรงกับ modification เดียวกัน → deviation `sl_widened` ตัวเดียว (ติด flag `plan_revised_after_entry`) cost นับครั้งเดียว |
| M28 | วิธีคำนวณ cost ของ deviation (เช่น early exit −$486 ในเทรดที่ชนะ, SL widened ในเทรดที่ไม่โดน SL) ไม่ได้นิยามใน spec | ดู Q8 |
| M29 | ภาพ export มีปุ่มล้นกรอบ (Login/Register ปุ่มยาวเกิน field, ปุ่ม "ดูเทรดของวันนี้" ใน Calendar) | ถือเป็น artifact; ปุ่มกว้างเท่า field/card |
| M30 | Onboarding web 3 ขั้น (ผู้ใช้ ✓ → บัญชี & Risk → Broker) vs mobile "1/2, 2/2" | flow เดียวกัน (ขั้นผู้ใช้ = register) แสดง stepper ต่างกันตามขนาดจอ |

### 8.4 Technical risks

| # | Risk | ผลกระทบ | แนวทาง |
|---|---|---|---|
| R1 | C: เต็ม | npm/pip/Docker/Playwright ติดตั้งไม่ได้ | เคลียร์ C: หรือย้าย cache ไป D: (`npm config set cache D:\…`, `UV_CACHE_DIR`, Docker data-root, `PLAYWRIGHT_BROWSERS_PATH`) |
| R2 | ไม่มี git repo | commit/CI ตาม phase prompt ไม่ได้ | `git init` + `.gitignore` (ไม่ commit `frontend/dist`, `node_modules`) + remote GitHub |
| R3 | Lightweight Charts ไม่มี drawing tools ในตัว | F-05 AC2, F-19 AC3 ใช้เวลามากกว่าคาด | เขียนเป็น series primitives (อิงตัวอย่าง plugin อย่างเป็นทางการ) เริ่มจาก horizontal/rect/trendline ใน Phase 3 แล้ว ray/text/measure; pinch zoom (F-19 AC4) มีในตัว |
| R4 | OHLC ต้องมาจาก broker ของ user (EA/cTrader) — บัญชี manual/OCR ไม่มีแหล่ง OHLC | กราฟ/MAE/MFE ของเทรด manual ว่าง | fallback: ใช้ OHLC symbol เดียวกันจากบัญชีอื่นของ user; ไม่มีเลย → ซ่อนกราฟ แสดง empty state; พิจารณา data provider ภายหลัง |
| R5 | MT5 EA latency ≤5s และ WebRequest whitelist | AC1 | EA ใช้ `OnTradeTransaction` + ส่งทันที + queue retry ในไฟล์; วัด latency ด้วย mock script ใน CI |
| R6 | cTrader Open API (protobuf/TCP, OAuth app ต้องสมัคร) | Phase 4 ล่าช้า | สมัคร app ล่วงหน้า; worker เป็น process แยกใน arq; ถ้ายังไม่ได้ credential ทำ MT5 ก่อน |
| R7 | OCR ≤15s และความแม่นยำ | F-09 | Claude vision + structured output (JSON schema) ต่อ field พร้อม confidence; จำกัดภาพ ≤10MB + ย่อฝั่ง client; ชุดภาพทดสอบใน `sources/` (ต้องตรวจว่าใช้ได้) |
| R8 | Performance 5,000 เทรด ใน 2s (F-18 AC4) | | ตาราง `trade_quality_summary` materialized + index `(user_id, closed_at)`, `(account_id, closed_at)`; cache Redis ต่อ filter; ทดสอบ load ใน Phase 7 |
| R9 | ความถูกต้องของ risk calc เทียบ MT5 (≤1%) | F-03 AC3 | ต้องมีค่าจริงจาก MT5 (tick value ต่อ symbol/บัญชี) — EA ส่ง `SYMBOL_TRADE_TICK_VALUE`/contract size มาด้วย เก็บใน `account_symbol_overrides` |
| R10 | Thai font line-height + tabular nums ใน Anuphan | ตัวเลขไทยไม่ tabular | ตัวเลขเป็น Inter อยู่แล้ว (Latin digits) — ห้ามใช้เลขไทย |
| R11 | Web Push บน iOS ต้องติดตั้ง PWA ก่อน | F-20 AC2 | แสดงคำแนะนำติดตั้งเมื่อเปิดจาก iOS Safari |

### 8.5 คำถามที่ต้องตัดสินก่อนเริ่ม Phase 1

| # | คำถาม | Default ถ้าไม่ตอบ |
|---|---|---|
| Q1 | `git init` ที่ root + ใช้ GitHub (remote ไหน) สำหรับ CI? | init local, CI file พร้อมแต่รอ remote |
| Q2 | Token: import ตรงจาก `design-system/` (ปัจจุบัน) หรือ copy ไป `frontend/src/styles` ตาม phase-1 prompt? | import ตรง (แหล่งเดียว) |
| Q3 | ระบบส่งอีเมล (จำเป็นสำหรับ invite mentor F-22 AC1, export data, forgot password) — ใช้ SMTP/provider ไหน? ทำ forgot password ใน MVP ไหม? | **ตอบแล้วใน spec (2026-10-22):** forgot/reset password ทำใน Phase 2 ด้วย Better Auth, SMTP (dev Mailpit) |
| Q4 | Attachment storage S3-compatible (MinIO dev) โอเคไหม? | ใช่ |
| Q5 | Design docs ให้แก้ได้ไหม (M1, M4, M11) หรือถือว่า read-only? | แก้เฉพาะ `.md` ให้ตรงกับ `components.css` |
| Q6 | "วัน" สำหรับ max daily loss / max trades / calendar ใช้ timezone ไหน (prop firm อย่าง FTMO ใช้เวลา server CE(S)T)? | ตั้งได้ต่อบัญชี (`trading_accounts.day_timezone`) default = timezone ของ user |
| Q7 | ปุ่ม "แชร์ให้ Mentor" หมายถึงอะไร (M23)? | = "ขอรีวิว" |
| Q8 | Cost ของ deviation (M28): (ก) counterfactual "ถ้าทำตามแผน" จาก OHLC หรือ (ข) สูตรตรง เช่น early exit = กำไรที่พลาดถึง TP ตามแผน, SL widened = risk ที่เพิ่ม × ผลจริง | (ข) สูตรตรงต่อ type เขียนไว้ใน `metrics/engine/cost.py` + ตาราง ADR — ตัดสินได้ถึง Phase 6 |
