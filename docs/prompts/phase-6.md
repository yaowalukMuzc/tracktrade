# Phase 6 — Measurement engine (Adherence, Quality, Diagnosis), Alerts, News

ก่อนเริ่ม: อ่าน `CLAUDE.md`, `docs/PLAN.md`, `docs/PROGRESS.md`, spec §1.2 (หลักการ Quality ≠ P/L), §2.8–2.9, F-13, F-14, F-15, F-20, F-21, §4 Phase 6

## Backend — Engines (deterministic, มี `engine_version`)
- **Adherence** (F-13): คำนวณเมื่อปิด position และเมื่อ match/plan เปลี่ยน (AC1)
  - Price & Size: entry slippage, SL widened/moved, TP moved, lot > planned 10%, early/late exit (AC2)
  - Rules: max trades/วัน, max daily loss, news blackout, revenge cooldown, unplanned (AC3)
  - Management: partial / BE / trailing ตาม `management_plan` (AC4)
  - ทุก `deviations` มี expected, actual, cost $ และ R (AC5); `score_pct` 0–100 (AC6)
  - **Fixture บังคับ**: ทำตามแผน 100% แต่โดน SL → adherence = 100 (AC7)
- **Quality** (F-14): 6 มิติ เก็บแยก source auto/self/mentor (AC1); auto ของ Execution/Risk/Discipline มาจาก deviations (AC2); final = mentor > self > auto ต่อมิติ แล้ว weighted average (weights ใน config) (AC3); grade A–D, quadrant โดย grade ≥ B = good (AC4); **P/L ห้ามเป็น input** + unit test ยืนยัน (AC5)
- **Diagnosis** (F-15): map deviation type → mistake_category → dimension (config) (AC1), aggregate mistake cost ต่อมิติ (AC2), primary dimension = cost R สูงสุดในช่วงเวลา (AC3)
- Recompute pipeline ผ่าน arq เมื่อปิด position / แก้ match / แก้ plan / mentor ให้คะแนน
- **Alerts** (F-20): position ใหม่ผิดกฎ → `rule_breaches` + `alerts` ≤5 วินาที (AC1), ส่ง WebSocket ถ้าออนไลน์ + Web Push ถ้าอนุญาต (AC2), mark read + filter ตามบัญชี (AC3), ส่งต่อ mentor ถ้าเปิดสิทธิ์ (AC4)
- **News** (F-21): provider adapter (เลือกตาม Open question; ทำ interface ให้สลับได้), ดึงรายสัปดาห์ + อัปเดตทุก 1 ชม. (AC1), filter ตามสกุลเงินของ symbol ที่ใช้ + impact (AC2), แจ้งก่อนข่าว high X นาที (AC3), rule news blackout ±N นาที (AC4)
- Fixture tests: Good-Loss, Bad-Win, unplanned, SL widened, revenge trade

## Frontend — หน้าจอ
| หน้า | Route | แบบอ้างอิง |
|---|---|---|
| Trade detail ครบ (KPI 5 ช่อง: P/L, Adherence, Quality, Quadrant, Mistake cost; กราฟ Plan vs Actual + legend; ตาราง Deviations พร้อม badge มิติ; ring adherence + 3 meters; Quality 6 มิติพร้อม source; Timeline; คอมเมนต์) | `/trades/:id` | `screens/web/08-WTradeDetail.png`, `screens/mobile/14-TradeDetail.png` |
| เติมคอลัมน์ Adherence / Quality / Quadrant ในตารางเทรด และ badge ในหน้า Today | `/trades`, `/` | `screens/web/06-WTrades.png` |
| แจ้งเตือน & ข่าว (filter chips, รายการแยก วันนี้/เมื่อวาน พร้อม unread dot, ขวา: ตารางปฏิทินข่าว impact bars + แถว blackout พื้น `loss-100`, toggle แจ้งก่อนข่าว) | `/alerts` | `screens/web/15-WAlerts.png`, `screens/mobile/25-Alerts.png`, `26-News.png` |
| Toast real-time จาก WebSocket (สไตล์ `Alert` บน `surface-raised` + `shadow-lg`) | ทั้งแอป | `design-system/components/Alert.md` |
| Badge จำนวนบน Sidebar/Bell | shell | `screens/web/03-WToday.png` |

กฎการแสดงผล: Good-Loss ใช้ `q-good-loss` (ไม่ใช่สีแดง), score color ≥80 `brand-700`, 60–79 `warning`, <60 `loss`; ตัวเลขทุกตัวพิมพ์ชัดเจน ไม่ใช้สีอย่างเดียว

## ตรวจก่อนจบ
- pytest: fixture ทั้ง 5 แบบ + AC7 + AC5 (เปลี่ยน P/L แล้ว quality ไม่เปลี่ยน), alert latency ≤5s (integration test), news blackout
- Playwright: สร้างเทรดที่ขยับ SL → เห็น deviation + toast; screenshot `/trades/:id`, `/alerts` เทียบภาพแบบ 1440/390 Light/Dark → `docs/qa/phase-6/`
- ติ๊ก `docs/PROGRESS.md`, commit, สรุปผล
