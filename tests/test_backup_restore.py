import json

from conftest import candidate, scorecard

CUSTOM_CRITERIA = [
    {"id": "k1", "label": "ความปลอดภัยในการทำงาน", "weight": 5},
    {"id": "k2", "label": "การสื่อสาร", "weight": 1},
]


def _restore(page, data):
    # applyRestore ถาม confirm ก่อนแทนที่ข้อมูล — ตอบตกลงให้อัตโนมัติ
    return page.evaluate("""d => { window.confirm = () => true; return applyRestore(d); }""", data)


def test_backup_includes_scorecard_criteria(open_ats):
    page = open_ats({"jobs": [], "candidates": [], "scorecardCriteria": CUSTOM_CRITERIA})
    payload = json.loads(page.evaluate("() => backupPayload()"))
    assert payload["scorecardCriteria"] == CUSTOM_CRITERIA


def test_restore_keeps_criteria_from_backup(open_ats):
    page = open_ats()
    assert _restore(page, {"jobs": [], "candidates": [], "scorecardCriteria": CUSTOM_CRITERIA})
    assert page.evaluate("() => DB.scorecardCriteria") == CUSTOM_CRITERIA
    # ต้องบันทึกลง localStorage ด้วย ไม่ใช่แค่ในหน่วยความจำ
    saved = page.evaluate("() => JSON.parse(localStorage.getItem('hma_ats_v1')).scorecardCriteria")
    assert saved == CUSTOM_CRITERIA


def test_backup_then_restore_round_trip(open_ats):
    page = open_ats({"jobs": [], "candidates": [], "scorecardCriteria": CUSTOM_CRITERIA})
    data = json.loads(page.evaluate("() => backupPayload()"))
    page.evaluate("() => { DB.scorecardCriteria = seedScorecardCriteria(); saveDB(); }")
    assert _restore(page, data)
    assert page.evaluate("() => DB.scorecardCriteria") == CUSTOM_CRITERIA


def test_old_backup_without_criteria_gets_defaults(open_ats):
    """ไฟล์สำรองที่ทำก่อนแก้บั๊กไม่มี scorecardCriteria — ต้องได้ค่าเริ่มต้น ไม่ใช่ undefined"""
    page = open_ats()
    assert _restore(page, {"jobs": [], "candidates": [candidate()]})
    assert page.evaluate("() => DB.scorecardCriteria.length") == 5


def test_interview_form_works_after_restoring_old_backup(open_ats):
    page = open_ats()
    _restore(page, {"jobs": [], "candidates": [candidate(scorecards=[scorecard()])]})
    page.evaluate("() => showCandDetail('cand1')")
    page.evaluate("() => { localStorage.setItem('hma_ats_sc_open','1'); refreshScorecardSection(); }")
    page.evaluate("() => openScorecardForm()")
    assert page.locator("#scForm .sc-crit").count() == 5
    # ใบเก่ายังใช้หัวข้อที่ freeze ไว้ตามเดิม
    assert "78" in page.locator("#scSection").inner_text()
