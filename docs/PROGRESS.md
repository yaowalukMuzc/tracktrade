# TrackTrade — Progress

> ติ๊ก `- [x]` เมื่อทำเสร็จ **และ** มีหลักฐาน (test / screenshot ใน `docs/qa/`) — ใส่ path หลักฐานต่อท้ายบรรทัดได้
> ที่มา: `docs/spec.md` §4 (Phase 1–8) และ §3 (F-01…F-23, NFR) · แผนรายละเอียดอยู่ใน `docs/PLAN.md`

## Phases (spec §4)

### Phase 1 — Foundation & Infrastructure
- [x] สร้าง monorepo: `frontend/`, `backend/`, `connectors/mt5-ea/`, `docs/` — `connectors/mt5-ea/` เป็น placeholder จนถึง Phase 4
- [x] Docker Compose: postgres17, redis, api, worker, web — ทุก service healthy + E2E `frontend/e2e/auth.flow.spec.ts` ผ่าน (2026-10-12, ทดสอบด้วย base image ที่ cache ไว้เพราะ Docker Hub ต่อไม่ได้ — ต้อง `docker compose up --build` ด้วย image จริงอีกครั้ง)
- [x] Backend skeleton: FastAPI app factory, settings (pydantic-settings), async SQLAlchemy, Alembic init, structured logging — `backend/tests` (35 tests)
- [x] Frontend skeleton: Vue3+TS+Vite+Tailwind+Pinia+Router+vue-i18n+Vite PWA, layout แบบ mobile-first พร้อม bottom nav — มีก่อน kickoff; Phase 1 เติมครบ: PWA icons (ชั่วคราว), ธีม Light/Dark/ตามระบบ, eslint (no-raw-text) + vitest, `components/ui/*` 20 ตัว, `/dev/ui`
- [x] Auth: register/login/refresh/logout, argon2, JWT, route guard ฝั่ง frontend (F-01) — `backend/tests/test_auth.py`, `frontend/e2e/auth.flow.spec.ts`, `docs/qa/phase-1/login-*.png`, `register-*.png` · **หมายเหตุ:** auth ชุดนี้เขียนเองบน FastAPI และจะถูกแทนด้วย Better Auth ใน Phase 2 (spec อัปเดต 2026-10-22)
- [x] ตั้ง CI: lint (ruff, eslint), type check (mypy, vue-tsc), pytest และ vitest — `.github/workflows/ci.yml`; ทุกขั้นผ่านบนเครื่อง local แล้ว แต่ยังไม่ได้รันบน GitHub Actions (ยังไม่ push)
- [x] ตั้งค่า arq worker และ WebSocket endpoint พื้นฐาน + Redis pub/sub — `backend/tests/test_realtime.py`
- [x] สร้าง seed `symbols`, `emotion_tags` และ `mistake_categories` — `backend/app/seeds/*.yaml` (30 / 17 / 25)

### Phase 2 — Auth (Better Auth), Accounts, Risk & Playbook
- [x] ระบบ Auth (Better Auth): login/register/forgot-password/reset-password + guard ทุกหน้า (F-01 AC5–AC8) — 2026-10-28
  - [x] ตั้ง Better Auth service (email/password, argon2, rate limit) + เพิ่มเข้า Docker Compose — `auth/` (`src/auth.ts`, `auth/test/*.spec.ts` 13 tests), `auth/Dockerfile`, service `auth` + `mailpit` ใน `docker-compose.yml`, nginx `/api/auth/` · ⚠️ ยัง build docker ไม่ได้เพราะ Docker Hub ต่อไม่ได้ (TLS timeout) — ทดสอบทั้ง stack แบบ native แทน ต้อง `docker compose up --build` อีกครั้ง
  - [x] ส่ง email reset password ผ่าน SMTP (dev: Mailpit) — `auth/src/mailer.ts` (TH/EN ตาม locale), `auth/test/auth.spec.ts`, `frontend/e2e/password-reset.spec.ts` (อ่านอีเมลผ่าน Mailpit API)
  - [x] FastAPI ตรวจ session/JWT จาก Better Auth แทน JWT ที่เขียนเอง; endpoint ที่ไม่ใช่ health/auth คืน 401 — `core/security.py` (JWKS), `modules/auth/deps.py` (+ เช็ก `auth_sessions`), `backend/tests/test_auth.py` (ไล่ทุก route ใน OpenAPI)
  - [x] Frontend: หน้า Forgot/Reset password, ใช้ Better Auth client, route guard ทุกหน้า — `api/authClient.ts`, `features/auth/ForgotPasswordView.vue`, `ResetPasswordView.vue`, `docs/qa/phase-2/forgot-*.png`, `reset-*.png`, e2e `auth.flow` + `password-reset` ผ่านทั้ง desktop/mobile
  - [x] Migration user เดิม + ถอด auth เดิม (`refresh_tokens`, `/auth/*` ของ FastAPI) — `alembic/versions/20261028_0002_better_auth.py`, `backend/tests/test_migrations.py`, `auth/test` (login ด้วย hash argon2 จาก Phase 1)
- [x] CRUD trading_accounts + account_symbol_overrides (F-02, F-03) — `modules/accounts/*`, `tests/test_accounts.py` (CRUD, archive/unarchive, mapping + resolve `XAUUSD.m`, ownership 404)
- [x] Risk profile + trading_rules พร้อมค่า default และ snapshot ต่อเทรด — default 1/3/10/5 + cooldown 30 / blackout 15; snapshot = ตาราง `risk_profile_versions` (append-only) + `risk_profile_at(account, time)`; เทรดจะเก็บ version id ใน Phase 4; rules 4 แบบ (`no_trading_window`, `max_lot_vs_plan`, `max_consecutive_losses`, `custom`)
- [x] Risk calculator service (lot ↔ risk amount ↔ R:R) พร้อม unit tests เทียบกับค่า MT5 — `modules/risk/calculator.py`, `POST /risk/calc`, `tests/test_risk_calculator.py` + `tests/fixtures/risk_mt5.csv` (EURUSD, XAUUSD, XAGUSD, USDJPY, GBPJPY, EURGBP, บัญชี EUR) · ⚠️ ค่า golden คำนวณจากสูตร profit ของ MT5 (Forex/CFD calc mode) ไม่ได้ export จาก terminal จริง — ควรเทียบกับ MT5 จริงเมื่อมี EA (Phase 4) และ broker override `tick_value` จะใช้แทนเมื่อ EA ส่งมา
- [x] Playbook: setups, checklist items, examples (upload attachments) (F-04) — `modules/playbook/*`, `modules/attachments/*`, `tests/test_playbook.py` (checklist เรียง/คง id, archive, ลบได้เฉพาะที่ไม่ถูกใช้ → 409 `setup_in_use`, รูปตรวจจาก bytes ≤10MB) · storage = disk (`core/storage.py`, volume `media`) แทน MinIO ไว้ก่อน (Docker Hub ใช้ไม่ได้) — interface พร้อมต่อ S3
- [x] หน้า UI: Accounts, Risk Settings, Playbook list/detail — `features/accounts`, `features/playbook`, `features/onboarding` (+ `/onboarding` guard เมื่อยังไม่มีบัญชี), account switcher ใช้ข้อมูลจริง; e2e `accounts.visual`, `playbook.visual`, `onboarding.visual` (desktop/mobile × light/dark) → `docs/qa/phase-2/*.png` · ส่วนที่ยังไม่มีข้อมูลแสดง "—"/empty state: สถิติ setup (Phase 7), balance/usage จริง + สถานะเชื่อมต่อ (Phase 4)
- [x] Audit log middleware สำหรับ entity สำคัญ — `modules/audit/*` (ตาราง `audit_logs` before/after เฉพาะ field ที่เปลี่ยน) บันทึกจาก service ของ account / risk profile / rules / symbol mapping / setup; `GET /accounts/{id}/audit-log`

> **การตัดสินใจ Better Auth (spec §5 — ตัดสินตอนเริ่ม Phase 2, 2026-10-28):** ดูรายละเอียดใน `docs/PLAN.md` §5.3
> - แยกเป็น Node service `auth/` (container `auth`) — nginx/Vite proxy `/api/auth/*` → auth, `/api/v1/*` → FastAPI (same-origin, cookie httpOnly)
> - FastAPI ตรวจ **JWT ของ Better Auth (jwt plugin) ผ่าน JWKS** + เช็กว่า session (`sid`) ยังอยู่ใน `auth_sessions` เพื่อให้ revoke มีผลทันที (AC6)
> - ตาราง auth ใช้ Alembic เป็นเจ้าของ schema เดียว (`users` + `auth_sessions/auth_accounts/auth_verifications/auth_jwks`)

### Phase 3 — Analysis, Plan & Plan Lock
- [x] Market analysis CRUD + narrative rich text editor (F-05) — `backend/app/modules/analysis/*` (`market_analyses`, narrative = Tiptap JSON + `narrative_text`), หน้า `/analysis/new`, `/analysis/:id` (autosave, key levels, Tiptap B/I/H2/รูป); `test_analysis.py`, e2e `analysis.visual`
- [x] ใส่ Lightweight Charts component พื้นฐาน + drawing tools + `chart_drawings` (F-19 AC3) — `components/chart/TradeChart.vue` (Lightweight Charts v5 + series primitive วาด trendline/ray/horizontal/rectangle/text/measure, เลือก/ลบได้, สีจาก token), `GET/PUT /chart-drawings`; vitest `TradeChart.spec.ts`, `geometry.spec.ts`; OHLC เป็น mock (`/market-data/ohlc`, `source: "mock"`) จนกว่าจะมีข้อมูลจริงจาก sync ใน Phase 4
- [x] Trade plan form: คำนวณ lot/risk/RR อัตโนมัติ, checklist answers, pre-trade emotion (F-06) — หน้า `/plans/new?analysis=`, `/plans/:id` คำนวณสดผ่าน `/risk/calc`, checklist, อารมณ์ก่อนเทรด, management toggles, preview บนกราฟ; `test_plans.py`, vitest `features/plans/form.spec.ts`, e2e `plan.visual`
- [x] Plan lock: `locked_at`, `lock_hash`, revisions append-only, บังคับกรอกเหตุผล — sha256 ของ snapshot ที่ normalize แล้ว (`plans/snapshot.py`), revision 1 = ตอน lock, revision ต่อไปต้องมี reason, DB trigger ห้าม UPDATE `trade_plan_revisions`; `test_plans.py::test_lock_hash_is_stable`, `test_locked_plan_changes_only_through_revisions`, e2e `plan.flow`
- [x] Plan state machine (draft/locked/triggered/closed/skipped/missed/invalidated/expired) + job สำหรับ expire — `plans/service.py` (`MANUAL_TRANSITIONS`, `mark_triggered` สำหรับ matching Phase 4, `expire_due`) + arq cron `expire_plans` ทุก 5 นาที; `test_status_changes_need_a_reason`, `test_expire_job`
- [x] หน้า "Today": analysis และ plan ของวันนี้ (คล้าย Journal ของ TradeMotion) — `GET /today` + หน้า `/` (KPI, Analysis + กราฟ, ตารางแผน, ต้องจัดการ, daily mood, ข่าว = empty state จนมี provider ใน Phase 6); e2e `today.visual` (desktop/mobile × light/dark) → `docs/qa/phase-3/*.png`

### Phase 4 — Execution Ingestion (Manual + Sync) & Matching
- [x] Manual position + executions entry (F-07) + การคำนวณ P/L, R และ MAE/MFE — `modules/positions/{calc,service,router}.py` (replay fills แบบ MT5, ใช้ profit ของโบรกเกอร์เมื่อมี, R = net / initial risk), `POST /positions` + `/positions/preview`, หน้า `/trades/new?mode=manual` (`features/trade-new`); `tests/test_position_calc.py` (ตัวเลขแบบ 10-ManualTrade: 4,403.18 / 4,383.75, +$968.00, +2.10R), `test_positions.py`, vitest `trade-new/model.spec.ts`, e2e `trade-new.flow` · MAE/MFE มาจาก `ohlc_bars` (bar ของ symbol เดียวกันจากบัญชีไหนก็ได้ — R4) — เทรด manual ที่ไม่มี bar ใดเลยจะเป็น "—"
- [x] Ingest API (idempotent, API key ต่อบัญชี, rate limit) — `POST /ingest/events` (`X-Api-Key`, protocol `connectors/mt5-ea/PROTOCOL.md`), key เก็บ sha256 + prefix/last4, rate limit ต่อ connection (`RATE_LIMIT_INGEST`), ≤2 MB; `tests/test_ingest.py` (ส่งซ้ำ/พร้อมกัน 4 request = 1 record, 401/422/413/429, event ถึง WebSocket < 5 วินาที)
- [ ] MT5 EA (MQL5): ส่ง deals/positions/SL-TP modifications + OHLC รอบเทรด (F-08) — ⚠️ เขียนครบแล้ว `connectors/mt5-ea/` (`TrackTrade.mq5`, `include/TrackTrade/*.mqh`, README ไทย/อังกฤษ, `tools/mock_ea.py`) แต่**ยังไม่ได้ compile ใน MetaEditor / ทดสอบกับบัญชี demo** (จุดที่ต้องเช็กก่อนอยู่ท้าย README) — ฝั่ง server ทดสอบด้วย payload แบบเดียวกันแล้ว
- [ ] cTrader Open API worker: OAuth flow, sync history 90 วัน, real-time events — ⚠️ โค้ดครบ (`modules/connections/ctrader/*`: OAuth + state ใช้ครั้งเดียว, token เข้ารหัส Fernet, JSON/WebSocket client, sync job retry 3 ครั้ง, process `ctrader-stream`) + `tests/test_ctrader.py` กับ fake server แต่**ยังไม่มี cTrader app (client id/secret) จึงยังไม่ได้ทดสอบกับของจริง**
- [x] `order_modifications` + การจำแนก risk increase/decrease — `calc.risk_direction` (SL ห่างขึ้น/ลบ SL = increase, เข้าใกล้/ตั้ง SL = decrease, TP = neutral); `test_position_calc.py::test_risk_direction`, `test_ingest.py` (SL widened → increase)
- [x] Matching engine execution ↔ plan + คิว pending ใน UI (F-10) — `positions/matching.py` (tolerance 0.3×SL, ช่วง locked_at–valid_until, ใช้ราคาแผน ณ เวลา entry), `GET /positions/match-queue`, `/match-candidates`, `PUT /match`; modal บน `/trades` (desktop) + `/trades/match` (mobile); `test_positions.py`, e2e `trades.spec.ts`, `docs/qa/phase-4/trades-*.png`
- [x] Unplanned flag + หน้า Connection status — `is_unplanned` + `unplanned_reason` (no_plan / plan_not_locked / locked_after_entry); แท็บการเชื่อมต่อใน `/accounts` + `/accounts/connections` (สถานะ, key แสดงครั้งเดียว, Sync ตอนนี้, ดาวน์โหลด EA, ประวัติการนำเข้า) + onboarding ขั้น Broker ใช้งานจริง; e2e `connections.visual`, `onboarding.visual` → `docs/qa/phase-4/connections-*.png`, `onboarding-broker-*.png`

> **การตัดสินใจ Phase 4 (2026-10-29)** — รายละเอียดใน `docs/PLAN.md` §5.4: protocol EA เดียว (`POST /ingest/events`, ตัวเลขเป็น string, เวลา UTC), คำสั่ง resync/ohlc ส่งกลับใน response ของ heartbeat (แทน `GET /ingest/commands`), เทรดจาก history import ที่ไม่มีแผนเลย = unplanned (ไม่เข้าคิว), แผน expired ยังจับคู่ได้ถ้า entry อยู่ในช่วงเวลา, `/positions` ใช้ offset/limit, cTrader ใช้ JSON/WebSocket

### Phase 5 — OCR Scan, Emotion & Review
- [ ] Upload ภาพ → Claude vision → extracted JSON → ฟอร์มยืนยันพร้อม highlight confidence (F-09)
- [ ] Emotion logs 3 จุด + in-trade prompt จาก modifications + daily mood (F-11)
- [ ] Trade review form + self-score rubric + mistake tags (F-12)
- [ ] Trade detail timeline (analysis → plan revisions → executions → emotions → review)
- [ ] Custom emotion tags (TH/EN)

### Phase 6 — Measurement Engine & Alerts
- [ ] Adherence engine: Price&Size, Rules, Management + deviations พร้อม cost $/R (F-13)
- [ ] Quality score engine: auto/self/mentor, weights config, grade, quadrant (F-14)
- [ ] Rule engine diagnosis: deviation → mistake category → dimension (F-15)
- [ ] Recompute pipeline (เมื่อปิด position / แก้ match / แก้ plan) ผ่าน worker
- [ ] Rule breach detection + alerts ผ่าน WebSocket + Web Push + Alert center (F-20)
- [ ] News provider integration + economic calendar UI + news blackout rule + pre-news alert (F-21)
- [ ] ชุด fixture tests: Good-Loss, Bad-Win, unplanned, SL widened, revenge trade

### Phase 7 — Analytics, Chart Overlay & AI Coach
- [ ] Trading Calendar (monthly/weekly, $/R toggle, badges) (F-17)
- [ ] Performance Dashboard: P/L section + Behavior section แยกกัน, Quality×Outcome matrix, breakdowns (F-18)
- [ ] Setup statistics ในหน้า Playbook (F-04 AC3)
- [ ] Chart overlay plan vs actual (F-19 AC1–AC2, AC4)
- [ ] AI Coach weekly report job + on-demand + หน้าแสดงรายงาน (F-16)
- [ ] Performance tuning: indexes, materialized views สำหรับ summary, Redis cache

### Phase 8 — Mentorship, Hardening & Launch
- [ ] Mentor invite/accept/revoke + permission layer (pnl_visibility, read-only) (F-22)
- [ ] Comments thread, mentor scoring, assignments (rule/goal)
- [ ] Mentor dashboard + review queue + forward alerts ไปยัง mentor
- [ ] Security review: OWASP checks, secret encryption, rate limits, data export/delete
- [ ] E2E tests (Playwright): Analysis → Plan lock → Execution → Review → Dashboard
- [ ] Load test (5,000 เทรด/ผู้ใช้, ingest burst) + backup/restore drill
- [ ] Production deploy (Docker Compose บน cloud, HTTPS, monitoring, error tracking)
- [ ] Beta onboarding กับ trader + mentor กลุ่มแรก และเก็บ feedback

---

## Acceptance Criteria (spec §3)

### F-01 Authentication & Profile
- [x] AC1: สมัครด้วย email/password ได้ และ password ต้องยาวอย่างน้อย 8 ตัวอักษร — `test_auth.py`, `docs/qa/phase-1/register-*.png` · Better Auth: `auth/test/auth.spec.ts` (sign-up)
- [x] AC2: Login แล้วได้ access token (15 นาที) และ refresh token (30 วัน, rotate ทุกครั้งที่ใช้) — Phase 1: `test_auth.py` · Better Auth: JWT 15 นาที (`/api/auth/token`) + session cookie 30 วัน (refresh ทุก 1 วัน) แทน refresh token; `auth/test/auth.spec.ts`, e2e `auth.flow`
- [x] AC3: ตั้ง locale (th/en) และ timezone ได้ UI เปลี่ยนภาษาทันทีโดยไม่ต้อง reload — `test_users.py`, `e2e/login.visual.spec.ts`, หน้า `/settings` · sign-up ส่ง locale/timezone ให้ Better Auth (validate แล้ว)
- [ ] AC4: user คนหนึ่งเข้าถึงข้อมูลของ user อื่นไม่ได้ (API คืน 404) ยกเว้นผ่าน mentor_link ที่ active — ส่วน 404 เสร็จแล้ว (`core/access.py` + test session ของคนอื่น = 404); ส่วน mentor_link รอ Phase 8
- [x] AC5: **Forgot password:** กรอก email แล้วระบบส่งลิงก์ reset (หมดอายุใน 1 ชั่วโมง, ใช้ได้ครั้งเดียว) และตอบข้อความเดียวกันไม่ว่า email จะมีในระบบหรือไม่ — `auth/test/auth.spec.ts`, e2e `password-reset`
- [x] AC6: **Reset password:** ตั้งรหัสใหม่ (≥ 8 ตัวอักษร) จากลิงก์ได้ และทุก session เดิมของ user ถูก revoke — `auth/test/auth.spec.ts`, `backend/tests/test_auth.py::test_revoked_session_stops_jwt_immediately`, e2e `password-reset`
- [x] AC7: **Guard:** ทุกหน้าที่ไม่ใช่ login/register/forgot/reset ต้อง login ก่อน (redirect ไป `/login?redirect=…`); ทุก API endpoint ยกเว้น health/auth คืน 401 เมื่อไม่มี session ที่ valid — `router/index.ts` (public เฉพาะ 4 หน้า), `backend/tests/test_auth.py::test_every_api_route_requires_a_session`
- [x] AC8: Auth ทั้งหมดใช้ Better Auth; user และข้อมูลเดิมจาก Phase 1 ย้ายมาได้โดยไม่ต้องสมัครใหม่ — migration 0002 + `test_migrations.py`, `auth/test/auth.spec.ts` (AC8)

> หมายเหตุ: AC1–AC3 ทำเสร็จแล้วด้วย auth ที่เขียนเองบน FastAPI (Phase 1) — ทดสอบซ้ำบน Better Auth แล้ว (2026-10-28)

### F-02 Trading Accounts & Risk Profile
- [x] AC1: สร้าง/แก้/archive บัญชีได้หลายบัญชี โดยแต่ละบัญชีมี type, currency และ initial balance — `test_accounts.py`, e2e `accounts.visual` (archive), onboarding
- [x] AC2: ทุกบัญชีต้องมี Risk Profile ซึ่งมีค่า default ให้ (1% ต่อเทรด, max daily loss 3%, max DD 10%, max trades 5) — `test_accounts.py::test_create_account_gets_default_risk_profile`, e2e onboarding (ค่าที่กรอกถูกบันทึก)
- [x] AC3: Dashboard filter ได้ทั้ง "ทุกบัญชี" และรายบัญชี — หน้า Today กรองตาม account switcher (`GET /today?account_id=`); `test_analysis.py::test_today`, e2e `today.visual` (สลับเป็น Demo แล้วแผนของ FTMO หายไป) · หน้ารายการ/สถิติใน Phase 4–7 ใช้ `accountParam` เดียวกัน
- [x] AC4: เมื่อแก้ Risk Profile ระบบเก็บ audit log และไม่คำนวณ adherence ของเทรดเก่าใหม่ (เทรดเก่าใช้ snapshot ของ profile ณ เวลาที่เทรด) — `test_accounts.py::test_risk_profile_update_versions_and_audit` (Phase 4 ต้องผูก position กับ version id)

### F-03 Symbol Specification
- [x] AC1: มี seed symbol ของ FX majors/minors และ XAUUSD/XAGUSD — `backend/app/seeds/symbols.yaml`, `test_platform.py`
- [x] AC2: map broker symbol (เช่น `XAUUSD.m`) กับ symbol มาตรฐานได้ต่อบัญชี — `test_accounts.py::test_symbol_mapping_and_resolve`
- [x] AC3: คำนวณ risk amount จาก (entry, SL, lot) ได้ถูกต้องเทียบกับ MT5 (คลาดเคลื่อนไม่เกิน 1%) — `test_risk_calculator.py` (ดูหมายเหตุใน Phase 2)

### F-04 Playbook (Structured Setups)
- [x] AC1: สร้าง setup ที่มี checklist, TF, session, default risk, management rules และภาพตัวอย่างได้ — `test_playbook.py`, e2e `playbook.visual`
- [x] AC2: setup ที่ถูกใช้แล้วลบไม่ได้ ทำได้เพียง archive — `test_playbook.py::test_used_setup_cannot_be_deleted_only_archived` (FK RESTRICT; trade_plans ใน Phase 3 ต้องอ้าง setups ด้วย ON DELETE RESTRICT)
- [ ] AC3: หน้า setup แสดงสถิติ: จำนวนเทรด, win rate, expectancy (R), avg adherence และ avg quality — UI + `GET /setups/{id}/stats` พร้อมแล้วแต่แสดง "—" จนกว่าจะมีเทรด (Phase 7)

### F-05 Market Analysis
- [x] AC1: สร้าง analysis ต่อ symbol/วัน ได้ โดยใส่ HTF bias, key levels, TF, session, narrative และ confidence — `test_analysis.py::test_create_analysis_with_all_fields`, e2e `analysis.visual` (สร้างผ่าน UI แล้ว reload)
- [x] AC2: วาดบนกราฟ (เส้น, กล่อง, ข้อความ, horizontal line) และบันทึกเป็น `chart_drawings` ได้ — `test_drawings_save_and_load`, e2e `analysis.visual` (วาดเส้นแนวนอน → reload)
- [x] AC3: 1 analysis สร้างได้หลาย plan (scenario A/B/…) — `test_one_analysis_many_scenarios`, e2e `plan.flow`

### F-06 Trade Plan & Plan Lock
- [x] AC1: Plan ต้องมีฟิลด์บังคับ: setup, direction, entry, SL, อย่างน้อย 1 TP และ risk % — `test_required_fields` (422), vitest `form.spec.ts`
- [x] AC2: ระบบคำนวณ planned lot, risk amount และ R:R ให้อัตโนมัติจาก risk profile — `test_planned_lot_risk_and_rr_are_calculated` (0.48 lot / $995.52 / R:R 1.94), e2e `plan.flow`
- [x] AC3: ถ้า checklist ข้อ required ยังไม่ครบ จะ lock ไม่ได้ (แสดงเตือน) — `test_lock_needs_required_checklist` (422 `checklist_incomplete` + รายการที่ขาด), e2e `plan.visual` (Alert + checklist ขอบแดง)
- [x] AC4: เมื่อ lock ระบบบันทึก `locked_at` และ `lock_hash`; การแก้หลัง lock ต้องสร้าง revision ใหม่และกรอกเหตุผลเสมอ — `test_locked_plan_changes_only_through_revisions`, e2e `plan.flow`, `plan.visual`
- [ ] AC5: revision ที่เกิดหลัง entry จะถูกติด `changed_after_entry=true` และนับเป็น deviation — ⚠️ บางส่วน: ติด flag แล้ว (`test_revision_after_entry_is_flagged`, หน้า plan แสดง "แก้หลังเข้าเทรด"); การนับเป็น deviation อยู่ใน adherence engine Phase 6
- [x] AC6: เปลี่ยนสถานะเป็น skipped/missed/invalidated ได้พร้อมเหตุผล; plan ที่หมด `valid_until` แล้วไม่มีเทรดจะกลายเป็น `expired` — `test_status_changes_need_a_reason`, `test_expire_job`
- [x] AC7: บันทึก pre-trade emotion (mood, confidence, tags) ได้ในฟอร์ม plan — `test_pre_trade_emotion`, หน้า plan (Mood / Confidence / tags)

### F-07 Manual Trade Entry
- [x] AC1: กรอก position พร้อม executions หลายรายการได้ (scale-in/partial close) — `POST /positions`, หน้า `/trades/new`; `test_manual_scale_in_partial_close_design_numbers`, e2e `trade-new.flow`
- [x] AC2: ระบบคำนวณ net P/L, R-multiple (จาก initial risk) และ avg entry/exit ให้ — `positions/calc.py`; `test_position_calc.py`
- [x] AC3: เลือก plan ที่จะผูกได้ ถ้าไม่ผูก plan หรือ plan ถูก lock หลังเวลา entry จะติด `is_unplanned=true` — `test_plan_locked_after_entry_is_unplanned`, `test_draft_plan_in_form_is_unplanned`

### F-08 Auto Sync MT5 / cTrader
- [ ] AC1: **MT5:** สร้าง API key ต่อบัญชีได้; EA ส่ง deals, positions และการแก้ SL/TP เข้า `/ingest` ภายใน 5 วินาทีหลังเกิดเหตุการณ์ — ⚠️ key + ingest + event → WebSocket < 5 วินาทีผ่านแล้ว (`test_ingest.py`); EA ส่งทันทีจาก `OnTradeTransaction` แต่ยังไม่ได้วัดใน MT5 จริง
- [ ] AC2: **cTrader:** เชื่อม OAuth ได้ และ worker ดึง deals/positions แบบ real-time — ⚠️ โค้ด + test กับ fake server (`test_ctrader.py`); รอ cTrader app credential เพื่อทดสอบจริง
- [x] AC3: ข้อมูลซ้ำ (broker_deal_id เดิม) ต้องไม่สร้าง record ใหม่ (idempotent) — `test_deal_flow_idempotent_matched_and_closed`, `test_concurrent_duplicate_batches_store_once`, `test_history_sync_imports_deals_and_picks_account`
- [ ] AC4: ซิงก์ประวัติย้อนหลังได้อย่างน้อย 90 วันตอนเชื่อมต่อครั้งแรก — ⚠️ server รับ history import ได้ (`test_history_import_does_not_flood_match_queue`), EA ส่ง 90 วันตอนรันครั้งแรก, cTrader ดึง 90 วัน (fake) — ยังไม่ได้ทดสอบกับโบรกเกอร์จริง
- [ ] AC5: ดึง OHLC (M1–D1) ช่วง ±N แท่งรอบเทรดมาเก็บใน `ohlc_bars` — ⚠️ server ส่งคำสั่ง `ohlc` ±200 แท่ง M1–D1 เมื่อเทรดปิด, เก็บ bar idempotent, คำนวณ MAE/MFE, กราฟใช้ bar จริง (`test_bars_fill_mae_mfe_and_chart`); ฝั่ง EA/cTrader ที่ดึง bar ยังไม่ได้ทดสอบจริง
- [x] AC6: หน้า connection แสดงสถานะ, last_sync_at และ error ล่าสุด — `GET /accounts/{id}/connections`, แท็บการเชื่อมต่อ + `/accounts/connections`; e2e `connections.visual`

### F-09 Screenshot Scan (OCR/AI)
- [ ] AC1: อัปโหลดภาพ (PNG/JPG ≤ 10MB) แล้วได้ข้อมูล symbol, direction, lot, entry, SL, TP, exit, เวลา และ P/L ภายใน 15 วินาที
- [ ] AC2: แสดงฟอร์มให้ user ตรวจ/แก้ก่อนยืนยัน และไม่บันทึกอัตโนมัติ
- [ ] AC3: ฟิลด์ที่ confidence ต่ำจะถูก highlight
- [ ] AC4: เมื่อยืนยันแล้ว position จะมี `source=ocr` และแนบภาพต้นฉบับไว้

### F-10 Execution ↔ Plan Matching
- [x] AC1: position ใหม่จะ auto-match กับ plan ที่ locked ซึ่ง symbol/direction ตรงกัน และ entry ห่างจาก plan ไม่เกิน tolerance (ค่า default 0.3×ระยะ SL) ภายในเวลา `valid_until` — `test_single_locked_plan_auto_matches_and_drives_plan_status`, `test_tolerance_boundary_inclusive`, `test_time_window`
- [x] AC2: ถ้ามีหลาย plan ที่เข้าเงื่อนไข หรือหาไม่เจอ ให้ `match_status=pending` และเข้าคิวให้ user เลือก — `test_two_candidates_pending_then_manual_pick_and_unplanned`, e2e `trades.spec.ts` (modal / หน้า match มือถือ) · ข้อยกเว้นที่ตั้งใจ: เทรดจาก history import ที่ไม่มีแผนเลย → unplanned (PLAN §5.4)
- [x] AC3: user แก้การ match ได้ และระบบคำนวณ metrics ใหม่ทันที — `PUT /positions/{id}/match` + สถานะแผนตาม (`sync_with_positions`) + job `recompute_position` (engine adherence/quality จะเสียบใน Phase 6)

### F-11 Emotion Tracking (3 จุด)
- [x] AC1: บันทึก **Pre-trade** ได้ใน plan (F-06 AC7) — `test_pre_trade_emotion`
- [ ] AC2: **In-trade:** เมื่อเกิด `order_modifications` ที่เพิ่ม risk หรือปิดก่อน TP ระบบสร้าง prompt ถามเหตุผลและอารมณ์ใน inbox ของ trade
- [ ] AC3: **Post-trade:** ฟอร์ม review มี mood, tags และ note
- [ ] AC4: user สร้าง emotion tag เองได้ และ tag ระบบแสดงได้ทั้ง TH และ EN
- [ ] AC5: มี daily mood (ไม่บังคับ) แสดงบน calendar — ⚠️ บางส่วน: บันทึกได้แล้วที่หน้า Today (`PUT /daily/{date}`, `test_daily_mood`, e2e `today.visual`); การแสดงบน calendar มากับ Phase 7

### F-12 Trade Review
- [ ] AC1: หลังปิด position จะมี review ที่สถานะ "รอรีวิว"
- [ ] AC2: review ประกอบด้วย what went well/wrong, lesson, would take again, self-score ตาม rubric (Analysis, Planning, Emotion) และ mistake tags
- [ ] AC3: แนบภาพและวาดบนกราฟของเทรดได้
- [ ] AC4: Timeline แสดงลำดับ analysis → plan (และ revisions) → executions/modifications → emotion logs → review

### F-13 Plan Adherence Engine
- [ ] AC1: คำนวณเมื่อ position ปิด และคำนวณใหม่เมื่อ match/plan เปลี่ยน
- [ ] AC2: **Price & Size:** ตรวจ entry slippage, SL widened/moved, TP moved, lot เกิน planned (>10%) และ early/late exit
- [ ] AC3: **Rules:** ตรวจ max trades/วัน, max daily loss, news blackout, revenge cooldown และ unplanned
- [ ] AC4: **Management:** ตรวจว่าทำ partial / BE / trailing ตาม `management_plan` หรือไม่
- [ ] AC5: deviation ทุกตัวต้องมี expected, actual และ cost ($ และ R) ที่คำนวณได้
- [ ] AC6: score_pct อยู่ในช่วง 0–100 และมี `engine_version` เพื่อ reproduce ได้
- [ ] AC7: fixture: เทรดที่ทำตามแผน 100% แต่โดน SL ต้องได้ adherence = 100

### F-14 Trade Quality Score (Hybrid)
- [ ] AC1: มีคะแนน 6 มิติ แต่ละมิติเก็บแยก source (auto/self/mentor)
- [ ] AC2: auto score ของ Execution, Risk และ Discipline คำนวณจาก deviations
- [ ] AC3: final score ใช้ลำดับ mentor > self > auto ต่อมิติ แล้วเฉลี่ยถ่วงน้ำหนัก (ปรับ weight ได้ใน config)
- [ ] AC4: ระบบกำหนด quadrant (good_win/good_loss/bad_win/bad_loss) โดยใช้ grade ≥ B เป็น "good"
- [ ] AC5: P/L **ไม่ถูกใช้** เป็น input ของ quality score (มี unit test ยืนยัน)

### F-15 Root-Cause Diagnosis (Rule Engine)
- [ ] AC1: deviation แต่ละ type map ไปยัง mistake_category/dimension ได้ (ตั้งค่าได้)
- [ ] AC2: dashboard แสดงสัดส่วน mistake ตามมิติ และ "mistake cost" รวม
- [ ] AC3: ระบุ "มิติที่เป็นปัญหาหลัก" ของช่วงเวลาที่เลือก (ใช้มิติที่ cost R สูงสุด)

### F-16 AI Coach
- [ ] AC1: สร้างรายงานรายสัปดาห์อัตโนมัติ (job ทุกวันจันทร์) และกดสร้างเองได้
- [ ] AC2: input เป็น aggregated metrics + trade summaries ที่ไม่มี PII (ไม่มี email, account number)
- [ ] AC3: รายงานต้องระบุ primary dimension, หลักฐาน (อ้างอิง trade id) และคำแนะนำ 3 ข้อ ในภาษาตาม locale
- [ ] AC4: ถ้า AI ล้มเหลว ให้ retry 3 ครั้ง แล้วแสดงสถานะ error โดยหน้าอื่นไม่ได้รับผลกระทบ

### F-17 Trading Calendar
- [ ] AC1: มุมมองรายเดือนแสดง P/L ต่อวัน (สลับ $/R ได้), จำนวนเทรด, mood และ badge adherence/quality
- [ ] AC2: คลิกวันเพื่อดูรายการเทรดและ journal ของวันนั้นได้
- [ ] AC3: มีมุมมอง Weekly และสรุปผลรวมของเดือน

### F-18 Performance Dashboard
- [ ] AC1: **P/L metrics:** net P/L, win rate, profit factor, expectancy (R), avg win/loss R, max DD และ equity curve
- [ ] AC2: **Behavior metrics (แยก section):** avg adherence, avg quality, % unplanned, Quality×Outcome matrix, mistake cost และ breakdown 6 มิติ
- [ ] AC3: breakdown ตาม setup, session, day-of-week, symbol และ emotion tag
- [ ] AC4: filter ได้ตามช่วงวันที่, บัญชี และ setup; ข้อมูลโหลดเสร็จภายใน 2 วินาทีสำหรับ 5,000 เทรด

### F-19 In-app Chart (Plan vs Actual)
- [ ] AC1: แสดงกราฟจาก `ohlc_bars` ใน TF ที่เลือก (M1–D1)
- [ ] AC2: overlay เส้น plan (entry/SL/TP แบบเส้นประ) เทียบกับ actual (จุด fill, เส้น SL/TP ที่ถูกแก้แสดงตามเวลา)
- [x] AC3: มี drawing tools (trendline, ray, horizontal, rectangle, text, measure); บันทึกและโหลดกลับได้ — `TradeChart` + `ChartToolbar`, `test_drawings_save_and_load`, e2e `analysis.visual`
- [ ] AC4: ใช้งานบนมือถือได้ (pinch zoom/pan) — ⚠️ บางส่วน: `TradeChart` เปิด pinch/drag ของ Lightweight Charts และวาดด้วยการแตะได้ (หน้า Analysis มือถือ); ยังไม่ได้ทดสอบบนเครื่องจริง — ปิดพร้อม overlay ใน Phase 7

### F-20 Alerts: Rule Breach
- [ ] AC1: เมื่อ position ใหม่ทำให้ผิด rule ระบบสร้าง `rule_breaches` และ `alerts` ภายใน 5 วินาที
- [ ] AC2: ส่ง alert ผ่าน WebSocket (ถ้าออนไลน์) และ Web Push (ถ้าอนุญาตไว้)
- [ ] AC3: alert center แสดงรายการ, mark read ได้ และ filter ตามบัญชีได้
- [ ] AC4: ถ้า mentor ได้รับสิทธิ์ จะได้รับ alert ของ trader ด้วย (ตั้งค่าได้)

### F-21 News / Economic Calendar
- [ ] AC1: ดึงข่าวรายสัปดาห์จาก provider และอัปเดตทุก 1 ชั่วโมง
- [ ] AC2: แสดงข่าวที่เกี่ยวกับสกุลเงินของ symbol ที่ trader ใช้ และ filter ตาม impact ได้
- [ ] AC3: แจ้งเตือนก่อนข่าว high-impact X นาที (ตั้งค่าได้)
- [ ] AC4: rule news blackout ใช้ข้อมูลนี้ตรวจเทรดที่เปิดในช่วง ±N นาทีรอบข่าว

### F-22 Mentorship
- [ ] AC1: trader ส่ง invite ด้วย email ได้; mentor accept แล้วสถานะเปลี่ยนเป็น active; trader revoke ได้ทุกเมื่อ
- [ ] AC2: ถ้าตั้ง `pnl_visibility=r_only` mentor ต้องไม่เห็นค่า $ ใดๆ ทั้งใน API และ UI
- [ ] AC3: mentor comment (thread) ได้ที่ position/plan/analysis/review
- [ ] AC4: mentor ให้ quality score (source=mentor) และ mistake tag ได้
- [ ] AC5: mentor มอบหมาย rule/goal ได้; rule ที่ trader ยอมรับจะเข้าไปใน `trading_rules`
- [ ] AC6: mentor แก้ข้อมูล analysis/plan/position ไม่ได้ (API คืน 403) และทุก action ถูกบันทึก audit
- [ ] AC7: mentor dashboard แสดงรายชื่อ trader, คิวเทรดที่รอรีวิว และ behavior metrics สรุปของแต่ละคน

### F-23 PWA & i18n
- [ ] AC1: ติดตั้งเป็นแอปได้บน iOS/Android/Desktop; มี offline shell และอ่านข้อมูลล่าสุดที่ cache ไว้ได้
- [ ] AC2: ข้อความทุกจุดผ่าน i18n (TH/EN) และไม่มี hard-coded string
- [ ] AC3: Mobile-first โดยใช้งานได้ครบที่ความกว้าง 375px

### Non-Functional Requirements
- [ ] Security: HTTPS
- [x] Security: hash password ด้วย argon2 — Better Auth custom hash argon2id (`auth/src/password.ts`) พารามิเตอร์เท่า Phase 1
- [x] Security: เข้ารหัส OAuth tokens (at rest) — Fernet (`core/crypto.py`, `FERNET_KEY`); `test_ctrader.py` ตรวจว่า token ใน DB ไม่ใช่ plain text
- [x] Security: เก็บ API key แบบ hash — sha256 + prefix/last4 (`connections/keys.py`); `test_key_shown_once_hashed_and_rotatable`
- [x] Security: rate limit บน auth และ ingest — auth: Better Auth `rateLimit` (`auth/test/rate-limit.spec.ts`); ingest: ต่อ connection (`test_ingest_rate_limit`)
- [ ] Privacy: ข้อมูลที่ส่งไป AI ไม่มี PII
- [ ] Privacy: ผู้ใช้ export และลบข้อมูลตัวเองได้
- [ ] Performance: API p95 < 300ms
- [ ] Performance: ingest event ถึง alert < 5s
- [ ] Reliability: ingest idempotent; job retry มี backoff; backup DB รายวัน — ingest idempotent ✅ + cTrader job retry backoff ✅ (Phase 4); backup DB รายวันรอ Phase 8
- [ ] Auditability: plan revisions, score sources และ mentor actions ตรวจย้อนหลังได้
