# Phase 7 — Trading Calendar, Performance Dashboard, Chart overlay, AI Coach

ก่อนเริ่ม: อ่าน `CLAUDE.md`, `docs/PLAN.md`, `docs/PROGRESS.md`, spec F-04 AC3, F-16, F-17, F-18, F-19, §4 Phase 7, NFR Performance

## Backend
- Aggregation endpoints (ใช้ materialized views + Redis cache): ต่อวัน (calendar), ต่อสัปดาห์, ช่วงวันที่, filter บัญชี/setup — โหลด ≤2 วินาทีสำหรับ 5,000 เทรด (F-18 AC4)
- P/L metrics: net P/L, win rate, profit factor, expectancy (R), avg win/loss R, max DD, equity curve (F-18 AC1)
- Behavior metrics แยก: avg adherence, avg quality, % unplanned, Quality×Outcome matrix, mistake cost, 6 มิติ (AC2)
- Breakdown ตาม setup, session, day-of-week, symbol, emotion tag (AC3)
- Setup statistics สำหรับ Playbook (F-04 AC3)
- Chart overlay data (F-19 AC1–AC2): OHLC ตาม TF + plan lines + actual fills + SL/TP ที่ถูกแก้ตามเวลา (step line)
- **AI Coach** (F-16): job ทุกวันจันทร์ + on-demand (AC1); input = aggregated metrics + trade summaries **ไม่มี PII** (AC2); output = primary dimension, หลักฐานอ้าง trade id, คำแนะนำ 3 ข้อ ตาม locale (AC3); retry 3 ครั้งแล้วแสดง error โดยหน้าอื่นไม่พัง (AC4); เก็บใน `ai_coach_reports`

## Frontend — หน้าจอ
| หน้า | Route | แบบอ้างอิง |
|---|---|---|
| Trading Calendar (grid เดือน cell สูง: วันที่ + mood icon, P/L หรือ R, จำนวนเทรด, badge adherence % + grade; คอลัมน์ "รวมสัปดาห์"; toggle $/R; คลิกวัน → panel ขวาแสดงรายละเอียดวัน + journal; สรุปเดือน; มุมมองรายสัปดาห์) | `/calendar` | `screens/web/10-WCalendar.png`, `screens/mobile/16-Calendar.png`, `17-DaySheet.png` |
| Performance (period segmented, filter บัญชี/setup, **P/L metrics** 6 tiles, **Behavior metrics** 4 tiles แยก section, Equity curve เส้น `brand-500` พื้น `chart-area` + toggle $/R, Quality × Outcome matrix, Mistake cost 6 มิติ, ตารางเทรดล่าสุด) | `/stats` | `screens/web/11-DesktopDashboard.png`, `screens/mobile/18-Performance.png`, `19-Behavior.png` |
| Breakdown (setup, session, day-of-week, symbol, emotion tag) | แท็บ/section ใน `/stats` | `screens/mobile/18-Performance.png` (bar แบบ diverging รอบเส้นกึ่งกลาง), `screens/web/12-WDiagnosis.png` (ตาราง emotion tag) |
| Diagnosis & AI Coach (การ์ดมิติหลักพื้น `brand-50`, mistake cost 6 มิติ สลับ R/$/%, emotion tag expectancy, ตาราง mistake ที่เกิดบ่อย; ขวา: รายงาน AI สัปดาห์ล่าสุด + หลักฐานลิงก์ไปเทรด + คำแนะนำ 3 ข้อ + note privacy, รายงานก่อนหน้า, สถานะล้มเหลว + ลองใหม่) | `/diagnosis` | `screens/web/12-WDiagnosis.png`, `screens/mobile/20-AICoach.png` |
| Playbook stats จริง | `/playbook` | `screens/web/13-WPlaybook.png` |
| Chart overlay Plan vs Actual บน Trade detail ด้วยข้อมูลจริง | `/trades/:id` | `screens/web/08-WTradeDetail.png` |

กฎกราฟ: ใช้ token `chart-*`, `dim-*`, `q-*`, `brand-500` เท่านั้น; P/L tiles เท่านั้นที่ระบายสี profit/loss; dimension ใช้สีเป็น mark ส่วน label เป็นสี ink; ทุกกราฟมีตัวเลขกำกับและ `aria-label`

## ตรวจก่อนจบ
- pytest: สูตร metrics ทุกตัว (เทียบตัวเลขที่คำนวณด้วยมือจาก fixture), AI Coach payload ไม่มี PII, retry/error path
- Load test aggregation 5,000 เทรด ≤2s
- Playwright: screenshot `/calendar`, `/stats`, `/diagnosis` เทียบภาพแบบ 1440/390 Light/Dark → `docs/qa/phase-7/`; คลิกวันใน calendar, สลับ $/R
- ติ๊ก `docs/PROGRESS.md`, commit, สรุปผล
