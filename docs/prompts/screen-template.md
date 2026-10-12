# แม่แบบ — สร้างหรือแก้หน้าจอให้ตรงแบบ

> คัดลอกด้านล่าง แล้วแทนค่าในวงเล็บเหลี่ยม

```
สร้าง/แก้หน้า [ชื่อหน้า] ที่ route [route] ให้ตรงกับแบบ

แบบอ้างอิง:
- Desktop: screens/web/[NN-ชื่อไฟล์].png
- Mobile: screens/mobile/[NN-ชื่อไฟล์].png
- Markup ต้นฉบับ: screens/source/[ชื่อไฟล์].dc.html (ดูโครงสร้าง ลำดับ section ข้อความ และ class tt-* ที่ใช้)
- Spec: [F-xx ACx, …]

ข้อกำหนด:
1. ใช้คอมโพเนนต์ใน src/components/ui ก่อนเสมอ ถ้าขาดให้สร้างตาม design-system/components.css + components/*.md
2. ใช้ Tailwind utilities ที่ผูกกับ token เท่านั้น ห้าม hex/px ที่ไม่ได้อยู่ใน token
3. ข้อความทั้งหมดผ่าน vue-i18n (th + en)
4. ทำครบ loading / empty / error state
5. Responsive: ≥1024 ตาม desktop, <1024 ตาม mobile; ตารางกว้าง scroll ในกล่อง
6. รองรับ Light/Dark

ตรวจ:
- Playwright screenshot ที่ 1440 และ 390 (Light + Dark) เก็บใน docs/qa/
- เปิดภาพคู่กับแบบ แล้วไล่เทียบ: layout/ลำดับ section, ระยะห่าง, ขนาดและน้ำหนักตัวอักษร, สี, ไอคอน, สถานะ badge, ตัวเลข/เครื่องหมาย
- แก้จนต่างกันไม่เกินเรื่องข้อมูลจริง แล้วสรุปจุดที่จงใจทำต่างจากแบบพร้อมเหตุผล
```
