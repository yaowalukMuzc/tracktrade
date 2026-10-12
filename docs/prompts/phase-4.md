# Phase 4 — Manual trade, MT5 / cTrader sync, Execution ↔ Plan matching, หน้า Trades

ก่อนเริ่ม: อ่าน `CLAUDE.md`, `docs/PLAN.md`, `docs/PROGRESS.md`, spec §2.6, F-07, F-08, F-10, §4 Phase 4, Open question เรื่อง MT5 bridge

## Backend
- `positions` + `executions` (scale-in / partial close) — คำนวณ avg entry/exit, net P/L (รวม commission, swap), R-multiple จาก initial risk, MAE/MFE จาก OHLC (F-07 AC1–AC2)
- `is_unplanned=true` เมื่อไม่ผูก plan หรือ plan ถูก lock หลังเวลา entry (F-07 AC3)
- **Ingest API** `/ingest` — auth ด้วย API key ต่อบัญชี (เก็บแบบ hash), rate limit, **idempotent** ด้วย `broker_deal_id` (F-08 AC3), event → alert ภายใน 5 วินาที (เตรียม hook ไว้สำหรับ Phase 6)
- `broker_connections` + หน้า status: kind, last_sync_at, status, error ล่าสุด (F-08 AC6)
- **MT5 EA (MQL5)** ใน `connectors/mt5-ea/`: ส่ง deals, positions, การแก้ SL/TP (→ `order_modifications` พร้อม `direction_of_risk` increase/decrease) ภายใน 5 วินาที (AC1), ส่ง OHLC M1–D1 ±N แท่งรอบเทรด (AC5), README การติดตั้ง (คัดลอก .ex5, Allow WebRequest, ใส่ API key)
- **cTrader Open API worker**: OAuth flow (token เข้ารหัส at rest), sync ย้อนหลัง 90 วันตอนเชื่อมครั้งแรก (AC4), รับ event real-time (AC2), retry with backoff
- `ingestion_jobs` บันทึกทุกการนำเข้า
- **Matching engine** (F-10): auto-match เมื่อ symbol/direction ตรง, entry ห่าง ≤ 0.3×ระยะ SL (config ได้), อยู่ใน `valid_until`; หลายแผนเข้าเงื่อนไขหรือไม่พบ → `match_status=pending`; user เลือกเอง/แก้ match ได้ → recompute (เตรียม hook Phase 6)
- อัปเดต `/today` ให้นับ "รอจับคู่" จริง

## Frontend — หน้าจอ
| หน้า | Route | แบบอ้างอิง |
|---|---|---|
| เทรด (tabs ทั้งหมด/รอรีวิว/รอจับคู่/Unplanned/เปิดอยู่, filter chips, toggle $/R, Alert รอจับคู่, ตาราง 12 คอลัมน์, pagination) | `/trades` | `screens/web/06-WTrades.png`, `screens/mobile/09-Trades.png` |
| Modal จับคู่เทรดกับแผน (สรุปเทรด, ตัวเลือกแผนแบบ radio + badge "แนะนำ", ตัวเลือก Unplanned) | modal บน `/trades` | `screens/web/06-WTrades.png`, `screens/mobile/12-MatchQueue.png` |
| เพิ่มเทรด — โหมดกรอกเอง (บัญชี/symbol/direction/initial SL-TP/ผูกแผน + เตือน unplanned, ตาราง executions, การ์ดคำนวณอัตโนมัติ) | `/trades/new?mode=manual` | `screens/web/07-WAddTrade.png` (แท็บ "กรอกเอง"), `screens/mobile/10-ManualTrade.png` |
| การเชื่อมต่อ (API key + copy, ดาวน์โหลด EA, sync now, สร้าง key ใหม่, cTrader reconnect, ประวัติการนำเข้า) | แท็บใน `/accounts` | `screens/web/14-WAccounts.png`, `screens/mobile/24-Connections.png` |

รายละเอียด:
- ตาราง: badge LONG/SHORT, Source (MT5/cTrader/OCR/Manual) แบบ outline, Adherence/Quality/Quadrant แสดง "—" จนกว่าจะมี engine (Phase 6), P/L มีเครื่องหมาย +/− และสี profit/loss
- ตารางกว้าง → scroll แนวนอนในกล่อง (`overflow-x-auto`) บนจอแคบ; มือถือใช้ TradeCard แทนตาราง
- Toggle $/R จำค่าต่อผู้ใช้

## ตรวจก่อนจบ
- pytest: idempotent ingest (ส่ง deal ซ้ำ 2 ครั้ง = 1 record), partial close / scale-in math, R-multiple, unplanned rule, matching tolerance + pending case
- ทดสอบ EA กับบัญชี demo (หรือ mock script ที่ยิง payload แบบเดียวกัน) แล้ววัด latency
- Playwright: เพิ่มเทรด manual → เห็นในตาราง → จับคู่ผ่าน modal; screenshot เทียบภาพแบบ 1440/390 Light/Dark → `docs/qa/phase-4/`
- ติ๊ก `docs/PROGRESS.md`, commit, สรุปผล
