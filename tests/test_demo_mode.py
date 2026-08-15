"""โหมดทดสอบต้องไม่ติดมาเองโดยไม่ได้ขอ

ความเสี่ยงที่แท้จริงคือคนทำงานจริงอยู่ในโหมดทดสอบโดยไม่รู้ตัว แล้วนึกว่าบันทึก
ผู้สมัครไปแล้วทั้งที่ข้อมูลอยู่คนละที่ — เทสต์ชุดนี้เฝ้าฝั่งที่อันตรายกว่า
คือการเปิดตามปกติแล้วต้องได้โหมดจริงเสมอ
"""


def test_normal_open_is_not_demo_mode(open_ats):
    page = open_ats()
    assert page.evaluate("() => DEMO") is False
    assert page.evaluate("() => ATS_KEY") == "hma_ats_v1"


def test_demo_banner_is_hidden_in_normal_mode(open_ats):
    page = open_ats()
    assert page.locator("#demoBar").is_hidden()


def test_demo_key_is_separate_from_the_real_one(open_ats):
    """คนละ key เท่านั้นที่ทำให้ข้อมูลทดสอบกับของจริงไม่ปนกัน"""
    page = open_ats()
    real = page.evaluate("() => ATS_KEY")
    assert real == "hma_ats_v1"
    assert page.evaluate("() => 'hma_ats_demo'") != real
