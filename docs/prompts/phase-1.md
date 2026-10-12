# Phase 1 — Foundation, Infrastructure, Design system ในโค้ด, App shell, Auth

ก่อนเริ่ม: อ่าน `CLAUDE.md`, `docs/PLAN.md`, `docs/PROGRESS.md` และ spec §1.5–1.6, §4 Phase 1, F-01, F-23

## A. Monorepo & infra
- โครง `frontend/`, `backend/`, `connectors/mt5-ea/`, `docs/` ตาม `docs/PLAN.md`
- `docker-compose.yml`: postgres:17, redis, api (FastAPI), worker (arq), web (Vite dev / nginx prod) พร้อม healthcheck และ `.env.example`
- CI (GitHub Actions): ruff, mypy, pytest / eslint, vue-tsc, vitest — ต้องผ่านก่อนจบ phase

## B. Backend skeleton
- FastAPI app factory, pydantic-settings, async SQLAlchemy 2, Alembic init, structured logging (JSON), error handler มาตรฐาน `{code, message, details}`
- arq worker + Redis pub/sub + WebSocket endpoint `/ws` (auth ด้วย access token) พร้อม ping test
- Seed: `symbols` (FX majors/minors, XAUUSD, XAGUSD — ใส่ digits/point/pip/contract size ถูกต้อง), `emotion_tags` (TH/EN + valence), `mistake_categories` (6 มิติ)

## C. Auth (F-01 ทุก AC)
- register / login / refresh (rotate ทุกครั้ง, 30 วัน) / logout, access token 15 นาที, argon2, rate limit
- ทุก query กรองตาม owner — เข้าถึงข้อมูลคนอื่นต้องได้ 404 (เขียน test)
- `users.locale`, `users.timezone` แก้ได้

## D. Frontend skeleton + Design system (สำคัญ)
1. Vue 3 + TS + Vite + Tailwind + Pinia + Router + vue-i18n + Vite PWA
2. Copy `design-system/tokens.css` → `src/styles/tokens.css`, merge `design-system/tailwind.config.js` เข้า `tailwind.config.ts` (`darkMode: ['selector','[data-theme="dark"]']`)
3. ฟอนต์ Google Fonts: Inter 400/500/600/700 + Anuphan 400/500/600/700, `font-family: Inter, Anuphan, …` ทั้งแอป, body line-height 1.6, ตัวเลข `tabular-nums`
4. ไอคอน `@hugeicons/vue` + `@hugeicons/core-free-icons` — ทำ wrapper `<AppIcon name size>` ที่ map ตามตาราง Iconography ใน `design-system/README.md`
5. Port คอมโพเนนต์จาก `design-system/components.css` + `components/*.md` เป็น Vue SFC ใน `src/components/ui/` อย่างน้อย: `Button`, `IconButton`, `Field` (Input/Select/Textarea + suffix + error + low-confidence), `SegmentedControl`, `Tabs`, `Chip`, `Badge`, `Grade`, `PnL`, `StatTile`, `Card`, `Alert`, `Toggle`, `Modal`, `Sheet`, `Table` — ใช้ Tailwind utilities จาก token เท่านั้น ห้าม hard-code hex
6. หน้า `/dev/ui` (เฉพาะ dev) แสดงทุกคอมโพเนนต์ทุก variant ทั้ง Light/Dark — เทียบกับ `design-system/components/*.md`
7. **App shell**
   - ≥1024px: Sidebar 240px ตาม `screens/source/WSide.dc.html` และ `screens/web/03-WToday.png` (wordmark "Track**Trade**", account switcher, เมนู วันนี้/ปฏิทิน/เทรด/สถิติ, กลุ่มเครื่องมือ, กลุ่มบัญชี, user + logout ด้านล่าง) + Topbar (title, actions)
   - <1024px: AppBar + BottomNav 5 รายการ ตาม `screens/mobile/05-Today.png`
   - ธีม Light/Dark/ตามระบบ เก็บใน user setting + localStorage
8. i18n: ไฟล์ `th.json`, `en.json` — ข้อความทุกจุดผ่าน `t()` (F-23 AC2), สลับภาษาไม่ต้อง reload (F-01 AC3)
9. **หน้า Login** `/login` ตาม `screens/web/01-WLogin.png` (split: ซ้ายพื้น Lavender `bg-brand-600` ข้อความ `text-on-brand`, ขวาฟอร์ม) และ `screens/mobile/01-Main.png`; **Register** ตาม `screens/mobile/02-Register.png` (validate รหัสผ่าน ≥8 ตัวพร้อม strength bar)
10. Route guard + auto refresh token + logout

## E. ตรวจก่อนจบ
- `docker compose up` แล้ว register → login → เห็น shell ว่าง → logout ได้
- Playwright: เปิด `/login` ที่ 1440 และ 390 แล้ว screenshot เก็บใน `docs/qa/phase-1/` — เปิดภาพคู่กับ `screens/web/01-WLogin.png` และ `screens/mobile/01-Main.png` แล้วแก้จนสี ระยะ ขนาดตัวอักษร ตรงแบบ
- contrast: ไม่มีตัวอักษรสีขาวบน `brand-600`; ข้อความสีแบรนด์ใช้ `brand-700`
- lint / type / test ผ่านทั้งหมด
- ติ๊ก `docs/PROGRESS.md`, commit เป็นชิ้นตามหัวข้อ A–D แล้วสรุปสิ่งที่ทำ + สิ่งที่ค้าง
