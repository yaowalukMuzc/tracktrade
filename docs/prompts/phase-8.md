# Phase 8 — Mentorship, Settings & Privacy, Hardening, Launch

ก่อนเริ่ม: อ่าน `CLAUDE.md`, `docs/PLAN.md`, `docs/PROGRESS.md`, spec §1.3 (roles), §2.9, F-22, F-23, NFR ทั้งหมด, §4 Phase 8

## Backend
- **Mentor link** (F-22): trader เชิญด้วย email → mentor accept → active; trader revoke ได้ตลอด (AC1)
- Permission layer: `pnl_visibility=r_only` → **ตัดค่า $ ทุกจุดทั้ง API และ UI** (AC2) — ทำที่ serializer layer เดียว + test ทุก endpoint ที่คืนเงิน
- Comments thread ที่ position/plan/analysis/review (AC3)
- Mentor ให้ quality score (`source=mentor`) + mistake tag (AC4) → trigger recompute
- Mentor assignments rule/goal; rule ที่ trader ยอมรับเข้า `trading_rules` (AC5)
- Mentor แก้ analysis/plan/position ไม่ได้ → 403 และทุก action ลง audit (AC6)
- Mentor dashboard API: รายชื่อ trader, คิวรีวิว, behavior metrics สรุป (AC7)
- Forward alerts ไป mentor (F-20 AC4)
- Privacy: export ข้อมูลทั้งหมด (CSV + JSON) และลบบัญชีถาวร
- Security review: OWASP checklist, เข้ารหัส OAuth tokens at rest, API key hash, rate limit auth/ingest, CORS, CSP, secret management
- Backup DB รายวัน + ซ้อม restore

## Frontend — หน้าจอ
| หน้า | Route | แบบอ้างอิง |
|---|---|---|
| ตั้งค่า (เมนูหมวดซ้าย; โปรไฟล์: ชื่อ/อีเมล/ภาษา/เขตเวลา/ธีม; การแจ้งเตือน toggles; Mentor: เชิญ, ตารางสิทธิ์ $ / R only, มอบหมายกฎ, ส่ง alert, ยกเลิกสิทธิ์, การ์ดกฎใหม่รอยอมรับ; ข้อมูล & ความเป็นส่วนตัว: export, รหัสผ่าน/อุปกรณ์, ลบบัญชีปุ่ม danger) | `/settings` | `screens/web/16-WSettings.png`, `screens/mobile/28-Settings.png`, `29-MentorInvite.png`, `27-More.png` |
| Mentor dashboard (Sidebar โหมด mentor; KPI 4 ช่อง; ตาราง behavior ราย trader: เทรด, adherence, grade, unplanned, แถบ Good/Bad, มิติหลัก, Net R, รอรีวิว, สิทธิ์; คิวรีวิว; alert ผิดกฎที่ถูกส่งต่อ) | `/mentor` | `screens/web/17-WMentor.png`, `screens/mobile/30-MentorDashboard.png` |
| Mentor trade review (badge "อ่านอย่างเดียว · R only", KPI แสดง R เท่านั้น, กราฟ, รีวิวของ trader, ให้คะแนน 6 มิติ source mentor, mistake tags, คอมเมนต์ thread, มอบหมายกฎ, บันทึกและไปเทรดถัดไป) | `/mentor/trades/:id` | `screens/web/18-WMentorTrade.png`, `screens/mobile/31-MentorTradeView.png` |
| คอมเมนต์ใน Trade detail ฝั่ง trader | `/trades/:id` | `screens/web/08-WTradeDetail.png` |

- Mentor mode: ซ่อนทุกปุ่มแก้ไขข้อมูลเทรด, `PnL` component รับ `visibility` แล้วแสดง R อย่างเดียวเมื่อ r_only
- **PWA** (F-23): ติดตั้งได้ iOS/Android/Desktop, offline shell + อ่านข้อมูลล่าสุดจาก cache (AC1); ตรวจทุกหน้าใช้งานได้ครบที่ 375px (AC3) เทียบ `screens/mobile/*`; ไม่มี hard-coded string (AC2 — เขียน lint rule/สคริปต์ตรวจ)

## Hardening & Launch
- E2E Playwright ครบ flow: Register → Onboarding → Analysis → Plan lock → Execution (ingest mock) → Match → Review → Dashboard → Mentor review (r_only ไม่มี $)
- Visual regression: screenshot ทุก route ที่ 1440 และ 390 ทั้ง Light/Dark เทียบกับ `screens/` เก็บที่ `docs/qa/phase-8/` และสรุปจุดที่ยังต่างจากแบบ
- Accessibility: axe ทุกหน้า, keyboard navigation, focus ring `focus-ring`, contrast AA ทั้ง 2 ธีม
- Load test 5,000 เทรด/ผู้ใช้ + ingest burst; API p95 <300ms
- Production deploy: Docker Compose บน cloud, HTTPS, monitoring, error tracking
- อัปเดต README การติดตั้ง/รัน และ `docs/PROGRESS.md` ให้ครบ แล้วสรุปสิ่งที่พร้อม launch และสิ่งที่เหลือ (Phase หลัง MVP ตาม spec §1.4)
