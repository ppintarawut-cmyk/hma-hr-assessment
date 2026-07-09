# Backup อัตโนมัติด้วย File System Access API ลงโฟลเดอร์ OneDrive

ความต้องการคือ "ข้อมูลผู้สมัครห้ามเสียเลย" ซึ่ง localStorage เดี่ยว ๆ ให้ไม่ได้
จึงเลือกให้ ATS เขียนสำเนา DB ทั้งก้อน (jobs + candidates) ลงไฟล์จริงผ่าน
File System Access API ทุกครั้งที่ข้อมูลเปลี่ยน โดยผู้ใช้ชี้ไฟล์ปลายทางไว้ในโฟลเดอร์
OneDrive → sync ขึ้น cloud อัตโนมัติ รอดทั้งกรณีล้าง browser และเครื่องพัง (RPO ≈ 0)

แลกกับ: ต้องกดอนุญาตสิทธิ์ไฟล์ 1 ครั้งต่อ session และผูกกับ Chrome/Edge
(browser อื่นใช้ปุ่ม export/import JSON แบบ manual เป็น fallback)

ทางเลือกที่ปัดตก: auto-download JSON ทุกการเปลี่ยนแปลง (ไฟล์ท่วม Downloads),
ปุ่ม manual อย่างเดียว (พึ่งวินัยมนุษย์ ไม่ตอบ "ห้ามเสียเลย"), backend (ขัดกับ 0001)

Status: accepted (2026-07-06) — implemented
