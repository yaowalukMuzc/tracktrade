# TrackTrade — Progress

> ติ๊ก `- [x]` เมื่อทำเสร็จ **และ** มีหลักฐาน (test / screenshot ใน `docs/qa/`) — ใส่ path หลักฐานต่อท้ายบรรทัดได้
> ที่มา: `docs/spec.md` §4 (Phase 1–8) และ §3 (F-01…F-23, NFR) · แผนรายละเอียดอยู่ใน `docs/PLAN.md`

## Phases (spec §4)

### Phase 1 — Foundation & Infrastructure
- [x] สร้าง monorepo: `frontend/`, `backend/`, `connectors/mt5-ea/`, `docs/` — `connectors/mt5-ea/` เป็น placeholder จนถึง Phase 4
- [x] Docker Compose: postgres17, redis, api, worker, web — ทุก service healthy + E2E `frontend/e2e/auth.flow.spec.ts` ผ่าน (2026-10-12, ทดสอบด้วย base image ที่ cache ไว้เพราะ Docker Hub ต่อไม่ได้ — ต้อง `docker compose up --build` ด้วย image จริงอีกครั้ง)
- [x] Backend skeleton: FastAPI app factory, settings (pydantic-settings), async SQLAlchemy, Alembic init, structured logging — `backend/tests` (35 tests)
- [x] Frontend skeleton: Vue3+TS+Vite+Tailwind+Pinia+Router+vue-i18n+Vite PWA, layout แบบ mobile-first พร้อม bottom nav — มีก่อน kickoff; Phase 1 เติมครบ: PWA icons (ชั่วคราว), ธีม Light/Dark/ตามระบบ, eslint (no-raw-text) + vitest, `components/ui/*` 20 ตัว, `/dev/ui`
- [x] Auth: register/login/refresh/logout, argon2, JWT, route guard ฝั่ง frontend (F-01) — `backend/tests/test_auth.py`, `frontend/e2e/auth.flow.spec.ts`, `docs/qa/phase-1/login-*.png`, `register-*.png`
- [x] ตั้ง CI: lint (ruff, eslint), type check (mypy, vue-tsc), pytest และ vitest — `.github/workflows/ci.yml`; ทุกขั้นผ่านบนเครื่อง local แล้ว แต่ยังไม่ได้รันบน GitHub Actions (ยังไม่ push)
- [x] ตั้งค่า arq worker และ WebSocket endpoint พื้นฐาน + Redis pub/sub — `backend/tests/test_realtime.py`
- [x] สร้าง seed `symbols`, `emotion_tags` และ `mistake_categories` — `backend/app/seeds/*.yaml` (30 / 17 / 25)

### Phase 2 — Accounts, Risk & Playbook
- [ ] CRUD trading_accounts + account_symbol_overrides (F-02, F-03)
- [ ] Risk profile + trading_rules พร้อมค่า default และ snapshot ต่อเทรด
- [ ] Risk calculator service (lot ↔ risk amount ↔ R:R) พร้อม unit tests เทียบกับค่า MT5
- [ ] Playbook: setups, checklist items, examples (upload attachments) (F-04)
- [ ] หน้า UI: Accounts, Risk Settings, Playbook list/detail
- [ ] Audit log middleware สำหรับ entity สำคัญ

### Phase 3 — Analysis, Plan & Plan Lock
- [ ] Market analysis CRUD + narrative rich text editor (F-05)
- [ ] ใส่ Lightweight Charts component พื้นฐาน + drawing tools + `chart_drawings` (F-19 AC3)
- [ ] Trade plan form: คำนวณ lot/risk/RR อัตโนมัติ, checklist answers, pre-trade emotion (F-06)
- [ ] Plan lock: `locked_at`, `lock_hash`, revisions append-only, บังคับกรอกเหตุผล
- [ ] Plan state machine (draft/locked/triggered/closed/skipped/missed/invalidated/expired) + job สำหรับ expire
- [ ] หน้า "Today": analysis และ plan ของวันนี้ (คล้าย Journal ของ TradeMotion)

### Phase 4 — Execution Ingestion (Manual + Sync) & Matching
- [ ] Manual position + executions entry (F-07) + การคำนวณ P/L, R และ MAE/MFE
- [ ] Ingest API (idempotent, API key ต่อบัญชี, rate limit)
- [ ] MT5 EA (MQL5): ส่ง deals/positions/SL-TP modifications + OHLC รอบเทรด (F-08)
- [ ] cTrader Open API worker: OAuth flow, sync history 90 วัน, real-time events
- [ ] `order_modifications` + การจำแนก risk increase/decrease
- [ ] Matching engine execution ↔ plan + คิว pending ใน UI (F-10)
- [ ] Unplanned flag + หน้า Connection status

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
- [x] AC1: สมัครด้วย email/password ได้ และ password ต้องยาวอย่างน้อย 8 ตัวอักษร — `test_auth.py`, `docs/qa/phase-1/register-*.png`
- [x] AC2: Login แล้วได้ access token (15 นาที) และ refresh token (30 วัน, rotate ทุกครั้งที่ใช้) — `test_auth.py` (rotate + reuse detection + grace 30s เมื่อ response หาย)
- [x] AC3: ตั้ง locale (th/en) และ timezone ได้ UI เปลี่ยนภาษาทันทีโดยไม่ต้อง reload — `test_users.py`, `e2e/login.visual.spec.ts`, หน้า `/settings`
- [ ] AC4: user คนหนึ่งเข้าถึงข้อมูลของ user อื่นไม่ได้ (API คืน 404) ยกเว้นผ่าน mentor_link ที่ active — ส่วน 404 เสร็จแล้ว (`core/access.py` + test session ของคนอื่น = 404); ส่วน mentor_link รอ Phase 8

### F-02 Trading Accounts & Risk Profile
- [ ] AC1: สร้าง/แก้/archive บัญชีได้หลายบัญชี โดยแต่ละบัญชีมี type, currency และ initial balance
- [ ] AC2: ทุกบัญชีต้องมี Risk Profile ซึ่งมีค่า default ให้ (1% ต่อเทรด, max daily loss 3%, max DD 10%, max trades 5)
- [ ] AC3: Dashboard filter ได้ทั้ง "ทุกบัญชี" และรายบัญชี
- [ ] AC4: เมื่อแก้ Risk Profile ระบบเก็บ audit log และไม่คำนวณ adherence ของเทรดเก่าใหม่ (เทรดเก่าใช้ snapshot ของ profile ณ เวลาที่เทรด)

### F-03 Symbol Specification
- [x] AC1: มี seed symbol ของ FX majors/minors และ XAUUSD/XAGUSD — `backend/app/seeds/symbols.yaml`, `test_platform.py`
- [ ] AC2: map broker symbol (เช่น `XAUUSD.m`) กับ symbol มาตรฐานได้ต่อบัญชี
- [ ] AC3: คำนวณ risk amount จาก (entry, SL, lot) ได้ถูกต้องเทียบกับ MT5 (คลาดเคลื่อนไม่เกิน 1%)

### F-04 Playbook (Structured Setups)
- [ ] AC1: สร้าง setup ที่มี checklist, TF, session, default risk, management rules และภาพตัวอย่างได้
- [ ] AC2: setup ที่ถูกใช้แล้วลบไม่ได้ ทำได้เพียง archive
- [ ] AC3: หน้า setup แสดงสถิติ: จำนวนเทรด, win rate, expectancy (R), avg adherence และ avg quality

### F-05 Market Analysis
- [ ] AC1: สร้าง analysis ต่อ symbol/วัน ได้ โดยใส่ HTF bias, key levels, TF, session, narrative และ confidence
- [ ] AC2: วาดบนกราฟ (เส้น, กล่อง, ข้อความ, horizontal line) และบันทึกเป็น `chart_drawings` ได้
- [ ] AC3: 1 analysis สร้างได้หลาย plan (scenario A/B/…)

### F-06 Trade Plan & Plan Lock
- [ ] AC1: Plan ต้องมีฟิลด์บังคับ: setup, direction, entry, SL, อย่างน้อย 1 TP และ risk %
- [ ] AC2: ระบบคำนวณ planned lot, risk amount และ R:R ให้อัตโนมัติจาก risk profile
- [ ] AC3: ถ้า checklist ข้อ required ยังไม่ครบ จะ lock ไม่ได้ (แสดงเตือน)
- [ ] AC4: เมื่อ lock ระบบบันทึก `locked_at` และ `lock_hash`; การแก้หลัง lock ต้องสร้าง revision ใหม่และกรอกเหตุผลเสมอ
- [ ] AC5: revision ที่เกิดหลัง entry จะถูกติด `changed_after_entry=true` และนับเป็น deviation
- [ ] AC6: เปลี่ยนสถานะเป็น skipped/missed/invalidated ได้พร้อมเหตุผล; plan ที่หมด `valid_until` แล้วไม่มีเทรดจะกลายเป็น `expired`
- [ ] AC7: บันทึก pre-trade emotion (mood, confidence, tags) ได้ในฟอร์ม plan

### F-07 Manual Trade Entry
- [ ] AC1: กรอก position พร้อม executions หลายรายการได้ (scale-in/partial close)
- [ ] AC2: ระบบคำนวณ net P/L, R-multiple (จาก initial risk) และ avg entry/exit ให้
- [ ] AC3: เลือก plan ที่จะผูกได้ ถ้าไม่ผูก plan หรือ plan ถูก lock หลังเวลา entry จะติด `is_unplanned=true`

### F-08 Auto Sync MT5 / cTrader
- [ ] AC1: **MT5:** สร้าง API key ต่อบัญชีได้; EA ส่ง deals, positions และการแก้ SL/TP เข้า `/ingest` ภายใน 5 วินาทีหลังเกิดเหตุการณ์
- [ ] AC2: **cTrader:** เชื่อม OAuth ได้ และ worker ดึง deals/positions แบบ real-time
- [ ] AC3: ข้อมูลซ้ำ (broker_deal_id เดิม) ต้องไม่สร้าง record ใหม่ (idempotent)
- [ ] AC4: ซิงก์ประวัติย้อนหลังได้อย่างน้อย 90 วันตอนเชื่อมต่อครั้งแรก
- [ ] AC5: ดึง OHLC (M1–D1) ช่วง ±N แท่งรอบเทรดมาเก็บใน `ohlc_bars`
- [ ] AC6: หน้า connection แสดงสถานะ, last_sync_at และ error ล่าสุด

### F-09 Screenshot Scan (OCR/AI)
- [ ] AC1: อัปโหลดภาพ (PNG/JPG ≤ 10MB) แล้วได้ข้อมูล symbol, direction, lot, entry, SL, TP, exit, เวลา และ P/L ภายใน 15 วินาที
- [ ] AC2: แสดงฟอร์มให้ user ตรวจ/แก้ก่อนยืนยัน และไม่บันทึกอัตโนมัติ
- [ ] AC3: ฟิลด์ที่ confidence ต่ำจะถูก highlight
- [ ] AC4: เมื่อยืนยันแล้ว position จะมี `source=ocr` และแนบภาพต้นฉบับไว้

### F-10 Execution ↔ Plan Matching
- [ ] AC1: position ใหม่จะ auto-match กับ plan ที่ locked ซึ่ง symbol/direction ตรงกัน และ entry ห่างจาก plan ไม่เกิน tolerance (ค่า default 0.3×ระยะ SL) ภายในเวลา `valid_until`
- [ ] AC2: ถ้ามีหลาย plan ที่เข้าเงื่อนไข หรือหาไม่เจอ ให้ `match_status=pending` และเข้าคิวให้ user เลือก
- [ ] AC3: user แก้การ match ได้ และระบบคำนวณ metrics ใหม่ทันที

### F-11 Emotion Tracking (3 จุด)
- [ ] AC1: บันทึก **Pre-trade** ได้ใน plan (F-06 AC7)
- [ ] AC2: **In-trade:** เมื่อเกิด `order_modifications` ที่เพิ่ม risk หรือปิดก่อน TP ระบบสร้าง prompt ถามเหตุผลและอารมณ์ใน inbox ของ trade
- [ ] AC3: **Post-trade:** ฟอร์ม review มี mood, tags และ note
- [ ] AC4: user สร้าง emotion tag เองได้ และ tag ระบบแสดงได้ทั้ง TH และ EN
- [ ] AC5: มี daily mood (ไม่บังคับ) แสดงบน calendar

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
- [ ] AC3: มี drawing tools (trendline, ray, horizontal, rectangle, text, measure); บันทึกและโหลดกลับได้
- [ ] AC4: ใช้งานบนมือถือได้ (pinch zoom/pan)

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
- [x] Security: hash password ด้วย argon2 — `core/security.py`
- [ ] Security: เข้ารหัส OAuth tokens (at rest)
- [ ] Security: เก็บ API key แบบ hash
- [ ] Security: rate limit บน auth และ ingest — auth เสร็จแล้ว (429 + test); ingest รอ Phase 4
- [ ] Privacy: ข้อมูลที่ส่งไป AI ไม่มี PII
- [ ] Privacy: ผู้ใช้ export และลบข้อมูลตัวเองได้
- [ ] Performance: API p95 < 300ms
- [ ] Performance: ingest event ถึง alert < 5s
- [ ] Reliability: ingest idempotent; job retry มี backoff; backup DB รายวัน
- [ ] Auditability: plan revisions, score sources และ mentor actions ตรวจย้อนหลังได้
