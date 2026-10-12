# Phase 5 — Screenshot OCR, Emotion 3 จุด, Trade Review, Timeline

ก่อนเริ่ม: อ่าน `CLAUDE.md`, `docs/PLAN.md`, `docs/PROGRESS.md`, spec §2.7, F-09, F-11, F-12, §4 Phase 5, NFR Privacy

## Backend
- **OCR** (F-09): upload PNG/JPG ≤10MB → arq job → Claude API (vision) → JSON `{symbol, direction, lot, entry, sl, tp, exit, open_time, close_time, pnl}` + confidence ต่อฟิลด์ → `ocr_uploads`; ต้องเสร็จ ≤15 วินาที (AC1); **ไม่บันทึก position อัตโนมัติ** (AC2); ยืนยันแล้ว `source=ocr` + แนบภาพ (AC4); ใช้ structured output / JSON schema และ validate ด้วย Pydantic
- **Emotion** (F-11): in-trade prompt — เมื่อ `order_modifications` เพิ่ม risk หรือปิดก่อน TP สร้าง prompt ใน inbox ของเทรด (AC2), post-trade อยู่ในฟอร์ม review (AC3), user สร้าง tag เองได้ + tag ระบบมี TH/EN (AC4), daily mood (AC5)
- **Trade Review** (F-12): สร้าง review สถานะ "รอรีวิว" เมื่อปิด position (AC1); fields what went well/wrong, lesson, would take again, self-score rubric (Analysis, Planning, Emotion = 25/50/75/100), mistake tags (AC2); แนบภาพ + drawing (AC3)
- **Timeline API** (F-12 AC4): รวมลำดับ analysis → plan + revisions → executions/modifications → emotion logs → review เรียงตามเวลา พร้อม type สำหรับเลือกไอคอน

## Frontend — หน้าจอ
| หน้า | Route | แบบอ้างอิง |
|---|---|---|
| เพิ่มเทรด — โหมด Screenshot (ภาพซ้ายพร้อมกรอบไฮไลต์, dropzone, Alert "อ่านได้ 9/11", ฟอร์ม 3 คอลัมน์, ช่อง low-confidence พื้น `warning-100` + helper "มั่นใจ 62%", ปุ่มสแกนใหม่/ยืนยัน) | `/trades/new?mode=scan` | `screens/web/07-WAddTrade.png`, `screens/mobile/11-ScanConfirm.png` |
| In-trade emotion prompt (sheet: สิ่งที่เกิด + risk ที่เพิ่ม, เหตุผล chips, mood 1–10, emotion chips, โน้ต, ภายหลัง/บันทึก) | sheet/modal จาก notification หรือ trade detail | `screens/mobile/13-InTradePrompt.png` (บน desktop ใช้ Modal สไตล์เดียวกัน) |
| Trade review (textarea 3 ช่อง, would take again, rubric 3 มิติแบบ segmented, mistake tags, อารมณ์หลังเทรด, ขวา: กราฟ + สรุป + ไฟล์แนบ) | `/trades/:id/review` | `screens/web/09-WReview.png`, `screens/mobile/15-Review.png` |
| Timeline ใน Trade detail (ไอคอนตามประเภท: brand=analysis/plan, loss=เพิ่ม risk, warning=revision หลัง entry, profit=review) | ส่วนหนึ่งของ `/trades/:id` | `screens/web/08-WTradeDetail.png` คอลัมน์ขวา, `design-system/components/Timeline.md` |
| Daily mood บนหน้าวันนี้ | `/` | `screens/web/03-WToday.png` |

## ตรวจก่อนจบ
- pytest: OCR job (mock Claude API) + timeout + ห้าม auto-save, prompt ถูกสร้างเมื่อ SL เพิ่ม risk, review ถูกสร้างเมื่อปิด position, timeline เรียงถูก
- ตรวจว่าไม่มี PII (email, account number) ใน payload ที่ส่งไป Claude API
- Playwright: อัปโหลดภาพตัวอย่าง → แก้ช่อง low-confidence → ยืนยัน; เขียนรีวิว; screenshot เทียบภาพแบบ → `docs/qa/phase-5/`
- ติ๊ก `docs/PROGRESS.md`, commit, สรุปผล
