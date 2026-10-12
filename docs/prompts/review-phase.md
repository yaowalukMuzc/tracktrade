# ตรวจงานก่อนปิด Phase

> ใช้: `ทำตาม docs/prompts/review-phase.md สำหรับ Phase [N]`

ทำหน้าที่เป็น reviewer ที่ไม่ได้เขียนโค้ดนี้ ตรวจ Phase [N] ตามลำดับ และ **ห้ามแก้โค้ดจนกว่าจะรายงานเสร็จ**

1. **Spec coverage** — ไล่ทุกข้อใน spec §4 Phase [N] และทุก AC ของ feature ที่เกี่ยวข้อง: ระบุ ✅ ผ่าน (ชี้ไฟล์/test ที่พิสูจน์), ⚠️ บางส่วน, ❌ ยังไม่ทำ
2. **Tests** — รัน lint, type check, pytest, vitest, Playwright ทั้งหมด รายงานผล
3. **Design fidelity** — screenshot ทุกหน้าของ phase นี้ที่ 1440 และ 390 ทั้ง Light/Dark แล้วเทียบกับ `screens/web/*` และ `screens/mobile/*` ทีละหน้า รายการจุดต่าง (ตำแหน่ง, สี, ตัวอักษร, ระยะ, ไอคอน, ข้อความ)
4. **Design rules** — grep หา hex/rgb ที่ hard-code นอก tokens, ข้อความที่ไม่ผ่าน i18n, ตัวอักษรสีขาวบน `brand-600`, P/L ที่ไม่มีเครื่องหมาย, ไอคอนที่ไม่ใช่ Hugeicons
5. **Security & data** — ownership (404 ข้ามผู้ใช้), mentor 403/r_only (ถ้าเกี่ยว), PII ที่ส่งไป AI, secrets ในโค้ด
6. **Performance** — query N+1, index ที่ขาด, ขนาด bundle

รายงานเป็นตาราง severity (High / Medium / Low) + ข้อเสนอแก้ แล้วถามฉันว่าจะให้แก้ข้อไหนก่อน
