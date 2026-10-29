# TrackTrade — Product & Technical Specification (v0.1)

> สถานะ: Draft · อัปเดต: 2026-10-22 (เพิ่ม Better Auth, ปรับ Scope) · ขอบเขต: MVP

## 1. ภาพรวมระบบ (System Overview)

### 1.1 Vision
TrackTrade คือระบบ Trading Journal & Trade Lifecycle ที่ไม่ได้เป็นแค่สมุดบันทึก แต่ใช้วัด **ช่องว่างระหว่าง Analysis → Plan → Execution → Outcome** เพื่อหาว่าปัญหาของ trader อยู่ที่มิติไหนใน 6 มิติต่อไปนี้:
**Analysis · Planning · Execution · Risk Management · Discipline · Emotion**

### 1.2 หลักการสำคัญ
1. **Quality ≠ P/L:** Trade Quality และ Plan Adherence วัดแยกจาก P/L ทุกเทรดจัดอยู่ใน matrix 4 ช่องดังนี้:
   - Good-Win
   - Good-Loss
   - Bad-Win (ชนะเพราะโชค)
   - Bad-Loss
2. **Plan-first:** Plan ต้องถูกบันทึกและ lock ก่อน entry เพื่อป้องกัน hindsight bias
3. **Objective ก่อน Subjective:** มิติที่วัดได้จะคำนวณอัตโนมัติ ส่วนมิติที่วัดไม่ได้ให้ trader/mentor ประเมินตาม rubric
4. **Explainable diagnosis:** ใช้ rule engine แบบ deterministic เป็นฐาน แล้วให้ AI Coach สรุป pattern ต่อ

### 1.3 ผู้ใช้ (Personas & Roles)
| Role | สิทธิ์ |
|---|---|
| **Trader** | เป็นเจ้าของข้อมูล จัดการบัญชี, playbook, analysis, plan, trade และ review |
| **Mentor/Coach** | เข้าถึงได้เมื่อได้รับ invite เท่านั้น ดูข้อมูล trader ที่แชร์, comment, ให้คะแนน quality, มอบหมาย rule/goal; **แก้ข้อมูลเทรดไม่ได้**; ดูแลได้หลาย trader |

### 1.4 Scope
- **ตลาด:** Forex + Gold (CFD) จาก MT5 / cTrader
- **บัญชี:** หลายบัญชีต่อ user (Live/Demo/Prop) โดยแต่ละบัญชีมี Risk Profile ของตัวเอง
- **ภาษา:** ไทย / อังกฤษ (i18n)
- **Monetization:** MVP ใช้ฟรี แต่เตรียม feature flag/plan ไว้สำหรับ Free/Pro
- **Authentication:** ใช้ **Better Auth** แบบ email/password ครอบคลุม register, login, logout, forgot-password และ reset-password (ส่งลิงก์ทาง email)
  - ทุกหน้า (ยกเว้น login/register/forgot/reset) ต้องผ่าน auth guard ทั้งฝั่ง frontend (route guard) และ backend (ทุก endpoint ตรวจ session)
  - การแยกสิทธิ์ใน MVP มีแค่ **ownership** (user เห็นเฉพาะข้อมูลของตัวเอง) และ **การแชร์ให้ mentor ผ่าน `mentor_links`** (F-22) ซึ่งเป็นสิทธิ์ระดับข้อมูล ไม่ใช่ระบบ role
- **Out of scope (Phase หลัง MVP):**
  - **Roles/permissions:** RBAC, admin role/admin panel, organization/team, permission matrix ที่ตั้งค่าได้ (`users.is_mentor` เป็นเพียง flag สำหรับเปิดหน้า mentor dashboard)
  - Social login (Google/Apple), 2FA/passkey, magic link
  - Missions/XP/Trophy
  - Backtest replay
  - Live plan-deviation alert
  - Post-trade reminder
  - Billing
  - Crypto/หุ้น/Futures
  - Mentor group
  - Auto-detect setup/trigger

### 1.5 Tech Stack
| Layer | Technology |
|---|---|
| Frontend | Vue 3 + TypeScript, Vite, Tailwind CSS, Pinia, Vite PWA, vue-i18n, TradingView Lightweight Charts |
| Backend | FastAPI, Python 3.12+, Pydantic v2, SQLAlchemy 2 (async), Alembic |
| Auth | Better Auth (Node/TypeScript service) — email/password, session, forgot/reset password; FastAPI ตรวจ session ผ่าน JWT/JWKS ของ Better Auth; ส่ง email ผ่าน SMTP (dev: Mailpit) |
| Data | PostgreSQL 17, Redis (cache, pub/sub, job queue) |
| Realtime | WebSocket (FastAPI) + Redis pub/sub fan-out, Web Push (PWA) |
| Background jobs | arq (Redis-based worker) |
| AI | Claude API: vision สำหรับ OCR และ text สำหรับ AI Coach |
| Connectors | MT5 EA (MQL5) → ingest API; cTrader Open API (OAuth) worker |
| Deploy | Docker Compose บน cloud (web, api, worker, postgres, redis) |

### 1.6 Architecture
```
[Vue PWA] ⇄ /api/auth/* ⇄ [Better Auth service] ── PostgreSQL 17 (ตาราง auth)
    │                              │ JWKS
    ▼                              ▼
[Vue PWA] ⇄ REST/WebSocket ⇄ [FastAPI API] ── PostgreSQL 17
                                  │  └─ Redis (cache / pub-sub / queue)
                                  ▼
                            [arq Workers]
                 ├─ ingestion (MT5 / cTrader / OCR)
                 ├─ matching (execution ↔ plan)
                 ├─ metrics (adherence / quality / diagnosis)
                 ├─ alerts (rule breach / news)
                 └─ ai_coach (Claude)
[MT5 EA] ──HTTPS (account API key)──► /ingest
[cTrader Open API] ◄──OAuth worker
```
**Backend modules:** `auth`, `users`, `accounts`, `symbols`, `playbooks`, `analysis`, `plans`, `executions`, `ingestion`, `market_data`, `emotions`, `reviews`, `metrics`, `diagnosis`, `alerts`, `news`, `mentorship`, `ai_coach`, `realtime`

### 1.7 Trade Lifecycle
```
Playbook/Setup
      │
      ▼
Market Analysis (1) ──► Trade Plan (N) ──► Position (N) ──► Executions/Modifications
                         │                    │
                         ├─ Skipped/Missed    └─► Outcome + Review + Scores + Diagnosis
                         └─ Invalidated
```
Plan states: `draft → locked → triggered → closed`, หรือ `skipped | missed | invalidated | expired`

---

## 2. Data Model

> ตารางทั้งหมดมีคอลัมน์ `id (uuid)`, `created_at`, `updated_at` เงินเก็บเป็น `numeric(18,2)`, ราคาเป็น `numeric(18,6)`, เวลาเป็น `timestamptz` (UTC)

### 2.1 Identity & Access
| Entity | ฟิลด์สำคัญ | หมายเหตุ |
|---|---|---|
| **users** | email (unique), password_hash, display_name, locale (th/en), timezone, plan_tier (free/pro), is_mentor | |
| **refresh_tokens** | user_id, token_hash, expires_at, revoked_at | เลิกใช้หลังย้ายไป Better Auth |
| **auth_sessions / auth_accounts / auth_verifications** | ตาม schema ของ Better Auth (session token, expires_at, password hash, reset-password token) | Better Auth จัดการ; ผูกกับ `users.id` |
| **mentor_links** | trader_id, mentor_id, status (pending/active/revoked), pnl_visibility (`currency`/`r_only`), can_assign_rules, invited_at, accepted_at | unique(trader_id, mentor_id) |
| **push_subscriptions** | user_id, endpoint, keys(jsonb) | Web Push |

### 2.2 Accounts & Risk
| Entity | ฟิลด์สำคัญ | หมายเหตุ |
|---|---|---|
| **trading_accounts** | user_id, name, broker, platform (mt5/ctrader/manual), account_type (live/demo/prop), account_number, currency, initial_balance, is_active | |
| **broker_connections** | account_id, kind (mt5_ea/ctrader_oauth), api_key_hash, oauth_tokens(enc), last_sync_at, status | |
| **risk_profiles** | account_id (1:1), risk_per_trade_pct, max_daily_loss (amount/pct), max_drawdown_pct, max_trades_per_day, revenge_cooldown_min, news_blackout_min | |
| **trading_rules** | account_id, created_by (trader/mentor), code, params(jsonb), severity, is_active | rule ที่ปรับแต่งได้ |
| **account_balance_snapshots** | account_id, date, balance, equity | ใช้คำนวณ DD |

### 2.3 Reference Data
| Entity | ฟิลด์สำคัญ |
|---|---|
| **symbols** | code (XAUUSD), asset_class (fx/metal), digits, point_size, pip_size, contract_size, quote_currency |
| **account_symbol_overrides** | account_id, symbol_id, broker_symbol (XAUUSD.m), contract_size, tick_value |
| **emotion_tags** | code, label_th, label_en, valence (pos/neg/neutral), user_id (null = ระบบ) |
| **mistake_categories** | code, dimension (analysis/planning/execution/risk/discipline/emotion), label_th, label_en |

### 2.4 Playbook
| Entity | ฟิลด์สำคัญ |
|---|---|
| **setups** | user_id, name, description, timeframes[], sessions[], default_risk_pct, management_rules(jsonb: partial/BE/trailing), is_archived |
| **setup_checklist_items** | setup_id, order, text, is_required |
| **setup_examples** | setup_id, attachment_id, note |

### 2.5 Analysis & Plan
| Entity | ฟิลด์สำคัญ | หมายเหตุ |
|---|---|---|
| **market_analyses** | user_id, account_id?, symbol_id, analysis_date, htf_bias (bull/bear/range), key_levels(jsonb), timeframes[], session, narrative (rich text), confidence 1–10 | |
| **chart_drawings** | owner_type (analysis/plan/position), owner_id, symbol_id, timeframe, payload(jsonb) | drawing tools |
| **trade_plans** | analysis_id, setup_id, account_id, symbol_id, direction, scenario_label (A/B), entry_type (market/limit/stop), entry_price, stop_loss, take_profits(jsonb [{price, pct}]), planned_risk_pct, planned_risk_amount, planned_lot, planned_rr, management_plan(jsonb), invalidation, valid_until, status, locked_at, lock_hash | |
| **trade_plan_revisions** | plan_id, revision_no, snapshot(jsonb), reason, changed_at, changed_after_entry (bool) | append-only |
| **plan_checklist_answers** | plan_id, checklist_item_id, checked, note | |

### 2.6 Execution
| Entity | ฟิลด์สำคัญ | หมายเหตุ |
|---|---|---|
| **positions** | account_id, plan_id?, symbol_id, direction, broker_position_id, source (manual/mt5/ctrader/ocr), opened_at, closed_at, avg_entry, avg_exit, total_lot, initial_sl, initial_tp, gross_pnl, commission, swap, net_pnl, r_multiple, mae, mfe, is_unplanned, match_status (auto/manual/pending), status (open/closed) | unique(account_id, broker_position_id) |
| **executions** | position_id, broker_deal_id, side (in/out), lot, price, executed_at, commission | partial close / scale-in |
| **order_modifications** | position_id, field (sl/tp/lot), old_value, new_value, modified_at, direction_of_risk (increase/decrease) | ใช้ตรวจการย้าย SL |
| **ingestion_jobs** | account_id, kind (sync/ocr/manual_import), status, payload(jsonb), error, created_by | |
| **ocr_uploads** | user_id, attachment_id, extracted(jsonb), confidence, confirmed_position_id? | |

### 2.7 Psychology & Review
| Entity | ฟิลด์สำคัญ |
|---|---|
| **emotion_logs** | user_id, owner_type (plan/position/day), owner_id, phase (pre/in/post/daily), mood 1–10, confidence 1–10, tags[], trigger_event (sl_moved/early_close/…), note, logged_at |
| **trade_reviews** | position_id (1:1), what_went_well, what_went_wrong, lesson, would_take_again (bool), submitted_at |
| **attachments** | user_id, owner_type, owner_id, storage_key, mime, size |

### 2.8 Measurement & Diagnosis
| Entity | ฟิลด์สำคัญ | หมายเหตุ |
|---|---|---|
| **adherence_results** | position_id (1:1), score_pct, price_size_score, rules_score, management_score, computed_at, engine_version | |
| **deviations** | position_id, type (entry_slippage/sl_widened/tp_moved/oversize/early_exit/late_exit/missed_partial/missed_be/unplanned/…), expected, actual, magnitude, cost_amount, cost_r | |
| **quality_scores** | position_id, dimension, source (auto/self/mentor), score 0–100, rubric(jsonb), scored_by, note | unique(position_id, dimension, source) |
| **trade_quality_summary** | position_id, final_score, quality_grade (A/B/C/D), outcome (win/loss/be), quadrant (good_win/good_loss/bad_win/bad_loss) | materialized |
| **mistakes** | position_id, category_id, source (rule/self/mentor), evidence(jsonb) | |
| **rule_breaches** | account_id, rule_id, position_id?, occurred_at, details(jsonb), alert_id? | |
| **ai_coach_reports** | user_id, period (week/month), period_start, metrics_input(jsonb), primary_dimension, summary_md, recommendations(jsonb), model, status | |

### 2.9 Market Data, News, Alerts, Mentorship
| Entity | ฟิลด์สำคัญ | หมายเหตุ |
|---|---|---|
| **ohlc_bars** | symbol_id, source_account_id, timeframe, ts, o, h, l, c, volume | PK(symbol_id, timeframe, ts), partition รายเดือน |
| **news_events** | provider_id, currency, title, impact (low/med/high), scheduled_at, actual, forecast, previous | |
| **alerts** | user_id, type (rule_breach/news), severity, title, body, ref_type, ref_id, read_at, delivered_channels[] | |
| **comments** | author_id, target_type (position/plan/analysis/review), target_id, parent_id, body | thread |
| **mentor_assignments** | mentor_link_id, kind (rule/goal), payload(jsonb), status, due_at | |
| **audit_logs** | actor_id, action, entity, entity_id, before(jsonb), after(jsonb), at | |

### 2.10 ER (ย่อ)
```
users 1─N trading_accounts 1─1 risk_profiles
users 1─N setups 1─N setup_checklist_items
users 1─N market_analyses 1─N trade_plans 1─N positions 1─N executions
trade_plans 1─N trade_plan_revisions ; positions 1─N order_modifications
positions 1─1 adherence_results ; positions 1─N deviations / quality_scores / mistakes
positions 1─1 trade_reviews ; emotion_logs → (plan | position | day)
users(trader) N─N users(mentor) via mentor_links
```

---

## 3. ฟีเจอร์และ Acceptance Criteria

> รูปแบบ: **F-xx ชื่อฟีเจอร์** แล้วตามด้วย AC ที่ทดสอบได้

### F-01 Authentication & Profile
- [x] AC1: สมัครด้วย email/password ได้ และ password ต้องยาวอย่างน้อย 8 ตัวอักษร
- [x] AC2: Login แล้วได้ access token (15 นาที) และ refresh token (30 วัน, rotate ทุกครั้งที่ใช้)
- [x] AC3: ตั้ง locale (th/en) และ timezone ได้ UI เปลี่ยนภาษาทันทีโดยไม่ต้อง reload
- [ ] AC4: user คนหนึ่งเข้าถึงข้อมูลของ user อื่นไม่ได้ (API คืน 404) ยกเว้นผ่าน mentor_link ที่ active
- [x] AC5: **Forgot password:** กรอก email แล้วระบบส่งลิงก์ reset (หมดอายุใน 1 ชั่วโมง, ใช้ได้ครั้งเดียว) และตอบข้อความเดียวกันไม่ว่า email จะมีในระบบหรือไม่
- [x] AC6: **Reset password:** ตั้งรหัสใหม่ (≥ 8 ตัวอักษร) จากลิงก์ได้ และทุก session เดิมของ user ถูก revoke
- [x] AC7: **Guard:** ทุกหน้าที่ไม่ใช่ login/register/forgot/reset ต้อง login ก่อน (redirect ไป `/login?redirect=…`); ทุก API endpoint ยกเว้น health/auth คืน 401 เมื่อไม่มี session ที่ valid
- [x] AC8: Auth ทั้งหมดใช้ Better Auth; user และข้อมูลเดิมจาก Phase 1 ย้ายมาได้โดยไม่ต้องสมัครใหม่

> หมายเหตุ: AC1–AC3 ทำเสร็จแล้วด้วย auth ที่เขียนเองบน FastAPI (Phase 1) — ทดสอบซ้ำบน Better Auth แล้ว (Phase 2, 2026-10-28)

### F-02 Trading Accounts & Risk Profile
- [x] AC1: สร้าง/แก้/archive บัญชีได้หลายบัญชี โดยแต่ละบัญชีมี type, currency และ initial balance
- [x] AC2: ทุกบัญชีต้องมี Risk Profile ซึ่งมีค่า default ให้ (1% ต่อเทรด, max daily loss 3%, max DD 10%, max trades 5)
- [x] AC3: Dashboard filter ได้ทั้ง "ทุกบัญชี" และรายบัญชี
- [x] AC4: เมื่อแก้ Risk Profile ระบบเก็บ audit log และไม่คำนวณ adherence ของเทรดเก่าใหม่ (เทรดเก่าใช้ snapshot ของ profile ณ เวลาที่เทรด)

### F-03 Symbol Specification
- [x] AC1: มี seed symbol ของ FX majors/minors และ XAUUSD/XAGUSD
- [x] AC2: map broker symbol (เช่น `XAUUSD.m`) กับ symbol มาตรฐานได้ต่อบัญชี
- [x] AC3: คำนวณ risk amount จาก (entry, SL, lot) ได้ถูกต้องเทียบกับ MT5 (คลาดเคลื่อนไม่เกิน 1%)

### F-04 Playbook (Structured Setups)
- [x] AC1: สร้าง setup ที่มี checklist, TF, session, default risk, management rules และภาพตัวอย่างได้
- [x] AC2: setup ที่ถูกใช้แล้วลบไม่ได้ ทำได้เพียง archive
- [ ] AC3: หน้า setup แสดงสถิติ: จำนวนเทรด, win rate, expectancy (R), avg adherence และ avg quality

### F-05 Market Analysis
- [x] AC1: สร้าง analysis ต่อ symbol/วัน ได้ โดยใส่ HTF bias, key levels, TF, session, narrative และ confidence
- [x] AC2: วาดบนกราฟ (เส้น, กล่อง, ข้อความ, horizontal line) และบันทึกเป็น `chart_drawings` ได้
- [x] AC3: 1 analysis สร้างได้หลาย plan (scenario A/B/…)

### F-06 Trade Plan & Plan Lock
- [x] AC1: Plan ต้องมีฟิลด์บังคับ: setup, direction, entry, SL, อย่างน้อย 1 TP และ risk %
- [x] AC2: ระบบคำนวณ planned lot, risk amount และ R:R ให้อัตโนมัติจาก risk profile
- [x] AC3: ถ้า checklist ข้อ required ยังไม่ครบ จะ lock ไม่ได้ (แสดงเตือน)
- [x] AC4: เมื่อ lock ระบบบันทึก `locked_at` และ `lock_hash`; การแก้หลัง lock ต้องสร้าง revision ใหม่และกรอกเหตุผลเสมอ
- [ ] AC5: revision ที่เกิดหลัง entry จะถูกติด `changed_after_entry=true` และนับเป็น deviation
- [x] AC6: เปลี่ยนสถานะเป็น skipped/missed/invalidated ได้พร้อมเหตุผล; plan ที่หมด `valid_until` แล้วไม่มีเทรดจะกลายเป็น `expired`
- [x] AC7: บันทึก pre-trade emotion (mood, confidence, tags) ได้ในฟอร์ม plan

### F-07 Manual Trade Entry
- [x] AC1: กรอก position พร้อม executions หลายรายการได้ (scale-in/partial close)
- [x] AC2: ระบบคำนวณ net P/L, R-multiple (จาก initial risk) และ avg entry/exit ให้
- [x] AC3: เลือก plan ที่จะผูกได้ ถ้าไม่ผูก plan หรือ plan ถูก lock หลังเวลา entry จะติด `is_unplanned=true`

### F-08 Auto Sync MT5 / cTrader
- [ ] AC1: **MT5:** สร้าง API key ต่อบัญชีได้; EA ส่ง deals, positions และการแก้ SL/TP เข้า `/ingest` ภายใน 5 วินาทีหลังเกิดเหตุการณ์
- [ ] AC2: **cTrader:** เชื่อม OAuth ได้ และ worker ดึง deals/positions แบบ real-time
- [x] AC3: ข้อมูลซ้ำ (broker_deal_id เดิม) ต้องไม่สร้าง record ใหม่ (idempotent)
- [ ] AC4: ซิงก์ประวัติย้อนหลังได้อย่างน้อย 90 วันตอนเชื่อมต่อครั้งแรก
- [ ] AC5: ดึง OHLC (M1–D1) ช่วง ±N แท่งรอบเทรดมาเก็บใน `ohlc_bars`
- [x] AC6: หน้า connection แสดงสถานะ, last_sync_at และ error ล่าสุด

### F-09 Screenshot Scan (OCR/AI)
- [ ] AC1: อัปโหลดภาพ (PNG/JPG ≤ 10MB) แล้วได้ข้อมูล symbol, direction, lot, entry, SL, TP, exit, เวลา และ P/L ภายใน 15 วินาที
- [ ] AC2: แสดงฟอร์มให้ user ตรวจ/แก้ก่อนยืนยัน และไม่บันทึกอัตโนมัติ
- [ ] AC3: ฟิลด์ที่ confidence ต่ำจะถูก highlight
- [ ] AC4: เมื่อยืนยันแล้ว position จะมี `source=ocr` และแนบภาพต้นฉบับไว้

### F-10 Execution ↔ Plan Matching
- [x] AC1: position ใหม่จะ auto-match กับ plan ที่ locked ซึ่ง symbol/direction ตรงกัน และ entry ห่างจาก plan ไม่เกิน tolerance (ค่า default 0.3×ระยะ SL) ภายในเวลา `valid_until`
- [x] AC2: ถ้ามีหลาย plan ที่เข้าเงื่อนไข หรือหาไม่เจอ ให้ `match_status=pending` และเข้าคิวให้ user เลือก
- [x] AC3: user แก้การ match ได้ และระบบคำนวณ metrics ใหม่ทันที

### F-11 Emotion Tracking (3 จุด)
- [x] AC1: บันทึก **Pre-trade** ได้ใน plan (F-06 AC7)
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
- [x] AC3: มี drawing tools (trendline, ray, horizontal, rectangle, text, measure); บันทึกและโหลดกลับได้
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
- **Security:**
  - ใช้ HTTPS
  - hash password ด้วย argon2 (ตั้ง custom hash ใน Better Auth แทนค่า default)
  - เข้ารหัส OAuth tokens (at rest)
  - เก็บ API key แบบ hash
  - rate limit บน auth และ ingest
- **Privacy:** ข้อมูลที่ส่งไป AI ต้องไม่มี PII; ผู้ใช้ export และลบข้อมูลตัวเองได้
- **Performance:** API p95 < 300ms; ingest event ถึง alert < 5s
- **Reliability:** ingest เป็น idempotent; job retry มี backoff; backup DB รายวัน
- **Auditability:** plan revisions, score sources และ mentor actions ต้องตรวจย้อนหลังได้

---

## 4. แผนการพัฒนา (8 Phases)

### Phase 1 — Foundation & Infrastructure
- [x] สร้าง monorepo: `frontend/`, `backend/`, `connectors/mt5-ea/`, `docs/`
- [x] Docker Compose: postgres17, redis, api, worker, web
- [x] Backend skeleton: FastAPI app factory, settings (pydantic-settings), async SQLAlchemy, Alembic init, structured logging
- [x] Frontend skeleton: Vue3+TS+Vite+Tailwind+Pinia+Router+vue-i18n+Vite PWA, layout แบบ mobile-first พร้อม bottom nav
- [x] Auth: register/login/refresh/logout, argon2, JWT, route guard ฝั่ง frontend (F-01)
- [x] ตั้ง CI: lint (ruff, eslint), type check (mypy, vue-tsc), pytest และ vitest
- [x] ตั้งค่า arq worker และ WebSocket endpoint พื้นฐาน + Redis pub/sub
- [x] สร้าง seed `symbols`, `emotion_tags` และ `mistake_categories`

### Phase 2 — Auth (Better Auth), Accounts, Risk & Playbook
- [x] ระบบ Auth (Better Auth): login/register/forgot-password/reset-password + guard ทุกหน้า (F-01 AC5–AC8)
  - [x] ตั้ง Better Auth service (email/password, argon2, rate limit) + เพิ่มเข้า Docker Compose
  - [x] ส่ง email reset password ผ่าน SMTP (dev: Mailpit)
  - [x] FastAPI ตรวจ session/JWT จาก Better Auth แทน JWT ที่เขียนเอง; endpoint ที่ไม่ใช่ health/auth คืน 401
  - [x] Frontend: หน้า Forgot/Reset password, ใช้ Better Auth client, route guard ทุกหน้า
  - [x] Migration user เดิม + ถอด auth เดิม (`refresh_tokens`, `/auth/*` ของ FastAPI)
- [x] CRUD trading_accounts + account_symbol_overrides (F-02, F-03)
- [x] Risk profile + trading_rules พร้อมค่า default และ snapshot ต่อเทรด
- [x] Risk calculator service (lot ↔ risk amount ↔ R:R) พร้อม unit tests เทียบกับค่า MT5
- [x] Playbook: setups, checklist items, examples (upload attachments) (F-04)
- [x] หน้า UI: Accounts, Risk Settings, Playbook list/detail
- [x] Audit log middleware สำหรับ entity สำคัญ

### Phase 3 — Analysis, Plan & Plan Lock
- [x] Market analysis CRUD + narrative rich text editor (F-05)
- [x] ใส่ Lightweight Charts component พื้นฐาน + drawing tools + `chart_drawings` (F-19 AC3)
- [x] Trade plan form: คำนวณ lot/risk/RR อัตโนมัติ, checklist answers, pre-trade emotion (F-06)
- [x] Plan lock: `locked_at`, `lock_hash`, revisions append-only, บังคับกรอกเหตุผล
- [x] Plan state machine (draft/locked/triggered/closed/skipped/missed/invalidated/expired) + job สำหรับ expire
- [x] หน้า "Today": analysis และ plan ของวันนี้ (คล้าย Journal ของ TradeMotion)

### Phase 4 — Execution Ingestion (Manual + Sync) & Matching
- [x] Manual position + executions entry (F-07) + การคำนวณ P/L, R และ MAE/MFE
- [x] Ingest API (idempotent, API key ต่อบัญชี, rate limit)
- [ ] MT5 EA (MQL5): ส่ง deals/positions/SL-TP modifications + OHLC รอบเทรด (F-08)
- [ ] cTrader Open API worker: OAuth flow, sync history 90 วัน, real-time events
- [x] `order_modifications` + การจำแนก risk increase/decrease
- [x] Matching engine execution ↔ plan + คิว pending ใน UI (F-10)
- [x] Unplanned flag + หน้า Connection status

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

## 5. Open Questions
- News feed provider (ForexFactory / Finnhub / FMP): ตัดสินใจภายใน Phase 6
- ค่าน้ำหนัก (weights) ของ Quality Score แต่ละมิติ และรายละเอียด rubric ของ self-assessment
- Tolerance ของ matching (ราคา/เวลา): ค่า default ต้อง validate กับข้อมูลจริง
- MT5 bridge ใช้ EA (MQL5) หรือ Python `MetaTrader5` package บน Windows VPS
- Storage ของ attachments (local volume vs S3-compatible)
- ~~Better Auth: แยกเป็น Node service หรือรวมกับ web container, และ FastAPI ตรวจ session แบบ JWT/JWKS หรือถาม Better Auth ทุก request~~ → ตัดสินแล้ว: Node service แยก + JWT/JWKS + เช็ก `auth_sessions` (PLAN §5.3)
- Email provider สำหรับ production (SMTP / Resend / SES)
