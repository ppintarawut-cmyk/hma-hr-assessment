"""หน้า resume จริงพร้อมไฮไลต์คำที่ใช้คิดคะแนน

กล่องไฮไลต์คำนวณจากบรรทัดชุดเดียวกับที่ตัวคิดคะแนนอ่าน (pdfItemsToLines)
ถ้าสองอย่างนี้หลุดจากกันเมื่อไหร่ HR จะเห็นไฮไลต์ที่ไม่ตรงกับคะแนน
"""

import pytest


# ทั้งบรรทัดเป็น text item เดียว (ทรงที่ PDF จาก Word/pdfkit ทำบ่อย)
ONE_ITEM_LINE = """[
  { str: 'Skills: Lean Manufacturing, Kaizen, Excel',
    transform: [10,0,0,10, 50,700], width: 200, height: 10 }
]"""

# บรรทัดเดียวกันแต่ถูกแตกเป็นหลายชิ้น
SPLIT_LINE = """[
  { str: 'Skills: ', transform: [10,0,0,10, 50,700], width: 36, height: 10 },
  { str: 'Lean',     transform: [10,0,0,10, 86,700], width: 20, height: 10 },
  { str: ' Manufacturing', transform: [10,0,0,10, 106,700], width: 64, height: 10 }
]"""


def test_lines_carry_part_offsets(open_ats):
    """part.start ต้องชี้ตำแหน่งจริงในบรรทัด รวมช่องว่างที่ระบบเติมให้ด้วย"""
    page = open_ats()
    lines = page.evaluate("() => pdfItemsToLines(" + SPLIT_LINE + ")")
    assert len(lines) == 1
    line = lines[0]
    assert line["text"] == "Skills: Lean Manufacturing"
    for part in line["parts"]:
        assert line["text"][part["start"]:part["start"] + len(part["s"])] == part["s"]


def test_line_text_matches_what_the_scorer_reads(open_ats):
    """ข้อความของบรรทัดต้องตรงกับที่ pdfItemsToText ส่งให้ตัวคิดคะแนน"""
    page = open_ats()
    joined = page.evaluate(
        "() => pdfItemsToLines(" + SPLIT_LINE + ").map(l => l.text.trim()).join('\\n')")
    assert joined == page.evaluate("() => pdfItemsToText(" + SPLIT_LINE + ").text")


@pytest.mark.parametrize("items", [ONE_ITEM_LINE, SPLIT_LINE])
def test_terms_are_found_regardless_of_how_the_pdf_split_the_line(open_ats, items):
    page = open_ats()
    ranges = page.evaluate(
        "(a) => { const L = pdfItemsToLines(" + items + ")[0];"
        "  return findTermRanges(L.text, ['Lean']).map(r => L.text.slice(r.start, r.end)); }", None)
    assert ranges == ["Lean"]


def test_ascii_terms_need_a_word_boundary(open_ats):
    """กติกาเดียวกับ textHasTerm — ไม่งั้นไฮไลต์จะไปโผล่กลางคำอื่น"""
    page = open_ats()
    assert page.evaluate("() => findTermRanges('cleaning the lean line', ['lean']).length") == 1
    assert page.evaluate("() => findTermRanges('Excellent', ['Excel']).length") == 0


def test_thai_terms_match_as_substring(open_ats):
    page = open_ats()
    got = page.evaluate(
        "() => findTermRanges('มีทักษะการทำงานเป็นทีมและสื่อสาร', ['ทำงานเป็นทีม'])"
        "        .map(r => r.start)")
    assert len(got) == 1


def test_overlapping_terms_both_reported(open_ats):
    """"Lean" กับ "Lean Manufacturing" เป็นคำพ้องของทักษะเดียวกัน ต้องได้ทั้งคู่"""
    page = open_ats()
    got = page.evaluate(
        "() => findTermRanges('Core: Lean Manufacturing', ['Lean', 'Lean Manufacturing'])"
        "        .map(r => r.end - r.start)")
    assert sorted(got) == [4, 18]


def test_repeated_term_does_not_loop_forever(open_ats):
    page = open_ats()
    assert page.evaluate("() => findTermRanges('ISO ISO ISO', ['ISO']).length") == 3


# ── ความกว้างโดยประมาณ (ใช้วางกล่อง) ──────────────────────────────────

def test_thai_combining_marks_have_no_width(open_ats):
    """สระบน/ล่างและวรรณยุกต์ลอยอยู่เหนือ-ใต้ตัวอักษร ถ้านับเป็นความกว้างกล่องจะเลื่อนขวา"""
    page = open_ats()
    plain = page.evaluate("() => textAdvance('กรม', 0, 3)")
    marked = page.evaluate("() => textAdvance('กรุ๊ม', 0, 5)")   # ก ร ุ ๊ ม — เพิ่มสระ+วรรณยุกต์
    assert plain == marked


def test_space_counts_less_than_a_letter(open_ats):
    page = open_ats()
    assert page.evaluate("() => textAdvance(' ', 0, 1)") < page.evaluate("() => textAdvance('a', 0, 1)")


def test_advance_is_measured_over_the_requested_range_only(open_ats):
    page = open_ats()
    assert page.evaluate("() => textAdvance('abcdef', 2, 4)") == 2
    assert page.evaluate("() => textAdvance('abc', 0, 99)") == 3      # ไม่ล้นออกนอกสตริง


# ── การเก็บไฟล์ต้นฉบับ ──────────────────────────────────────────────────

def test_original_file_never_reaches_the_database(open_ats):
    """ไฟล์อยู่ในหน่วยความจำเพื่อเปิดดูหน้าจริงเท่านั้น — ห้ามหลุดลง localStorage/ไฟล์สำรอง
    (โควตา localStorage ~5MB · ไฟล์ resume ไฟล์เดียวก็เกินได้)"""
    page = open_ats()
    rec = page.evaluate("""() => makeCandidate(
        { name: 'ทดสอบ ระบบ', resumeText: 'x', file: { name: 'a.pdf' } },
        { score: 0, breakdown: [], matched: [], missing: [], missingRequired: [] },
        {}
    )""")
    assert "file" not in rec
