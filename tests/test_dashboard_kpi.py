import re

from test_stage_history import hist

from conftest import candidate


def open_dashboard(open_ats, db=None):
    page = open_ats(db)
    page.evaluate("() => document.querySelector('.tab[data-tab=dashboard]').click()")
    return page


def tile(page, label):
    """ช่อง KPI ที่หัวข้อตรงกับ label ทั้งข้อความ (กัน รับเข้าทำงาน ไปโดน เวลาเฉลี่ยจนรับเข้าทำงาน)"""
    head = page.locator(".kpi-head", has_text=re.compile("^" + re.escape(label) + "$"))
    return page.locator("#kpiGrid .kpi", has=head)


def test_kpis_are_two_groups_of_four(open_ats):
    page = open_dashboard(open_ats)
    groups = page.locator("#kpiGrid .kpi-group")
    assert groups.count() == 2
    assert [groups.nth(i).locator(".kpi").count() for i in range(2)] == [4, 4]
    assert groups.nth(0).locator(".kpi-group-title").inner_text() == "Pipeline และผลลัพธ์"


def test_values_use_ink_not_brand_red(open_ats):
    """ตัวเลขสีแดงอ่านเหมือน "ไม่ดี" — ค่าทุกช่องต้องเป็นสีหมึกเดียวกัน"""
    page = open_dashboard(open_ats, {"jobs": [], "candidates": [candidate(score=74)]})
    colors = page.evaluate("""() => [...document.querySelectorAll('#kpiGrid .kpi-val:not(.no-data)')]
        .map(e => getComputedStyle(e).color)""")
    assert len(set(colors)) == 1
    assert colors[0] != page.evaluate(
        "() => getComputedStyle(document.querySelector('.tab.active')).color")


def test_empty_database_shows_dash_not_zero_for_averages(open_ats):
    page = open_dashboard(open_ats)
    avg = tile(page, "คะแนน Match เฉลี่ย")
    assert avg.locator(".kpi-val").inner_text() == "—"
    assert avg.locator(".kpi-meter").count() == 0
    assert tile(page, "เวลาเฉลี่ยจนรับเข้าทำงาน").locator(".kpi-val").inner_text() == "—"
    assert page.locator("#kpiGrid .kpi-link").count() == 0


def test_context_lines(open_ats):
    page = open_dashboard(open_ats, {"jobs": [], "candidates": [
        candidate(id="a", stage="Interview", score=80),
        candidate(id="b", stage="Interview", score=60),
        candidate(id="c", stage="Offer", score=40),
        candidate(id="d", stage="Hired", score=90)]})
    assert "Interview 2 · Offer 1" in tile(page, "อยู่ระหว่างคัดเลือก").inner_text()
    assert "25% ของผู้สมัครทั้งหมด" in tile(page, "รับเข้าทำงาน").inner_text()
    avg = tile(page, "คะแนน Match เฉลี่ย")
    assert avg.locator(".kpi-val").inner_text() == "68 / 100"
    assert avg.locator(".kpi-meter").get_attribute("title") == "68%"


def test_stuck_tile_badge_and_drill_down(open_ats):
    page = open_dashboard(open_ats, {"jobs": [], "candidates": [
        candidate(stage="Interview", stageHistory=hist(("Applied", 30), ("Interview", 20)))]})
    t = tile(page, "ค้างสถานะเกิน 14 วัน")
    assert "ต้องติดตาม" in t.inner_text()
    t.click()
    assert page.locator("#tab-candidates").is_visible()
    assert page.evaluate("() => document.getElementById('candSort').value") == "stuck"


def test_no_stuck_shows_good_badge_and_no_link(open_ats):
    page = open_dashboard(open_ats, {"jobs": [], "candidates": [
        candidate(stage="Interview", stageHistory=hist(("Applied", 5), ("Interview", 2)))]})
    t = tile(page, "ค้างสถานะเกิน 14 วัน")
    assert "ไม่มีค้าง" in t.inner_text()
    assert t.get_attribute("data-go") is None


def test_ai_tile_opens_candidates_sorted_by_ai_with_keyboard(open_ats):
    from test_ai_detect import AI_SUMMARY
    page = open_dashboard(open_ats, {"jobs": [], "candidates": [candidate(resumeText=AI_SUMMARY)]})
    t = tile(page, "สัญญาณใช้ AI สูง")
    t.focus()
    page.keyboard.press("Enter")
    assert page.locator("#tab-candidates").is_visible()
    assert page.evaluate("() => document.getElementById('candSort').value") == "ai"
