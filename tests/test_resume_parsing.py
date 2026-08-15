"""ความแม่นยำของการดึงชื่อ/อีเมลจาก resume

เคสส่วนใหญ่มาจากปัญหาจริง: resume ที่มีอีเมลชัดเจน แต่ระบบหาไม่เจอ เพราะ PDF
ไม่ได้เก็บข้อความเป็นบรรทัด — pdf.js คืนมาเป็นชิ้น ๆ ตามรอยต่อฟอนต์/เคิร์นนิ่ง
ทำให้อีเมลถูกแทรกช่องว่างหรือถูกตัดข้ามบรรทัด
"""

import pytest


# ── อีเมลที่ถูก PDF แทรกช่องว่าง/ตัดบรรทัด ──────────────────────────────

@pytest.mark.parametrize("raw, want", [
    ("Somchai Jaidee\nsomchai.j @gmail.com", "somchai.j@gmail.com"),   # ช่องว่างก่อน @
    ("somchai.j@ gmail.com", "somchai.j@gmail.com"),                   # ช่องว่างหลัง @
    ("Contact: somchai @ gmail.com", "somchai@gmail.com"),             # ขนาบสองข้าง
    ("somchai .jaidee@gmail.com", "somchai.jaidee@gmail.com"),         # แตกกลาง local part
    ("somchai@gmail. com", "somchai@gmail.com"),                       # ช่องว่างก่อน TLD
    ("somchai.j@\ngmail.com", "somchai.j@gmail.com"),                  # ตัดหลัง @
    ("somchai.j\n@gmail.com", "somchai.j@gmail.com"),                  # ตัดก่อน @
    ("somchai@gmail.\ncom", "somchai@gmail.com"),                      # TLD ตกบรรทัดถัดไป
    ("somchai(at)gmail(dot)com", "somchai@gmail.com"),                 # เขียนกันสแปม
    ("somchai＠gmail.com", "somchai@gmail.com"),                        # @ เต็มความกว้าง
])
def test_finds_email_broken_by_pdf_extraction(open_ats, raw, want):
    page = open_ats()
    assert page.evaluate("(t) => extractEmail(t)", raw) == want


def test_finds_email_hidden_in_mailto_link(open_ats):
    """บาง resume โชว์แค่คำว่า Email แล้วผูก mailto: ไว้ — text layer ไม่มีอีเมลเลย"""
    page = open_ats()
    got = page.evaluate(
        "(a) => extractEmail(a[0], [a[1]])",
        ["Somchai Jaidee\nEmail", "mailto:somchai@gmail.com"])
    assert got == "somchai@gmail.com"


@pytest.mark.parametrize("raw", [
    "photo@2x.png",                      # ชื่อไฟล์รูป ไม่ใช่อีเมล
    "Sales Manager at hino.co.th",       # "at" ไม่มีวงเล็บ — ถ้ารับจะได้อีเมลปลอม
    "Follow @somchai on X",              # @ ลอย ๆ
    "ประวัติส่วนตัว\nสมชาย ใจดี",          # ไม่มีอีเมลจริง
])
def test_does_not_invent_emails(open_ats, raw):
    page = open_ats()
    assert page.evaluate("(t) => extractEmail(t)", raw) == ""


def test_prefers_candidate_email_over_company_email(open_ats):
    page = open_ats()
    got = page.evaluate(
        "(t) => extractEmail(t)",
        "เรียน hr@hino.co.th\nสมชาย ใจดี\nอีเมล somchai@gmail.com")
    assert got == "somchai@gmail.com"


def test_repair_does_not_swallow_preceding_year(open_ats):
    """ซ่อมช่องว่างต้องไม่ลามจนดูด "2020." เข้ามาเป็นส่วนหนึ่งของอีเมล"""
    page = open_ats()
    assert page.evaluate(
        "(t) => extractEmail(t)", "จบปี 2020. somchai@gmail.com") == "somchai@gmail.com"


# ── ชื่อผู้สมัคร ─────────────────────────────────────────────────────────

def test_name_on_same_line_as_phone_and_email(open_ats):
    """resume สมัยใหม่มักพิมพ์ชื่อ+เบอร์+อีเมลรวมบรรทัดเดียว — เดิมข้ามทั้งบรรทัด"""
    page = open_ats()
    got = page.evaluate(
        "(a) => extractName(a[0], a[1])",
        ["SOMCHAI JAIDEE | 081-234-5678 | somchai@gmail.com\nSales Executive", "somchai@gmail.com"])
    assert got == "SOMCHAI JAIDEE"


@pytest.mark.parametrize("raw, want", [
    ("ประวัติส่วนตัว\nนายสมชาย ใจดี", "สมชาย ใจดี"),          # ตัดคำนำหน้า
    ("PERSONAL INFORMATION\nSomchai Jaidee\nBangkok", "Somchai Jaidee"),   # ข้ามหัวข้อ
    ("ชื่อ-นามสกุล\nสมชาย ใจดี", "สมชาย ใจดี"),                # ฉลากอยู่คนละบรรทัดกับค่า
    ("Name: Somchai Jaidee", "Somchai Jaidee"),
    ("Jaidee, Somchai\nBangkok", "Jaidee, Somchai"),        # นามสกุล, ชื่อ — ห้ามหั่นที่คอมมา
])
def test_name_from_text(open_ats, raw, want):
    page = open_ats()
    assert page.evaluate("(t) => extractName(t, '')", raw) == want


@pytest.mark.parametrize("line", [
    "ข้อมูลส่วนตัว ผู้สมัคร",
    "ประวัติ การทำงาน",
    "ตำแหน่งที่สมัคร Sales",
    "PERSONAL INFORMATION",
    "Work Experience",
])
def test_headings_are_never_taken_as_a_name(open_ats, line):
    """หัวข้อไทยต้องถูกกรองด้วย — \\b ของ JS regex ไม่เกิดขอบเขตหลังอักษรไทย"""
    page = open_ats()
    assert page.evaluate("(s) => looksLikeName(s)", line) is False


def test_name_from_largest_font_on_first_page(open_ats):
    """เกือบทุก resume พิมพ์ชื่อตัวโตสุดไว้บนสุด — ใช้เป็นตัวช่วยเมื่อกวาดบรรทัดไม่เจอ"""
    page = open_ats()
    got = page.evaluate(
        "(t) => extractName(t, '', { bigText: 'Somchai Jaidee' })", "081-234-5678\nBangkok")
    assert got == "Somchai Jaidee"


def test_name_falls_back_to_email_then_filename(open_ats):
    page = open_ats()
    assert page.evaluate(
        "(e) => extractName('Curriculum Vitae\\n2020-2024', e)",
        "somchai.jaidee@gmail.com") == "Somchai Jaidee"
    assert page.evaluate(
        "(f) => extractName('...', '', { fileName: f })",
        "Resume_Somchai_Jaidee_2026.pdf") == "Somchai Jaidee"


def test_generic_mailbox_is_not_turned_into_a_name(open_ats):
    """hr@hino.co.th เป็นอีเมลองค์กร — ห้ามกลายเป็นผู้สมัครชื่อ "Hr" """
    page = open_ats()
    assert page.evaluate("() => extractName('Curriculum Vitae\\n2020', 'hr@hino.co.th')") == ""


# ── การต่อ text item จาก PDF (ต้นตอของบั๊ก) ──────────────────────────────

ITEMS = """[
  { str: 'SOMCHAI JAIDEE', transform: [18,0,0,18, 50,700], width: 150, height: 18 },
  { str: 'somchai.j',      transform: [10,0,0,10, 50,680], width: 42,  height: 10 },
  { str: '@gmail.com',     transform: [10,0,0,10, 92,680], width: 50,  height: 10 },
  { str: 'Bangkok',        transform: [10,0,0,10, 200,680], width: 40, height: 10 }
]"""


def test_adjacent_items_are_joined_without_a_space(open_ats):
    """หัวใจของบั๊ก: เดิมเติมช่องว่างทุกรอยต่อ ทำให้อีเมลที่ถูกแตกชิ้นพัง"""
    page = open_ats()
    text = page.evaluate("() => pdfItemsToText(" + ITEMS + ").text")
    assert "somchai.j@gmail.com" in text
    assert "somchai.j @gmail.com" not in text
    assert "somchai.j@gmail.com Bangkok" in text   # ห่างกันจริงบนหน้ากระดาษ = ต้องมีช่องว่าง


def test_biggest_text_on_page_is_reported(open_ats):
    page = open_ats()
    assert page.evaluate("() => pdfItemsToText(" + ITEMS + ").bigText") == "SOMCHAI JAIDEE"


def test_space_items_still_separate_words(open_ats):
    """บางไฟล์คั่นคำด้วย text item ที่เป็นช่องว่างล้วน — ต้องไม่ถูกทิ้งจนคำติดกัน"""
    page = open_ats()
    text = page.evaluate("""() => pdfItemsToText([
      { str: 'Somchai', transform: [10,0,0,10, 50,700], width: 40, height: 10 },
      { str: ' ',       transform: [10,0,0,10, 90,700], width: 5,  height: 10 },
      { str: 'Jaidee',  transform: [10,0,0,10, 95,700], width: 35, height: 10 }
    ]).text""")
    assert text == "Somchai Jaidee"


def test_lines_are_ordered_top_to_bottom(open_ats):
    """PDF นับแกน Y จากล่างขึ้นบน — ถ้าไม่เรียง ชื่อจะไม่ได้อยู่บรรทัดแรก"""
    page = open_ats()
    text = page.evaluate("""() => pdfItemsToText([
      { str: 'ล่าง', transform: [10,0,0,10, 50,100], width: 20, height: 10 },
      { str: 'บน',  transform: [10,0,0,10, 50,700], width: 20, height: 10 }
    ]).text""")
    assert text == "บน\nล่าง"


# ── pipeline เต็ม ───────────────────────────────────────────────────────

def test_parse_resume_end_to_end(open_ats):
    page = open_ats()
    parsed = page.evaluate(
        "(t) => parseResume(t)",
        "SOMCHAI JAIDEE | 081-234-5678 | somchai.j @gmail.com\nEDUCATION\nBachelor of Engineering")
    assert parsed["email"] == "somchai.j@gmail.com"
    assert parsed["name"] == "SOMCHAI JAIDEE"
    assert parsed["phone"] == "081-234-5678"
    assert [w for w in parsed["warnings"] if w.startswith("ไม่พบ")] == []


def test_displayed_resume_text_is_not_rewritten(open_ats):
    """ซ่อมข้อความเพื่อ "ค้นหา" เท่านั้น — ข้อความที่ HR อ่านต้องเป็นของจริงจากไฟล์"""
    page = open_ats()
    parsed = page.evaluate("(t) => parseResume(t)", "Somchai\nsomchai.j @gmail.com")
    assert "somchai.j @gmail.com" in parsed["resumeText"]


def test_warns_when_name_or_email_missing(open_ats):
    page = open_ats()
    warnings = page.evaluate("() => parseResume('2020 - 2024 ทำงานที่โรงงาน').warnings")
    assert any(w.startswith("ไม่พบอีเมล") for w in warnings)
    assert any(w.startswith("ไม่พบชื่อผู้สมัคร") for w in warnings)


def test_reports_every_email_found(open_ats):
    page = open_ats()
    parsed = page.evaluate(
        "(t) => parseResume(t)", "สมชาย ใจดี\nอีเมล somchai@gmail.com\nหัวหน้างาน boss@abc.co.th")
    assert parsed["email"] == "somchai@gmail.com"
    assert set(parsed["emailsFound"]) == {"somchai@gmail.com", "boss@abc.co.th"}
    assert any("พบอีเมล 2 รายการ" in w for w in parsed["warnings"])


# ── แก้ชื่อ/อีเมลในตารางผลสแกน ──────────────────────────────────────────

def test_scan_row_fields_are_editable(open_ats):
    """ถ้าตัวอ่านพลาด HR ต้องพิมพ์ทับได้ก่อนกดเพิ่ม ไม่ใช่เพิ่มก่อนแล้วค่อยไปแก้"""
    page = open_ats()
    page.evaluate("""() => {
      scanResults = [{ id: 's1', fileName: 'a.pdf', jobId: '', status: 'ok',
        name: '', email: '', score: 0, matched: [], missing: [], missingRequired: [],
        warnings: ['ไม่พบอีเมลใน resume — กรอกเองได้ในช่องอีเมล'] }];
      renderScanTable();
    }""")
    page.evaluate("() => updateScanField('s1', 'email', ' Somchai@Gmail.com ')")
    row = page.evaluate("() => scanResults[0]")
    assert row["email"] == "somchai@gmail.com"          # trim + lowercase
    assert row["warnings"] == []                        # คำเตือนหายเมื่อกรอกแล้ว
