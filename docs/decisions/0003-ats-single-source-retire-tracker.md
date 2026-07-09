# ATS เป็นแหล่งความจริงเดียวเรื่องผู้สมัคร — เลิกใช้ recruitment-tracker

recruitment-tracker.html ซ้ำซ้อนกับแท็บผู้สมัคร + Dashboard ของ hma-ats.html เกือบทั้งหมด
จึงเลิกพัฒนา/เลิกใช้ (ไม่ commit เข้า repo) เพื่อไม่ต้องดูแลสองระบบที่ทำงานเดียวกัน
ผู้สมัครทุกคนมี record เดียวใน ATS

เฟสถัดไป: ATS จะดึงผลสอบ (IQ/EQ/AQ/ฯลฯ) จาก hma-testing-system มาแสดงในหน้าผู้สมัคร
โดยอ่านจาก **Firestore ของ testing system แบบ read-only** (ผู้สมัครทำข้อสอบบนเครื่องตัวเอง
ผลถูก sync ขึ้น Firestore — localStorage ของเครื่อง HR ไม่มีข้อมูลนี้) ใช้ "อีเมลผู้สมัคร"
เป็น join key หลัก และเลขบัตรประชาชนเป็น key สำรองฝั่ง testing system

ส่วนข้อมูลผู้สมัคร/resume ของ ATS เอง **ไม่ขึ้น cloud** — คงอยู่ local + FSA backup ตาม [0002]
เพราะข้อความ resume เป็น PII เข้มข้นกว่าผลสอบ และผู้ใช้มีคนเดียว (ดู [0001])

Status: accepted (2026-07-06) — implemented
