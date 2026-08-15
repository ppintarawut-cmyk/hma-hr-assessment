"""อ่าน JD จากไฟล์ → ค่าที่กรอกลงฟอร์มตำแหน่งงาน

JD จริงมาสองทรงหลัก: เอกสารข้อความ (PDF/DOCX ที่ฝ่ายงานส่งมา) กับตาราง Excel
ทั้งคู่จบที่ parseJD / jdRowsToJobs ตัวเดียวกัน
"""

import pytest


JD_TH = """บริษัท ฮีโน่ มอเตอร์ส เอเชีย จำกัด
ประกาศรับสมัครงาน

ตำแหน่ง : วิศวกรฝ่ายผลิต (Production Engineer)
แผนก : Production Engineering

หน้าที่ความรับผิดชอบ
- วางแผนและควบคุมกระบวนการผลิตให้ได้ตามเป้าหมาย
- วิเคราะห์ปัญหาหน้างานและปรับปรุงประสิทธิภาพด้วยหลัก Lean และ Kaizen

คุณสมบัติผู้สมัคร
- วุฒิปริญญาตรี สาขาวิศวกรรมอุตสาหการ
- ประสบการณ์ 3-5 ปี ในงานผลิต
- มีความรู้ ISO, 5S"""

JD_EN = """Senior Logistics Planner
Department: Supply Chain

Responsibilities
- Plan inbound and outbound logistics using SAP

Requirements
- Bachelor's degree in Logistics, Supply Chain or Engineering
- At least 5 years of experience in logistics planning
- Strong Excel and Power BI skills"""


def parse(page, text, hints="{}"):
    return page.evaluate("(t) => parseJD(t, " + hints + ")", text)


def test_reads_thai_jd_document(open_ats):
    page = open_ats()
    jd = parse(page, JD_TH)
    assert jd["title"] == "วิศวกรฝ่ายผลิต (Production Engineer)"
    assert jd["dept"] == "Production Engineering"
    assert jd["minExp"] == 3                      # "3-5 ปี" → เกณฑ์ผ่านคือขั้นต่ำ
    assert "ปริญญาตรี" in jd["eduKeywords"] and "วิศวกรรม" in jd["eduKeywords"]


def test_reads_english_jd_document(open_ats):
    page = open_ats()
    jd = parse(page, JD_EN)
    assert jd["title"] == "Senior Logistics Planner"     # ไม่มีฉลาก → บรรทัดแรก
    assert jd["dept"] == "Supply Chain"
    assert jd["minExp"] == 5


def test_qualifications_are_split_from_the_job_description(open_ats):
    page = open_ats()
    jd = parse(page, JD_TH)
    assert "หน้าที่ความรับผิดชอบ" in jd["jd"]
    assert "วุฒิปริญญาตรี" not in jd["jd"]
    assert "วุฒิปริญญาตรี" in jd["quals"] and "3-5 ปี" in jd["quals"]


def test_skills_are_suggested_from_the_whole_document(open_ats):
    page = open_ats()
    names = [s["name"] for s in parse(page, JD_TH)["skills"]]
    assert any("Lean" in n for n in names)
    assert any("Kaizen" in n for n in names)
    assert any("ISO" in n for n in names)
    assert all(s["weight"] == 3 and s["required"] is False for s in parse(page, JD_TH)["skills"])


def test_field_of_study_follows_the_document_not_our_list_order(open_ats):
    """JD เขียนว่า "Logistics, Supply Chain or Engineering" — สาขาหลักคือตัวที่ถูกพูดถึงก่อน"""
    page = open_ats()
    assert "logistics" in parse(page, JD_EN)["eduKeywords"]


def test_title_falls_back_to_largest_text_then_filename(open_ats):
    page = open_ats()
    by_big = parse(page, "Responsibilities\n- do things", "{ bigText: 'Sales Engineer' }")
    assert by_big["title"] == "Sales Engineer"
    by_file = parse(page, "", "{ fileName: 'JD_Sales_Engineer.pdf' }")
    assert by_file["title"] == "Sales Engineer"


@pytest.mark.parametrize("text, want", [
    ("ประสบการณ์อย่างน้อย 2 ปี", 2),
    ("3+ years experience", 3),
    ("ประสบการณ์ 5 ปีขึ้นไป", 5),
    ("minimum of 4 years", 4),
    ("ประสบการณ์ 2-4 ปี", 2),                    # ช่วงปี → เอาขั้นต่ำ
    ("experience 10 years in sales", 10),
    ("ไม่ระบุประสบการณ์", 0),
    ("3 ปี", 3),                                  # ค่าจากช่องตาราง — ตัวเลขลอย ๆ นับได้
])
def test_required_years_formats(open_ats, text, want):
    page = open_ats()
    assert page.evaluate("(t) => extractRequiredYears(t)", text) == want


def test_bare_year_in_long_text_is_not_treated_as_the_requirement(open_ats):
    """ใน JD เต็มฉบับ "สัญญาจ้าง 1 ปี" ไม่ใช่เกณฑ์ประสบการณ์"""
    page = open_ats()
    long_text = "ตำแหน่งนี้เป็นสัญญาจ้าง 1 ปี ต่อสัญญาได้ตามผลงาน " + ("x" * 60)
    assert page.evaluate("(t) => extractRequiredYears(t)", long_text) == 0


# ── JD ที่มาเป็นตาราง Excel ──────────────────────────────────────────────

JOB_TABLE = """[
  ['อัตรากำลังปี 2026', '', '', '', ''],
  ['ตำแหน่ง', 'แผนก', 'ประสบการณ์', 'วุฒิการศึกษา', 'คุณสมบัติ'],
  ['Sales Engineer', 'Sales', '3 ปี', 'ปริญญาตรี วิศวกรรม', 'ดูแล CRM เจรจาต่อรองเก่ง'],
  ['HR Officer', 'HR', 'อย่างน้อย 2 ปี', 'ปริญญาตรี ทรัพยากรบุคคล', 'รู้กฎหมายแรงงาน ใช้ Excel'],
  ['', '', '', '', '']
]"""

# ฟอร์มสองคอลัมน์ — ฉลากอยู่ซ้าย ค่าอยู่ขวา
JOB_FORM = """[
  ['ใบขอกำลังคน (Manpower Request)', ''],
  ['ตำแหน่ง', 'เจ้าหน้าที่จัดซื้อ'],
  ['แผนก', 'Procurement'],
  ['ประสบการณ์', 'อย่างน้อย 2 ปี'],
  ['หน้าที่', 'จัดซื้อวัตถุดิบ ใช้ SAP และ Excel']
]"""


def test_job_table_becomes_one_job_per_row(open_ats):
    page = open_ats()
    jobs = page.evaluate("() => jdRowsToJobs(" + JOB_TABLE + ")")
    assert [j["title"] for j in jobs] == ["Sales Engineer", "HR Officer"]   # ข้ามหัวเรื่อง+แถวว่าง
    assert jobs[0]["dept"] == "Sales" and jobs[0]["minExp"] == 3
    assert jobs[1]["minExp"] == 2
    assert "ทรัพยากรบุคคล" in jobs[1]["eduKeywords"]
    assert any("CRM" in s["name"] for s in jobs[0]["skills"])


def test_two_column_form_is_not_mistaken_for_a_job_table(open_ats):
    """แถว ["ตำแหน่ง", "เจ้าหน้าที่จัดซื้อ"] มีคำว่า "หน้าที่" อยู่ในค่า — เคยถูกอ่านเป็นหัวตาราง"""
    page = open_ats()
    assert page.evaluate("() => jdRowsToJobs(" + JOB_FORM + ")") == []


def test_two_column_form_is_read_as_a_single_jd(open_ats):
    page = open_ats()
    jd = page.evaluate("() => parseJD(sheetRowsToText(" + JOB_FORM + "), {})")
    assert jd["title"] == "เจ้าหน้าที่จัดซื้อ"
    assert jd["dept"] == "Procurement"
    assert jd["minExp"] == 2
    assert any("SAP" in s["name"] for s in jd["skills"])


def test_label_regex_alternatives_all_work(open_ats):
    """jdLabelValue ต่อ pattern ท้าย source ที่มี | อยู่ — ต้องครอบวงเล็บก่อน
    ไม่งั้นทางเลือกแรก ๆ จะไม่มีส่วนที่ต่อท้ายติดไปด้วย"""
    page = open_ats()
    for text, want in [("ตำแหน่ง: ช่างเทคนิค", "ช่างเทคนิค"),
                       ("Position: Technician", "Technician"),
                       ("ตำแหน่งงาน : ช่างเทคนิค", "ช่างเทคนิค")]:
        assert page.evaluate("(t) => jdLabelValue(t, JD_LABELS.title)", text) == want
