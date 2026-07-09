# HMA ATS — ระบบติดตามผู้สมัครของ Hino Motors Asia (HR)

Single-file web app (hma-ats.html) สำหรับ HR คนเดียว: สแกน resume ให้คะแนน match
กับเกณฑ์ตำแหน่ง และติดตามผู้สมัครใน pipeline — ข้อมูลอยู่ในเครื่อง (localStorage + backup ไฟล์)

## Language

**ผู้สมัคร (Candidate)**:
บุคคล 1 คนที่สมัคร 1 ตำแหน่ง — เป็น record ใน ATS เท่านั้น (แหล่งความจริงเดียว ดู decision 0003)
_Avoid_: applicant, ผู้ทำแบบทดสอบ (คำหลังหมายถึงคนในระบบสอบ ไม่ใช่ ATS)

**ผลสแกน (Scan result)**:
ผลชั่วคราวจากการอ่าน resume 1 ไฟล์ ที่ยังไม่ถูกกดยืนยันเป็นผู้สมัคร — อยู่ในหน่วยความจำ ไม่ persist
_Avoid_: draft candidate

**ตำแหน่งงาน (Job requisition)**:
ตำแหน่งที่เปิดรับ พร้อมเกณฑ์คะแนน (ทักษะ+น้ำหนัก, ประสบการณ์ขั้นต่ำ, คีย์เวิร์ดวุฒิ)
_Avoid_: position (ในโค้ดใช้ jobId เสมอ)

**Core Competency / เกณฑ์ทักษะ**:
รายการทักษะของตำแหน่งหนึ่ง แต่ละรายการมีน้ำหนัก 1–5 และ flag "จำเป็น" — ใช้คิดคะแนน match
_Avoid_: requirement, keyword list

**คะแนน Match**:
คะแนน 0–100 จากการเทียบ resume กับเกณฑ์ตำแหน่ง (ทักษะ 60 · ประสบการณ์ 25 · การศึกษา 15
ปรับฐานตามเกณฑ์ที่ตำแหน่งใช้จริง) — เป็นข้อมูลช่วยตัดสินใจ ไม่ใช่คำตัดสิน
_Avoid_: คะแนนสอบ (คำนั้นหมายถึงผลจาก testing system)

**ผลสอบ (Test result)**:
คะแนน IQ/EQ/AQ/ฯลฯ จาก hma-testing-system — อยู่ใน Firestore ของระบบสอบ
ATS อ่านแบบ read-only โดย match ด้วยอีเมลผู้สมัคร
_Avoid_: assessment score (ชนกับ stage "Assessment" ใน pipeline)

**ไฟล์สำรอง (Backup file)**:
ไฟล์ JSON สำเนา DB ทั้งก้อน (jobs + candidates) ที่ ATS เขียนอัตโนมัติผ่าน
File System Access API ลงโฟลเดอร์ OneDrive (ดู decision 0002)
_Avoid_: export (คำนั้นสงวนให้ CSV ที่เปิดใน Excel ซึ่งนำกลับเข้าระบบไม่ได้)
