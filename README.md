# HMA Testing System
**Hino Motors Asia — HR Psychometric Assessment Platform**

Single-file web application สำหรับประเมินผู้สมัครงานด้วยแบบทดสอบ IQ · EQ · AQ · Business English · Leadership · Excel

---

## Quick Start

```
เปิดไฟล์ hma-testing-system.html ใน browser
ไม่ต้องติดตั้ง server ไม่ต้องมี database
```

> ⚠️ ต้องเปิดผ่าน `http://` หรือ `https://` เท่านั้น — **ไม่รองรับ `file://`** เพราะใช้ localStorage

---

## Architecture

| Layer | Detail |
|---|---|
| Runtime | Vanilla JS (ES2020) — ไม่มี framework |
| Styling | CSS custom properties (Hino Red theme + Dark mode) |
| Storage | `localStorage` — data อยู่ใน browser ของเครื่องนั้น |
| Charts | Chart.js 4.4.1 (CDN) |
| Export | SheetJS / xlsx 0.18.5 (CDN) |
| Deployment | Single `.html` file, ~250 KB |

---

## Features

### ฝั่งผู้สมัคร
- ลงทะเบียนเลือก **ตำแหน่งที่สมัคร** (dropdown) → ระบบ mapping ชุดข้อสอบอัตโนมัติ
- แบบทดสอบ 6 ชุด — IQ, EQ, AQ, Business English, Leadership, Excel
- ทำต่อจากที่ค้างได้ (จับเวลาต่อเนื่อง)
- สลับภาษา **ไทย ⟷ English** ได้ตลอดการสอบ
  - โจทย์ IQ / EQ / AQ มีทั้งสองภาษา
  - โจทย์ Business English คงเป็นภาษาอังกฤษ (เพื่อความ validity)
- PDPA consent ก่อนเริ่มสอบ

### ฝั่ง HR / Admin
- Dashboard ผู้สมัครพร้อม Pass Rate, เปรียบเทียบตามชุดสอบ
- Export Excel รายงานผลทั้งหมด
- **Sidebar เครื่องมือ** (☰) — เข้าถึงทุกเครื่องมือจากจุดเดียว
- จัดการชุดข้อสอบตามตำแหน่ง (checkbox matrix แก้ได้ real-time)
- จัดการข้อสอบ / คำแนะนำแต่ละชุด
- ระบบสิทธิ์ 3 ระดับ: Super Admin · HR Admin · Viewer

---

## Deployment Options

### ตัวเลือก 1 — SharePoint (แนะนำสำหรับ HMA)
```
1. อัปโหลด hma-testing-system.html ไปที่ Document Library
2. เปิด link ตรงจาก SharePoint (มี https:// → localStorage ใช้ได้)
3. แชร์ link ให้ผู้สมัครและ HR
```

### ตัวเลือก 2 — Static Web Hosting
```
วาง hma-testing-system.html บน:
  - Azure Static Web Apps
  - AWS S3 + CloudFront
  - Nginx / Apache (ไม่ต้องมี server-side)
```

### ตัวเลือก 3 — Local Network
```
python3 -m http.server 8080
แล้วเปิด http://[IP]:8080/hma-testing-system.html
```

> ℹ️ ไฟล์ใช้ CDN ภายนอก (Chart.js, xlsx) — ถ้า environment ไม่มีอินเทอร์เน็ต ต้อง bundle library เข้ามาใน HTML ก่อน

---

## Admin Access

| Username | Password | Role |
|---|---|---|
| `admin` | `hma2024` | Super Admin |

> 🔐 **เปลี่ยนรหัสก่อน deploy จริงทุกครั้ง** — หาใน HTML ที่บรรทัด `ADMIN_DATA` และแก้ค่า `password`

การเพิ่ม admin เพิ่มเติมทำได้ที่ **Admin → ☰ → จัดการทีม**

---

## Position → Test Set Mapping

ค่าเริ่มต้น (แก้ได้ที่ Admin → ☰ → ชุดสอบ/ตำแหน่ง):

| ตำแหน่ง | IQ | EQ | Business English | AQ | Leadership | Excel |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| ระดับบริหาร / หัวหน้างาน | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| พนักงานสำนักงาน | ✓ | ✓ | ✓ | | | ✓ |
| ฝ่ายบุคคล (HR) | ✓ | ✓ | ✓ | ✓ | ✓ | |
| วิศวกร / สายเทคนิค | ✓ | ✓ | ✓ | ✓ | | ✓ |
| ทั่วไป (พื้นฐาน) | ✓ | ✓ | | ✓ | | |

---

## Test Bank Summary

| ชุด | จำนวนข้อ | เวลา | Scoring | มาตรฐาน |
|---|:---:|:---:|---|---|
| IQ — Cognitive Ability | 15 | 12 นาที | Binary (0/1) | SHL / Wonderlic GMA |
| EQ — Emotional Intelligence | 12 | 15 นาที | Graded (0–2) | Goleman 4-domain |
| Business English | 15 | 20 นาที | Binary (0/1) | TOEIC / CEFR A2–C1 |
| AQ — Adversity Quotient | 12 | 12 นาที | Graded (0–2) | Stoltz CORE model |
| Leadership | 12 | 15 นาที | Graded (0–2) | MLQ Transformational |
| Excel Skills | 16 | 20 นาที | Binary (0/1) | MOS Specialist |

---

## localStorage Keys

| Key | Content |
|---|---|
| `hma_theme` | `"dark"` / `"light"` |
| `hma_lang` | `"th"` / `"en"` |
| `hma_position_presets` | JSON array ของตำแหน่ง + ชุดข้อสอบ (แก้โดย HR) |
| `hma_admin_users` | JSON array ของ admin accounts |
| `hma_session_*` | Session ผู้สมัครที่กำลังสอบ |

> Data ไม่ sync ข้าม browser / device — ถ้าต้องการ multi-device ในอนาคตต้องเพิ่ม backend

---

## Known Constraints

- **Single-device only** — ผู้สมัครต้องทำสอบบนเครื่องเดียวตลอด ถ้าปิด browser ข้อมูล session อาจหาย
- **No offline support** — ต้องมีอินเทอร์เน็ตสำหรับ CDN libraries
- **Admin panel = Thai only** — UI แอดมินเป็นภาษาไทยตั้งใจ (เครื่องมือภายใน) ส่วน candidate flow รองรับ TH/EN
- **Review screen** — chrome หน้าเฉลยเป็นภาษาไทย แต่โจทย์/ตัวเลือกสลับตามภาษาที่เลือก

---

## File Structure

```
hma-testing-system.html    ← ไฟล์เดียว ทุกอย่างอยู่ในนี้
  ├── <style>              CSS (lines ~9–420)
  ├── <body>               HTML pages (lines ~421–870)
  ├── <script> Block 1     Data + Core Logic (~1,700 lines)
  │     ├── TESTS[]        6 test definitions
  │     ├── ALL_QUESTIONS  Question banks (IQ/EQ/AQ/EN/LEADER/EXCEL)
  │     ├── LANG + I18N    Bilingual system
  │     ├── Q_TH           Thai question overlay (IQ/EQ/AQ)
  │     ├── DEFAULT_POSITION_PRESETS
  │     └── Core functions (nav, submitReg, renderDash, renderQ …)
  └── <script> Block 2     UI / Initialization (~400 lines)

hma-testing-system.js      ← JS extracted (reference only)
README.md                  ← this file
```

---

## Version History (สรุป session นี้)

| เพิ่ม | รายละเอียด |
|---|---|
| 🌐 Bilingual TH/EN | toggle ภาษา ครอบคลุม candidate flow ทั้งหมด |
| 🎯 Position → Test mapping | dropdown เดียว จับคู่ชุดข้อสอบอัตโนมัติ |
| 🔧 HR Position Editor | checkbox matrix ใน admin sidebar แก้ได้ real-time |
| 📝 Thai questions | IQ 15 / EQ 12 / AQ 12 ข้อ แปลครบ |
| ☰ Admin Sidebar | drawer เปิด-ปิด รวมเครื่องมือทั้งหมด |

---

*HMA Testing System · Hino Motors Asia HR Department*
