# วิธีใช้ prompt ชุดนี้กับ Claude Code

ไฟล์ในโฟลเดอร์นี้คือ prompt สำหรับสั่ง Claude Code ทีละขั้น ตาม 8 Phase ใน `docs/spec.md` §4 และอ้างอิงงานออกแบบใน `design-system/` และ `screens/`

## ลำดับการใช้
| ลำดับ | ไฟล์ | ทำอะไร |
|---|---|---|
| 0 | `kickoff.md` | ให้ Claude Code อ่านทุกอย่าง แล้วเขียนแผนลง `docs/PLAN.md` — ยังไม่เขียนโค้ด |
| 1 | `phase-1.md` | Foundation & Infrastructure + App shell + Design system ในโค้ด + Login |
| 2 | `phase-2.md` | Accounts, Risk, Symbol, Playbook + Onboarding |
| 3 | `phase-3.md` | Analysis, Plan & Plan Lock + Chart component + หน้า Today |
| 4 | `phase-4.md` | Manual trade, MT5/cTrader sync, Matching + หน้า Trades |
| 5 | `phase-5.md` | Screenshot OCR, Emotion 3 จุด, Review + Timeline |
| 6 | `phase-6.md` | Adherence / Quality / Diagnosis engine + Alerts + News |
| 7 | `phase-7.md` | Calendar, Performance, Chart overlay, AI Coach |
| 8 | `phase-8.md` | Mentorship, Security, E2E, Deploy |
| — | `screen-template.md` | prompt แม่แบบสำหรับสั่งทำ/แก้หน้าจอทีละหน้า |
| — | `review-phase.md` | prompt ตรวจงานก่อนปิด phase |

## วิธีสั่ง
ในโฟลเดอร์โปรเจกต์ เปิด `claude` แล้วพิมพ์:

```
ทำตาม docs/prompts/phase-1.md
```

## เคล็ดลับ
- **ทำทีละ phase** และเริ่ม session ใหม่ (`/clear`) เมื่อขึ้น phase ใหม่ เพื่อให้ context สะอาด — ทุก prompt สั่งให้อ่าน `CLAUDE.md`, `docs/PLAN.md` และ `docs/PROGRESS.md` ก่อนอยู่แล้ว
- phase ที่ใหญ่ (4, 6, 7) แบ่งสั่งเป็นครึ่ง backend / frontend ได้ เช่น `ทำตาม docs/prompts/phase-4.md เฉพาะส่วน Backend`
- ใช้ **Plan mode** (Shift+Tab) ตอนเริ่มแต่ละ phase ถ้าอยากเห็นแผนก่อนให้ลงมือ
- ปิดท้ายทุก phase ด้วย `ทำตาม docs/prompts/review-phase.md สำหรับ Phase N`
- ถ้าหน้าจอไม่ตรงแบบ ใช้ `screen-template.md` แล้วแนบชื่อไฟล์ภาพ
