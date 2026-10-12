# Kickoff — อ่านทั้งหมดและวางแผน (ยังไม่เขียนโค้ด)

คุณคือ tech lead ของโปรเจกต์ TrackTrade งานนี้ **ห้ามเขียนโค้ดแอป** ให้อ่านและวางแผนเท่านั้น

## 1. อ่านให้ครบตามลำดับ
1. `CLAUDE.md` — กฎการออกแบบและตาราง screen → route → feature
2. `docs/spec.md` ทั้งไฟล์ — Data model (§2), Feature + Acceptance Criteria F-01…F-23 (§3), NFR, 8 Phases (§4), Open questions (§5)
3. `design-system/README.md` และ `design-system/components/*.md` ทุกไฟล์
4. `design-system/tokens.css`, `design-system/tailwind.config.js`, `design-system/components.css`
5. ดูภาพทุกไฟล์ใน `screens/web/` (18 หน้า, desktop 1440px — แบบหลัก) และ `screens/mobile/` (31 หน้า, 390px — PWA บนมือถือ)
6. เปิด `screens/source/WSide.dc.html`, `WToday.dc.html`, `WPlan.dc.html` เพื่อดูโครง markup และ class ที่ใช้ (template syntax `{{…}}`, `<sc-for>`, `<sc-if>`, `<dc-import>` เป็นของเครื่องมือออกแบบ ไม่ใช่ Vue)

## 2. เขียน `docs/PLAN.md` ให้มีหัวข้อต่อไปนี้
- **Monorepo layout** ตาม spec Phase 1: `frontend/`, `backend/`, `connectors/mt5-ea/`, `docs/` — **คง `design-system/` และ `screens/` ไว้ที่ root ตามเดิม** (prompt ทุก phase อ้าง path นี้)
- **Frontend architecture**: โครงโฟลเดอร์ `src/` (app shell, router, stores, i18n, `components/ui/*` ที่ port จาก `components.css`, `components/chart/*`, `features/<domain>/*`), naming, วิธีผูก token → Tailwind, วิธีสลับธีม (`data-theme` บน `<html>`), วิธีใช้ Hugeicons (`@hugeicons/vue`)
- **Component inventory**: ตารางคอมโพเนนต์ UI ทั้งหมดจาก `design-system/components/*.md` + คอมโพเนนต์ที่เห็นในภาพแต่ยังไม่มีใน DS (เช่น Sidebar, Topbar, Modal, Sheet, Table, Toggle, Toast, Stepper) — ระบุ props หลักและหน้าที่ใช้
- **Screen → Phase mapping**: ทุกหน้าใน `screens/web` และ `screens/mobile` ว่าจะถูกสร้างใน phase ไหน, route อะไร, ใช้ API endpoint ไหน
- **Backend architecture**: modules ตาม spec §1.6, โครง FastAPI app factory, settings, DB session, Alembic, arq worker, WebSocket hub
- **API contract draft**: รายการ endpoint หลักต่อ module (method, path, request/response schema ย่อ) ที่หน้าจอต้องใช้
- **Testing strategy**: pytest (unit + fixture ตาม spec F-13 AC7, F-14 AC5, Phase 6 fixture list), vitest + @vue/test-utils, Playwright (E2E + visual check เทียบภาพใน `screens/web`)
- **Risks & open questions**: รวม §5 ของ spec + สิ่งที่ภาพออกแบบไม่ครอบคลุม (เช่น empty / loading / error states) พร้อมข้อเสนอ default

## 3. สร้าง `docs/PROGRESS.md`
checklist ทุกข้อของ spec §4 (Phase 1–8) และทุก AC ของ F-01…F-23 ในรูป `- [ ]` เพื่อใช้ติ๊กตลอดโปรเจกต์

## 4. รายงานกลับ
สรุปสั้นๆ: โครงที่เสนอ, จุดที่ spec กับภาพออกแบบไม่ตรงกัน (ถ้ามี), คำถามที่ต้องให้ฉันตัดสินใจก่อนเริ่ม Phase 1 — แล้วหยุดรอ
