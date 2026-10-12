# Phase 3 — Market Analysis, Trade Plan & Plan Lock, Chart, หน้า Today

ก่อนเริ่ม: อ่าน `CLAUDE.md`, `docs/PLAN.md`, `docs/PROGRESS.md`, spec §1.7 (lifecycle + plan states), §2.5, F-05, F-06, F-11 AC1, F-19 AC3, §4 Phase 3

## Backend
- `market_analyses` CRUD (htf_bias, key_levels jsonb, timeframes[], session, narrative rich text, confidence 1–10) — F-05
- `chart_drawings` (owner analysis/plan/position, payload jsonb) บันทึก/โหลดกลับ — F-19 AC3
- `trade_plans`: ฟิลด์บังคับ setup/direction/entry/SL/≥1 TP/risk% (F-06 AC1), คำนวณ planned lot/risk/R:R ด้วย risk calculator Phase 2 (AC2)
- `plan_checklist_answers` — lock ไม่ได้ถ้า required ยังไม่ครบ คืน error พร้อมรายการที่ขาด (AC3)
- **Lock**: บันทึก `locked_at` + `lock_hash` (sha256 ของ snapshot ที่ normalize แล้ว); แก้หลัง lock = สร้าง `trade_plan_revisions` ใหม่ + บังคับ reason (AC4); revision หลัง entry ติด `changed_after_entry=true` (AC5)
- State machine `draft → locked → triggered → closed` | `skipped | missed | invalidated | expired` พร้อม reason (AC6) + arq job expire ตาม `valid_until`
- Pre-trade `emotion_logs` (phase=pre: mood, confidence, tags) ในฟอร์ม plan (AC7, F-11 AC1)
- Endpoint `/today` รวม: analysis ของวัน, plans, สถิติวัน (P/L, trades x/max, daily loss used), งานค้าง (รอจับคู่/รอรีวิว — ตอนนี้คืน 0), daily mood

## Frontend — Chart component (ใช้ซ้ำทั้งแอป)
- `components/chart/TradeChart.vue` ด้วย TradingView Lightweight Charts: สีจาก token `chart-up`, `chart-down`, `chart-grid`, เส้นแผน `chart-plan` เส้นประ, ป้ายราคา TP/EN/SL ด้านขวา (ดู `screens/web/05-WPlan.png`), zone สี่เหลี่ยม `brand-500` โปร่ง, key level เส้น `warning`
- Drawing tools: trendline, ray, horizontal, rectangle, text, measure, ลบ — toolbar แนวตั้งซ้ายตาม `screens/web/04-WAnalysis.png`
- TF chips M5…D1, รองรับ pinch zoom/pan บนมือถือ (F-19 AC4)
- Phase นี้ใช้ OHLC mock/fixture ไปก่อน (ข้อมูลจริงมาใน Phase 4)

## Frontend — หน้าจอ
| หน้า | Route | แบบอ้างอิง |
|---|---|---|
| วันนี้ (alert ข่าว, KPI 4 ช่อง, การ์ด Analysis + กราฟ, ตารางแผนวันนี้, ด้านขวา: ต้องจัดการ / daily mood / ข่าววันนี้) | `/` | `screens/web/03-WToday.png`, `screens/mobile/05-Today.png` |
| Market Analysis (กราฟใหญ่ + drawing, ขวา: bias/TF/session/confidence, key levels, แผนจาก analysis นี้; narrative rich text) | `/analysis/new`, `/analysis/:id` | `screens/web/04-WAnalysis.png`, `screens/mobile/06-Analysis.png` |
| Trade Plan (Setup & Direction, ราคา & Risk + กล่องคำนวณ, preview บนกราฟ, management toggles, ขวา: Checklist, อารมณ์ก่อนเทรด, Revisions) | `/plans/new?analysis=`, `/plans/:id` | `screens/web/05-WPlan.png`, `screens/mobile/07-PlanForm.png` |
| Plan locked + revision sheet (ต้องกรอกเหตุผล, เตือน "แก้หลังเข้าเทรด", แสดง risk ที่เพิ่ม) | `/plans/:id` | `screens/mobile/08-PlanLocked.png` |

พฤติกรรมที่ต้องตรงแบบ:
- ปุ่ม "ล็อกแผน (x/3)" disabled จน required ครบ; กดตอนยังไม่ครบ → Alert loss + กล่อง checklist ขอบแดง; ล็อกแล้ว → แถบ PlanLock (`tt-lock`) + hash สั้น + badge Locked
- Direction toggle LONG/SHORT ใช้ `profit-100`/`loss-100` และคำเสมอ
- MoodScale 1–10 + emotion chips (pos/neg)
- คำนวณ Risk amount / Planned lot / R:R แบบ realtime ขณะพิมพ์

## ตรวจก่อนจบ
- pytest: lock_hash เสถียร, revision หลัง lock ต้องมี reason, changed_after_entry, expire job, checklist required
- vitest: TradeChart render เส้นแผนถูกราคา, plan form validation
- Playwright flow: สร้าง analysis → สร้าง plan A → ติ๊ก checklist → lock → แก้ SL ผ่าน revision; screenshot `/`, `/analysis/:id`, `/plans/:id` ที่ 1440/390 → `docs/qa/phase-3/` เทียบภาพแบบ ทั้ง Light/Dark
- ติ๊ก `docs/PROGRESS.md`, commit, สรุปผล
