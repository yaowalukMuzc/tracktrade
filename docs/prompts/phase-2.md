# Phase 2 — Auth (Better Auth), Accounts, Risk, Symbol spec, Playbook + Onboarding

ก่อนเริ่ม: อ่าน `CLAUDE.md`, `docs/PLAN.md` (โดยเฉพาะ §5.3), `docs/PROGRESS.md`, spec §1.4–1.6, §2.1–2.4, F-01, F-02, F-03, F-04, §4 Phase 2

## Auth — Better Auth (ทำก่อน, F-01 AC5–AC8)
- Service `auth/` (Node/TS, Better Auth) + เพิ่ม `auth` และ `mailpit` ใน Docker Compose; nginx/Vite proxy `/api/auth/*` → auth
- email/password, argon2 (custom hash เข้ากับ hash เดิม), rate limit, `rememberMe`
- Forgot/Reset password ส่งอีเมลผ่าน SMTP (dev: Mailpit); ลิงก์หมดอายุ 1 ชม. ใช้ครั้งเดียว; reset แล้ว revoke ทุก session
- FastAPI ตรวจ JWT ของ Better Auth ผ่าน JWKS + เช็ก session ยังอยู่; ทุก endpoint ยกเว้น health คืน 401 เมื่อไม่มี session
- Alembic: ตาราง `auth_*`, ย้าย password hash เดิมไป `auth_accounts`, ถอด `refresh_tokens` และ `/api/v1/auth/*`
- Frontend: Better Auth client, หน้า `/forgot-password`, `/reset-password`, guard ทุกหน้า, Settings อุปกรณ์ที่ login
- ทดสอบซ้ำ F-01 AC1–AC3 หลังย้าย

## Backend
- CRUD `trading_accounts` (archive แทนลบ) + `account_symbol_overrides` (map `XAUUSD.m` → `XAUUSD`) — F-02 AC1, F-03 AC2
- `risk_profiles` 1:1 ต่อบัญชี สร้างอัตโนมัติด้วยค่า default 1% / daily loss 3% / DD 10% / max 5 trades (F-02 AC2) + `revenge_cooldown_min`, `news_blackout_min`
- `trading_rules` (created_by trader/mentor, severity, params jsonb)
- **Snapshot** risk profile ต่อเทรด (F-02 AC4) — แก้ profile ไม่ทำให้ค่าเก่าเปลี่ยน
- Audit log middleware สำหรับ entity สำคัญ (เก็บ before/after)
- **Risk calculator service**: entry + SL + risk% + balance → risk amount, lot (ปัดตาม lot step), R:R จาก TP หลายระดับ; และย้อนกลับ lot → risk — unit test เทียบค่า MT5 คลาดเคลื่อน ≤1% (F-03 AC3) รวม XAUUSD (contract 100), EURUSD, USDJPY, GBPJPY
- Playbook: `setups`, `setup_checklist_items` (order, is_required), `setup_examples` (upload attachment), ลบได้เฉพาะ setup ที่ยังไม่ถูกใช้ ไม่งั้น archive (F-04 AC1–AC2)

## Frontend — หน้าจอ
| หน้า | Route | แบบอ้างอิง |
|---|---|---|
| Onboarding (stepper 3 ขั้น: ผู้ใช้ ✓ → บัญชี & Risk → Broker) | `/onboarding` | `screens/web/02-WOnboarding.png`, `screens/mobile/03-Onboarding.png`, `04-ConnectBroker.png` |
| บัญชี & การเชื่อมต่อ (ตารางบัญชี, แท็บ Risk Profile / กฎเพิ่มเติม / Symbol mapping / การเชื่อมต่อ / Audit log, การ์ด "วันนี้" แสดง meter daily loss / DD / trades) | `/accounts` | `screens/web/14-WAccounts.png`, `screens/mobile/23-Accounts.png` |
| Playbook (รายการ setup ซ้าย + รายละเอียดขวา: KPI, checklist ลากเรียงได้, management rules, ภาพตัวอย่าง) | `/playbook` | `screens/web/13-WPlaybook.png`, `screens/mobile/21-Playbook.png`, `22-SetupDetail.png` |

รายละเอียดที่ต้องตรงแบบ:
- Risk Profile แสดงคำอธิบายเป็นเงิน "1% ของ $100,000 = $1,000 ต่อเทรด" ด้วย `Alert` info
- ช่องตัวเลขใช้ `Field` แบบ `num` (ชิดขวา, tabular) + suffix (%, นาที, USD)
- Account switcher ใน Sidebar/AppBar ใช้งานได้จริง: "ทุกบัญชี" หรือรายบัญชี (F-02 AC3) เก็บใน Pinia store และส่งเป็น query param ไปทุก API
- Playbook stats (F-04 AC3) ยังไม่มีข้อมูล — แสดง placeholder "—" ไว้ก่อน (เติมใน Phase 7)
- ทำ empty state ตามหลักใน README (1 ประโยค + 1 ปุ่ม) และ loading skeleton

## ตรวจก่อนจบ
- pytest: risk calculator, archive rule, snapshot, ownership 404
- vitest: Field num formatting, account switcher store
- Playwright screenshot `/onboarding`, `/accounts`, `/playbook` ที่ 1440/390 → `docs/qa/phase-2/` เทียบกับภาพแบบแล้วแก้จนตรง ทั้ง Light/Dark
- ติ๊ก `docs/PROGRESS.md`, commit, สรุปผล
